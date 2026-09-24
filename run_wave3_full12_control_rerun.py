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
from run_wave3_kkdigital_hook_grounding_repair import apply_kk_hook_repair
from src.enrichment.source_selection import select_fresh_alternate_evidence
from src.enrichment.derived_state import recompute_source_derived_evidence
from src.enrichment.brandactive_successor import apply_brandactive_successor_dm
from src.schema.conformance import sanitize_batch

BASELINE = Path("research/catalogfix_wave1_candidates.json")
DM_ENRICHMENTS = Path("research/wave2_dm_enrichment.json")
EVIDENCE_DIAGNOSTIC = Path("research/wave2_run_b_evidence_diagnostic.json")
RUBRIC = Path("research/wave2_run_c_evidence_score_rubric.json")
RUN_E_SPEC = Path("research/wave2_run_e_ctg_evidence_substitution.json")
RUN_F_DM = Path("research/wave2_run_f_7thsense_observed_management.json")
RUN_G_SPEC = Path("research/wave2_run_g_omegacode_source_substitution.json")
RUN_H_SPEC = Path("research/wave2_run_h_omegacode_grounding_bundle_repair.json")
RUN_K_SPEC = Path("research/wave3_run_k_derived_state_spec.json")
RUN_L_SPEC = Path("research/wave3_run_l_kkdigital_hook_grounding_spec.json")

BRANDACTIVE_RESULT = Path("research/wave3_brandactive_expanded_scope_result.observed.json")
EPOINT_RESULT = Path("research/wave3_epoint_expanded_scope_result.json")
STORISE_RESULT = Path("research/storise_source_policy_resolution.json")

RUN_ID = os.getenv("RUN_ID", "lg-2026-09-24-wave3-full12-control-rerun-v1")
RUN_TS = os.getenv("RUN_TIMESTAMP_UTC", "2026-09-24T20:00:00Z")

BASELINE_PASSED = {
    "InteractOne", "Graftstudio", "Ruby Digital Agency", "asioso",
    "Noto Agency", "The Commerce Team Global", "7thSENSE",
    "OmegaCode", "KK Digital",
}

VALID_DISCOVERY_TERMINALS = {
    "recent_evidence_found",
    "no_recent_evidence_found_in_expanded_scope",
}
VALID_POLICY_TERMINALS = {
    "resolved",
    "insufficient_primary_source",
    "unresolved_conflict",
}


def _load_required(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"PRECONDITION_MISSING: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def preflight() -> dict:
    brandactive = _load_required(BRANDACTIVE_RESULT)
    epoint = _load_required(EPOINT_RESULT)
    storise = _load_required(STORISE_RESULT)

    ba_status = brandactive.get("terminal_status")
    ep_status = epoint.get("terminal_status")
    st_status = storise.get("resolution_status")

    errors = []
    if ba_status not in VALID_DISCOVERY_TERMINALS:
        errors.append(f"Brand Active non-terminal: {ba_status}")
    if ep_status not in VALID_DISCOVERY_TERMINALS:
        errors.append(f"e-point non-terminal: {ep_status}")
    if st_status not in VALID_POLICY_TERMINALS:
        errors.append(f"Storise non-terminal: {st_status}")

    if errors:
        raise RuntimeError("PRECONDITION_FAILED: " + "; ".join(errors))

    return {
        "brandactive": brandactive,
        "epoint": epoint,
        "storise": storise,
    }


async def main() -> None:
    async with Actor:
        try:
            tails = preflight()
        except Exception as exc:
            await Actor.set_value("FULL12_PREFLIGHT", {
                "status": "blocked",
                "reason": str(exc),
                "required_artifacts": [
                    str(BRANDACTIVE_RESULT),
                    str(EPOINT_RESULT),
                    str(STORISE_RESULT),
                ],
            })
            await Actor.set_status_message(
                f"Full 12 blocked: {exc}",
                is_terminal=True,
            )
            return

        candidates = json.loads(BASELINE.read_text(encoding="utf-8"))
        dm_enrichments = json.loads(DM_ENRICHMENTS.read_text(encoding="utf-8"))
        evidence_diagnostic = json.loads(EVIDENCE_DIAGNOSTIC.read_text(encoding="utf-8"))
        rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
        run_e_spec = json.loads(RUN_E_SPEC.read_text(encoding="utf-8"))
        run_f_spec = json.loads(RUN_F_DM.read_text(encoding="utf-8"))
        run_g_spec = json.loads(RUN_G_SPEC.read_text(encoding="utf-8"))
        run_h_spec = json.loads(RUN_H_SPEC.read_text(encoding="utf-8"))
        run_k_spec = json.loads(RUN_K_SPEC.read_text(encoding="utf-8"))
        run_l_spec = json.loads(RUN_L_SPEC.read_text(encoding="utf-8"))

        # Reconstruct the stable 9/12 state through Run M/L/K/H lineage.
        apply_frozen_dm(candidates, dm_enrichments)
        apply_evidence_sourcing_only(candidates, evidence_diagnostic)
        apply_score_only(candidates, rubric)
        apply_hook_grounding_only(candidates)
        apply_ctg_substitution(candidates, run_e_spec)
        apply_run_f_dm(candidates, run_f_spec)
        apply_omegacode_substitution(candidates, run_g_spec)
        apply_grounding_bundle_repair(candidates, run_h_spec)

        source_selection_report = await select_fresh_alternate_evidence(
            candidates, evidence_diagnostic, run_timestamp_utc=RUN_TS,
        )
        recompute_source_derived_evidence(candidates, source_selection_report, run_k_spec)
        apply_kk_hook_repair(candidates, run_l_spec)
        apply_brandactive_successor_dm(candidates)

        # Tail artifacts are control inputs only. This control rerun does NOT
        # silently mutate candidate evidence or policy state from summaries.
        # Any future application of fresh e-point evidence or resolved Storise
        # provenance must be represented as an explicit prior experiment.
        passed, reserve, manifest = evaluate_batch(
            candidates,
            run_id=RUN_ID,
            run_timestamp_utc=RUN_TS,
        )
        passed, reserve = sanitize_batch(passed, reserve)

        passed_names = {row["company_name"] for row in passed}
        regressions = sorted(BASELINE_PASSED - passed_names)
        promotions = sorted(passed_names - BASELINE_PASSED)

        per_record = []
        current_by_name = {
            row["company_name"]: ("passed", row) for row in passed
        }
        current_by_name.update({
            row["company_name"]: ("reserve", row) for row in reserve
        })

        for name in sorted(current_by_name):
            bucket, row = current_by_name[name]
            baseline_status = "passed" if name in BASELINE_PASSED else "reserve"
            current_status = "passed" if bucket == "passed" else row.get("exclude_stage")
            changed = (baseline_status == "passed" and bucket != "passed") or (
                baseline_status == "reserve" and current_status != "reserve"
            )
            per_record.append({
                "company_name": name,
                "baseline_status": baseline_status,
                "current_status": current_status,
                "changed": changed,
                "change_reason": (
                    "unexpected"
                    if name in BASELINE_PASSED and bucket != "passed"
                    else "by_design"
                    if name in {"Brand Active", "e-point", "Storise"} and changed
                    else "stable"
                ),
            })

        unexpected = [
            row for row in per_record if row["change_reason"] == "unexpected"
        ]

        traffic_light = "green"
        if unexpected or regressions:
            traffic_light = "red"

        manifest["wave3_full12_control"] = {
            "status": "complete",
            "baseline_passed_count": 9,
            "baseline_passed_set": sorted(BASELINE_PASSED),
            "tails": {
                "brandactive_terminal_status": tails["brandactive"].get("terminal_status"),
                "epoint_terminal_status": tails["epoint"].get("terminal_status"),
                "storise_resolution_status": tails["storise"].get("resolution_status"),
            },
            "stable_passed_regressions": regressions,
            "promotions_vs_9_12_baseline": promotions,
            "per_record_diff": per_record,
            "traffic_light": traffic_light,
            "control_note": (
                "Tail summaries are not applied as candidate mutations in this control rerun. "
                "Only explicit prior experiment code may change candidate state."
            ),
        }

        await Actor.set_value("FULL12_PREFLIGHT", {"status": "passed", "tails": tails})
        await Actor.set_value("BATCH_MANIFEST", manifest)
        await Actor.set_value("PASSED", passed)
        await Actor.set_value("RESERVE", reserve)
        await Actor.set_value("FULL12_DIFF", per_record)

        await Actor.set_status_message(
            f"Full 12 control complete: {len(passed)} passed / {len(reserve)} reserve; "
            f"regressions={len(regressions)}; traffic_light={traffic_light}",
            is_terminal=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
