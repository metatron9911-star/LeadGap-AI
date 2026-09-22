from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .dm_role_matrix import role_match_score

ALLOWED_SOURCES = {
    "linkedin", "team_page", "about_page", "kontakt_page",
    "clutch", "local_registry", "speaker_page",
}

SOURCE_PRIORITY = {
    "linkedin": 0,
    "local_registry": 1,
    "team_page": 2,
    "about_page": 3,
    "kontakt_page": 4,
    "clutch": 5,
    "speaker_page": 6,
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


def dm_confidence(segment: str, candidate: DMCandidate) -> float:
    """Deterministic DM confidence = 0.7 role-fit + 0.3 source/evidence confidence."""
    role_score = role_match_score(segment, candidate.role)
    source_conf = max(0.0, min(1.0, float(candidate.confidence)))
    return round(0.7 * role_score + 0.3 * source_conf, 6)


def resolve_decision_maker(segment: str, candidates: Iterable[DMCandidate]) -> DMResolution:
    scored = []
    for candidate in candidates:
        if candidate.source not in ALLOWED_SOURCES:
            continue
        role_score = role_match_score(segment, candidate.role)
        if role_score <= 0:
            continue
        source_conf = max(0.0, min(1.0, float(candidate.confidence)))
        total = dm_confidence(segment, candidate)
        scored.append((
            total,
            role_score,
            source_conf,
            SOURCE_PRIORITY.get(candidate.source, 999),
            candidate.name.casefold(),
            candidate,
        ))

    # Stable tie-break: total score, role match, source confidence, fixed source priority, name.
    scored.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3], item[4]))
    if not scored:
        return DMResolution(None, None, "no role-matched decision-maker found")

    primary = scored[0][5]
    fallback = scored[1][5] if len(scored) > 1 else None
    return DMResolution(primary, fallback, None)


def dm_report_entry(company_name: str, segment: str, resolution: DMResolution) -> dict:
    primary = resolution.primary
    return {
        "company_name": company_name,
        "segment": segment,
        "dm_found": primary is not None,
        "dm_role_match": role_match_score(segment, primary.role if primary else None),
        "dm_source": primary.source if primary else None,
        "dm_confidence": dm_confidence(segment, primary) if primary else None,
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
