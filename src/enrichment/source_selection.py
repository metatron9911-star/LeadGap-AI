from __future__ import annotations

from copy import deepcopy

from outreach_v101 import parse_evidence_date, evidence_is_wave1_eligible
from src.enrichment.date_extraction import collect_date_diagnostic


def _diagnostic_map(evidence_diagnostic: list[dict]) -> dict[str, dict]:
    return {
        row.get("company_name"): row
        for row in evidence_diagnostic
        if row.get("company_name")
    }


async def select_fresh_alternate_evidence(
    candidates: list[dict],
    evidence_diagnostic: list[dict],
    *,
    run_timestamp_utc: str,
) -> list[dict]:
    """
    Collector-level source selection:
    - acts only when the currently selected evidence is undated/ineligible
    - probes candidate_evidence URLs already discovered by prior diagnostics
    - promotes only a defensibly dated alternate that is itself inside the frozen freshness window
    - preserves source provenance explicitly
    - does not alter thresholds, rubric, DM matrix, or source-policy
    """
    diag_by_company = _diagnostic_map(evidence_diagnostic)
    report: list[dict] = []

    for row in candidates:
        company = row.get("company_name")

        current_raw = row.get("evidence_date_raw")
        current_date, _ = parse_evidence_date(current_raw, run_timestamp_utc)
        if evidence_is_wave1_eligible(current_date, run_timestamp_utc):
            report.append({
                "company_name": company,
                "status": "skipped_current_source_already_fresh",
                "evidence_url": row.get("evidence_url"),
                "evidence_date_raw": current_raw,
            })
            continue

        diag = diag_by_company.get(company) or {}
        alt = diag.get("candidate_evidence") or {}
        alt_url = alt.get("evidence_url")

        if not alt_url:
            report.append({
                "company_name": company,
                "status": "no_alternate_candidate_evidence",
            })
            continue

        current_url = row.get("evidence_url")
        if current_url == alt_url:
            report.append({
                "company_name": company,
                "status": "alternate_already_selected",
                "evidence_url": current_url,
            })
            continue

        date_diag = await collect_date_diagnostic(alt_url)
        selected = date_diag.get("defensible_publication_date")
        if not selected or not selected.get("normalized_date"):
            report.append({
                "company_name": company,
                "status": "alternate_not_promoted_no_defensible_date",
                "current_evidence_url": current_url,
                "alternate_evidence_url": alt_url,
                "signals": date_diag.get("signals") or [],
            })
            continue

        alternate_date, _ = parse_evidence_date(
            selected["normalized_date"],
            run_timestamp_utc,
        )
        if not evidence_is_wave1_eligible(alternate_date, run_timestamp_utc):
            report.append({
                "company_name": company,
                "status": "alternate_not_promoted_outside_freshness_window",
                "current_evidence_url": current_url,
                "alternate_evidence_url": alt_url,
                "selected_signal": selected,
            })
            continue

        before = {
            "evidence_url": row.get("evidence_url"),
            "evidence_date_raw": row.get("evidence_date_raw"),
            "evidence_type": row.get("evidence_type"),
            "recent_evidence": row.get("recent_evidence"),
            "evidence_content": row.get("evidence_content"),
            "source_urls": list(row.get("source_urls") or []),
        }

        row["evidence_url"] = alt_url
        row["evidence_date_raw"] = selected["normalized_date"]

        note = alt.get("note") or ""
        if note:
            row["recent_evidence"] = note

        row["evidence_type"] = alt.get("evidence_type") or "press"

        urls = list(row.get("source_urls") or [])
        if alt_url not in urls:
            urls.append(alt_url)
        row["source_urls"] = urls

        row["source_selection_provenance"] = {
            "mode": "collector_alternate_evidence_selection",
            "from_url": current_url,
            "to_url": alt_url,
            "date_signal": deepcopy(selected),
            "date_diagnostic_policy": date_diag.get("policy"),
            "freshness_guard": {
                "run_timestamp_utc": run_timestamp_utc,
                "eligible": True,
            },
        }

        report.append({
            "company_name": company,
            "status": "alternate_promoted",
            "before": before,
            "after": {
                "evidence_url": row.get("evidence_url"),
                "evidence_date_raw": row.get("evidence_date_raw"),
                "evidence_type": row.get("evidence_type"),
                "recent_evidence": row.get("recent_evidence"),
                "source_urls": row.get("source_urls"),
            },
            "selected_signal": selected,
        })

    return report
