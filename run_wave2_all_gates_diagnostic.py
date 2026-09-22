from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from apify import Actor

from outreach_v101 import (
    EXCLUSION_PRECEDENCE,
    evidence_is_wave1_eligible,
    hook_grounding_ok,
    parse_evidence_date,
)
from run_wave2_evidence_only import apply_evidence_sourcing_only, apply_frozen_dm
from run_wave2_evidence_score_only import apply_score_only
from run_wave2_hook_grounding_only import apply_hook_grounding_only

BASELINE = Path("research/catalogfix_wave1_candidates.json")
DM_ENRICHMENTS = Path("research/wave2_dm_enrichment.json")
EVIDENCE_DIAGNOSTIC = Path("research/wave2_run_b_evidence_diagnostic.json")
RUBRIC = Path("research/wave2_run_c_evidence_score_rubric.json")

RUN_ID = os.getenv("RUN_ID", "lg-2026-09-22-wave2-all-gates-diagnostic")
RUN_TS = os.getenv("RUN_TIMESTAMP_UTC", "2026-09-22T15:55:00Z")


def all_gate_flags(record: dict) -> dict[str, bool]:
    signal_count = int(record.get("signal_count") or 0)
    decision_maker_ok = bool(record.get("decision_maker_name") and record.get("decision_maker_role"))
    parsed_date, _ = parse_evidence_date(record.get("evidence_date_raw"), RUN_TS)

    grounding_failed = False
    if record.get("personalization_hook") or record.get("hook_grounding"):
        grounding_failed = not hook_grounding_ok(
            record.get("hook_grounding") or [],
            record.get("evidence_content") or "",
        )

    return {
        "pre_filter": signal_count < 2,
        "no_decision_maker": not decision_maker_ok,
        "no_recent_evidence": not evidence_is_wave1_eligible(parsed_date, RUN_TS),
        "low_fit_score": int(record.get("fit_score") or 0) < 75,
        "low_evidence_score": int(record.get("evidence_score") or 0) < 70,
        "language_mismatch": record.get("language_ok") != "en",
        "manual_exclude": bool(record.get("manual_exclude")) or grounding_failed,
    }


def diagnostic_row(record: dict) -> dict:
    flags = all_gate_flags(record)
    failing = [stage for stage in EXCLUSION_PRECEDENCE if flags[stage]]
    return {
        "company_name": record.get("company_name"),
        "segment": record.get("segment"),
        "all_failing_gates": failing,
        "first_blocking_gate": failing[0] if failing else None,
        "multi_gate": len(failing) > 1,
        "gate_count": len(failing),
        "manual_exclude_reason": (
            "hook_grounding_failed"
            if flags["manual_exclude"]
            and not bool(record.get("manual_exclude"))
            else record.get("manual_exclude_reason")
        ),
        "fit_score": record.get("fit_score"),
        "evidence_score": record.get("evidence_score"),
        "evidence_date_raw": record.get("evidence_date_raw"),
        "decision_maker_name": record.get("decision_maker_name"),
        "decision_maker_role": record.get("decision_maker_role"),
    }


async def main() -> None:
    async with Actor:
        candidates = json.loads(BASELINE.read_text(encoding="utf-8"))
        dm_enrichments = json.loads(DM_ENRICHMENTS.read_text(encoding="utf-8"))
        evidence_diagnostic = json.loads(EVIDENCE_DIAGNOSTIC.read_text(encoding="utf-8"))
        rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))

        # Reconstruct exact Run D candidate state.
        apply_frozen_dm(candidates, dm_enrichments)
        apply_evidence_sourcing_only(candidates, evidence_diagnostic)
        apply_score_only(candidates, rubric)
        apply_hook_grounding_only(candidates)

        report = [diagnostic_row(row) for row in candidates]
        reserve = [row for row in report if row["first_blocking_gate"] is not None]
        passed = [row for row in report if row["first_blocking_gate"] is None]

        summary = {
            "run_id": RUN_ID,
            "artifact_type": "diagnostic",
            "reconstruction_basis": "Run D deterministic state",
            "run_timestamp_utc": RUN_TS,
            "candidates": len(report),
            "passed": len(passed),
            "reserve": len(reserve),
            "multi_gate_reserve_count": sum(1 for row in reserve if row["multi_gate"]),
            "single_gate_reserve_count": sum(1 for row in reserve if not row["multi_gate"]),
            "first_blocking_histogram": {
                stage: sum(1 for row in reserve if row["first_blocking_gate"] == stage)
                for stage in EXCLUSION_PRECEDENCE
            },
            "all_failing_gate_counts": {
                stage: sum(1 for row in reserve if stage in row["all_failing_gates"])
                for stage in EXCLUSION_PRECEDENCE
            },
        }

        await Actor.set_value("ALL_GATES_REPORT", report)
        await Actor.set_value("ALL_GATES_RESERVE", reserve)
        await Actor.set_value("ALL_GATES_SUMMARY", summary)

        Actor.log.info("ALL_GATES_SUMMARY %s", json.dumps(summary, ensure_ascii=False, sort_keys=True))
        await Actor.set_status_message(
            f"All-gates diagnostic complete: {len(passed)} passed / {len(reserve)} reserve; "
            f"{summary['multi_gate_reserve_count']} multi-gate reserve",
            is_terminal=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
