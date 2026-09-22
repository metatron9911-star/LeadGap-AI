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

## Wave 2 measured series: D → H

Reference baseline remains `lg-2026-09-22-01`.

Intermediate DM-only state remains commit `6ff36a5`.

### Run D — hook-grounding logic
- result: 5 passed / 7 reserve
- Noto promoted after fixing grounding against the substituted source
- first-blocking histogram: no_decision_maker=3, no_recent_evidence=3, low_evidence_score=1
- attribution: grounding/manual_exclude
- invariant checks: I1/I2/I3 pass

### Run E — CTG evidence substitution
- result: 6 passed / 6 reserve
- The Commerce Team Global promoted
- attribution: evidence_low_quality → stronger fresh source under the same rubric
- collector unchanged; this validated downstream handling, not discovery
- invariant checks: I1/I2/I3 pass

### Run F — PIM/MDM role-matrix title gap
- result: 7 passed / 5 reserve
- 7thSENSE promoted
- change: add CEO alongside Managing Partner for pim_mdm_integrator
- interpretation: title-gap closure, not replacement of Managing Partner
- regressions: 0
- invariant checks: I1/I2/I3 pass

### Run G — OmegaCode fresh source substitution
- result: 7 passed / 5 reserve
- no promotion, but no regression
- substitution removed no_recent_evidence and low_evidence_score for OmegaCode
- it also introduced a new manual_exclude via hook grounding because the new source narrowed claim coverage
- classification: sourcing_gap confirmed; new why-class source_bundle_mismatch exposed
- invariant checks: I1/I2/I3 pass

### Run H — OmegaCode grounding bundle repair
- result: 8 passed / 4 reserve
- OmegaCode promoted
- repair: preserve fresh PPWR evidence for recency/workflow and add first-party MDM/PIM support into the existing single-string grounding context with explicit provenance metadata
- structural evidence model unchanged
- grounding rule unchanged
- regressions: 0
- invariant checks: I1/I2/I3 pass

### Run H measured state
Passed segment distribution:
- shopify_commerce_agency: 4
- pim_mdm_integrator: 3
- pl_cee_de_smb_agency: 1

First-blocking reserve:
- e-point: no_recent_evidence
- KK Digital: no_recent_evidence
- Brand Active: no_decision_maker
- Storise: no_decision_maker

All-failing reserve stacks:
- e-point: no_recent_evidence + low_evidence_score
- KK Digital: no_recent_evidence + low_evidence_score
- Brand Active: no_decision_maker + no_recent_evidence + low_evidence_score
- Storise: no_decision_maker + no_recent_evidence + low_evidence_score

Freeze artifacts live under `research/freeze_run_h/`. They are explicitly marked reconstructed because raw KVS export was not retrieved. The observed Run H terminal result was 8 passed / 4 reserve with 0 regressions.

## Wave 2 headline

**The rules layer saturated at 8/12; further gains require collector improvements or explicit source-policy changes, not looser scoring/rubric/threshold rules.**

After Run H, every remaining blocker sits outside the scoring/threshold path:

- Brand Active — no verified current successor → collector / DM sourcing
- e-point — no fresh qualifying PIM/product-data evidence found in current scope → search-scope / collector
- KK Digital — relevant source exists but publication date remains unresolved → collector / date extraction
- Storise — legal identity chain is supportable, but acceptance of that chain as DM evidence is unresolved → source-policy

This marks a natural boundary between Wave 2 (pipeline/rule calibration) and Wave 3 (collector and source-policy work).

