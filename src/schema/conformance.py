from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
MAIN_SCHEMA = ROOT / "schemas" / "leadgap-lead.json"
RESERVE_SCHEMA = ROOT / "schemas" / "leadgap-reserve.json"


def load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def strip_to_schema(record: dict, schema: dict) -> dict:
    allowed = set((schema.get("properties") or {}).keys())
    return {key: value for key, value in record.items() if key in allowed}


def validate_record(record: dict, schema: dict) -> list[str]:
    validator = Draft202012Validator(schema)
    return [error.message for error in sorted(validator.iter_errors(record), key=lambda e: list(e.path))]


def sanitize_and_validate_main(record: dict) -> dict:
    schema = load_schema(MAIN_SCHEMA)
    clean = strip_to_schema(record, schema)
    errors = validate_record(clean, schema)
    if errors:
        raise ValueError("main schema validation failed: " + "; ".join(errors))
    return clean


def sanitize_and_validate_reserve(record: dict) -> dict:
    schema = load_schema(RESERVE_SCHEMA)
    clean = strip_to_schema(record, schema)
    errors = validate_record(clean, schema)
    if errors:
        raise ValueError("reserve schema validation failed: " + "; ".join(errors))
    return clean


def sanitize_batch(main_rows: Iterable[dict], reserve_rows: Iterable[dict]) -> tuple[list[dict], list[dict]]:
    return (
        [sanitize_and_validate_main(row) for row in main_rows],
        [sanitize_and_validate_reserve(row) for row in reserve_rows],
    )
