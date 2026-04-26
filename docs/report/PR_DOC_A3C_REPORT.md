# PR DOC-A3C Report — Doctor linked recommendation / care-order panel actionability and final DOC closure

## What changed after DOC-A3B
- Replaced doctor linked recommendation panel Back-only behavior with a bounded doctor workflow keyboard:
  - Open chart
  - Open encounter (only when booking-linked encounter context is truly resolvable and clinically active)
  - Issue follow-up recommendation (reuses existing DOC-A2 contextual recommendation flow)
  - Back to booking
- Replaced doctor linked care-order panel Back-only behavior with a bounded doctor awareness keyboard:
  - Open chart
  - Open encounter (same safe availability guard)
  - Back to booking
- Added safe linked encounter resolver used by both keyboards and action handling. It validates:
  - booking exists
  - booking belongs to doctor and patient context
  - booking status is clinically active (`checked_in` / `in_service`)
  - encounter can be resolved
  - encounter is non-terminal
- Added bounded linked encounter callback path (`open_linked_encounter`) for both runtime card callback codec and legacy callback compatibility.
- Added compact localized doctor copy for:
  - open encounter
  - issue follow-up recommendation
  - unavailable linked action

## Exact files changed
- `app/interfaces/bots/doctor/router.py`
- `tests/test_booking_linked_opens_12b1.py`
- `locales/en.json`
- `locales/ru.json`
- `docs/report/PR_DOC_A3C_REPORT.md`

## How linked recommendation actionability is wired
- Linked recommendation open now renders panel body unchanged, but keyboard switched to dedicated doctor linked recommendation keyboard.
- “Issue follow-up recommendation” routes to existing booking-context `add_recommendation` callback path, which reuses DOC-A2 encounter-bound recommendation type selection and pending capture flow.
- “Open encounter” CTA is conditionally shown only if resolver confirms valid active booking/encounter context.
- Manual/stale open-encounter callbacks are bounded by compact unavailable alert; no raw technical reason is exposed.

## How linked care-order actionability is wired
- Linked care-order open now renders panel body unchanged, but keyboard switched to dedicated doctor linked care-order keyboard.
- Actions are intentionally bounded to clinical continuity only:
  - chart context
  - optional encounter continuity
  - back to booking
- No pickup operation CTA/mutations were added.

## How admin-only pickup mutation was avoided
- Doctor linked care-order keyboard never renders pickup handling actions.
- Doctor callback routing includes no care-order mutation handlers.
- Existing admin pickup flows were left untouched.

## Tests added/updated
- Updated doctor linked panel tests to verify recommendation and care-order panels are no longer Back-only.
- Added assertions that linked recommendation panel exposes chart continuity and recommendation continuation, and routes to canonical recommendation type chooser when context is valid.
- Added assertions that linked care-order panel exposes clinical-awareness continuity only and does not show pickup/admin mutation actions.
- Added conditional availability coverage for linked encounter CTA (present only for active valid booking/encounter context).
- Added stale/manual linked encounter callback bounded behavior test via legacy callback path.
- Existing DOC-A3A/B encounter completion tests remained green (no regression).
- Added DOC-A3C no-migration artifact guard test.

## Environment / full execution note
- No environment blocker prevented targeted test execution in this PR scope.

## DOC-A3 closure statement
- **DOC-A3 is now considered closed** for the bounded doctor continuity scope (A3A + A3B + A3C) under the specified non-goals and no-migration constraint.
