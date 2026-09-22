# Wave2 — Run A diff vs baseline

## Run metadata

- baseline_run_id: lg-2026-09-22-01
- wave2_run_id: <fill>
- date: <fill>
- candidates: same 12
- commit: <SHA wave2-dm-email-enrichment>
- scoring / thresholds / exclusion_precedence / priority_formula: unchanged

## Mode

- dm_enrichment: complete
- email_verification: not_run
- email_verification_reason: provider_skipped — no valid API key in environment
- provider_skipped: true

> Invariant: `provider_skipped` is a valid terminal status, not an error.
> `email_coverage` under `provider_skipped` means “not verified”, not “verified and none found”.
> Simulated verifier keys/results are forbidden.

## 1. Headline

| metric | baseline | wave2 | delta |
|---|---:|---:|---:|
| candidates_raw | 12 | | |
| passed_pre_filter | 12 | | |
| passed_thresholds | 4 | | |
| reserve_count | 8 | | |
| email_coverage (>=0.8) | 0/4 | n/a | n/a |

## 2. Exclusion reasons histogram

| reason | baseline | wave2 | delta |
|---|---:|---:|---:|
| pre_filter | 0 | | |
| no_decision_maker | 6 | | |
| no_recent_evidence | 1 | | |
| low_fit_score | 0 | | |
| low_evidence_score | 1 | | |
| language_mismatch | 0 | | |
| manual_exclude | 0 | | |

## 3. Segment distribution (passed)

| segment | baseline | wave2 | delta |
|---|---:|---:|---:|
| shopify_commerce_agency | 3 | | |
| pim_mdm_integrator | 1 | | |
| pl_cee_de_smb_agency | 0 | | |

## 4. Source mix

| source | baseline | wave2 | delta |
|---|---:|---:|---:|
| linkedin | 2 | | |
| clutch | 0 | | |
| shopify_partners | 0 | | |
| apify_store | 0 | | |
| google | 2 | | |
| referral | 0 | | |
| other | 0 | | |

Invariant: `sum(source_mix) == passed_thresholds`.

## 5. DM coverage (wave2-only)

| metric | value |
|---|---|
| dm_coverage | |
| dm_role_match | |
| dm_confidence_avg | |

Breakdown by `dm_missing_reason`:
- not_found:
- ambiguous:
- source_blocked:

## 6. Email verification

- status: not_run
- reason: provider_skipped
- emails_found: n/a
- emails_verified: n/a
- catch_all_rate: n/a
- email_provider: n/a
- email_confidence_source: n/a

> Fill in Run A' after at least one real verifier is configured.
> Do not rebuild/re-run the DM stage; run email verification on top of the frozen DM-only Run A artifacts.

## 7. Candidate transitions

| candidate_id | baseline_status | wave2_status | reason |
|---|---|---|---|
| | passed/reserve | | |

## 8. Conclusions

- recovered from the six baseline `no_decision_maker`:
- verified email coverage > 0: n/a (not_run)
- source_mix changed:
- touch scoring: no / yes (justify)

## 9. Artifacts

- batch_manifest.json
- passed.json
- reserve.jsonl
- dm_enrichment_report.json
- email_verification_report.json — absent under `provider_skipped`
- schema_conformance.log

## 10. Follow-up before final Run A

- [ ] configure >=1 real verifier: HUNTER_API_KEY / NEVERBOUNCE_API_KEY / ZEROBOUNCE_API_KEY / MILLIONVERIFIER_API_KEY
- [ ] run email verification over the frozen DM-only Run A output
- [ ] fill section 6
- [ ] update headline `email_coverage`
