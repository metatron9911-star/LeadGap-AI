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
from run_wave2_omegacode_grounding_bundle_repair import apply_grounding_bundle_repair
from src.enrichment.source_selection import select_fresh_alternate_evidence
from src.schema.conformance import sanitize_batch

BASELINE = Path("research/catalogfix_wave1_candidates.json")
DM_ENRICHMENTS = Path("research/wave2_dm_enrichment.json")
EVIDENCE_DIAGNOSTIC = Path("research/wave2_run_b_evidence_diagnostic.json")
RUBRIC = Path("research/wave2_run_c_evidence_score_rubric.json")
RUN_E_SPEC = Path("research/wave2_run_e_ctg_evidence_substitution.json")
RUN_F_DM = Path("research/wave2_run_f_7thsense_observed_management.json")
RUN_G_SPEC = Path("research/wave2_run_g_omegacode_source_substitution.json")
RUN_H_SPEC = Path("research/wave2_run_h_omegacode_grounding_bundle_repair.json")

RUN_ID = os.getenv("RUN_ID", "lg-2026-09-23-wave3-run-j-source-selection-full-rerun")
RUN_TS = os.getenv("RUN_TIMESTAMP_UTC", "2026-09-22T15:55:00Z")


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

        # Reconstruct frozen Run H measured state exactly.
        apply_frozen_dm(candidates, dm_enrichments)
        apply_evidence_sourcing_only(candidates, evidence_diagnostic)
        apply_score_only(candidates, rubric)
        apply_hook_grounding_only(candidates)
        apply_ctg_substitution(candidates, run_e_spec)
        apply_run_f_dm(candidates, run_f_spec)
        apply_omegacode_substitution(candidates, run_g_spec)
        apply_grounding_bundle_repair(candidates, run_h_spec)

        # Wave 3 collector improvement: for rows whose selected evidence is stale/undated,
        # probe previously discovered alternate evidence URLs and promote only those with
        # a defensible publication date.
        source_selection_report = await select_fresh_alternate_evidence(
            candidates,
            evidence_diagnostic,
        )

        passed, reserve, manifest = evaluate_batch(
            candidates,
            run_id=RUN_ID,
            run_timestamp_utc=RUN_TS,
        )
        passed, reserve = sanitize_batch(passed, reserve)

        run_h_passed = {
            "InteractOne",
            "Graftstudio",
            "Ruby Digital Agency",
            "asioso",
            "Noto Agency",
            "The Commerce Team Global",
            "7thSENSE",
            "OmegaCode",
        }
        passed_names = {row["company_name"] for row in passed}
        regressions = sorted(run_h_passed - passed_names)
        promotions = sorted(passed_names - run_h_passed)

        manifest["wave3_source_selection"] = {
            "status": "complete",
            "mode": "collector-level-full-rerun",
            "collector_version": "alternate-evidence-source-selection-v1",
            "full_batch_rerun": True,
            "thresholds_changed": False,
            "rubric_changed": False,
            "dm_matrix_changed": False,
            "grounding_rule_changed": False,
            "source_policy_changed": False,
            "regressions_on_run_h_passed_set": regressions,
            "promotions_vs_run_h": promotions,
            "source_selection_report": source_selection_report,
        }

        await Actor.set_value("BATCH_MANIFEST", manifest)
        await Actor.set_value("PASSED", passed)
        await Actor.set_value("RESERVE", reserve)
        await Actor.set_value("SOURCE_SELECTION_REPORT", source_selection_report)

        Actor.log.info("RUN_J_BATCH_MANIFEST %s", json.dumps(manifest, ensure_ascii=False, sort_keys=True))
        Actor.log.info("RUN_J_SOURCE_SELECTION_REPORT %s", json.dumps(source_selection_report, ensure_ascii=False, sort_keys=True))

        promoted_sources = sum(
            1 for row in source_selection_report
            if row.get("status") == "alternate_promoted"
        )
        await Actor.set_status_message(
            f"Run J complete: {len(passed)} passed / {len(reserve)} reserve; "
            f"alternate_promoted={promoted_sources}; regressions={len(regressions)}",
            is_terminal=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
