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

## Invariant scope for all-gates diagnostics

I2 applies only to the first-blocking histogram:

`sum(first_blocking_histogram.values()) == reserve_count`.

It does **not** apply to `all_failing_gate_counts`, because multi-gate reserve candidates are counted once per failing gate there. Therefore `sum(all_failing_gate_counts.values())` may exceed `reserve_count` by design.

## Diagnostic-mode scope

All-gates mode is a planning diagnostic, not a permanent production output. Use it when:
- selecting or sequencing fixes;
- a first-blocking bucket may hide downstream failures;
- a change unexpectedly moves candidates between exclusion stages.

Normal runs may continue to emit the compact first-blocking histogram. Recompute the all-gates view only when planning or validating a structural change.

## Why-diagnostic enums

Why-diagnostics are gate-specific, not one shared enum.

For evidence-related gates:

`evidence_gate_why = no_evidence_exists | sourcing_gap | cutoff_policy_question | evidence_low_quality | rubric_missed`

For decision-maker gates:

`dm_gate_why = role_matrix_narrow | role_actually_wrong | dm_not_public`

A gate is an observed failure condition; a why-diagnostic identifies the underlying cause and therefore the likely fix class. In particular, `low_evidence_score` may be caused by weak selected evidence, missing/old evidence, or a scoring-rubric problem. Do not infer the fix class from the gate alone.

## All-gates invariants

`all_failing_gate_counts` is a diagnostic view, not a manifest accounting field. It is not subject to I1, I2, or I3. Multi-gate candidates are intentionally counted once per failing gate, so its total may exceed both `reserve_count` and `candidates_raw`.

## Data-level source substitution

An evidence-substitution calibration run may replace the selected evidence for a candidate while leaving collector behavior unchanged. A successful promotion proves only that downstream scoring/gating can work with a stronger input. It does **not** prove that the collector would discover that stronger source automatically. Collector-discovery improvement remains a separate follow-up experiment.

## Fix taxonomy

### Data-level fix
Examples: evidence substitution for one candidate.

Expected properties:
- one candidate's input changes;
- zero regression is expected on the existing passed set;
- first-blocking histogram changes by exactly the candidates whose input changed (or by zero if no promotion);
- attribution is to the input change only;
- collector capability is not implied by a manually substituted source.

### Rule-level fix
Examples: decision-maker role-matrix expansion.

Expected properties:
- the rule applies globally to every candidate in the affected segment;
- a full 12-candidate rerun is required;
- regression check on the existing passed set is mandatory;
- reserve candidates other than the motivating target may move between first-blocking gates without being promoted;
- attribution is to the global rule change, not to a single candidate.

A rule-level experiment may be motivated by one candidate, but it must be interpreted as a global rule change.

## Why-diagnostic targeting rule

Run why-diagnostics against the **current first-blocking gate**, not merely against every failing gate on the candidate.

For a multi-gate reserve candidate, diagnose the gate that currently determines exclusion under `EXCLUSION_PRECEDENCE`. A downstream failing gate may be recorded for context, but it should not drive the next experiment until the first blocker is cleared.

This preserves attribution: a fix should target the gate that can actually change the candidate's first-blocking state or promote it.

## Cutoff-policy diagnostic rule

`cutoff_policy_question` applies only when **no fresh qualifying source exists at all** within the frozen evidence window.

If a fresh qualifying source exists but the collector/input did not select it, classify the failure as `sourcing_gap`, regardless of whether an older source is also present.

Do not use the existence of an older out-of-window source as evidence for changing the cutoff until fresh-source discovery has been exhausted.

## Gate-stack mutation after data substitution

A data-level source substitution can change the entire gate stack, not only remove the targeted gate.

After any substitution, the new all-gates state must be recomputed and compared with the pre-substitution stack. Three outcomes are possible:
- the targeted gate is removed;
- an already-existing downstream gate becomes first-blocking;
- a new gate is introduced because the substituted evidence no longer supports another validation condition.

Do not assume a substitution can only reveal pre-existing gates.

## Hook-grounding why classes

A hook-grounding failure can arise from at least two distinct causes:

- `hook_overclaim`: the hook claim is not actually supported by the company/source evidence. Fix the hook.
- `source_bundle_mismatch`: the company capability is real, but the substituted selected evidence no longer supports every hook claim under the current grounding validator. Fix the evidence bundle/source selection; do not weaken grounding.

Grounding rules should not be relaxed merely because a substituted source is narrower than the prior evidence.

## Evidence-bundle compatibility in v1.0.1

The current evaluator is **single-string grounding**: `hook_grounding_ok()` receives one `evidence_content` string and checks every declared claim against that normalized string. It does not natively iterate over an evidence-item list or inspect multiple source fields.

Therefore a data-level bundle repair in the current model may preserve multiple source contents by composing them into the existing `evidence_content` field while storing explicit provenance metadata separately. This is a compatibility technique, not a claim that the core evidence model is list-native.

If a future change converts evidence from a single string to a first-class list of items and changes evaluator behavior, that is a structural/rule-level model change and must be tested separately.

## Claim-coverage preservation for substitutions

A data-level source substitution should preserve the full claim coverage of the pre-substitution evidence context unless the hook itself is intentionally revised.

If the new source grounds fewer claims than the previous context, the substitution is a narrowing. Any resulting grounding failure should be classified as `source_bundle_mismatch`, not automatically as a pipeline defect.

After each substitution:
1. recompute all-gates on the new state;
2. compare the pre- and post-substitution gate stacks;
3. record any newly created gates explicitly.

## Multi-gate run-count expectation

The number of runs needed for a candidate is better approximated by the number of **distinct fix classes** encountered, not by the initial failing-gate count.

A fix can introduce a new failure class that was not present in the initial stack, so the required run count can grow during the series.

## Grounding why-taxonomy (frozen at Run H)

Grounding-related failures are classified by cause:

- `grounding_bug`: evaluator/code validates the wrong grounding context or otherwise misapplies the rule.
- `hook_overclaim`: a hook claim is not actually supported by the company/source evidence. Fix the hook.
- `source_bundle_mismatch`: the claim is true, but the selected/substituted evidence context no longer covers every declared hook claim. Repair the evidence bundle/context without weakening grounding.

Known limitation: first-party capability pages may be used as `self_claim` grounding evidence. This is valid under the current experiment semantics but is not independent verification. Treat `self_claim_only_grounding` as a precision limitation to monitor, not as a current failing gate.

