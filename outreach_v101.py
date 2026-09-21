from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import tldextract

SEGMENT_PRIORITY = {
    "shopify_commerce_agency": 0,
    "pim_mdm_integrator": 1,
    "pl_cee_de_smb_agency": 2,
}

EXCLUSION_PRECEDENCE = [
    "pre_filter",
    "no_decision_maker",
    "no_recent_evidence",
    "low_fit_score",
    "low_evidence_score",
    "language_mismatch",
    "manual_exclude",
]

ALLOWED_EMAIL_SOURCES = {
    "hunter",
    "clearbit",
    "dropcontact",
    "neverbounce",
    "other_verifier",
}

# Use the PSL snapshot bundled with the pinned tldextract package.
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=())


def utc_run_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        text = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_evidence_date(
    raw: str | None,
    run_timestamp_utc: str | datetime,
) -> tuple[str | None, str | None]:
    """Return (YYYY-MM-DD, precision). Never guesses an undated/ambiguous source."""
    if not raw:
        return None, None

    text = raw.strip()
    run_dt = utc_run_timestamp(run_timestamp_utc)

    # Exact ISO date.
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        try:
            parsed = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None, None
        return parsed.isoformat(), "exact"

    # Common relative forms such as "3 weeks ago", "21 days ago", "2 months ago".
    m = re.fullmatch(r"(?i)(\d+)\s+(day|days|week|weeks|month|months)\s+ago", text)
    if m:
        qty = int(m.group(1))
        unit = m.group(2).lower()
        if unit.startswith("day"):
            delta = timedelta(days=qty)
        elif unit.startswith("week"):
            delta = timedelta(weeks=qty)
        else:
            # Operationally deterministic approximation for relative UI labels.
            delta = timedelta(days=30 * qty)
        return (run_dt - delta).date().isoformat(), "approximate"

    # Q1-Q4 is insufficient unless a year is present.
    if re.fullmatch(r"(?i)Q[1-4](?:\s+case\s+study)?", text):
        return None, None

    # Do not infer dates from free text.
    return None, None


def evidence_age_days(evidence_date: str, run_timestamp_utc: str | datetime) -> int:
    run_date = utc_run_timestamp(run_timestamp_utc).date()
    ev = date.fromisoformat(evidence_date)
    return (run_date - ev).days


def evidence_is_wave1_eligible(evidence_date: str | None, run_timestamp_utc: str | datetime) -> bool:
    if not evidence_date:
        return False
    age = evidence_age_days(evidence_date, run_timestamp_utc)
    return 0 <= age <= 90


def normalized_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def load_stopwords(path: str | Path | None = None) -> frozenset[str]:
    if path is None:
        path = Path(__file__).with_name("stopwords_v1.txt")
    return frozenset(
        line.strip().lower()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


STOPWORDS_V1 = load_stopwords()


def token_set(text: str) -> set[str]:
    return {
        tok
        for tok in normalized_text(text).split()
        if tok and tok not in STOPWORDS_V1
    }


def jaccard_similarity(a: str, b: str) -> float:
    left, right = token_set(a), token_set(b)
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def first_line_ok(candidate: str, accepted_lines: Iterable[str], threshold: float = 0.60) -> bool:
    return all(jaccard_similarity(candidate, other) <= threshold for other in accepted_lines)


def registrable_domain(url_or_host: str) -> str:
    raw = (url_or_host or "").strip()
    if not raw:
        return ""
    host = urlparse(raw if "://" in raw else f"https://{raw}").hostname or ""
    host = host.lower().strip(".")
    if not host:
        return ""
    ext = _EXTRACT(host)
    if not ext.domain or not ext.suffix:
        return host
    return f"{ext.domain}.{ext.suffix}"


def choose_primary_segment(segment_scores: dict[str, int]) -> tuple[str, list[str]]:
    if not segment_scores:
        raise ValueError("segment_scores must not be empty")
    ranked = sorted(
        segment_scores.items(),
        key=lambda kv: (-kv[1], SEGMENT_PRIORITY.get(kv[0], 999), kv[0]),
    )
    primary = ranked[0][0]
    secondary = [seg for seg, _ in ranked[1:]]
    return primary, secondary


def dedupe_companies(candidates: list[dict]) -> list[dict]:
    """One passed company per registrable domain; preserve secondary segment signals."""
    by_domain: dict[str, list[dict]] = {}
    for c in candidates:
        key = registrable_domain(c.get("website", ""))
        if not key:
            key = f"__missing__:{c.get('company_name','')}"
        by_domain.setdefault(key, []).append(c)

    out: list[dict] = []
    for key in sorted(by_domain):
        group = by_domain[key]
        segment_scores: dict[str, int] = {}
        for c in group:
            seg = c.get("segment")
            fit = int(c.get("fit_score") or 0)
            if seg:
                segment_scores[seg] = max(segment_scores.get(seg, -1), fit)

        primary, secondary = choose_primary_segment(segment_scores)
        primary_rows = [c for c in group if c.get("segment") == primary]
        winner = sorted(
            primary_rows,
            key=lambda c: (
                -int(c.get("fit_score") or 0),
                -int(c.get("evidence_score") or 0),
                str(c.get("company_name") or "").lower(),
            ),
        )[0].copy()
        winner["segment"] = primary
        winner["secondary_segments"] = secondary
        winner["canonical_domain"] = key
        out.append(winner)
    return out


def apply_email_policy(
    work_email: str | None,
    email_source: str | None,
    email_confidence: float | None,
) -> tuple[str | None, float | None, str]:
    source = (email_source or "").lower() or None
    confidence = float(email_confidence) if email_confidence is not None else None
    if (
        work_email
        and source in ALLOWED_EMAIL_SOURCES
        and confidence is not None
        and confidence >= 0.8
    ):
        return work_email, confidence, "email"
    return None, None, "linkedin_or_site_form"


def determine_exclusion_stage(flags: dict[str, bool]) -> str | None:
    for stage in EXCLUSION_PRECEDENCE:
        if flags.get(stage):
            return stage
    return None


def priority_score(fit_score: int, evidence_score: int) -> int:
    return math.floor(0.5 * fit_score + 0.5 * evidence_score)


def priority_sort_key(lead: dict) -> tuple:
    return (
        -int(lead.get("priority_score") or 0),
        -int(lead.get("evidence_score") or 0),
        -int(lead.get("fit_score") or 0),
        str(lead.get("company_name") or "").casefold(),
    )


def hook_grounding_ok(hook_grounding: list[dict], evidence_content: str) -> bool:
    """All declared hook claims must be present in retrieved evidence content."""
    haystack = normalized_text(evidence_content)
    if not hook_grounding:
        return False
    for item in hook_grounding:
        claim = normalized_text(str(item.get("claim") or ""))
        if not claim or claim not in haystack:
            return False
    return True


def primary_source_mix(leads: list[dict]) -> dict[str, int]:
    keys = ["linkedin", "clutch", "shopify_partners", "apify_store", "google", "referral", "other"]
    counts = {k: 0 for k in keys}
    for lead in leads:
        source = lead.get("primary_discovery_source")
        if source not in counts:
            source = "other"
        counts[source] += 1
    return counts


def build_manifest(
    *,
    run_id: str,
    run_timestamp_utc: str | datetime,
    passed_leads: list[dict],
    reserve_leads: list[dict],
    candidates_raw: int,
    passed_pre_filter: int,
) -> dict:
    ts = utc_run_timestamp(run_timestamp_utc).isoformat().replace("+00:00", "Z")
    hist = {stage: 0 for stage in EXCLUSION_PRECEDENCE}
    for lead in reserve_leads:
        stage = lead.get("exclude_stage")
        if stage in hist:
            hist[stage] += 1

    source_mix = primary_source_mix(passed_leads)
    if sum(source_mix.values()) != len(passed_leads):
        raise AssertionError("source_mix invariant failed")

    email_ok = sum(1 for x in passed_leads if x.get("work_email") and (x.get("email_confidence") or 0) >= 0.8)

    return {
        "run_id": run_id,
        "date": utc_run_timestamp(run_timestamp_utc).date().isoformat(),
        "run_timestamp_utc": ts,
        "target_segments": {
            "shopify_commerce_agency": 4,
            "pim_mdm_integrator": 4,
            "pl_cee_de_smb_agency": 4,
        },
        "thresholds_applied": {
            "fit_score_min": 75,
            "evidence_score_min": 70,
            "evidence_max_age_days": 90,
            "email_confidence_min": 0.8,
            "language_ok": "en",
            "priority_formula": "floor(0.5*fit + 0.5*evidence)",
        },
        "exclusion_precedence_applied": EXCLUSION_PRECEDENCE,
        "totals": {
            "candidates_raw": candidates_raw,
            "passed_pre_filter": passed_pre_filter,
            "passed_thresholds": len(passed_leads),
            "reserve_count": len(reserve_leads),
        },
        "segment_distribution_passed": {
            seg: sum(1 for x in passed_leads if x.get("segment") == seg)
            for seg in (
                "shopify_commerce_agency",
                "pim_mdm_integrator",
                "pl_cee_de_smb_agency",
            )
        },
        "exclusion_reasons_histogram": hist,
        "source_mix": source_mix,
        "email_coverage": {
            "with_confident_email": email_ok,
            "without_email": len(passed_leads) - email_ok,
        },
        "notes": "",
    }


def evaluate_candidate(candidate: dict, run_timestamp_utc: str | datetime) -> tuple[str, dict]:
    """Evaluate one research candidate deterministically into main or reserve."""
    record = candidate.copy()
    signal_count = int(record.get("signal_count") or 0)
    decision_maker_ok = bool(record.get("decision_maker_name") and record.get("decision_maker_role"))

    parsed_date, precision = parse_evidence_date(
        record.get("evidence_date_raw"),
        run_timestamp_utc,
    )
    if parsed_date:
        record["evidence_date"] = parsed_date
        record["evidence_date_precision"] = precision

    flags = {
        "pre_filter": signal_count < 2,
        "no_decision_maker": not decision_maker_ok,
        "no_recent_evidence": not evidence_is_wave1_eligible(parsed_date, run_timestamp_utc),
        "low_fit_score": int(record.get("fit_score") or 0) < 75,
        "low_evidence_score": int(record.get("evidence_score") or 0) < 70,
        "language_mismatch": record.get("language_ok") != "en",
        "manual_exclude": bool(record.get("manual_exclude")),
    }
    stage = determine_exclusion_stage(flags)

    if stage is None:
        email, conf, channel = apply_email_policy(
            record.get("work_email"),
            record.get("email_source"),
            record.get("email_confidence"),
        )
        record["work_email"] = email
        record["email_confidence"] = conf
        record["outreach_channel"] = channel
        record["priority_score"] = priority_score(
            int(record.get("fit_score") or 0),
            int(record.get("evidence_score") or 0),
        )
        return "passed", record

    reserve = {
        "company_name": record.get("company_name") or "",
        "website": record.get("website") or "",
        "country": record.get("country"),
        "segment": record.get("segment") or "unknown",
        "exclude_stage": stage,
        "exclude_reason": record.get("exclude_reason")
        or {
            "pre_filter": "fewer than two qualifying ICP signals",
            "no_decision_maker": "no qualifying decision-maker verified",
            "no_recent_evidence": "no defensible evidence date inside the 90-day UTC window",
            "low_fit_score": "fit_score below 75",
            "low_evidence_score": "evidence_score below 70",
            "language_mismatch": "first-wave language is not English",
            "manual_exclude": record.get("manual_exclude_reason") or "manual exclusion",
        }[stage],
        "fit_score": record.get("fit_score"),
        "evidence_score": record.get("evidence_score"),
        "recent_evidence": record.get("recent_evidence"),
        "evidence_type": record.get("evidence_type"),
        "evidence_url": record.get("evidence_url"),
        "evidence_date": parsed_date,
        "decision_maker_name": record.get("decision_maker_name"),
        "decision_maker_role": record.get("decision_maker_role"),
        "source_urls": record.get("source_urls") or [],
    }
    return "reserve", reserve


def evaluate_batch(candidates: list[dict], *, run_id: str, run_timestamp_utc: str | datetime) -> tuple[list[dict], list[dict], dict]:
    """Evaluate, dedupe and manifest a research batch."""
    passed_raw: list[dict] = []
    reserve: list[dict] = []
    passed_pre_filter = 0

    for candidate in candidates:
        if int(candidate.get("signal_count") or 0) >= 2:
            passed_pre_filter += 1
        bucket, row = evaluate_candidate(candidate, run_timestamp_utc)
        if bucket == "passed":
            passed_raw.append(row)
        else:
            reserve.append(row)

    passed = dedupe_companies(passed_raw)
    passed.sort(key=priority_sort_key)

    manifest = build_manifest(
        run_id=run_id,
        run_timestamp_utc=run_timestamp_utc,
        passed_leads=passed,
        reserve_leads=reserve,
        candidates_raw=len(candidates),
        passed_pre_filter=passed_pre_filter,
    )
    return passed, reserve, manifest
