# Wave2 runbook — DM enrichment + email verification

Baseline: `lg-2026-09-22-01`.

## Invariants

Do not change ICP, fit/evidence thresholds, exclusion precedence, priority formula, or the 0.8 email-confidence minimum.

## Decision-maker enrichment

Use the role matrix in `src/enrichment/dm_role_matrix.py`.
Accepted evidence sources: LinkedIn, team/about/kontakt pages, Clutch, local registries, speaker pages.
Resolve one primary DM and at most one fallback. Missing DM is explicit; never infer a person or role.

## Email verification

`src/verification/email_waterfall.py` supports environment-backed verifiers:

- `HUNTER_API_KEY`
- `NEVERBOUNCE_API_KEY`
- `ZEROBOUNCE_API_KEY`
- `MILLIONVERIFIER_API_KEY`

Optional: `ZEROBOUNCE_BASE_URL` (defaults to EU endpoint).

No API key is committed. Missing credentials skip the provider. Only verifier-backed valid/deliverable results at confidence >= 0.8 may enable email outreach. Catch-all/unknown/risky remain non-verified.

## CI gate

CI runs:
1. compile
2. existing smoke tests
3. v1.0.1 preflight
4. wave2 unit tests
5. wave1 calibration regression
6. artifact upload

## Wave2 runs

Run A: reuse the exact baseline candidate set.
Run B: a fresh 12-candidate batch.

Artifacts to retain:
- batch_manifest.json
- passed.json
- reserve.jsonl
- dm_enrichment_report.json
- email_verification_report.json
- schema_conformance.log

Do not send outbound email as part of these calibration runs.


## Deterministic DM confidence

`dm_confidence = 0.7 * role_match_score + 0.3 * source/evidence confidence`.
Tie-break order is fixed: total score, role match, source confidence, fixed source priority, candidate name.

## Verifier status semantics

Manifest/reporting must distinguish:
- `skipped`: no verifier credentials configured;
- `partial`: at least one verifier configured, but not the full waterfall;
- `complete`: all configured waterfall providers available.

`provider_skipped` lists providers skipped because credentials are absent. A skipped provider is never counted as an email miss.

Confidence provenance is explicit:
- Hunter numeric score → `hunter_score`;
- NeverBounce categorical valid → `neverbounce_category`;
- ZeroBounce categorical valid → `zerobounce_category`;
- MillionVerifier categorical valid → `millionverifier_category`.

A categorical valid result may satisfy policy, but it is never represented as if the provider emitted a numeric score.
