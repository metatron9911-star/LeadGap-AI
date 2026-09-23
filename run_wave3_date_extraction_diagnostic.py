from __future__ import annotations

import asyncio
import json
import os

from apify import Actor

from src.enrichment.date_extraction import collect_date_diagnostic

TARGET_URL = os.getenv(
    "TARGET_URL",
    "https://kkdigital.pl/wdrozenie-shopify-dla-hekiertmeble-pl-i-wsparcie-dalszej-ekspansji/",
)


async def main() -> None:
    async with Actor:
        report = await collect_date_diagnostic(TARGET_URL)
        await Actor.set_value("DATE_EXTRACTION_DIAGNOSTIC", report)
        Actor.log.info("DATE_EXTRACTION_DIAGNOSTIC %s", json.dumps(report, ensure_ascii=False, sort_keys=True))

        selected = report.get("defensible_publication_date")
        if selected:
            await Actor.set_status_message(
                f"Date diagnostic complete: defensible publication date {selected.get('normalized_date')} via {selected.get('kind')}",
                is_terminal=True,
            )
        else:
            await Actor.set_status_message(
                "Date diagnostic complete: no defensible publication date extracted",
                is_terminal=True,
            )


if __name__ == "__main__":
    asyncio.run(main())
