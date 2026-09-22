from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from apify import Actor

from outreach_v101 import evaluate_batch
from run_wave2_evidence_only import apply_evidence_sourcing_only, apply_frozen_dm
from run_wave2_evidence_score_only import apply_score_only
from src.schema.conformance import sanitize_batch

BASELINE = Path("research/catalogfix_wave1_candidates.json")
DM_ENRICHMENTS = Path("research/wave2_dm_enrichment.json")
EVIDENCE_DIAGNOSTIC = Path("research/wave2_run_b_evidence_diagnostic.json")
RUBRIC = Path("research/wave2_run_c_evidence_score_rubric.json")

RUN_ID = os.getenv("RUN_ID", "lg-2026-09-22-wave2-run-d-hook-grounding-only")
RUN_TS = os.getenv("RUN_TIMESTAMP_UTC", "2026-09-22T15:55:00Z")


def apply_hook_grounding_only(candidates: list[dict]) -> dict:
    target_url = (
        "https://notoagency.pl/blogs/strefa-wiedzy/"
        "shopify-dla-marki-odziezowej-premium-na-co-zwrocic-uwage"
    )
    for row in candidates:
        if row.get("company_name") != "Noto Agency":
            continue
        if row.get("evidence_url") != target_url:
            raise ValueError("Run D target evidence URL does not match frozen Run B/C evidence")
        before = {
            "personalization_hook": row.get("personalization_hook"),
            "hook_grounding": row.get("hook_grounding"),
        }
        row["personalization_hook"] = (
            "Your September Shopify article for premium fashion brands stood out — "
            "it is exactly the kind of current implementation work where cleaner catalog inputs matter."
        )
        row["hook_grounding"] = [
            {"claim": "Shopify", "grounded_in": target_url},
            {"claim": "premium fashion brands", "grounded_in": target_url},
        ]
        row["first_line"] = (
            "Your September Shopify article for premium fashion brands caught my eye because "
            "catalog cleanup often becomes invisible implementation work."
        )
        return {
            "company_name": "Noto Agency",
            "before": before,
            "after": {
                "personalization_hook": row["personalization_hook"],
                "hook_grounding": row["hook_grounding"],
            },
            "evidence_url": target_url,
            "dm_logic_changed": False,
            "evidence_sourcing_changed": False,
            "evidence_score_changed": False,
            "thresholds_changed": False,
            "evidence_max_age_days_changed": False,
        }
    raise ValueError("Noto Agency not found")


async def main() -> None:
    async with Actor:
        candidates = json.loads(BASELINE.read_text(encoding="utf-8"))
        dm_enrichments = json.loads(DM_ENRICHMENTS.read_text(encoding="utf-8"))
        evidence_diagnostic = json.loads(EVIDENCE_DIAGNOSTIC.read_text(encoding="utf-8"))
        rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))

        apply_frozen_dm(candidates, dm_enrichments)
        evidence_report = apply_evidence_sourcing_only(candidates, evidence_diagnostic)
        score_report = apply_score_only(candidates, rubric)
        hook_report = apply_hook_grounding_only(candidates)

        passed, reserve, manifest = evaluate_batch(
            candidates,
            run_id=RUN_ID,
            run_timestamp_utc=RUN_TS,
        )
        passed, reserve = sanitize_batch(passed, reserve)

        manifest["hook_grounding_experiment"] = {
            "status": "complete",
            "mode": "hook-grounding-only",
            "target_company": "Noto Agency",
            "frozen_run_timestamp_utc": RUN_TS,
            "dm_logic_changed": False,
            "evidence_sourcing_changed_from_run_c": False,
            "evidence_score_changed_from_run_c": False,
            "thresholds_changed": False,
            "evidence_max_age_days_changed": False,
        }

        await Actor.set_value("BATCH_MANIFEST", manifest)
        await Actor.set_value("PASSED", passed)
        await Actor.set_value("RESERVE", reserve)
        await Actor.set_value("EVIDENCE_SOURCING_REPORT", evidence_report)
        await Actor.set_value("EVIDENCE_SCORE_REPORT", score_report)
        await Actor.set_value("HOOK_GROUNDING_REPORT", hook_report)

        Actor.log.info("RUN_D_BATCH_MANIFEST %s", json.dumps(manifest, ensure_ascii=False, sort_keys=True))
        Actor.log.info("RUN_D_HOOK_REPORT %s", json.dumps(hook_report, ensure_ascii=False, sort_keys=True))
        await Actor.set_status_message(
            f"Run D complete: {len(passed)} passed / {len(reserve)} reserve",
            is_terminal=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
