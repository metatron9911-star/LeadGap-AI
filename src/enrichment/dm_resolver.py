from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .dm_role_matrix import role_match_score

ALLOWED_SOURCES = {
    "linkedin", "team_page", "about_page", "kontakt_page",
    "clutch", "local_registry", "speaker_page",
}

@dataclass(frozen=True)
class DMCandidate:
    name: str
    role: str
    source: str
    source_url: str
    confidence: float = 0.0


@dataclass(frozen=True)
class DMResolution:
    primary: DMCandidate | None
    fallback: DMCandidate | None
    missing_reason: str | None


def resolve_decision_maker(segment: str, candidates: Iterable[DMCandidate]) -> DMResolution:
    scored = []
    for candidate in candidates:
        if candidate.source not in ALLOWED_SOURCES:
            continue
        role_score = role_match_score(segment, candidate.role)
        if role_score <= 0:
            continue
        source_conf = max(0.0, min(1.0, float(candidate.confidence)))
        total = 0.7 * role_score + 0.3 * source_conf
        scored.append((total, source_conf, candidate.name.casefold(), candidate))

    scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
    if not scored:
        return DMResolution(None, None, "no role-matched decision-maker found")

    primary = scored[0][3]
    fallback = scored[1][3] if len(scored) > 1 else None
    return DMResolution(primary, fallback, None)


def dm_report_entry(company_name: str, segment: str, resolution: DMResolution) -> dict:
    primary = resolution.primary
    return {
        "company_name": company_name,
        "segment": segment,
        "dm_found": primary is not None,
        "dm_role_match": role_match_score(segment, primary.role if primary else None),
        "dm_source": primary.source if primary else None,
        "dm_confidence": primary.confidence if primary else None,
        "dm_missing_reason": resolution.missing_reason,
        "primary": None if primary is None else {
            "name": primary.name,
            "role": primary.role,
            "source": primary.source,
            "source_url": primary.source_url,
        },
        "fallback": None if resolution.fallback is None else {
            "name": resolution.fallback.name,
            "role": resolution.fallback.role,
            "source": resolution.fallback.source,
            "source_url": resolution.fallback.source_url,
        },
    }
