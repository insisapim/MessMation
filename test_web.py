"""HTTP boundary checks; mocked model responses, no external API calls."""
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from main import app
from schemas import DocumentCheck, ReceiptData


class WebTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "MESSMATION_DEMO": "false", "MESSMATION_AGENT": "true",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_health_and_assets(self):
        self.assertEqual(self.client.get("/healthz").json(), {"status": "ok"})
        for path in ("/", "/web/app.js", "/web/style.css", "/web/favicon.svg",
                     "/web/fonts/NotoSansThai-Regular.ttf"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_invalid_input_never_calls_model(self):
        with patch("pipeline.check_document", new_callable=AsyncMock) as model:
            self.assertEqual(self.client.post("/api/extract", data={"mode": "text", "text": " "}).status_code, 422)
            self.assertEqual(self.client.post("/api/extract", data={"mode": "text", "text": "x" * 12001}).status_code, 422)
            response = self.client.post("/api/extract", data={"mode": "image"}, files={"image": ("fake.png", b"not an image", "image/png")})
            self.assertEqual(response.status_code, 415)
            model.assert_not_awaited()

    def test_non_receipt_skips_extraction(self):
        check = DocumentCheck(document_type="not_receipt", reason="Payment confirmation")
        with patch("pipeline.check_document", new_callable=AsyncMock, return_value=check), patch("pipeline.extract_receipt_agent", new_callable=AsyncMock) as extractor:
            response = self.client.post("/api/extract", data={"mode": "text", "text": "Payment confirmation"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["document_type"], "not_receipt")
            self.assertIsNone(response.json()["data"])
            extractor.assert_not_awaited()

    def test_stream_orders_result_before_done(self):
        check = DocumentCheck(document_type="receipt", reason="Retail receipt")
        receipt = ReceiptData(merchant_name="Test", receipt_date=None, total=120, currency="THB", receipt_number=None)
        with patch("pipeline.check_document", new_callable=AsyncMock, return_value=check), patch("pipeline.extract_receipt_agent", new_callable=AsyncMock, return_value=receipt):
            response = self.client.post("/api/extract/stream", data={"mode": "text", "text": "Total 120 THB"})
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/event-stream", response.headers["content-type"])
            events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
            self.assertEqual([e["type"] for e in events][-2:], ["result", "done"])
            self.assertEqual(events[-2]["data"]["data"]["total"], 120)
            self.assertFalse(any(e["demo"] for e in events))

    def test_demo_rejected_by_evaluation_endpoint(self):
        with patch.dict(os.environ, {"MESSMATION_DEMO": "true"}):
            response = self.client.post("/api/extract", data={"mode": "text", "text": "Receipt"})
            self.assertEqual(response.status_code, 503)

    def test_model_error_ends_stream(self):
        with patch("pipeline.check_document", new_callable=AsyncMock, side_effect=RuntimeError("mock failure")):
            response = self.client.post("/api/extract/stream", data={"mode": "text", "text": "Receipt"})
            events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
            self.assertEqual([e["type"] for e in events][-2:], ["error", "done"])
            self.assertNotIn("mock failure", response.text)


if __name__ == "__main__":
    unittest.main()
