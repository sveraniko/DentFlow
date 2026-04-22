# PR ADM-A3A Report — Admin linked recommendation panel actionability

## What changed
- Added a dedicated admin linked-recommendation keyboard for booking-linked recommendation open.
- Replaced Back-only keyboard on linked recommendation panel with actionable continuity CTAs:
  - Open patient (always shown)
  - Open related care order (shown only when booking-linked care order is resolvable)
  - Back (always shown)
- Kept recommendation panel body rendering unchanged.
- Reused canonical booking callback surfaces (`_encode_booking_callback`) and existing booking page actions (`open_patient`, `open_care_order`, `open_booking`) instead of introducing parallel viewers.

## Exact files changed
- `app/interfaces/bots/admin/router.py`
- `tests/test_booking_linked_opens_12b1.py`
- `docs/report/PR_ADM_A3A_REPORT.md`

## How recommendation panel actionability is wired now
- Added `_admin_linked_recommendation_keyboard(...)` and switched `open_recommendation` to use it.
- Keyboard wiring:
  - **Open patient** -> canonical booking callback with `CardAction.OPEN_PATIENT`, `page_or_index="open_patient"`.
  - **Open care order** -> canonical booking callback with `CardAction.OPEN_CARE_ORDER`, `page_or_index="open_care_order"`.
  - **Back** -> canonical booking callback with `CardAction.OPEN`, `page_or_index="open_booking"`.
- This preserves source/state-token discipline from the existing booking callback codec path.

## How related care-order presence is resolved
- Added bounded helper `_resolve_latest_linked_care_order(...)` in admin router.
- Resolution reuses existing linked care-order truth pattern:
  1. list patient orders (`list_patient_orders`),
  2. filter by exact `booking_id`,
  3. choose deterministic newest via `_select_latest_care_order(...)`.
- Helper is reused by both:
  - linked recommendation CTA presence decision,
  - linked care-order panel rendering.

## Tests added/updated
- Updated `tests/test_booking_linked_opens_12b1.py` with minimal targeted coverage:
  1. linked recommendation panel now shows actionable CTAs (not Back-only),
  2. Open patient CTA from linked recommendation lands on canonical patient context,
  3. Open care-order CTA opens canonical linked care-order panel,
  4. care-order CTA is hidden when no linked order exists,
  5. manually crafted `open_care_order` callback without linked order remains bounded (no crash; missing panel + Back).

## Environment / execution
- Focused linked-open tests were run.
- Full repository suite was not executed in this bounded PR.
- No environment blocker prevented targeted execution.

## Explicit non-goals intentionally left for ADM-A3B
- No care-order -> pickup queue/detail bridge.
- No recommendation lifecycle action redesign.
- No recommendation engine/domain semantics redesign.
- No broad admin workdesk redesign.
- No doctor/owner/calendar flow changes.
- No migrations.
