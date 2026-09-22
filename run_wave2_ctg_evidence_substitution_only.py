from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from apify import Actor

from outreach_v101 import evaluate_batch
from run_wave2_evidence_only import apply_evidence_sourcing_only, apply_frozen_dm
from run_wave2_evidence_score_only import apply_score_only
from run_wave2_hook_grounding_only import apply_hook_grounding_only
from src.schema.conformance import sanitize_batch

BASELINE = Path("research/catalogfix_wave1_candidates.json")
DM_ENRICHMENTS = Path("research/wave2_dm_enrichment.json")
EVIDENCE_DIAGNOSTIC = Path("research/wave2_run_b_evidence_diagnostic.json")
RUBRIC = Path("research/wave2_run_c_evidence_score_rubric.json")
RUN_E_SPEC = Path("research/wave2_run_e_ctg_evidence_substitution.json")

RUN_ID = os.getenv("RUN_ID", "lg-2026-09-22-wave2-run-e-ctg-evidence-substitution-only")
RUN_TS = os.getenv("RUN_TIMESTAMP_UTC", "2026-09-22T15:55:00Z")


def apply_ctg_substitution(candidates: list[dict], spec: dict) -> dict:
    target = spec["target_company"]
    replacement = spec["substituted_evidence"]
    score = spec["rubric"]["total"]
    for row in candidates:
        if row.get("company_name") != target:
            continue
        before = {
            "recent_evidence": row.get("recent_evidence"),
            "evidence_type": row.get("evidence_type"),
            "evidence_url": row.get("evidence_url"),
            "evidence_date_raw": row.get("evidence_date_raw"),
            "evidence_content": row.get("evidence_content"),
            "evidence_score": row.get("evidence_score"),
            "source_urls": list(row.get("source_urls") or []),
        }
        row["recent_evidence"] = replacement["recent_evidence"]
        row["evidence_type"] = replacement["evidence_type"]
        row["evidence_url"] = replacement["evidence_url"]
        row["evidence_date_raw"] = replacement["evidence_date_raw"]
        row["evidence_content"] = replacement["evidence_content"]
        urls = list(row.get("source_urls") or [])
        for url in replacement.get("source_urls_append") or []:
            if url not in urls:
                urls.append(url)
        row["source_urls"] = urls
        row["evidence_score"] = score
        return {
            "company_name": target,
            "diagnostic": spec["diagnostic"],
            "before": before,
            "after": {
                "recent_evidence": row["recent_evidence"],
                "evidence_type": row["evidence_type"],
                "evidence_url": row["evidence_url"],
                "evidence_date_raw": row["evidence_date_raw"],
                "evidence_score": row["evidence_score"],
                "source_urls": row["source_urls"],
            },
            "rubric": spec["rubric"],
            "collector_behavior_changed": False,
            "global_scoring_logic_changed": False,
            "thresholds_changed": False,
            "dm_logic_changed": False,
            "evidence_max_age_days_changed": False,
        }
    raise ValueError(f"{target} not found")


async def main() -> None:
    async with Actor:
        candidates = json.loads(BASELINE.read_text(encoding="utf-8"))
        dm_enrichments = json.loads(DM_ENRICHMENTS.read_text(encoding="utf-8"))
        evidence_diagnostic = json.loads(EVIDENCE_DIAGNOSTIC.read_text(encoding="utf-8"))
        rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
        run_e_spec = json.loads(RUN_E_SPEC.read_text(encoding="utf-8"))

        # Reconstruct Run D state first.
        apply_frozen_dm(candidates, dm_enrichments)
        apply_evidence_sourcing_only(candidates, evidence_diagnostic)
        apply_score_only(candidates, rubric)
        apply_hook_grounding_only(candidates)

        substitution_report = apply_ctg_substitution(candidates, run_e_spec)

        passed, reserve, manifest = evaluate_batch(
            candidates,
            run_id=RUN_ID,
            run_timestamp_utc=RUN_TS,
        )
        passed, reserve = sanitize_batch(passed, reserve)

        manifest["evidence_sourcing"] = {
            "status": "complete",
            "mode": "evidence-substitution-only",
            "applied_companies": ["The Commerce Team Global"],
            "diagnostics": {"The Commerce Team Global": "evidence_low_quality"},
            "collector_behavior_changed": False,
            "global_scoring_logic_changed": False,
            "thresholds_changed": False,
            "dm_logic_changed": False,
            "evidence_max_age_days_changed": False,
            "frozen_run_timestamp_utc": RUN_TS,
        }

        await Actor.set_value("BATCH_MANIFEST", manifest)
        await Actor.set_value("PASSED", passed)
        await Actor.set_value("RESERVE", reserve)
        await Actor.set_value("CTG_EVIDENCE_SUBSTITUTION_REPORT", substitution_report)

        Actor.log.info("RUN_E_BATCH_MANIFEST %s", json.dumps(manifest, ensure_ascii=False, sort_keys=True))
        Actor.log.info("RUN_E_SUBSTITUTION_REPORT %s", json.dumps(substitution_report, ensure_ascii=False, sort_keys=True))
        await Actor.set_status_message(
            f"Run E complete: {len(passed)} passed / {len(reserve)} reserve",
            is_terminal=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
