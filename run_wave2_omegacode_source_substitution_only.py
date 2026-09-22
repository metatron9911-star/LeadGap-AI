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
from run_wave2_ctg_evidence_substitution_only import apply_ctg_substitution
from run_wave2_role_matrix_only import apply_run_f_dm
from src.schema.conformance import sanitize_batch

BASELINE = Path("research/catalogfix_wave1_candidates.json")
DM_ENRICHMENTS = Path("research/wave2_dm_enrichment.json")
EVIDENCE_DIAGNOSTIC = Path("research/wave2_run_b_evidence_diagnostic.json")
RUBRIC = Path("research/wave2_run_c_evidence_score_rubric.json")
RUN_E_SPEC = Path("research/wave2_run_e_ctg_evidence_substitution.json")
RUN_F_DM = Path("research/wave2_run_f_7thsense_observed_management.json")
RUN_G_SPEC = Path("research/wave2_run_g_omegacode_source_substitution.json")

RUN_ID = os.getenv("RUN_ID", "lg-2026-09-22-wave2-run-g-omegacode-source-substitution-only")
RUN_TS = os.getenv("RUN_TIMESTAMP_UTC", "2026-09-22T15:55:00Z")


def apply_omegacode_substitution(candidates: list[dict], spec: dict) -> dict:
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
        row["evidence_score"] = score
        urls = list(row.get("source_urls") or [])
        for url in replacement.get("source_urls_append") or []:
            if url not in urls:
                urls.append(url)
        row["source_urls"] = urls
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
        run_f_spec = json.loads(RUN_F_DM.read_text(encoding="utf-8"))
        run_g_spec = json.loads(RUN_G_SPEC.read_text(encoding="utf-8"))

        # Reconstruct Run F state first.
        apply_frozen_dm(candidates, dm_enrichments)
        apply_evidence_sourcing_only(candidates, evidence_diagnostic)
        apply_score_only(candidates, rubric)
        apply_hook_grounding_only(candidates)
        apply_ctg_substitution(candidates, run_e_spec)
        apply_run_f_dm(candidates, run_f_spec)

        substitution_report = apply_omegacode_substitution(candidates, run_g_spec)

        passed, reserve, manifest = evaluate_batch(
            candidates,
            run_id=RUN_ID,
            run_timestamp_utc=RUN_TS,
        )
        passed, reserve = sanitize_batch(passed, reserve)

        expected_existing_passed = {
            "InteractOne",
            "Graftstudio",
            "Ruby Digital Agency",
            "asioso",
            "Noto Agency",
            "The Commerce Team Global",
            "7thSENSE",
        }
        passed_names = {row["company_name"] for row in passed}
        regressions = sorted(expected_existing_passed - passed_names)

        manifest["evidence_sourcing"] = {
            "status": "complete",
            "mode": "evidence-substitution-only",
            "applied_companies": ["OmegaCode"],
            "diagnostics": {"OmegaCode": "sourcing_gap"},
            "collector_behavior_changed": False,
            "global_scoring_logic_changed": False,
            "thresholds_changed": False,
            "dm_logic_changed": False,
            "evidence_max_age_days_changed": False,
            "full_batch_rerun": True,
            "regressions_on_run_f_passed_set": regressions,
            "frozen_run_timestamp_utc": RUN_TS,
        }

        await Actor.set_value("BATCH_MANIFEST", manifest)
        await Actor.set_value("PASSED", passed)
        await Actor.set_value("RESERVE", reserve)
        await Actor.set_value("OMEGACODE_EVIDENCE_SUBSTITUTION_REPORT", substitution_report)

        Actor.log.info("RUN_G_BATCH_MANIFEST %s", json.dumps(manifest, ensure_ascii=False, sort_keys=True))
        Actor.log.info("RUN_G_SUBSTITUTION_REPORT %s", json.dumps(substitution_report, ensure_ascii=False, sort_keys=True))
        await Actor.set_status_message(
            f"Run G complete: {len(passed)} passed / {len(reserve)} reserve; regressions={len(regressions)}",
            is_terminal=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
