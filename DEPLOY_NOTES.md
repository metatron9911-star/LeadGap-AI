# LeadGap AI – deployment notes

Actor: `w_met/leadgap-ai-local-business-opportunity-finder`
Release candidate: `0.0.35d`
Actor definition version: `0.35`

## What changed in 0.0.35d

- Added `.actor/actor.json`, `input_schema.json`, `output_schema.json`, and `dataset_schema.json`.
- Country selector now exposes all 15 supported markets.
- Appointment-led niches keep booking gaps commercially qualified when audit confidence is sufficient.
- Embedded Typeform, HubSpot, Jotform, Google Forms, and Calendly iframes count as form/booking evidence instead of being missed.
- Pay-per-event output uses `Actor.push_data(..., charged_event_name="qualified-opportunity")` and now checks `ChargeResult` so work stops when the run charge limit is reached.
- `apify` is pinned to `>=2.7.0,<3.0.0`, a documented SDK line with `charged_event_name` support.

## Required live validation before publishing

1. Manual mode: audit 1–2 known URLs and confirm output fields.
2. `Dentist / Manchester / UK`, 10 discovered, max 5 results: confirm at least one usable booking/lead-capture opportunity when market data permits.
3. `Plumber / Bristol / UK`, 10 discovered, max 5 results: confirm Screwfix/Toolstation/retail noise is rejected.
4. `Beauty Salon / Berlin / DE`, 10 discovered, max 5 results: confirm German booking/contact signals still work.
5. Check dataset Output tab: `Sales-ready leads` view should render with the buyer-facing columns.
6. Check Billing: `qualified-opportunity` event count must equal the number of paid dataset items.
7. Confirm actual Google Maps payload field for hours (`openingHours` or alternative) and adjust passthrough if necessary.

Do not publish over the last confirmed working build until these live checks pass.


## 0.0.35 pre-live fixes
- Localized candidate-page discovery and booking signals for DE/FR/ES/IT/NL/PL.
- Appointment-niche aliases expanded (Dental, Beauty, Legal, Tax, etc.).
- Appointment leads now get niche-specific `whyThisLead`.
- Contact-form detection now reads labels/ARIA attributes and common embedded form providers.
- `Accept-Language` now uses full locale preferences with English fallback.
- Opening-hours fallback also checks `openingHoursDetailed`.
- PPE push handling catches write failures while preserving Apify's `charged_count` semantics.


## 0.0.35d localization patch

- Expanded localized contact-form field hints/context for DE/FR/ES/IT/NL/PL.
- Expanded booking detection for common Dutch, Italian, Polish, German, French, and Spanish phrases.
- Added appointment-niche Lead capture copy when booking exists but an enquiry form is missing.
- Local smoke tests cover localized forms, booking phrases, and Dental lead-capture qualification.

- 0.0.35d adds NICHE_RULES aliases and smoke coverage for Dental / Legal / Salon plus the Plumber retail guard.


## 0.0.35d hardening

- Added relevance aliases for Plumbing, Roofing, Cleaning, Landscaping, Building and Electrical.
- Added a dedicated general Spa/Wellness relevance rule; `Spa` is no longer treated as `Med Spa`.
- Added a 0.6 s throttle before DuckDuckGo HTML external-site checks to reduce burst-rate failures.
- README no longer claims dedicated restaurant menu/reservation scoring; restaurants currently use generic conversion scoring after niche relevance filtering.
- Smoke tests now cover gerund/service aliases, general Spa, and the Screwfix retail guard.


## 0.0.35d external-search hardening

- DuckDuckGo HTTP 202 responses are treated as `UNAVAILABLE`.
- A successful HTTP response with no parsable `.result` nodes is also treated as `UNAVAILABLE`.
- `NOT_FOUND` now means search results were actually parsed but no candidate cleared the official-site threshold.


## 0.0.35d-observe — live-run observability only

This build intentionally freezes 0.0.35d commercial logic and adds diagnostics only.

Log records:
- `PLACE_INPUT` — one compact line for every Google Maps business returned before dedup/relevance.
- `PLACE_DIAG` — relevance result plus audit status, booking/contact/CTA/click-to-call signals, primary opportunity, confidence, sales priority, doNotPitch, website source, external check, qualification and push result.
- `MAPS_FIRST_PLACE` — the full first Google Maps item once per automatic run to inspect actual upstream field names such as opening hours.
- `RUN_SUMMARY` — discovered, after_dedup, after_relevance, after_commercial_eval, qualified, pushed, FOUND, NOT_FOUND and UNAVAILABLE counts.

Use this build for the frozen live-run matrix. Do not change filtering/scoring unless live evidence identifies a regression.


Observability integrity fix:
- `SEEN_PLACE_ID` and both `SEEN_WEBSITE` early-continue branches now emit `PLACE_DIAG` with `skipReason`, so no post-relevance place disappears from diagnostics.
- Renamed summary counter `after_audit` to `after_commercial_eval` because it counts both audited websites and no-website commercial evaluations.
