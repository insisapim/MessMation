from pydantic import ValidationError

from schemas import ReceiptData
import re

def check_currency_evidence(
    source_text: str,
    currency: str | None,
) -> list[dict]:
    amount = r"\d+(?:[,.]\d+)*"

    baht_pattern = (
        rf"(?:{amount}\s*(?:บาท|฿|THB\b))"
        rf"|(?:(?:฿|\bTHB)\s*{amount})"
    )

    has_baht_amount = re.search(
        baht_pattern,
        source_text,
        flags=re.IGNORECASE,
    )

    foreign_pattern = (
        r"\b(?:USD|EUR|GBP|JPY|CNY|RMB|SGD|HKD|AUD|CAD|"
        r"CHF|KRW|INR|MYR|VND|IDR|PHP|TWD|NZD)\b"
        r"|[$€£¥₹₩]"
        r"|ดอลลาร์|ยูโร|ปอนด์|เยน|หยวน|วอน|รูปี|ริงกิต"
    )

    has_foreign_marker = re.search(
        foreign_pattern,
        source_text,
        flags=re.IGNORECASE,
    )

    if has_baht_amount and not has_foreign_marker and currency != "THB":
        return [{
            "field": "currency",
            "type": "currency_evidence_mismatch",
            "message": (
                "The source contains an amount explicitly marked in Thai "
                "baht, but currency is not THB. Recheck the original receipt "
                "and submit corrected data."
            ),
        }]

    return []

def validate_receipt(
    receipt_json: str,
    *,
    source_text: str | None = None,
) -> dict:
    try:
        receipt = ReceiptData.model_validate_json(receipt_json)

    except ValidationError as exc:
        return {
            "valid": False,
            "data": None,
            "errors": [
                {
                    "field": ".".join(
                        str(part) for part in error["loc"]
                    ) or "$",
                    "type": error["type"],
                    "message": error["msg"],
                }
                for error in exc.errors()
            ],
        }

    if source_text is not None:
        errors = check_currency_evidence(
            source_text,
            receipt.currency,
        )

        if errors:
            return {
                "valid": False,
                "data": None,
                "errors": errors,
            }

    return {
        "valid": True,
        "data": receipt.model_dump(mode="json"),
        "errors": [],
    }

if __name__ == "__main__":
    import json

    source = "ร้านทดสอบ\nยอดสุทธิ 120 บาท\nชำระเงินแล้ว"

    proposal = {
        "merchant_name": "ร้านทดสอบ",
        "receipt_date": None,
        "total": 120,
        "currency": None,
        "receipt_number": None,
    }

    rejected = validate_receipt(
        json.dumps(proposal, ensure_ascii=False),
        source_text=source,
    )

    assert rejected["valid"] is False
    assert rejected["errors"][0]["type"] == "currency_evidence_mismatch"

    proposal["currency"] = "THB"

    accepted = validate_receipt(
        json.dumps(proposal, ensure_ascii=False),
        source_text=source,
    )

    assert accepted["valid"] is True

    print("\nCurrency evidence checks passed.")
    cases = {
        "valid_receipt": {
            "merchant_name": "ร้านทดสอบ",
            "receipt_date": "2026-10-23",
            "total": 120,
            "currency": "THB",
            "receipt_number": None,
        },
        "invalid_receipt": {
            "merchant_name": "ร้านทดสอบ",
            "receipt_date": "2026-02-30",
            "total": -120,
            "currency": "thb",
            "receipt_number": None,
        },
    }

    for name, receipt in cases.items():
        result = validate_receipt(
            json.dumps(receipt, ensure_ascii=False)
        )
        print(f"\n{name}")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    print("\ninvalid_json")
    print(
        json.dumps(
            validate_receipt('{"merchant_name":'),
            ensure_ascii=False,
            indent=2,
        )
    )