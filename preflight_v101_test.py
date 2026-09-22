from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from outreach_v101 import (
    apply_email_policy,
    build_manifest,
    dedupe_companies,
    determine_exclusion_stage,
    evidence_is_wave1_eligible,
    first_line_ok,
    hook_grounding_ok,
    jaccard_similarity,
    parse_evidence_date,
    primary_source_mix,
    registrable_domain,
    evaluate_batch,
)

RUN_TS = "2026-09-22T00:00:00Z"


def ok(name: str) -> None:
    print(f"PASS {name}")


# Schema syntax gate before behavioral tests.
for schema_path in (
    Path("schemas/leadgap-lead.json"),
    Path("schemas/leadgap-reserve.json"),
):
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)


# 1. evidence_date exact
value, precision = parse_evidence_date("2026-08-14", RUN_TS)
assert value == "2026-08-14"
assert precision == "exact"
assert evidence_is_wave1_eligible(value, RUN_TS)
ok("01 evidence_date exact")


# 2. evidence_date approximate
value, precision = parse_evidence_date("3 weeks ago", RUN_TS)
assert value == "2026-09-01", (value, precision)
assert precision == "approximate"
assert evidence_is_wave1_eligible(value, RUN_TS)
ok("02 evidence_date approximate")


# 3. evidence_date insufficient
value, precision = parse_evidence_date("Q3 case study", RUN_TS)
assert value is None and precision is None
stage = determine_exclusion_stage({"no_recent_evidence": True})
assert stage == "no_recent_evidence"
ok("03 evidence_date insufficient")


# 4. hook grounding fail
source = "We migrated a large catalog to Shopify Plus for a retail client."
grounding = [{
    "claim": "12k-SKU catalog",
    "grounded_in": "https://agency.example/case",
}]
assert not hook_grounding_ok(grounding, source)
ok("04 hook grounding fail")


# 5. precedence
stage = determine_exclusion_stage({
    "pre_filter": True,
    "no_decision_maker": True,
    "low_fit_score": True,
})
assert stage == "pre_filter"
manifest = build_manifest(
    run_id="synthetic-precedence",
    run_timestamp_utc=RUN_TS,
    passed_leads=[],
    reserve_leads=[{
        "company_name": "Synthetic",
        "exclude_stage": stage,
    }],
    candidates_raw=1,
    passed_pre_filter=0,
)
assert manifest["exclusion_reasons_histogram"]["pre_filter"] == 1
assert manifest["exclusion_reasons_histogram"]["no_decision_maker"] == 0
ok("05 precedence")


# 6. Jaccard 65%
shared = [f"s{i}" for i in range(13)]
a = " ".join(shared + ["a1", "a2", "a3"])
b = " ".join(shared + ["b1", "b2", "b3", "b4"])
score = jaccard_similarity(a, b)
assert abs(score - 0.65) < 1e-9, score
assert not first_line_ok(b, [a])
ok("06 Jaccard 65%")


# 7. Jaccard 55%
shared = [f"x{i}" for i in range(11)]
a = " ".join(shared + ["a1", "a2", "a3", "a4"])
b = " ".join(shared + ["b1", "b2", "b3", "b4", "b5"])
score = jaccard_similarity(a, b)
assert abs(score - 0.55) < 1e-9, score
assert first_line_ok(b, [a])
ok("07 Jaccard 55%")


# 8. PSL dedupe: co.uk and .com stay distinct
assert registrable_domain("https://example.co.uk") == "example.co.uk"
assert registrable_domain("https://example.com") == "example.com"
assert registrable_domain("https://example.co.uk") != registrable_domain("https://example.com")
out = dedupe_companies([
    {
        "company_name": "Example UK",
        "website": "https://example.co.uk",
        "segment": "shopify_commerce_agency",
        "fit_score": 90,
        "evidence_score": 80,
    },
    {
        "company_name": "Example US",
        "website": "https://example.com",
        "segment": "shopify_commerce_agency",
        "fit_score": 90,
        "evidence_score": 80,
    },
])
assert len(out) == 2
ok("08 PSL distinct registrable domains")


# 9. PSL subdomain: one company + secondary_segments
out = dedupe_companies([
    {
        "company_name": "Example",
        "website": "https://blog.example.com/case",
        "segment": "pim_mdm_integrator",
        "fit_score": 82,
        "evidence_score": 89,
    },
    {
        "company_name": "Example",
        "website": "https://www.example.com",
        "segment": "shopify_commerce_agency",
        "fit_score": 88,
        "evidence_score": 77,
    },
])
assert len(out) == 1, out
assert out[0]["canonical_domain"] == "example.com"
assert out[0]["segment"] == "shopify_commerce_agency"
assert out[0]["secondary_segments"] == ["pim_mdm_integrator"]
ok("09 PSL subdomain dedupe")


# 10. email no verifier
email, confidence, channel = apply_email_policy(
    "hello@example.com",
    None,
    None,
)
assert email is None and confidence is None
assert channel == "linkedin_or_site_form"
ok("10 email no verifier")


# 11. email below threshold
email, confidence, channel = apply_email_policy(
    "hello@example.com",
    "hunter",
    0.75,
)
assert email is None and confidence is None
assert channel == "linkedin_or_site_form"
ok("11 email below threshold")


# 12. source_mix primary discovery only
leads = [
    {
        "company_name": "Alpha",
        "primary_discovery_source": "linkedin",
        "source_urls": [
            "https://linkedin.com/company/alpha",
            "https://clutch.co/profile/alpha",
        ],
    }
]
mix = primary_source_mix(leads)
assert mix["linkedin"] == 1
assert mix["clutch"] == 0
assert sum(mix.values()) == len(leads)
ok("12 source_mix primary discovery only")


print("ALL 12 PRE-FLIGHT TESTS PASSED")

# Output schema conformance gate (in addition to the mandatory 12 rule tests).
main_schema = json.loads(Path("schemas/leadgap-lead.json").read_text(encoding="utf-8"))
reserve_schema = json.loads(Path("schemas/leadgap-reserve.json").read_text(encoding="utf-8"))
main_validator = Draft202012Validator(main_schema)
reserve_validator = Draft202012Validator(reserve_schema)

synthetic_pass = {
    "company_name": "Schema Safe Ltd",
    "website": "https://schema-safe.example.com",
    "country": "GB",
    "segment": "shopify_commerce_agency",
    "subtype": "Shopify agency",
    "decision_maker_name": "Alex Example",
    "decision_maker_role": "Founder",
    "linkedin_url": "https://linkedin.com/in/alex-example",
    "recent_evidence": "A dated Shopify migration case with supplier product data.",
    "evidence_type": "case_study",
    "evidence_url": "https://schema-safe.example.com/case",
    "evidence_date_raw": "2026-09-10",
    "personalization_hook": "Your recent Shopify Plus migration case highlights a recurring supplier-data cleanup step.",
    "hook_grounding": [{"claim": "Shopify Plus", "grounded_in": "https://schema-safe.example.com/case"}],
    "evidence_content": "Shopify Plus migration",
    "relevance_reason": "The agency handles catalog migration and supplier product data before Shopify onboarding.",
    "catalog_workflow_signal": "Catalog migration and supplier product data handling.",
    "likely_pain": "Manual normalization before Shopify import.",
    "recommended_angle": "shopify_onboarding",
    "recommended_offer": "pilot_engagement",
    "first_line": "Your recent Shopify Plus migration case points to a recurring catalog-cleanup step before launch.",
    "fit_score": 90,
    "evidence_score": 90,
    "language_ok": "en",
    "primary_discovery_source": "google",
    "source_urls": ["https://schema-safe.example.com/case"],
    "signal_count": 3,
    "excluded_signals": [],
    "work_email": None,
    "email_confidence": None,
    "email_source": None,
    "exclude_reason": None,
    "human_pass_notes": None,
}

passed, reserve, _ = evaluate_batch(
    [synthetic_pass],
    run_id="schema-conformance",
    run_timestamp_utc=RUN_TS,
)
assert len(passed) == 1 and not reserve
assert not list(main_validator.iter_errors(passed[0])), list(main_validator.iter_errors(passed[0]))
ok("schema conformance main output")

synthetic_reserve = dict(synthetic_pass)
synthetic_reserve["company_name"] = "Reserve Safe Ltd"
synthetic_reserve["website"] = "https://reserve-safe.example.com"
synthetic_reserve["signal_count"] = 0
passed, reserve, _ = evaluate_batch(
    [synthetic_reserve],
    run_id="schema-conformance-reserve",
    run_timestamp_utc=RUN_TS,
)
assert not passed and len(reserve) == 1
assert not list(reserve_validator.iter_errors(reserve[0])), list(reserve_validator.iter_errors(reserve[0]))
ok("schema conformance reserve output")

