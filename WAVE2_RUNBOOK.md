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
