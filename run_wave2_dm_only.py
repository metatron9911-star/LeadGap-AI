from __future__ import annotations

import json
import os
from pathlib import Path

from outreach_v101 import evaluate_batch
from src.enrichment.dm_resolver import DMCandidate, dm_report_entry, resolve_decision_maker
from src.schema.conformance import sanitize_batch

BASELINE = Path("research/catalogfix_wave1_candidates.json")
ENRICHMENTS = Path("research/wave2_dm_enrichment.json")
OUTDIR = Path("research/wave2_dm_only_output")
RUN_ID = os.getenv("RUN_ID", "lg-2026-09-22-wave2-dm-only")
RUN_TS = os.getenv("RUN_TIMESTAMP_UTC", "2026-09-22T15:55:00Z")


def main() -> None:
    candidates = json.loads(BASELINE.read_text(encoding="utf-8"))
    enrichments = json.loads(ENRICHMENTS.read_text(encoding="utf-8"))
    by_company = {row["company_name"]: row for row in enrichments}

    reports: list[dict] = []
    recovered = 0

    for row in candidates:
        spec = by_company.get(row["company_name"])
        if not spec:
            # Existing baseline DM counts as already-covered.
            if row.get("decision_maker_name") and row.get("decision_maker_role"):
                reports.append({
                    "company_name": row["company_name"],
                    "segment": row["segment"],
                    "dm_found": True,
                    "dm_role_match": None,
                    "dm_source": "baseline",
                    "dm_confidence": 1.0,
                    "dm_missing_reason": None,
                    "primary": {
                        "name": row["decision_maker_name"],
                        "role": row["decision_maker_role"],
                        "source": "baseline",
                        "source_url": row.get("linkedin_url"),
                    },
                    "fallback": None,
                    "recovered_in_wave2": False,
                })
            continue

        dm_candidates = [
            DMCandidate(
                item["name"],
                item["role"],
                item["source"],
                item["source_url"],
                item["confidence"],
            )
            for item in spec.get("candidates", [])
        ]
        resolution = resolve_decision_maker(row["segment"], dm_candidates)
        report = dm_report_entry(row["company_name"], row["segment"], resolution)
        report["recovered_in_wave2"] = resolution.primary is not None
        if resolution.primary is None and spec.get("missing_reason"):
            report["dm_missing_reason"] = spec["missing_reason"]
        reports.append(report)

        if resolution.primary is not None:
            recovered += 1
            row["decision_maker_name"] = resolution.primary.name
            row["decision_maker_role"] = resolution.primary.role
            if resolution.primary.source == "linkedin":
                row["linkedin_url"] = resolution.primary.source_url

    passed, reserve, manifest = evaluate_batch(
        candidates,
        run_id=RUN_ID,
        run_timestamp_utc=RUN_TS,
    )
    passed, reserve = sanitize_batch(passed, reserve)

    total = len(candidates)
    covered = sum(1 for row in candidates if row.get("decision_maker_name") and row.get("decision_maker_role"))
    matched_reports = [r for r in reports if r.get("dm_found") and r.get("dm_role_match") is not None]
    manifest["dm_enrichment"] = {
        "mode": "complete",
        "dm_coverage": covered / total if total else 0.0,
        "dm_covered": covered,
        "dm_total": total,
        "recovered_from_baseline_no_decision_maker": recovered,
        "dm_role_match": (
            sum(float(r["dm_role_match"]) for r in matched_reports) / len(matched_reports)
            if matched_reports else 0.0
        ),
        "dm_confidence": (
            sum(float(r["dm_confidence"]) for r in matched_reports) / len(matched_reports)
            if matched_reports else 0.0
        ),
        "dm_missing_reason": {
            r["company_name"]: r["dm_missing_reason"]
            for r in reports if not r.get("dm_found")
        },
    }
    manifest["email_verification"] = {
        "status": "not_run",
        "verification_status": "skipped",
        "reason": "provider_skipped — no real verifier API key configured for DM-only Run A",
        "provider_skipped": True,
        "email_coverage": None,
    }

    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "passed.json").write_text(json.dumps(passed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (OUTDIR / "reserve.jsonl").open("w", encoding="utf-8") as handle:
        for row in reserve:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (OUTDIR / "batch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUTDIR / "dm_enrichment_report.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUTDIR / "schema_conformance.log").write_text(
        f"main_rows={len(passed)} OK\nreserve_rows={len(reserve)} OK\n",
        encoding="utf-8",
    )

    print("WAVE2_DM_ONLY_MANIFEST")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
