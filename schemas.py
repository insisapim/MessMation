import copy
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import receipt_agent as agent


SOURCE = "ร้านทดสอบ\nใบเสร็จ\nยอดสุทธิ 120 บาท"

VALID_DATA = {
    "merchant_name": "ร้านทดสอบ",
    "receipt_date": None,
    "total": 120.0,
    "currency": "THB",
    "receipt_number": None,
}


def model_response(data, call_id):
    """จำลองโมเดลเรียก validate_receipt"""
    call = SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(
            name="validate_receipt",
            arguments=json.dumps({
                "receipt_json": json.dumps(data, ensure_ascii=False)
            }),
        ),
    )
    message = SimpleNamespace(content=None, tool_calls=[call])
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)]
    )


class AgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_BASE_URL": "https://example.invalid/v1",
        })
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

        self.client = MagicMock()
        self.client.chat.completions.create = AsyncMock()

        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=self.client)
        context.__aexit__ = AsyncMock(return_value=False)

        self.client_patch = patch.object(
            agent, "AsyncOpenAI", return_value=context
        )
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)

    async def test_feedback_then_success(self):
        invalid_data = {**VALID_DATA, "total": -120.0}
        requests = []

        responses = iter([
            model_response(invalid_data, "call_invalid"),
            model_response(VALID_DATA, "call_fixed"),
        ])

        async def respond(**kwargs):
            requests.append(copy.deepcopy(kwargs["messages"]))
            return next(responses)

        self.client.chat.completions.create.side_effect = respond

        result = await agent.extract_receipt_agent(text=SOURCE)

        self.assertEqual(result.model_dump(), VALID_DATA)
        self.assertEqual(
            self.client.chat.completions.create.await_count, 2
        )

        feedback_messages = [
            message for message in requests[1]
            if message["role"] == "tool"
        ]
        self.assertEqual(len(feedback_messages), 1)

        feedback = feedback_messages[0]
        self.assertEqual(feedback["tool_call_id"], "call_invalid")

        payload = json.loads(feedback["content"])
        self.assertFalse(payload["valid"])
        self.assertTrue(any(
            error["field"] == "total"
            for error in payload["errors"]
        ))

    async def test_stops_at_call_limit(self):
        invalid_data = {**VALID_DATA, "total": -120.0}

        self.client.chat.completions.create.side_effect = [
            model_response(invalid_data, f"call_{i}")
            for i in range(agent.MAX_MODEL_CALLS)
        ]

        with self.assertRaisesRegex(RuntimeError, "call limit"):
            await agent.extract_receipt_agent(text=SOURCE)

        self.assertEqual(
            self.client.chat.completions.create.await_count,
            agent.MAX_MODEL_CALLS,
        )


if __name__ == "__main__":
    unittest.main()