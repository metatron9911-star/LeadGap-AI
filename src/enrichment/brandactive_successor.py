from __future__ import annotations


def apply_brandactive_successor_dm(candidates: list[dict]) -> dict:
    """
    Collector-level successor discovery for Brand Active.

    Provenance:
    1) BrandActive imprint -> current responsible entity: Cloudflight Poland sp. z o.o.
    2) Cloudflight imprint -> Paweł Paszkiewicz, Managing Director / President of Management Board.

    No role-matrix change: 'managing director' is already allowed for PL/CEE/DE SMB agency.
    """
    for row in candidates:
        if row.get("company_name") != "Brand Active":
            continue

        before = {
            "decision_maker_name": row.get("decision_maker_name"),
            "decision_maker_role": row.get("decision_maker_role"),
            "source_urls": list(row.get("source_urls") or []),
        }

        row["decision_maker_name"] = "Paweł Paszkiewicz"
        row["decision_maker_role"] = "Managing Director"

        urls = list(row.get("source_urls") or [])
        for url in (
            "https://brandactive.co/en/imprint",
            "https://www.cloudflight.io/en/imprint/",
            "https://engineering.cloudflight.io/en/blog/brand-active-announcement/",
        ):
            if url not in urls:
                urls.append(url)
        row["source_urls"] = urls

        row["dm_successor_provenance"] = {
            "mode": "first_party_operator_successor_chain",
            "brand_operator_source": "https://brandactive.co/en/imprint",
            "brand_operator_entity": "Cloudflight Poland sp. z o.o.",
            "operator_dm_source": "https://www.cloudflight.io/en/imprint/",
            "decision_maker_name": "Paweł Paszkiewicz",
            "decision_maker_role": "Managing Director",
            "merger_context_source": "https://engineering.cloudflight.io/en/blog/brand-active-announcement/",
        }

        return {
            "company_name": "Brand Active",
            "status": "successor_dm_applied",
            "before": before,
            "after": {
                "decision_maker_name": row["decision_maker_name"],
                "decision_maker_role": row["decision_maker_role"],
                "source_urls": row["source_urls"],
            },
        }

    raise ValueError("Brand Active not found")
