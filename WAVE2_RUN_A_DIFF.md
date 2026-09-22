# Wave2 — Run A diff vs baseline

## Run metadata

- baseline_run_id: lg-2026-09-22-01
- wave2_run_id: lg-2026-09-22-wave2-dm-only
- date: 2026-09-22
- candidates: same 12
- commit: 17173b5c82f05e99971a636515da318e72fb62ed
- scoring / thresholds / exclusion_precedence / priority_formula: unchanged

## Mode

- dm_enrichment: complete
- email_verification: not_run
- email_verification_reason: provider_skipped — no real verifier API key in environment
- provider_skipped: true

> Invariant: `provider_skipped` is a valid terminal status, not an error.
> `email_coverage` under `provider_skipped` means “not verified”, not “verified and none found”.
> Simulated verifier keys/results are forbidden.

## 1. Headline

| metric | baseline | wave2 | delta |
|---|---:|---:|---:|
| candidates_raw | 12 | 12 | 0 |
| passed_pre_filter | 12 | 12 | 0 |
| passed_thresholds | 4 | 4 | 0 |
| reserve_count | 8 | 8 | 0 |
| email_coverage (>=0.8) | 0/4 | n/a | n/a |

## 2. Exclusion reasons histogram

| reason | baseline | wave2 | delta |
|---|---:|---:|---:|
| pre_filter | 0 | 0 | 0 |
| no_decision_maker | 6 | 3 | -3 |
| no_recent_evidence | 1 | 4 | +3 |
| low_fit_score | 0 | 0 | 0 |
| low_evidence_score | 1 | 1 | 0 |
| language_mismatch | 0 | 0 | 0 |
| manual_exclude | 0 | 0 | 0 |

Interpretation: DM enrichment recovered 3 of the 6 baseline `no_decision_maker` cases. Because exclusion precedence is unchanged, those three now expose the next real blocker: `no_recent_evidence`.

## 3. Segment distribution (passed)

| segment | baseline | wave2 | delta |
|---|---:|---:|---:|
| shopify_commerce_agency | 3 | 3 | 0 |
| pim_mdm_integrator | 1 | 1 | 0 |
| pl_cee_de_smb_agency | 0 | 0 | 0 |

No segment-level pass count changed in DM-only mode because all three recovered DMs remain blocked by later evidence gates.

## 4. Source mix

| source | baseline | wave2 | delta |
|---|---:|---:|---:|
| linkedin | 2 | 2 | 0 |
| clutch | 0 | 0 | 0 |
| shopify_partners | 0 | 0 | 0 |
| apify_store | 0 | 0 | 0 |
| google | 2 | 2 | 0 |
| referral | 0 | 0 | 0 |
| other | 0 | 0 | 0 |

Invariant holds: `sum(source_mix) == passed_thresholds == 4`.

## 5. DM coverage (wave2-only)

| metric | value |
|---|---:|
| dm_coverage | 75% (9/12) |
| recovered_from_baseline_no_decision_maker | 3/6 |
| dm_role_match (new recoveries avg) | 0.9167 |
| dm_confidence_avg (new recoveries) | 0.9317 |

Recovered:
- e-point → Łukasz Krukowski, CTO
- OmegaCode → Tomasz Michałowski, CTO
- Noto Agency → Zofia Komada, CEO / President of Management Board

Still missing under the fixed role matrix:
- 7thSENSE → management is public, but no current role matching the fixed PIM/MDM matrix was verified
- Brand Active → no current qualifying Owner / CEO / Managing Director / Head of Client Services verified; former CEO evidence is stale
- Storise → company/team pages expose no named qualifying decision-maker

## 6. Email verification

- status: not_run
- verification_status: skipped
- reason: provider_skipped
- emails_found: n/a
- emails_verified: n/a
- catch_all_rate: n/a
- email_provider: n/a
- email_confidence_source: n/a

> Fill in Run A' after at least one real verifier is configured.
> Do not rebuild/re-run the DM stage; run email verification on top of the frozen DM-only Run A artifacts.

## 7. Candidate transitions

| candidate | baseline_status | wave2_status | reason |
|---|---|---|---|
| InteractOne | passed | passed | unchanged |
| Graftstudio | passed | passed | unchanged |
| Ruby Digital Agency | passed | passed | unchanged |
| The Commerce Team Global | reserve: low_evidence_score | reserve: low_evidence_score | unchanged |
| asioso | passed | passed | unchanged |
| 7thSENSE | reserve: no_decision_maker | reserve: no_decision_maker | no fixed-matrix DM verified |
| e-point | reserve: no_decision_maker | reserve: no_recent_evidence | CTO recovered; next gate is undated evidence |
| OmegaCode | reserve: no_decision_maker | reserve: no_recent_evidence | CTO recovered; next gate is undated evidence |
| KK Digital | reserve: no_recent_evidence | reserve: no_recent_evidence | unchanged |
| Brand Active | reserve: no_decision_maker | reserve: no_decision_maker | no current qualifying DM verified |
| Noto Agency | reserve: no_decision_maker | reserve: no_recent_evidence | CEO recovered; next gate is undated evidence |
| Storise | reserve: no_decision_maker | reserve: no_decision_maker | no named qualifying DM verified |

## 8. Conclusions

- recovered from the six baseline `no_decision_maker`: **3/6 (50%)**
- DM coverage moved from **6/12 to 9/12 (50% → 75%)**
- `passed_thresholds`: unchanged at **4/12**
- why pass count did not move: the three recovered companies immediately hit the next unchanged gate, `no_recent_evidence`
- verified email coverage > 0: **n/a (not_run)**
- source_mix changed: **no**
- touch scoring: **no**
- next supply-side bottleneck after DM: **recent dated evidence**, not scoring

## 9. Artifacts

GitHub Actions artifact: `wave2-dm-only-run-a`

Contains:
- batch_manifest.json
- passed.json
- reserve.jsonl
- dm_enrichment_report.json
- schema_conformance.log

`email_verification_report.json` is intentionally absent under `provider_skipped`.

## 10. Follow-up before final Run A

- [ ] configure >=1 real verifier: HUNTER_API_KEY / NEVERBOUNCE_API_KEY / ZEROBOUNCE_API_KEY / MILLIONVERIFIER_API_KEY
- [ ] run email verification over the frozen DM-only Run A output
- [ ] fill section 6
- [ ] update headline `email_coverage`

Before changing any threshold, separately investigate the new visible bottleneck: three recovered DMs are now blocked by missing qualifying recent dated evidence.
