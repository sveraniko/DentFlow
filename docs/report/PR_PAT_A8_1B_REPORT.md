# PR PAT-A8-1B Report — Reserve success continuity to canonical current order

## What changed
- Added direct patient callback `careo:open:<care_order_id>` in patient router.
- Implemented bounded ownership-safe handler for `careo:open:*`:
  - resolves patient identity,
  - validates order ownership,
  - opens canonical care-order detail card when valid,
  - shows bounded alert when invalid/foreign/missing.
- Replaced reserve success text-only finish with a continuity panel in `_reserve_product(...)`.
- Reserve success now shows compact patient-facing copy:
  - product,
  - pickup branch label,
  - human-readable localized order status,
  - next-step hint.
- Reserve success now includes explicit CTA buttons:
  1. `Open current order` -> `careo:open:<care_order_id>`
  2. `My reserves / orders` -> `care:orders`
- Recommendation-linked reserve path keeps direct reserve semantics and now lands on the same continuity panel (via shared `_reserve_product(...)` path).

## Exact files changed
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `tests/test_patient_care_ui_cc4c.py`

## How reserve success continuity now works
1. Patient taps reserve.
2. Existing domain path remains intact: create order -> transition to confirmed -> create reservation.
3. Instead of ending with text-only success, router renders continuity panel with two CTAs:
   - open newly created current order (`careo:open:*`)
   - open canonical orders surface (`care:orders`).

## How `careo:open:*` ownership safety is enforced
- Callback handler resolves patient identity from Telegram user.
- Fetches target order by id.
- Compares order `patient_id` with resolved patient.
- If mismatch/missing/invalid id: bounded user alert, no technical details.
- If valid: renders the same canonical care-order detail/card surface used by existing order list navigation.

## Tests added/updated
- `tests/test_patient_home_surface_pat_a1_2.py`
  - reserve success panel includes continuity CTAs;
  - recommendation-linked reserve uses same continuity and forwards recommendation id in create-order payload;
  - `careo:open:*` opens canonical detail for owner and is denied for foreign patient.
- `tests/test_patient_care_ui_cc4c.py`
  - localized continuity CTA labels exist for EN/RU.

## Environment / execution notes
- Targeted tests were run for changed patient-care continuity behavior.
- No migrations added.

## Explicit non-goals intentionally left for PAT-A8-2A / PAT-A8-2B
- No proactive pickup-ready Telegram push notifications yet.
- No pickup state-machine redesign.
- No payment/checkout changes.
- No recommendation engine redesign.
- No care-commerce domain redesign.
- No admin/doctor/owner flow changes.
- No migrations.
