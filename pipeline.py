import asyncio

from openai import APIError, APITimeoutError
from pydantic import ValidationError

from llm import MissingConfigError, check_document, extract_receipt
from schemas import DocumentCheck, ExtractionResponse, ReceiptData


async def pipeline_events(
    *,
    text: str | None = None,
    image_bytes: bytes | None = None,
    mime: str | None = None,
    demo: bool = False,
):
    def event(event_type: str, **payload):
        return {
            "type": event_type,
            "demo": demo,
            **payload,
        }

    try:
        yield event(
            "progress",
            message="รับข้อมูลและตรวจรูปแบบข้อมูลนำเข้าแล้ว",
        )

        if demo:
            yield event(
                "progress",
                message="โหมดจำลอง: ไม่เรียก AI และไม่อ่านข้อมูลจริง",
            )

        yield event(
            "progress",
            message="กำลังตรวจประเภทเอกสาร",
        )

        if demo:
            await asyncio.sleep(0.7)

            check = DocumentCheck(
                document_type="receipt",
                reason="ผลจำลองสำหรับทดสอบหน้าเว็บ",
            )
        else:
            check = await check_document(
                text=text,
                image_bytes=image_bytes,
                mime=mime,
            )

        if check.document_type != "receipt":
            yield event(
                "progress",
                message=f"หยุดการแปลงข้อมูล: {check.reason}",
            )

            result = ExtractionResponse(
                document_type=check.document_type,
                reason=check.reason,
                data=None,
            )

        else:
            yield event(
                "progress",
                message="พบใบเสร็จร้านค้า กำลังแปลงข้อมูล",
            )

            if demo:
                await asyncio.sleep(0.7)

                receipt = ReceiptData(
                    merchant_name="ร้านจำลอง — ไม่ใช่ผลจาก AI",
                    receipt_date="2026-10-23",
                    total=150,
                    currency="THB",
                    receipt_number="DEMO-001",
                )
            else:
                receipt = await extract_receipt(
                    text=text,
                    image_bytes=image_bytes,
                    mime=mime,
                )

            yield event(
                "progress",
                message="ข้อมูลผ่าน schema แล้ว",
            )

            result = ExtractionResponse(
                document_type="receipt",
                reason=check.reason,
                data=receipt,
            )

        yield event(
            "result",
            data=result.model_dump(mode="json"),
        )

    except MissingConfigError:
        yield event(
            "error",
            status_code=503,
            message="กรุณาตั้งค่า API key และ base URL ใน .env",
        )

    except ValidationError:
        yield event(
            "error",
            status_code=502,
            message="AI ตอบกลับผิดรูปแบบที่กำหนด",
        )

    except APITimeoutError:
        yield event(
            "error",
            status_code=504,
            message="AI ใช้เวลานานเกินกำหนด",
        )

    except APIError as exc:
        upstream_status = getattr(exc, "status_code", None)

        print(
            "[AI ERROR]",
            type(exc).__name__,
            f"upstream_status={upstream_status}",
            flush=True,
        )

        yield event(
            "error",
            status_code=502,
            message=(
                "บริการ AI ไม่พร้อมใช้งาน "
                f"(upstream status: {upstream_status})"
            ),
        )

    except Exception as exc:
        print(
            "[PIPELINE ERROR]",
            type(exc).__name__,
            flush=True,
        )

        yield event(
            "error",
            status_code=500,
            message="เกิดข้อผิดพลาดภายในระบบ",
        )

    yield event("done")