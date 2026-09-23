from __future__ import annotations

import asyncio
import json
from pathlib import Path

from apify import Actor

from outreach_v101 import parse_evidence_date, evidence_is_wave1_eligible
from src.enrichment.date_extraction import collect_date_diagnostic

CANDIDATES = Path("research/wave3_brandactive_evidence_candidates.json")
RUN_TS = "2026-09-22T15:55:00Z"


async def main() -> None:
    async with Actor:
        spec = json.loads(CANDIDATES.read_text(encoding="utf-8"))
        results = []

        for item in spec["candidates"]:
            diag = await collect_date_diagnostic(item["url"])
            selected = diag.get("defensible_publication_date")
            normalized = selected.get("normalized_date") if selected else None
            parsed, _ = parse_evidence_date(normalized, RUN_TS)
            fresh = evidence_is_wave1_eligible(parsed, RUN_TS)

            results.append({
                "url": item["url"],
                "reason": item["reason"],
                "defensible_publication_date": selected,
                "fresh_inside_90d": fresh,
                "signals": diag.get("signals") or [],
            })

        fresh = [r for r in results if r["fresh_inside_90d"]]
        await Actor.set_value("BRANDACTIVE_EVIDENCE_DISCOVERY", {
            "company_name": spec["company_name"],
            "run_timestamp_utc": RUN_TS,
            "results": results,
            "fresh_candidates": fresh,
            "policy": spec["selection_policy"],
        })
        await Actor.set_status_message(
            f"BrandActive evidence diagnostic complete: fresh={len(fresh)}/{len(results)}",
            is_terminal=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
