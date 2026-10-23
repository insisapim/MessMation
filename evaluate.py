import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import httpx

from schemas import ReceiptData


FIELDS = [
    "merchant_name",
    "receipt_date",
    "total",
    "currency",
    "receipt_number",
]


def load_examples(path: Path) -> list[dict]:
    examples = []
    seen_ids = set()

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        example = json.loads(line)

        example_id = example["id"]

        if example_id in seen_ids:
            raise ValueError(f"ID ซ้ำ: {example_id}")

        seen_ids.add(example_id)

        gold = ReceiptData.model_validate(example["gold"])
        example["gold"] = gold.model_dump()

        if example["mode"] == "text":
            text = example.get("text", "")

            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"ข้อความว่างที่บรรทัด {line_number}")

            if len(text.strip()) > 12000:
                raise ValueError(f"ข้อความยาวเกินกำหนด: {example_id}")

        elif example["mode"] == "image":
            image_path = path.parent / example["image"]

            if not image_path.is_file():
                raise ValueError(f"ไม่พบภาพ: {image_path}")

        else:
            raise ValueError(f"mode ไม่ถูกต้อง: {example_id}")

        examples.append(example)

    if not examples:
        raise ValueError("ชุดข้อมูลไม่มีตัวอย่าง")

    return examples


def send_example(
    client: httpx.Client,
    url: str,
    example: dict,
    dataset_dir: Path,
) -> httpx.Response:

    if example["mode"] == "text":
        return client.post(
            url,
            data={
                "mode": "text",
                "text": example["text"],
            },
        )

    image_path = dataset_dir / example["image"]

    with image_path.open("rb") as image_file:
        return client.post(
            url,
            data={"mode": "image"},
            files={
                "image": (
                    image_path.name,
                    image_file,
                    "application/octet-stream",
                )
            },
        )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("dataset", type=Path)

    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/api/extract",
    )

    args = parser.parse_args()

    examples = load_examples(args.dataset)

    rows = []
    valid_count = 0
    exact_count = 0

    correct_by_field = {field: 0 for field in FIELDS}

    present_correct = 0
    present_total = 0
    null_correct = 0
    null_total = 0

    with httpx.Client(timeout=150.0) as client:
        for example in examples:
            started = time.perf_counter()

            prediction = None
            response_body = None
            http_status = None
            error = None
            schema_valid = False

            try:
                response = send_example(
                    client,
                    args.url,
                    example,
                    args.dataset.parent,
                )

                http_status = response.status_code
                response_body = response.json()

                if response.status_code != 200:
                    error = response_body.get(
                        "detail",
                        f"HTTP {response.status_code}",
                    )

                elif response_body.get("document_type") != "receipt":
                    error = (
                        "ระบบไม่ได้จัดประเภทเป็นใบเสร็จ: "
                        f"{response_body.get('document_type')}"
                    )

                else:
                    receipt = ReceiptData.model_validate(
                        response_body.get("data")
                    )

                    prediction = receipt.model_dump()
                    schema_valid = True

            except Exception as exc:
                error = f"Request/evaluation failed: {type(exc).__name__}"

            elapsed = time.perf_counter() - started

            gold = example["gold"]
            field_results = {}

            for field in FIELDS:
                correct = (
                    schema_valid
                    and prediction[field] == gold[field]
                )

                field_results[field] = correct
                correct_by_field[field] += int(correct)

                if gold[field] is None:
                    null_total += 1
                    null_correct += int(correct)
                else:
                    present_total += 1
                    present_correct += int(correct)

            exact = all(field_results.values())

            valid_count += int(schema_valid)
            exact_count += int(exact)

            rows.append({
                "id": example["id"],
                "mode": example["mode"],
                "gold": gold,
                "prediction": prediction,
                "schema_valid": schema_valid,
                "field_correct": field_results,
                "exact_match": exact,
                "http_status": http_status,
                "response": response_body,
                "error": error,
                "elapsed_seconds": round(elapsed, 3),
            })

            print(
                f"{example['id']}: "
                f"schema={schema_valid}, "
                f"fields={sum(field_results.values())}/{len(FIELDS)}, "
                f"exact={exact}, "
                f"time={elapsed:.1f}s"
            )

    count = len(examples)

    summary = {
        "dataset": str(args.dataset),
        "examples": count,
        "schema_valid_rate": valid_count / count,
        "field_accuracy": (
            sum(correct_by_field.values())
            / (count * len(FIELDS))
        ),
        "document_exact_match": exact_count / count,
        "accuracy_by_field": {
            field: correct_by_field[field] / count
            for field in FIELDS
        },
        "present_field_accuracy": (
            present_correct / present_total
            if present_total else None
        ),
        "null_field_accuracy": (
            null_correct / null_total
            if null_total else None
        ),
        "average_elapsed_seconds": (
            sum(row["elapsed_seconds"] for row in rows) / count
        ),
    }

    output_dir = args.dataset.parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output_path = output_dir / f"{args.dataset.stem}-{timestamp}.json"

    output_path.write_text(
        json.dumps(
            {"summary": summary, "examples": rows},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nSummary:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    main()