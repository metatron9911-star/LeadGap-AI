from __future__ import annotations

from collections import Counter

from .email_policy import confidence_bucket


def email_metrics(results: list[dict]) -> dict:
    found = sum(1 for row in results if row.get("email"))
    verified = sum(1 for row in results if row.get("decision") == "verified")
    catch_all = sum(1 for row in results if row.get("status") in {"catch_all", "accept_all"})
    providers = Counter(row.get("provider") for row in results if row.get("provider"))
    dist = Counter(confidence_bucket(row.get("confidence")) for row in results)
    return {
        "emails_found": found,
        "emails_verified": verified,
        "catch_all_rate": (catch_all / found) if found else 0.0,
        "email_confidence_dist": dict(sorted(dist.items())),
        "email_provider": dict(sorted(providers.items())),
    }


def dm_metrics(rows: list[dict]) -> dict:
    total = len(rows)
    found = sum(1 for row in rows if row.get("dm_found"))
    sources = Counter(row.get("dm_source") for row in rows if row.get("dm_source"))
    role_matches = [float(row.get("dm_role_match") or 0) for row in rows if row.get("dm_found")]
    confidences = [float(row.get("dm_confidence") or 0) for row in rows if row.get("dm_found")]
    missing = Counter(row.get("dm_missing_reason") for row in rows if row.get("dm_missing_reason"))
    return {
        "dm_coverage": (found / total) if total else 0.0,
        "dm_role_match": (sum(role_matches) / len(role_matches)) if role_matches else 0.0,
        "dm_source": dict(sorted(sources.items())),
        "dm_confidence": (sum(confidences) / len(confidences)) if confidences else 0.0,
        "dm_missing_reason": dict(sorted(missing.items())),
    }
