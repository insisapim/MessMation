from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("ข้อความต้องไม่เป็นค่าว่าง")

        return value


class DocumentCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: Literal["receipt", "not_receipt", "unclear"]
    reason: str = Field(min_length=1, max_length=500)


class ReceiptData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_name: str | None = Field(min_length=1)
    receipt_date: str | None = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    total: float | None = Field(
        strict=True,
        ge=0,
        allow_inf_nan=False,
    )
    currency: str | None = Field(
        pattern=r"^[A-Z]{3}$"
    )
    receipt_number: str | None = Field(min_length=1)

    @field_validator("receipt_date")
    @classmethod
    def validate_receipt_date(cls, value: str | None):
        if value is not None:
            date.fromisoformat(value)

        return value


class ExtractionResponse(DocumentCheck):
    data: ReceiptData | None