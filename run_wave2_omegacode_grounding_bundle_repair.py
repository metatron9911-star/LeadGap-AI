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
from run_wave2_omegacode_source_substitution_only import apply_omegacode_substitution
from src.schema.conformance import sanitize_batch

BASELINE = Path("research/catalogfix_wave1_candidates.json")
DM_ENRICHMENTS = Path("research/wave2_dm_enrichment.json")
EVIDENCE_DIAGNOSTIC = Path("research/wave2_run_b_evidence_diagnostic.json")
RUBRIC = Path("research/wave2_run_c_evidence_score_rubric.json")
RUN_E_SPEC = Path("research/wave2_run_e_ctg_evidence_substitution.json")
RUN_F_DM = Path("research/wave2_run_f_7thsense_observed_management.json")
RUN_G_SPEC = Path("research/wave2_run_g_omegacode_source_substitution.json")
RUN_H_SPEC = Path("research/wave2_run_h_omegacode_grounding_bundle_repair.json")

RUN_ID = os.getenv("RUN_ID", "lg-2026-09-22-wave2-run-h-omegacode-grounding-bundle-repair")
RUN_TS = os.getenv("RUN_TIMESTAMP_UTC", "2026-09-22T15:55:00Z")


def apply_grounding_bundle_repair(candidates: list[dict], spec: dict) -> dict:
    target = spec["target_company"]
    support = spec["grounding_support_item"]
    for row in candidates:
        if row.get("company_name") != target:
            continue

        before = {
            "evidence_content": row.get("evidence_content"),
            "hook_grounding": row.get("hook_grounding"),
            "source_urls": list(row.get("source_urls") or []),
        }

        support_text = (
            "OmegaCode enterprise ecommerce capability page: "
            "PIM, MDM, ESB & global data architecture; "
            "Master Data Management (MDM/PIM) is part of the managed enterprise capability set."
        )
        primary_text = row.get("evidence_content") or ""
        row["evidence_content"] = primary_text.rstrip() + "\n\n" + support_text

        urls = list(row.get("source_urls") or [])
        if support["evidence_url"] not in urls:
            urls.append(support["evidence_url"])
        row["source_urls"] = urls

        row["grounding_evidence_items"] = [
            {
                "evidence_type": spec["primary_evidence"]["evidence_type"],
                "evidence_url": spec["primary_evidence"]["evidence_url"],
                "evidence_date_raw": spec["primary_evidence"]["evidence_date_raw"],
                "role": spec["primary_evidence"]["role"],
            },
            {
                "evidence_type": support["evidence_type"],
                "evidence_url": support["evidence_url"],
                "role": support["role"],
                "supported_claims": support["supported_claims"],
            },
        ]

        row["hook_grounding"] = [
            {"claim": "PIM", "grounded_in": spec["primary_evidence"]["evidence_url"]},
            {"claim": "MDM", "grounded_in": support["evidence_url"]},
        ]

        return {
            "company_name": target,
            "diagnostic": spec["diagnostic"],
            "mode": spec["mode"],
            "before": before,
            "after": {
                "evidence_content": row["evidence_content"],
                "hook_grounding": row["hook_grounding"],
                "source_urls": row["source_urls"],
                "grounding_evidence_items": row["grounding_evidence_items"],
            },
            "structural_model_change": False,
            "global_grounding_rule_changed": False,
            "collector_behavior_changed": False,
            "thresholds_changed": False,
            "dm_logic_changed": False,
            "evidence_scoring_changed": False,
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
        run_h_spec = json.loads(RUN_H_SPEC.read_text(encoding="utf-8"))

        # Reconstruct Run G state exactly.
        apply_frozen_dm(candidates, dm_enrichments)
        apply_evidence_sourcing_only(candidates, evidence_diagnostic)
        apply_score_only(candidates, rubric)
        apply_hook_grounding_only(candidates)
        apply_ctg_substitution(candidates, run_e_spec)
        apply_run_f_dm(candidates, run_f_spec)
        apply_omegacode_substitution(candidates, run_g_spec)

        repair_report = apply_grounding_bundle_repair(candidates, run_h_spec)

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

        manifest["grounding_repair"] = {
            "status": "complete",
            "mode": "grounding-bundle-repair-only",
            "applied_companies": ["OmegaCode"],
            "diagnostics": {"OmegaCode": "source_bundle_mismatch"},
            "evaluator_model": "single evidence_content string",
            "structural_model_change": False,
            "global_grounding_rule_changed": False,
            "collector_behavior_changed": False,
            "thresholds_changed": False,
            "dm_logic_changed": False,
            "evidence_scoring_changed": False,
            "full_batch_rerun": True,
            "regressions_on_run_g_passed_set": regressions,
        }

        await Actor.set_value("BATCH_MANIFEST", manifest)
        await Actor.set_value("PASSED", passed)
        await Actor.set_value("RESERVE", reserve)
        await Actor.set_value("OMEGACODE_GROUNDING_REPAIR_REPORT", repair_report)

        Actor.log.info("RUN_H_BATCH_MANIFEST %s", json.dumps(manifest, ensure_ascii=False, sort_keys=True))
        Actor.log.info("RUN_H_REPAIR_REPORT %s", json.dumps(repair_report, ensure_ascii=False, sort_keys=True))
        await Actor.set_status_message(
            f"Run H complete: {len(passed)} passed / {len(reserve)} reserve; regressions={len(regressions)}",
            is_terminal=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
