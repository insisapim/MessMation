import json
import os
from fastapi import Depends
from fastapi.responses import StreamingResponse
from pipeline import pipeline_events
from io import BytesIO
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from schemas import ExtractionResponse

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

MAX_IMAGE_BYTES = 5 * 1024 * 1024 

IMAGE_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}

app.mount(
    "/web",
    StaticFiles(directory=WEB_DIR),
    name="web",
)


@app.get("/")
def home():
    return FileResponse(WEB_DIR / "index.html")


async def prepare_input(
    mode: Literal["text", "image"] = Form(...),
    text: str = Form(""),
    image: UploadFile | None = File(None),
):
    image_bytes = None
    mime = None

    if mode == "text":
        text = text.strip()

        if not text:
            raise HTTPException(422, "กรุณากรอกข้อความ")

        if len(text) > 12000:
            raise HTTPException(422, "ข้อความยาวเกิน 12,000 ตัวอักษร")

        print("[Backend] รับข้อมูลโหมดข้อความ")

    else:
        if image is None:
            raise HTTPException(422, "กรุณาเลือกรูปภาพ")

        try:
            image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
        finally:
            await image.close()

        if not image_bytes:
            raise HTTPException(422, "ไฟล์ภาพว่าง")

        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "ภาพต้องมีขนาดไม่เกิน 5 MiB")

        try:
            with Image.open(BytesIO(image_bytes)) as picture:
                mime = IMAGE_TYPES.get(picture.format)

                if mime is None:
                    raise HTTPException(
                        415,
                        "รองรับเฉพาะ JPEG, PNG และ WebP",
                    )

                if picture.width * picture.height > 20_000_000:
                    raise HTTPException(
                        413,
                        "ภาพมีความละเอียดสูงเกินไป กรุณาย่อภาพ",
                    )

                picture.verify()

        except (
            UnidentifiedImageError,
            OSError,
            SyntaxError,
            Image.DecompressionBombError,
        ) as exc:
            raise HTTPException(
                415,
                "ไฟล์ไม่ใช่รูปภาพที่อ่านได้ หรือไฟล์เสีย",
            ) from exc

        print("[Backend] รับข้อมูลโหมดรูปภาพ")

    return {
                "text": text if mode == "text" else None,
                "image_bytes": image_bytes,
                "mime": mime,
            }


def demo_enabled() -> bool:
    return (
        os.getenv("MESSMATION_DEMO", "false").strip().lower()
        == "true"
    )


@app.post("/api/extract", response_model=ExtractionResponse)
async def extract_json(payload: dict = Depends(prepare_input)):
    if demo_enabled():
        raise HTTPException(
            status_code=503,
            detail="ปิด MESSMATION_DEMO ก่อนรัน evaluation",
        )

    result = None
    failure = None

    async for event in pipeline_events(**payload):
        if event["type"] == "result":
            result = event["data"]

        elif event["type"] == "error":
            failure = event

    if failure is not None:
        raise HTTPException(
            status_code=failure["status_code"],
            detail=failure["message"],
        )

    if result is None:
        raise HTTPException(500, "ระบบจบการทำงานโดยไม่มีผลลัพธ์")

    return result


@app.post("/api/extract/stream")
async def extract_stream(payload: dict = Depends(prepare_input)):
    demo = demo_enabled()

    async def stream():
        async for event in pipeline_events(**payload, demo=demo):
            encoded = json.dumps(event, ensure_ascii=False)

            yield f"data: {encoded}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )