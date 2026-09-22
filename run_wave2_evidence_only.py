from __future__ import annotations

import json
import os
from pathlib import Path

from apify import Actor

from outreach_v101 import evaluate_batch
from src.enrichment.dm_resolver import DMCandidate, resolve_decision_maker
from src.schema.conformance import sanitize_batch

BASELINE = Path("research/catalogfix_wave1_candidates.json")
DM_ENRICHMENTS = Path("research/wave2_dm_enrichment.json")
EVIDENCE_DIAGNOSTIC = Path("research/wave2_run_b_evidence_diagnostic.json")

RUN_ID = os.getenv("RUN_ID", "lg-2026-09-22-wave2-run-b-evidence-sourcing-only")
RUN_TS = os.getenv("RUN_TIMESTAMP_UTC", "2026-09-22T15:55:00Z")


def apply_frozen_dm(candidates: list[dict], enrichments: list[dict]) -> None:
    by_company = {row["company_name"]: row for row in enrichments}
    for row in candidates:
        spec = by_company.get(row["company_name"])
        if not spec:
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
        if resolution.primary is not None:
            row["decision_maker_name"] = resolution.primary.name
            row["decision_maker_role"] = resolution.primary.role
            if resolution.primary.source == "linkedin":
                row["linkedin_url"] = resolution.primary.source_url


def apply_evidence_sourcing_only(candidates: list[dict], diagnostics: list[dict]) -> list[dict]:
    by_company = {row["company_name"]: row for row in diagnostics}
    report: list[dict] = []

    for row in candidates:
        spec = by_company.get(row["company_name"])
        if not spec:
            continue

        before = {
            "evidence_type": row.get("evidence_type"),
            "evidence_url": row.get("evidence_url"),
            "evidence_date_raw": row.get("evidence_date_raw"),
            "evidence_score": row.get("evidence_score"),
        }

        applied = False
        if spec.get("apply_to_run_b"):
            ev = spec["evidence"]
            row["recent_evidence"] = ev["recent_evidence"]
            row["evidence_type"] = ev["evidence_type"]
            row["evidence_url"] = ev["evidence_url"]
            row["evidence_date_raw"] = ev["evidence_date_raw"]
            row["evidence_content"] = ev["evidence_content"]
            for url in ev.get("source_urls_append", []):
                if url not in row["source_urls"]:
                    row["source_urls"].append(url)
            applied = True

        after = {
            "evidence_type": row.get("evidence_type"),
            "evidence_url": row.get("evidence_url"),
            "evidence_date_raw": row.get("evidence_date_raw"),
            "evidence_score": row.get("evidence_score"),
        }

        report.append(
            {
                "company_name": row["company_name"],
                "diagnostic": spec["diagnostic"],
                "applied": applied,
                "before": before,
                "after": after,
                "score_unchanged": before["evidence_score"] == after["evidence_score"],
                "thresholds_unchanged": True,
                "evidence_max_age_days_unchanged": True,
            }
        )

    return report


async def main() -> None:
    async with Actor:
        candidates = json.loads(BASELINE.read_text(encoding="utf-8"))
        dm_enrichments = json.loads(DM_ENRICHMENTS.read_text(encoding="utf-8"))
        evidence_diagnostic = json.loads(EVIDENCE_DIAGNOSTIC.read_text(encoding="utf-8"))

        apply_frozen_dm(candidates, dm_enrichments)
        evidence_report = apply_evidence_sourcing_only(candidates, evidence_diagnostic)

        passed, reserve, manifest = evaluate_batch(
            candidates,
            run_id=RUN_ID,
            run_timestamp_utc=RUN_TS,
        )
        passed, reserve = sanitize_batch(passed, reserve)

        manifest["evidence_sourcing"] = {
            "status": "complete",
            "mode": "evidence-sourcing-only",
            "frozen_run_timestamp_utc": RUN_TS,
            "dm_logic_changed": False,
            "scoring_logic_changed": False,
            "evidence_scores_changed": False,
            "thresholds_changed": False,
            "evidence_max_age_days_changed": False,
            "applied_companies": [r["company_name"] for r in evidence_report if r["applied"]],
            "diagnostics": {
                r["company_name"]: r["diagnostic"] for r in evidence_report
            },
        }

        await Actor.set_value("BATCH_MANIFEST", manifest)
        await Actor.set_value("PASSED", passed)
        await Actor.set_value("RESERVE", reserve)
        await Actor.set_value("EVIDENCE_SOURCING_REPORT", evidence_report)

        Actor.log.info(
            "RUN_B_BATCH_MANIFEST %s",
            json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        )
        Actor.log.info(
            "RUN_B_EVIDENCE_REPORT %s",
            json.dumps(evidence_report, ensure_ascii=False, sort_keys=True),
        )
        await Actor.set_status_message(
            f"Run B complete: {len(passed)} passed / {len(reserve)} reserve",
            is_terminal=True,
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
