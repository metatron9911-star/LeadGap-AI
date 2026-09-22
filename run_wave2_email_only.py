from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
from apify import Actor

from outreach_v101 import evaluate_batch
from src.enrichment.dm_resolver import DMCandidate, dm_report_entry, resolve_decision_maker
from src.schema.conformance import sanitize_batch

BASELINE = Path("research/catalogfix_wave1_candidates.json")
ENRICHMENTS = Path("research/wave2_dm_enrichment.json")

RUN_ID = os.getenv("RUN_ID", "lg-2026-09-22-wave2-run-a-prime-email-only")
# Keep the frozen DM-only timestamp so evidence-age gates cannot move in this experiment.
RUN_TS = os.getenv("RUN_TIMESTAMP_UTC", "2026-09-22T15:55:00Z")

PROSPEO_URL = "https://api.prospeo.io/enrich-person"
PROSPEO_API_KEY = os.getenv("PROSPEO_API_KEY", "").strip()


def company_host(website: str | None) -> str:
    raw = (website or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return (parsed.hostname or "").lower().strip(".")


def _bool_value(value) -> bool:
    if isinstance(value, dict):
        return bool(value.get("value"))
    return bool(value)


async def prospeo_find_verified_email(
    client: httpx.AsyncClient,
    *,
    full_name: str,
    company_name: str,
    website: str,
    linkedin_url: str | None,
) -> dict:
    payload = {
        "only_verified_email": True,
        "enrich_mobile": False,
        "data": {
            "full_name": full_name,
            "company_name": company_name,
            "company_website": company_host(website),
        },
    }
    if linkedin_url:
        payload["data"]["linkedin_url"] = linkedin_url

    response = None
    data = {}
    for attempt in range(4):
        response = await client.post(
            PROSPEO_URL,
            headers={
                "Content-Type": "application/json",
                "X-KEY": PROSPEO_API_KEY,
            },
            json=payload,
        )

        try:
            data = response.json()
        except Exception:
            return {
                "status": "error",
                "provider": "prospeo",
                "http_status": response.status_code,
                "error_code": "NON_JSON_RESPONSE",
            }

        if response.status_code != 429:
            break

        # Free plan is capped at 1 enrich request/second. Respect that limit
        # instead of turning a transient 429 into a provider failure.
        await asyncio.sleep(1.25 * (attempt + 1))

    if response is None:
        return {"status": "error", "provider": "prospeo", "error_code": "NO_RESPONSE"}

    if response.status_code != 200 or data.get("error"):
        return {
            "status": "not_found" if data.get("error_code") == "NO_MATCH" else "error",
            "provider": "prospeo",
            "http_status": response.status_code,
            "error_code": data.get("error_code"),
        }

    person = data.get("person") or {}
    email_obj = person.get("email") or {}
    email = email_obj.get("email")
    prospeo_status = email_obj.get("status")

    if not email or prospeo_status != "VERIFIED":
        return {
            "status": "not_found",
            "provider": "prospeo",
            "http_status": response.status_code,
            "error_code": None,
            "prospeo_email_status": prospeo_status,
        }

    return {
        "status": "found_verified",
        "provider": "prospeo",
        "email": email,
        "prospeo_email_status": prospeo_status,
        "prospeo_verification_method": email_obj.get("verification_method"),
        "free_enrichment": data.get("free_enrichment"),
    }


def apply_frozen_dm_enrichment(candidates: list[dict], enrichments: list[dict]) -> list[dict]:
    by_company = {row["company_name"]: row for row in enrichments}

    for row in candidates:
        spec = by_company.get(row["company_name"])
        if not spec:
            continue

        dm_candidates = [
            DMCandidate(
                item["name"],
                item["role"],
                item["source"],
                item["source_url"],
                item["confidence"],
            )
            for item in spec.get("candidates", [])
        ]
        resolution = resolve_decision_maker(row["segment"], dm_candidates)
        if resolution.primary is not None:
            row["decision_maker_name"] = resolution.primary.name
            row["decision_maker_role"] = resolution.primary.role
            if resolution.primary.source == "linkedin":
                row["linkedin_url"] = resolution.primary.source_url

    return candidates


async def main() -> None:
    async with Actor:
        if not PROSPEO_API_KEY:
            raise RuntimeError("PROSPEO_API_KEY is not configured")
        candidates = json.loads(BASELINE.read_text(encoding="utf-8"))
        enrichments = json.loads(ENRICHMENTS.read_text(encoding="utf-8"))
        candidates = apply_frozen_dm_enrichment(candidates, enrichments)

        reports: list[dict] = []

        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for row in candidates:
                company = row.get("company_name") or ""
                dm_name = row.get("decision_maker_name")
                website = row.get("website") or ""
                linkedin_url = row.get("linkedin_url")

                report = {
                    "company_name": company,
                    "decision_maker_name": dm_name,
                    "website": website,
                    "finder": "prospeo",
                    "verifier": "prospeo",
                    "verification_status": "not_run",
                    "email_confidence_source": None,
                }

                if not dm_name or not website:
                    report["verification_status"] = "skipped_missing_dm_or_website"
                    reports.append(report)
                    continue

                found = await prospeo_find_verified_email(
                    client,
                    full_name=dm_name,
                    company_name=company,
                    website=website,
                    linkedin_url=linkedin_url,
                )
                report["prospeo"] = found

                if found.get("status") != "found_verified":
                    report["verification_status"] = (
                        "not_found" if found.get("status") == "not_found" else "provider_error"
                    )
                    reports.append(report)
                    continue

                email = found["email"]
                # Prospeo was called with only_verified_email=true and returned
                # email.status=VERIFIED (verification_method is retained in report).
                # Adapt that categorical verified signal to the frozen numeric
                # email policy without changing its >=0.8 threshold.
                confidence = 1.0
                row["work_email"] = email
                row["email_source"] = "other_verifier"
                row["email_confidence"] = confidence
                row["email_confidence_source"] = "other_verifier_score"
                report["email"] = email
                report["verification_status"] = "verified"
                report["email_confidence"] = confidence
                report["email_confidence_source"] = "other_verifier_score"

                reports.append(report)

                # Free Prospeo API is rate-limited to one enrich request/second.
                await asyncio.sleep(1.05)

        passed, reserve, manifest = evaluate_batch(
            candidates,
            run_id=RUN_ID,
            run_timestamp_utc=RUN_TS,
        )
        passed, reserve = sanitize_batch(passed, reserve)

        verified_reports = [r for r in reports if r.get("verification_status") == "verified"]
        passed_by_company = {r.get("company_name"): r for r in passed}
        verified_passed = [
            r for r in verified_reports if r.get("company_name") in passed_by_company
        ]

        manifest["email_verification"] = {
            "status": "complete",
            "finder": "prospeo",
            "verifier": "prospeo",
            "verification_status_counts": {
                status: sum(1 for r in reports if r.get("verification_status") == status)
                for status in (
                    "verified",
                    "rejected",
                    "not_found",
                    "provider_error",
                    "skipped_missing_dm_or_website",
                )
            },
            "verified_all_candidates": len(verified_reports),
            "verified_passed_candidates": len(verified_passed),
            "email_coverage": manifest.get("email_coverage"),
            "email_confidence_source": "other_verifier_score",
            "confidence_adapter": "Prospeo VERIFIED -> 1.0 categorical adapter (not a probability)",
            "frozen_run_timestamp_utc": RUN_TS,
            "dm_rebuilt": False,
            "scoring_changed": False,
            "thresholds_changed": False,
            "evidence_policy_changed": False,
        }

        await Actor.set_value("BATCH_MANIFEST", manifest)
        await Actor.set_value("PASSED", passed)
        await Actor.set_value("RESERVE", reserve)
        await Actor.set_value("EMAIL_VERIFICATION_REPORT", reports)

        Actor.log.info("RUN_A_PRIME_BATCH_MANIFEST %s", json.dumps(manifest, ensure_ascii=False, sort_keys=True))
        Actor.log.info(
            "RUN_A_PRIME_EMAIL_REPORT %s",
            json.dumps(reports, ensure_ascii=False, sort_keys=True),
        )
        await Actor.set_status_message(
            f"Run A' complete: {len(verified_passed)}/{len(passed)} passed leads have confident email",
            is_terminal=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
