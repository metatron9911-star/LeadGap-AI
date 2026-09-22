from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

import httpx

from .email_policy import classify_verification, normalize_status

@dataclass(frozen=True)
class VerificationResult:
    provider: str
    email: str
    status: str
    confidence: float | None
    raw_status: str | None
    decision: str


def _confidence_from_score(score) -> float | None:
    if score is None:
        return None
    try:
        x = float(score)
    except (TypeError, ValueError):
        return None
    if x > 1:
        x /= 100.0
    return max(0.0, min(1.0, x))


class EmailWaterfall:
    """Verifier-only waterfall. Missing credentials skip a provider; no confidence is invented."""

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    def _get(self, url: str, params: dict) -> dict:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    def hunter(self, email: str) -> VerificationResult | None:
        key = os.getenv("HUNTER_API_KEY")
        if not key:
            return None
        payload = self._get("https://api.hunter.io/v2/email-verifier", {"email": email, "api_key": key})
        data = payload.get("data") or {}
        raw = data.get("status")
        conf = _confidence_from_score(data.get("score"))
        status = normalize_status(raw)
        return VerificationResult("hunter", email, status, conf, raw, classify_verification(status, conf))

    def neverbounce(self, email: str) -> VerificationResult | None:
        key = os.getenv("NEVERBOUNCE_API_KEY")
        if not key:
            return None
        payload = self._get("https://api.neverbounce.com/v4.2/single/check", {"key": key, "email": email})
        raw = payload.get("result")
        status = normalize_status(raw)
        # NeverBounce exposes a categorical result, not a comparable 0-1 score.
        conf = 1.0 if status == "valid" else None
        return VerificationResult("neverbounce", email, status, conf, raw, classify_verification(status, conf))

    def zerobounce(self, email: str) -> VerificationResult | None:
        key = os.getenv("ZEROBOUNCE_API_KEY")
        if not key:
            return None
        base = os.getenv("ZEROBOUNCE_BASE_URL", "https://api-eu.zerobounce.net")
        payload = self._get(f"{base.rstrip('/')}/v2/validate", {"api_key": key, "email": email, "ip_address": ""})
        raw = payload.get("status")
        status = normalize_status(raw)
        conf = 1.0 if status == "valid" else None
        return VerificationResult("zerobounce", email, status, conf, raw, classify_verification(status, conf))

    def millionverifier(self, email: str) -> VerificationResult | None:
        key = os.getenv("MILLIONVERIFIER_API_KEY")
        if not key:
            return None
        payload = self._get("https://api.millionverifier.com/api/v3", {"api": key, "email": email, "timeout": 10})
        raw = payload.get("result")
        quality = normalize_status(payload.get("quality"))
        status = normalize_status(raw)
        # MillionVerifier does not expose a cross-provider numeric confidence score.
        conf = 1.0 if status == "ok" or quality == "valid" else (1.0 if status == "valid" else None)
        return VerificationResult("millionverifier", email, status, conf, raw, classify_verification(status, conf))

    def verify(self, email: str) -> list[VerificationResult]:
        results: list[VerificationResult] = []
        for method in (self.hunter, self.neverbounce, self.zerobounce, self.millionverifier):
            result = method(email)
            if result is None:
                continue
            results.append(result)
            if result.decision in {"verified", "invalid"}:
                break
        return results
