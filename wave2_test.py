from __future__ import annotations

from src.enrichment.dm_resolver import DMCandidate, resolve_decision_maker
from src.enrichment.dm_role_matrix import role_match_score
from src.verification.email_policy import classify_verification, normalize_status
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
    assert resolution.primary.name in {"A Person", "B Person"}
    assert resolution.fallback is not None
    assert resolution.missing_reason is None


def test_dm_missing_reason():
    resolution = resolve_decision_maker(
        "shopify_commerce_agency",
        [DMCandidate("No Match", "Designer", "about_page", "https://example.com/about", 0.9)],
    )
    assert resolution.primary is None
    assert resolution.missing_reason


def test_email_policy():
    assert classify_verification("valid", 0.90) == "verified"
    assert classify_verification("deliverable", 0.80) == "verified"
    assert classify_verification("valid", 0.79) == "reserve"
    assert classify_verification("catch_all", None) == "reserve"
    assert classify_verification("unknown", None) == "reserve"
    assert classify_verification("risky", None) == "reserve"
    assert classify_verification("invalid", 1.0) == "invalid"
    assert normalize_status("catch-all") == "catch_all"


def test_manifest_metrics():
    dm = dm_metrics([
        {"dm_found": True, "dm_role_match": 1.0, "dm_source": "linkedin", "dm_confidence": 0.9},
        {"dm_found": False, "dm_missing_reason": "not found"},
    ])
    assert dm["dm_coverage"] == 0.5
    assert dm["dm_source"]["linkedin"] == 1

    email = email_metrics([
        {"email": "a@example.com", "provider": "hunter", "status": "valid", "confidence": 0.95, "decision": "verified"},
        {"email": "b@example.com", "provider": "neverbounce", "status": "catch_all", "confidence": None, "decision": "reserve"},
    ])
    assert email["emails_found"] == 2
    assert email["emails_verified"] == 1
    assert email["catch_all_rate"] == 0.5


if __name__ == "__main__":
    test_role_matrix()
    test_dm_resolution_primary_and_fallback()
    test_dm_missing_reason()
    test_email_policy()
    test_manifest_metrics()
    print("WAVE2 UNIT TESTS PASSED")
