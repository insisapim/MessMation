from io import BytesIO
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import APIError, APITimeoutError
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from llm import MissingConfigError, check_document
from schemas import DocumentCheck

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


@app.post("/api/extract", response_model=DocumentCheck)
async def extract(
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

        # ตรวจเนื้อหาไฟล์จริง ไม่เชื่อเพียงนามสกุลหรือ Content-Type
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

    try:
        print("[Backend] กำลังส่งให้ AI ตรวจประเภทเอกสาร")

        result = await check_document(
            text=text if mode == "text" else None,
            image_bytes=image_bytes,
            mime=mime,
        )

        print("[Backend] ผลตรวจ:", result.document_type)

        return result

    except MissingConfigError as exc:
        raise HTTPException(
            503,
            "กรุณาตั้งค่า API key และ base URL ใน .env",
        ) from exc

    except ValidationError as exc:
        raise HTTPException(
            502,
            "AI ตอบกลับผิดรูปแบบ JSON ที่กำหนด",
        ) from exc

    except APITimeoutError as exc:
        raise HTTPException(
            504,
            "AI ใช้เวลานานเกินกำหนด กรุณาลองใหม่",
        ) from exc

    except APIError as exc:
        raise HTTPException(
            502,
            "ติดต่อ AI ไม่สำเร็จ กรุณาตรวจการตั้งค่าและโควตา",
        ) from exc