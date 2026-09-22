from __future__ import annotations

import json
import os
from pathlib import Path

from jsonschema import Draft202012Validator

from outreach_v101 import evaluate_batch

INPUT = Path("research/catalogfix_wave1_candidates.json")
OUTDIR = Path("research/wave1_output")
RUN_ID = os.getenv("RUN_ID", "lg-2026-09-22-01")
RUN_TS = os.getenv("RUN_TIMESTAMP_UTC", "2026-09-22T04:12:00Z")


def validate_rows(rows: list[dict], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for idx, row in enumerate(rows, start=1):
        errors = sorted(validator.iter_errors(row), key=lambda e: list(e.path))
        if errors:
            joined = "; ".join(error.message for error in errors)
            raise AssertionError(f"{schema_path.name} row {idx}: {joined}")


def main() -> None:
    candidates = json.loads(INPUT.read_text(encoding="utf-8"))
    if len(candidates) != 12:
        raise AssertionError(f"Expected exactly 12 wave-1 candidates, got {len(candidates)}")

    passed, reserve, manifest = evaluate_batch(
        candidates,
        run_id=RUN_ID,
        run_timestamp_utc=RUN_TS,
    )

    validate_rows(passed, Path("schemas/leadgap-lead.json"))
    validate_rows(reserve, Path("schemas/leadgap-reserve.json"))

    if sum(manifest["source_mix"].values()) != manifest["totals"]["passed_thresholds"]:
        raise AssertionError("source_mix total != passed_thresholds")

    if manifest["totals"]["candidates_raw"] != 12:
        raise AssertionError("manifest candidates_raw != 12")

    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "passed.json").write_text(
        json.dumps(passed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (OUTDIR / "reserve.jsonl").open("w", encoding="utf-8") as handle:
        for row in reserve:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (OUTDIR / "batch_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("CATALOGFIX_WAVE1_MANIFEST")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"PASSED_ROWS={len(passed)}")
    print(f"RESERVE_ROWS={len(reserve)}")


if __name__ == "__main__":
    main()
