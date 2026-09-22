from __future__ import annotations

VALID = {"valid", "deliverable"}
NON_VERIFIED = {"catch_all", "accept_all", "unknown", "risky", "unverified"}
INVALID = {"invalid", "disposable"}

CATEGORICAL_PROVIDERS = {"neverbounce", "zerobounce", "millionverifier"}


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
    """Generic policy used for numeric-score providers."""
    norm = normalize_status(status)
    conf = None if confidence is None else float(confidence)
    if norm in VALID and conf is not None and conf >= 0.8:
        return "verified"
    if norm in INVALID:
        return "invalid"
    return "reserve"


def provider_policy(provider: str, status: str | None, confidence: float | None) -> tuple[str, float | None, str | None]:
    """Return (decision, policy_confidence, confidence_source).

    Hunter uses its numeric score. Categorical providers use a policy confidence
    of 1.0 only for their explicit valid/deliverable class; the source field
    makes clear that this is categorical, not a provider numeric score.
    """
    provider = (provider or "").strip().lower()
    norm = normalize_status(status)

    if provider == "hunter":
        conf = None if confidence is None else float(confidence)
        return classify_verification(norm, conf), conf, "hunter_score" if conf is not None else None

    if provider in CATEGORICAL_PROVIDERS:
        if norm in VALID:
            return "verified", 1.0, f"{provider}_category"
        if norm in INVALID:
            return "invalid", None, f"{provider}_category"
        return "reserve", None, f"{provider}_category"

    return classify_verification(norm, confidence), confidence, "other_verifier_score" if confidence is not None else None


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
