from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from apify import Actor

from outreach_v101 import evaluate_batch
from run_wave2_evidence_only import apply_evidence_sourcing_only, apply_frozen_dm
from src.schema.conformance import sanitize_batch

BASELINE = Path("research/catalogfix_wave1_candidates.json")
DM_ENRICHMENTS = Path("research/wave2_dm_enrichment.json")
EVIDENCE_DIAGNOSTIC = Path("research/wave2_run_b_evidence_diagnostic.json")
RUBRIC = Path("research/wave2_run_c_evidence_score_rubric.json")

RUN_ID = os.getenv("RUN_ID", "lg-2026-09-22-wave2-run-c-evidence-score-only")
RUN_TS = os.getenv("RUN_TIMESTAMP_UTC", "2026-09-22T15:55:00Z")


def apply_score_only(candidates: list[dict], rubric: dict) -> dict:
    target = rubric["noto_agency"]
    expected = sum(target["component_scores"].values())
    if expected != target["total"]:
        raise ValueError(f"rubric total mismatch: {expected} != {target['total']}")

    target_url = target["source_url"]
    report = {
        "company_name": "Noto Agency",
        "source_url": target_url,
        "before_score": None,
        "after_score": target["total"],
        "threshold": rubric["threshold"],
        "components": target["component_scores"],
        "passed_score_gate": target["total"] >= rubric["threshold"],
        "scoring_logic_changed_globally": False,
        "score_changed_only_for_target": True,
    }

    for row in candidates:
        if row.get("company_name") != "Noto Agency":
            continue
        if row.get("evidence_url") != target_url:
            raise ValueError("Run C target evidence URL does not match frozen Run B evidence")
        report["before_score"] = row.get("evidence_score")
        row["evidence_score"] = target["total"]
        break
    else:
        raise ValueError("Noto Agency not found")

    return report


async def main() -> None:
    async with Actor:
        candidates = json.loads(BASELINE.read_text(encoding="utf-8"))
        dm_enrichments = json.loads(DM_ENRICHMENTS.read_text(encoding="utf-8"))
        evidence_diagnostic = json.loads(EVIDENCE_DIAGNOSTIC.read_text(encoding="utf-8"))
        rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))

        apply_frozen_dm(candidates, dm_enrichments)
        evidence_report = apply_evidence_sourcing_only(candidates, evidence_diagnostic)
        score_report = apply_score_only(candidates, rubric)

        passed, reserve, manifest = evaluate_batch(
            candidates,
            run_id=RUN_ID,
            run_timestamp_utc=RUN_TS,
        )
        passed, reserve = sanitize_batch(passed, reserve)

        manifest["evidence_score_experiment"] = {
            "status": "complete",
            "mode": "evidence-score-only",
            "rubric_version": rubric["version"],
            "target_company": "Noto Agency",
            "target_score": score_report["after_score"],
            "threshold": rubric["threshold"],
            "frozen_run_timestamp_utc": RUN_TS,
            "dm_logic_changed": False,
            "sourcing_changed_from_run_b": False,
            "thresholds_changed": False,
            "evidence_max_age_days_changed": False,
            "global_scoring_logic_changed": False,
        }

        await Actor.set_value("BATCH_MANIFEST", manifest)
        await Actor.set_value("PASSED", passed)
        await Actor.set_value("RESERVE", reserve)
        await Actor.set_value("EVIDENCE_SOURCING_REPORT", evidence_report)
        await Actor.set_value("EVIDENCE_SCORE_REPORT", score_report)
        await Actor.set_value("EVIDENCE_SCORE_RUBRIC", rubric)

        Actor.log.info(
            "RUN_C_BATCH_MANIFEST %s",
            json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        )
        Actor.log.info(
            "RUN_C_SCORE_REPORT %s",
            json.dumps(score_report, ensure_ascii=False, sort_keys=True),
        )
        await Actor.set_status_message(
            f"Run C complete: {len(passed)} passed / {len(reserve)} reserve",
            is_terminal=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
