import base64
import json
import os

from openai import AsyncOpenAI

from llm import EXTRACTION_PROMPT, MissingConfigError
from receipt_tools import validate_receipt
from schemas import ReceiptData

MAX_MODEL_CALLS = 3

VALIDATION_TOOL = {
    "type": "function",
    "function": {
        "name": "validate_receipt",
        "description": "Validate proposed receipt JSON against the schema.",
        "parameters": {
            "type": "object",
            "properties": {
                "receipt_json": {
                    "type": "string",
                    "description": "Receipt JSON encoded as a string.",
                }
            },
            "required": ["receipt_json"],
            "additionalProperties": False,
        },
    },
}

AGENT_INSTRUCTIONS = """
Use the validate_receipt tool to submit your proposed receipt JSON.
Do not return the receipt as plain assistant text.

If the tool reports errors, correct the proposed JSON using the
original receipt and the error feedback, then call the tool again.

Never invent missing information to satisfy validation.
Use null for missing or ambiguous values as instructed.

Tool validation checks structure and constraints, not factual accuracy.
Before submitting, check every value against the original receipt.
"""


def execute_tool(
    name: str,
    arguments_json: str,
    *,
    source_text: str | None = None,
) -> dict:
    if name != "validate_receipt":
        return {
            "valid": False,
            "errors": [{"message": "Unknown tool. Use validate_receipt."}],
        }

    try:
        arguments = json.loads(arguments_json)
    except json.JSONDecodeError:
        return {
            "valid": False,
            "errors": [{"message": "Tool arguments must be valid JSON."}],
        }

    if (
        not isinstance(arguments, dict)
        or set(arguments) != {"receipt_json"}
        or not isinstance(arguments["receipt_json"], str)
    ):
        return {
            "valid": False,
            "errors": [{
                "message": "Provide only receipt_json, with a string value."
            }],
        }

    return validate_receipt(
        arguments["receipt_json"],
        source_text=source_text,
    )


async def extract_receipt_agent(
    *,
    text: str | None = None,
    image_bytes: bytes | None = None,
    mime: str | None = None,
) -> ReceiptData:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()

    if not api_key or not base_url:
        raise MissingConfigError()

    if image_bytes is not None:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        content = [
            {
                "type": "text",
                "text": "Extract this retail receipt using the validation tool.",
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime};base64,{encoded}"
                },
            },
        ]
    else:
        content = [{
            "type": "text",
            "text": f"Extract this retail receipt:\n\n{text}",
        }]

    rules = EXTRACTION_PROMPT.replace(
        "Return ONLY one JSON object with exactly these keys:",
        "The receipt JSON submitted to the tool must have exactly these keys:",
    )

    messages = [
        {
            "role": "system",
            "content": rules + "\n" + AGENT_INSTRUCTIONS,
        },
        {
            "role": "user",
            "content": content,
        },
    ]

    async with AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=60,
        max_retries=0,
    ) as client:
        for attempt in range(1, MAX_MODEL_CALLS + 1):
            print(
                f"[Agent] model call {attempt}/{MAX_MODEL_CALLS}",
                flush=True,
            )

            response = await client.chat.completions.create(
                model="gemma-4-E4B-it",
                temperature=0,
                max_tokens=1000,
                messages=messages,
                tools=[VALIDATION_TOOL],
                tool_choice="auto",
            )

            message = response.choices[0].message
            calls = message.tool_calls or []

            if not calls:
                messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                })
                messages.append({
                    "role": "user",
                    "content": (
                        "Call validate_receipt with your proposed receipt JSON. "
                        "A plain-text answer cannot complete this task."
                    ),
                })
                continue

            if len(calls) > 4 or any(c.type != "function" for c in calls):
                raise RuntimeError("Unexpected or excessive tool calls")

            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in calls
                ],
            })

            for call in calls:
                if len(calls) != 1:
                    result = {
                        "valid": False,
                        "errors": [{
                            "message": (
                                "Submit exactly one validate_receipt call "
                                "per round."
                            )
                        }],
                    }
                else:
                    result = execute_tool(
                    call.function.name,
                    call.function.arguments,
                    source_text=text if image_bytes is None else None,
                    )

                print(
                    f"[Agent] tool={call.function.name} "
                    f"valid={result['valid']}",
                    flush=True,
                )

                if result["valid"]:
                    return ReceiptData.model_validate(result["data"])

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

    raise RuntimeError(
        "Agent did not produce validated receipt data within the call limit"
    )