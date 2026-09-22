from __future__ import annotations

VALID = {"valid", "deliverable"}
NON_VERIFIED = {"catch_all", "accept_all", "unknown", "risky", "unverified"}
INVALID = {"invalid", "disposable"}


def normalize_status(value: str | None) -> str:
    raw = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "acceptall": "accept_all",
        "catchall": "catch_all",
        "ok": "valid",
        "good": "valid",
    }
    return aliases.get(raw, raw)


def classify_verification(status: str | None, confidence: float | None) -> str:
    norm = normalize_status(status)
    conf = None if confidence is None else float(confidence)
    if norm in VALID and conf is not None and conf >= 0.8:
        return "verified"
    if norm in INVALID:
        return "invalid"
    return "reserve"


def confidence_bucket(confidence: float | None) -> str:
    if confidence is None:
        return "null"
    x = float(confidence)
    if x >= 0.9:
        return "0.90-1.00"
    if x >= 0.8:
        return "0.80-0.89"
    if x >= 0.5:
        return "0.50-0.79"
    return "0.00-0.49"
