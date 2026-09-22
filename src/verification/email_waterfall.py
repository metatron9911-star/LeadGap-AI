from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from .email_policy import normalize_status, provider_policy

PROVIDER_ENV = {
    "hunter": "HUNTER_API_KEY",
    "neverbounce": "NEVERBOUNCE_API_KEY",
    "zerobounce": "ZEROBOUNCE_API_KEY",
    "millionverifier": "MILLIONVERIFIER_API_KEY",
}

@dataclass(frozen=True)
class VerificationResult:
    provider: str
    email: str
    status: str
    confidence: float | None
    confidence_source: str | None
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
    """Verifier-only waterfall. Missing credentials are reported, never treated as zero coverage."""

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    def configured_providers(self) -> list[str]:
        return [provider for provider, env in PROVIDER_ENV.items() if os.getenv(env)]

    def skipped_providers(self) -> list[str]:
        return [provider for provider, env in PROVIDER_ENV.items() if not os.getenv(env)]

    def verification_status(self) -> str:
        configured = self.configured_providers()
        if not configured:
            return "skipped"
        if len(configured) < len(PROVIDER_ENV):
            return "partial"
        return "complete"

    def _get(self, url: str, params: dict) -> dict:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    def _result(self, provider: str, email: str, raw_status: str | None, raw_confidence: float | None) -> VerificationResult:
        status = normalize_status(raw_status)
        decision, confidence, confidence_source = provider_policy(provider, status, raw_confidence)
        return VerificationResult(provider, email, status, confidence, confidence_source, raw_status, decision)

    def hunter(self, email: str) -> VerificationResult | None:
        key = os.getenv("HUNTER_API_KEY")
        if not key:
            return None
        payload = self._get("https://api.hunter.io/v2/email-verifier", {"email": email, "api_key": key})
        data = payload.get("data") or {}
        return self._result("hunter", email, data.get("status"), _confidence_from_score(data.get("score")))

    def neverbounce(self, email: str) -> VerificationResult | None:
        key = os.getenv("NEVERBOUNCE_API_KEY")
        if not key:
            return None
        payload = self._get("https://api.neverbounce.com/v4.2/single/check", {"key": key, "email": email})
        return self._result("neverbounce", email, payload.get("result"), None)

    def zerobounce(self, email: str) -> VerificationResult | None:
        key = os.getenv("ZEROBOUNCE_API_KEY")
        if not key:
            return None
        base = os.getenv("ZEROBOUNCE_BASE_URL", "https://api-eu.zerobounce.net")
        payload = self._get(f"{base.rstrip('/')}/v2/validate", {"api_key": key, "email": email, "ip_address": ""})
        return self._result("zerobounce", email, payload.get("status"), None)

    def millionverifier(self, email: str) -> VerificationResult | None:
        key = os.getenv("MILLIONVERIFIER_API_KEY")
        if not key:
            return None
        payload = self._get("https://api.millionverifier.com/api/v3", {"api": key, "email": email, "timeout": 10})
        raw = payload.get("result") or payload.get("quality")
        return self._result("millionverifier", email, raw, None)

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

    def run_summary(self, email: str, results: list[VerificationResult]) -> dict:
        return {
            "email": email,
            "verification_status": self.verification_status(),
            "configured_providers": self.configured_providers(),
            "provider_skipped": self.skipped_providers(),
            "results": [result.__dict__ for result in results],
        }
