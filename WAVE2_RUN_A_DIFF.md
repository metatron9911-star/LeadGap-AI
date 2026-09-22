# Wave2 — Run A diff vs baseline

- baseline_run_id: lg-2026-09-22-01
- wave2_run_id: <fill>
- date: <fill>
- candidates: same 12
- scoring/thresholds/exclusion_precedence: unchanged

## 1. Headline

| metric | baseline | wave2 | delta |
|---|---:|---:|---:|
| candidates_raw | 12 | | |
| passed_pre_filter | 12 | | |
| passed_thresholds | 4 | | |
| reserve_count | 8 | | |
| email_coverage (>=0.8) | 0/4 | | |

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
| dm_confidence | |
| dm_source | |
| dm_missing_reason | |

## 6. Email verification (wave2-only)

| metric | value |
|---|---|
| verification_status | |
| provider_skipped | |
| emails_found | |
| emails_verified | |
| catch_all_rate | |
| email_provider | |
| email_confidence_source | |

`email_confidence_dist`:
- 0.80–0.89:
- 0.90–1.00:

## 7. Candidate transitions

| candidate_id | baseline_status | wave2_status | reason |
|---|---|---|---|
| | passed/reserve | | |

## 8. Conclusions

- recovered from the six baseline `no_decision_maker`:
- verified email coverage > 0:
- source_mix changed:
- touch scoring: **no** unless evidence proves otherwise.

## 9. Artifacts

- batch_manifest.json
- passed.json
- reserve.jsonl
- dm_enrichment_report.json
- email_verification_report.json
- schema_conformance.log
