from __future__ import annotations


def recompute_source_derived_evidence(
    candidates: list[dict],
    source_selection_report: list[dict],
    spec: dict,
) -> list[dict]:
    """
    Recompute evidence fields invalidated by source mutation.
    Applies only to rows actually promoted by source-selection and only when
    the selected URL matches a frozen target spec.
    """
    promoted = {
        row.get("company_name")
        for row in source_selection_report
        if row.get("status") == "alternate_promoted"
    }
    targets = spec.get("targets") or {}
    report: list[dict] = []

    for row in candidates:
        company = row.get("company_name")
        if company not in promoted:
            continue

        target = targets.get(company)
        if not target:
            report.append({
                "company_name": company,
                "status": "promoted_without_recompute_spec",
            })
            continue

        if row.get("evidence_url") != target.get("evidence_url"):
            report.append({
                "company_name": company,
                "status": "selected_url_mismatch",
                "selected_url": row.get("evidence_url"),
                "expected_url": target.get("evidence_url"),
            })
            continue

        components = target.get("component_scores") or {}
        total = sum(int(v) for v in components.values())
        if total != int(target.get("total") or -1):
            raise ValueError(
                f"Run K score mismatch for {company}: {total} != {target.get('total')}"
            )

        before = {
            "evidence_score": row.get("evidence_score"),
            "evidence_content": row.get("evidence_content"),
            "recent_evidence": row.get("recent_evidence"),
            "evidence_type": row.get("evidence_type"),
            "evidence_date_raw": row.get("evidence_date_raw"),
        }

        row["evidence_score"] = total
        row["evidence_content"] = target["evidence_content"]
        row["recent_evidence"] = target["scoring_basis"]
        row["evidence_type"] = target["evidence_type"]
        row["evidence_date_raw"] = target["evidence_date_raw"]
        row["evidence_score_components"] = components
        row["evidence_score_rubric_version"] = spec["rubric_version"]

        report.append({
            "company_name": company,
            "status": "recomputed",
            "before": before,
            "after": {
                "evidence_score": row.get("evidence_score"),
                "evidence_content": row.get("evidence_content"),
                "recent_evidence": row.get("recent_evidence"),
                "evidence_type": row.get("evidence_type"),
                "evidence_date_raw": row.get("evidence_date_raw"),
                "evidence_score_components": row.get("evidence_score_components"),
                "evidence_score_rubric_version": row.get("evidence_score_rubric_version"),
            },
        })

    return report
