from __future__ import annotations

import os

from src.enrichment.dm_resolver import DMCandidate, dm_report_entry, resolve_decision_maker
from src.enrichment.dm_role_matrix import role_match_score
from src.schema.conformance import sanitize_and_validate_main, sanitize_and_validate_reserve
from src.verification.email_policy import classify_verification, normalize_status, provider_policy
from src.verification.email_waterfall import EmailWaterfall
from src.verification.manifest_metrics import dm_metrics, email_metrics


def test_role_matrix():
    assert role_match_score("shopify_commerce_agency", "Founder & CEO") > 0
    assert role_match_score("pim_mdm_integrator", "Solution Architect") > 0
    assert role_match_score("pl_cee_de_smb_agency", "Head of Client Services") > 0
    assert role_match_score("pim_mdm_integrator", "SEO Manager") == 0


def test_dm_resolution_primary_and_fallback():
    resolution = resolve_decision_maker(
        "pim_mdm_integrator",
        [
            DMCandidate("A Person", "Solution Architect", "linkedin", "https://linkedin.com/in/a", 0.90),
            DMCandidate("B Person", "Managing Partner", "speaker_page", "https://example.com/speaker", 0.85),
            DMCandidate("C Person", "Marketing Manager", "about_page", "https://example.com/about", 0.99),
        ],
    )
    assert resolution.primary is not None
    assert resolution.primary.name == "B Person"
    assert resolution.fallback is not None
    assert resolution.fallback.name == "A Person"
    report = dm_report_entry("Example", "pim_mdm_integrator", resolution)
    assert 0 <= report["dm_confidence"] <= 1
    assert report["dm_source"] == "speaker_page"


def test_dm_deterministic_tie_break():
    same = [
        DMCandidate("Beta", "CTO", "linkedin", "https://linkedin.com/in/beta", 0.9),
        DMCandidate("Alpha", "CTO", "linkedin", "https://linkedin.com/in/alpha", 0.9),
    ]
    first = resolve_decision_maker("pim_mdm_integrator", same)
    second = resolve_decision_maker("pim_mdm_integrator", list(reversed(same)))
    assert first.primary.name == second.primary.name == "Alpha"


def test_dm_missing_reason():
    resolution = resolve_decision_maker(
        "shopify_commerce_agency",
        [DMCandidate("No Match", "Designer", "about_page", "https://example.com/about", 0.9)],
    )
    assert resolution.primary is None
    assert resolution.missing_reason


def test_email_policy_generic():
    assert classify_verification("valid", 0.90) == "verified"
    assert classify_verification("deliverable", 0.80) == "verified"
    assert classify_verification("valid", 0.79) == "reserve"
    assert classify_verification("catch_all", None) == "reserve"
    assert classify_verification("unknown", None) == "reserve"
    assert classify_verification("risky", None) == "reserve"
    assert classify_verification("invalid", 1.0) == "invalid"
    assert normalize_status("catch-all") == "catch_all"


def test_provider_matrix():
    cases = [
        ("hunter", "valid", 0.90, "verified"),
        ("hunter", "valid", 0.79, "reserve"),
        ("hunter", "accept_all", 0.99, "reserve"),
        ("neverbounce", "valid", None, "verified"),
        ("neverbounce", "catchall", None, "reserve"),
        ("neverbounce", "unknown", None, "reserve"),
        ("neverbounce", "invalid", None, "invalid"),
        ("zerobounce", "valid", None, "verified"),
        ("zerobounce", "catch-all", None, "reserve"),
        ("zerobounce", "unknown", None, "reserve"),
        ("zerobounce", "invalid", None, "invalid"),
        ("millionverifier", "ok", None, "verified"),
        ("millionverifier", "catch_all", None, "reserve"),
        ("millionverifier", "unknown", None, "reserve"),
        ("millionverifier", "invalid", None, "invalid"),
    ]
    for provider, status, confidence, expected in cases:
        decision, policy_conf, confidence_source = provider_policy(provider, status, confidence)
        assert decision == expected, (provider, status, decision)
        if expected == "verified":
            assert policy_conf is not None and policy_conf >= 0.8
            assert confidence_source


def test_provider_skipped_status(monkeypatch=False):
    old = {key: os.environ.pop(key, None) for key in (
        "HUNTER_API_KEY", "NEVERBOUNCE_API_KEY", "ZEROBOUNCE_API_KEY", "MILLIONVERIFIER_API_KEY"
    )}
    try:
        wf = EmailWaterfall()
        assert wf.verification_status() == "skipped"
        assert len(wf.skipped_providers()) == 4
    finally:
        for key, value in old.items():
            if value is not None:
                os.environ[key] = value


def test_manifest_metrics():
    dm = dm_metrics([
        {"dm_found": True, "dm_role_match": 1.0, "dm_source": "linkedin", "dm_confidence": 0.9},
        {"dm_found": False, "dm_missing_reason": "not found"},
    ])
    assert dm["dm_coverage"] == 0.5
    assert dm["dm_source"]["linkedin"] == 1

    email = email_metrics([
        {"email": "a@example.com", "provider": "hunter", "status": "valid", "confidence": 0.95, "confidence_source": "hunter_score", "decision": "verified"},
        {"email": "b@example.com", "provider": "neverbounce", "status": "catch_all", "confidence": None, "confidence_source": "neverbounce_category", "decision": "reserve"},
    ], verification_status="partial", provider_skipped=["zerobounce"])
    assert email["emails_found"] == 2
    assert email["emails_verified"] == 1
    assert email["catch_all_rate"] == 0.5
    assert email["verification_status"] == "partial"
    assert email["provider_skipped"] == ["zerobounce"]
    assert email["email_confidence_source"]["hunter_score"] == 1


def test_resolver_to_main_schema_conformance():
    resolution = resolve_decision_maker(
        "shopify_commerce_agency",
        [DMCandidate("Alex Example", "Founder", "linkedin", "https://linkedin.com/in/alex-example", 0.95)],
    )
    assert resolution.primary is not None
    row = {
        "company_name": "Schema Safe Ltd",
        "website": "https://schema-safe.example.com",
        "country": "GB",
        "segment": "shopify_commerce_agency",
        "subtype": "Shopify agency",
        "decision_maker_name": resolution.primary.name,
        "decision_maker_role": resolution.primary.role,
        "linkedin_url": resolution.primary.source_url,
        "recent_evidence": "A dated Shopify migration case with supplier product data.",
        "evidence_type": "case_study",
        "evidence_url": "https://schema-safe.example.com/case",
        "evidence_date": "2026-09-10",
        "evidence_date_precision": "exact",
        "personalization_hook": "Your recent Shopify Plus migration case highlights a recurring supplier-data cleanup step.",
        "hook_grounding": [{"claim": "Shopify Plus", "grounded_in": "https://schema-safe.example.com/case"}],
        "relevance_reason": "The agency handles catalog migration and supplier product data before Shopify onboarding.",
        "catalog_workflow_signal": "Catalog migration and supplier product data handling.",
        "likely_pain": "Manual normalization before Shopify import.",
        "recommended_angle": "shopify_onboarding",
        "recommended_offer": "pilot_engagement",
        "first_line": "Your recent Shopify Plus migration case points to a recurring catalog-cleanup step before launch.",
        "fit_score": 90,
        "evidence_score": 90,
        "priority_score": 90,
        "excluded_signals": [],
        "language_ok": "en",
        "primary_discovery_source": "google",
        "source_urls": ["https://schema-safe.example.com/case"],
        "exclude_reason": None,
        "human_pass_notes": None,
        "work_email": None,
        "email_confidence": None,
        "email_source": None,
        "email_confidence_source": None,
        # research-only fields must be stripped:
        "evidence_content": "PRIVATE RESEARCH TEXT",
        "signal_count": 4,
        "canonical_domain": "schema-safe.example.com",
        "dm_source_raw": "linkedin scrape",
        "raw_html": "<html>research</html>",
    }
    clean = sanitize_and_validate_main(row)
    for forbidden in ("evidence_content", "signal_count", "canonical_domain", "dm_source_raw", "raw_html"):
        assert forbidden not in clean


def test_reserve_conformance_strips_internal():
    row = {
        "company_name": "Reserve Safe",
        "website": "https://reserve-safe.example.com",
        "country": "GB",
        "segment": "shopify_commerce_agency",
        "exclude_stage": "no_decision_maker",
        "exclude_reason": "no qualifying decision-maker verified",
        "fit_score": 90,
        "evidence_score": 80,
        "recent_evidence": "A valid recent case exists but the decision maker could not be verified.",
        "evidence_type": "case_study",
        "evidence_url": "https://reserve-safe.example.com/case",
        "evidence_date": "2026-09-10",
        "decision_maker_name": None,
        "decision_maker_role": None,
        "source_urls": ["https://reserve-safe.example.com/case"],
        "raw_html": "<html>no</html>",
    }
    clean = sanitize_and_validate_reserve(row)
    assert "raw_html" not in clean


if __name__ == "__main__":
    test_role_matrix()
    test_dm_resolution_primary_and_fallback()
    test_dm_deterministic_tie_break()
    test_dm_missing_reason()
    test_email_policy_generic()
    test_provider_matrix()
    test_provider_skipped_status()
    test_manifest_metrics()
    test_resolver_to_main_schema_conformance()
    test_reserve_conformance_strips_internal()
    print("WAVE2 UNIT TESTS PASSED")
