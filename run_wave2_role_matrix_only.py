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
from src.enrichment.dm_resolver import DMCandidate, resolve_decision_maker, dm_report_entry
from src.schema.conformance import sanitize_batch

BASELINE = Path("research/catalogfix_wave1_candidates.json")
DM_ENRICHMENTS = Path("research/wave2_dm_enrichment.json")
EVIDENCE_DIAGNOSTIC = Path("research/wave2_run_b_evidence_diagnostic.json")
RUBRIC = Path("research/wave2_run_c_evidence_score_rubric.json")
RUN_E_SPEC = Path("research/wave2_run_e_ctg_evidence_substitution.json")
RUN_F_DM = Path("research/wave2_run_f_7thsense_observed_management.json")

RUN_ID = os.getenv("RUN_ID", "lg-2026-09-22-wave2-run-f-role-matrix-only")
RUN_TS = os.getenv("RUN_TIMESTAMP_UTC", "2026-09-22T15:55:00Z")


def apply_run_f_dm(candidates: list[dict], spec: dict) -> dict:
    target = spec["target_company"]
    observed = [
        DMCandidate(
            item["name"],
            item["role"],
            item["source"],
            item["source_url"],
            item["confidence"],
        )
        for item in spec["observed_management"]
    ]
    for row in candidates:
        if row.get("company_name") != target:
            continue
        resolution = resolve_decision_maker(row["segment"], observed)
        report = dm_report_entry(row["company_name"], row["segment"], resolution)
        if resolution.primary is None:
            raise ValueError("Run F role-matrix change still did not resolve 7thSENSE")
        row["decision_maker_name"] = resolution.primary.name
        row["decision_maker_role"] = resolution.primary.role
        report["rule_change"] = spec["rule_change"]
        report["collector_behavior_changed"] = False
        return report
    raise ValueError(f"{target} not found")


async def main() -> None:
    async with Actor:
        candidates = json.loads(BASELINE.read_text(encoding="utf-8"))
        dm_enrichments = json.loads(DM_ENRICHMENTS.read_text(encoding="utf-8"))
        evidence_diagnostic = json.loads(EVIDENCE_DIAGNOSTIC.read_text(encoding="utf-8"))
        rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
        run_e_spec = json.loads(RUN_E_SPEC.read_text(encoding="utf-8"))
        run_f_spec = json.loads(RUN_F_DM.read_text(encoding="utf-8"))

        # Reconstruct Run E state first.
        apply_frozen_dm(candidates, dm_enrichments)
        apply_evidence_sourcing_only(candidates, evidence_diagnostic)
        apply_score_only(candidates, rubric)
        apply_hook_grounding_only(candidates)
        apply_ctg_substitution(candidates, run_e_spec)

        passed_before = {
            row["company_name"]
            for row in candidates
            if row.get("decision_maker_name") and row.get("decision_maker_role")
        }

        dm_report = apply_run_f_dm(candidates, run_f_spec)

        passed, reserve, manifest = evaluate_batch(
            candidates,
            run_id=RUN_ID,
            run_timestamp_utc=RUN_TS,
        )
        passed, reserve = sanitize_batch(passed, reserve)

        passed_names = {row["company_name"] for row in passed}
        expected_existing_passed = {
            "InteractOne",
            "Graftstudio",
            "Ruby Digital Agency",
            "asioso",
            "Noto Agency",
            "The Commerce Team Global",
        }
        regressions = sorted(expected_existing_passed - passed_names)

        manifest["dm_rule_experiment"] = {
            "status": "complete",
            "mode": "role-matrix-only",
            "affected_segment": "pim_mdm_integrator",
            "rule_change": run_f_spec["rule_change"],
            "target_company": "7thSENSE",
            "collector_behavior_changed": False,
            "thresholds_changed": False,
            "evidence_logic_changed": False,
            "evidence_max_age_days_changed": False,
            "full_batch_rerun": True,
            "regressions_on_run_e_passed_set": regressions,
            "brand_active_expected_unaffected_reason": "different segment; PL/CEE/DE matrix already includes CEO, but no verified current candidate was available",
            "storise_expected_unaffected_reason": "different segment; no public qualifying candidate was available",
        }

        await Actor.set_value("BATCH_MANIFEST", manifest)
        await Actor.set_value("PASSED", passed)
        await Actor.set_value("RESERVE", reserve)
        await Actor.set_value("RUN_F_DM_REPORT", dm_report)

        Actor.log.info("RUN_F_BATCH_MANIFEST %s", json.dumps(manifest, ensure_ascii=False, sort_keys=True))
        Actor.log.info("RUN_F_DM_REPORT %s", json.dumps(dm_report, ensure_ascii=False, sort_keys=True))
        await Actor.set_status_message(
            f"Run F complete: {len(passed)} passed / {len(reserve)} reserve; regressions={len(regressions)}",
            is_terminal=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
