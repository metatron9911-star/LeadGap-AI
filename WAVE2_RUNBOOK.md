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


## provider_skipped invariant

`provider_skipped` is a valid terminal status, not an error condition.

When no real verifier credentials are configured:
- `verification_status = "skipped"`;
- email coverage is reported as **not run / n/a**, not as a verified zero;
- no simulated key or fabricated verifier response may be used;
- DM-only Run A may proceed and its artifacts are frozen for the later email-only Run A' stage.

A later Run A' should apply real email verification on top of the frozen DM-only results rather than rerunning the decision-maker stage.

## First-blocking vs all-failing gates

The manifest histogram is a **first-blocking-gate histogram**. It records only the first failing gate selected by `EXCLUSION_PRECEDENCE` for each reserve candidate.

Therefore:
- histogram bucket size is not the same as total number of failing conditions;
- one candidate may fail multiple gates simultaneously;
- resolving the first visible gate may only move the candidate to the next failing gate;
- promotion requires clearing **all** failing gates for that candidate.

Before treating a histogram bucket as a binding constraint, inspect an all-gates diagnostic for the affected reserve candidates.

## Hook grounding semantics

`hook_grounding` is not a separate exclusion stage. It is a validation input to `manual_exclude`:
- if any declared hook claim is absent from `evidence_content`, `grounding_failed=True`;
- this sets the existing `manual_exclude` flag;
- because `manual_exclude` is last in `EXCLUSION_PRECEDENCE`, it can remain hidden behind earlier failures such as `no_recent_evidence` or `low_evidence_score`.

When `manual_exclude` is caused by hook grounding, reports should state that explicitly instead of implying a human/manual decision.

## Reconstructed deterministic artifacts

Raw Apify KVS artifacts are preferred for freeze.

If raw KVS retrieval is unavailable, a reconstructed artifact may be used for protocol purposes only when:
1. the reconstruction function/version is identified;
2. all inputs and source commits/branches are fixed;
3. the reconstructed artifact is marked `artifact_type: reconstructed`;
4. deterministic invariants are re-evaluated;
5. the freeze note records that the artifact was reconstructed rather than exported raw.

This does not replace the reference baseline. `lg-2026-09-22-01` remains the permanent comparison baseline.

## Email stage note

Run A' email-only **was executed** on top of the frozen DM-only state. It improved confident email coverage among passed leads from 0/4 to 2/4 while leaving pass/reserve counts unchanged. Runs B/C/D did not rerun email enrichment and should be read as evidence/hook experiments on the same 12-candidate calibration batch.

