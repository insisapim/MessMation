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

    document_type: Literal[
        "receipt",
        "not_receipt",
        "unclear",
    ]

    reason: str = Field(min_length=1, max_length=500)