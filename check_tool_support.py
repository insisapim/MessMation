import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI, APIError

from receipt_tools import validate_receipt


load_dotenv(Path(__file__).resolve().parent / ".env")

TOOL = {
    "type": "function",
    "function": {
        "name": "validate_receipt",
        "description": "Check proposed receipt JSON against the receipt schema.",
        "parameters": {
            "type": "object",
            "properties": {
                "receipt_json": {
                    "type": "string",
                    "description": "The receipt JSON object encoded as a string.",
                }
            },
            "required": ["receipt_json"],
            "additionalProperties": False,
        },
    },
}


async def main():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()

    if not api_key or not base_url:
        print("CONFIG_ERROR: API key or base URL is missing.")
        return

    sample = {
        "merchant_name": "ร้านทดสอบ",
        "receipt_date": "2026-10-23",
        "total": 120,
        "currency": "THB",
        "receipt_number": None,
    }

    messages = [
        {
            "role": "system",
            "content": (
                "You are testing a validation tool. "
                "Call validate_receipt with the supplied JSON unchanged. "
                "After receiving the tool result, briefly report whether "
                "validation passed. Do not call the tool again."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(sample, ensure_ascii=False),
        },
    ]

    async with AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=60,
        max_retries=0,
    ) as client:
        first = await client.chat.completions.create(
            model="gemma-4-E4B-it",
            temperature=0,
            max_tokens=500,
            messages=messages,
            tools=[TOOL],
            tool_choice="auto",
        )

        message = first.choices[0].message
        calls = message.tool_calls or []

        if not calls:
            print("NO_TOOL_CALL: No native tool call was returned.")
            print("Model response:", message.content)
            return

        if (
            len(calls) != 1
            or calls[0].type != "function"
            or calls[0].function.name != "validate_receipt"
        ):
            print("UNEXPECTED_TOOL_CALL: Tool was not executed.")
            return

        call = calls[0]

        try:
            arguments = json.loads(call.function.arguments)
        except json.JSONDecodeError:
            print("INVALID_ARGUMENTS: Arguments are not valid JSON.")
            return

        if (
            not isinstance(arguments, dict)
            or set(arguments) != {"receipt_json"}
            or not isinstance(arguments["receipt_json"], str)
        ):
            print("INVALID_ARGUMENTS: Expected only receipt_json as a string.")
            return

        print("NATIVE_TOOL_CALL:", call.function.name)

        result = validate_receipt(arguments["receipt_json"])
        print("TOOL_RESULT:")
        print(json.dumps(result, ensure_ascii=False, indent=2))

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
            ],
        })
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "content": json.dumps(result, ensure_ascii=False),
        })

        second = await client.chat.completions.create(
            model="gemma-4-E4B-it",
            temperature=0,
            max_tokens=200,
            messages=messages,
            tools=[TOOL],
            tool_choice="auto",
        )

        final = second.choices[0].message

        if final.tool_calls:
            print("EXTRA_TOOL_CALL: Stopped at the probe's two-request limit.")
            return

        if not final.content:
            print("EMPTY_FINAL_RESPONSE")
            return

        print("FINAL_RESPONSE:", final.content)
        print("ROUND_TRIP_OK: Tool result was sent back successfully.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except APIError as exc:
        print(
            "API_ERROR:",
            type(exc).__name__,
            "status=",
            getattr(exc, "status_code", None),
        )