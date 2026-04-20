# PR 12B-1 Report — Admin/Doctor linked-open convergence

## What was changed

- Replaced admin booking linked-open placeholders for recommendation and care order with bounded, localized panels:
  - recommendation panel now uses booking-linked lookup (`list_for_booking`) and deterministic newest selection.
  - care-order panel now resolves patient orders, filters to exact `booking_id`, selects newest deterministically, and renders via care-order card runtime builders/adapters.
- Replaced doctor booking linked-open placeholder/minimal outputs with bounded, localized panels using the same booking-linked recommendation and care-order logic.
- Preserved linked back navigation from linked object panel back to booking card.
- Added optional dependency wiring:
  - admin router now accepts optional `recommendation_service`.
  - doctor router now accepts optional `care_commerce_service`.
  - runtime wiring now passes both services into corresponding routers.
- Added minimal i18n keys required for staff linked recommendation/care-order panels and missing states in EN/RU.

## Exact files changed

- `app/interfaces/bots/admin/router.py`
- `app/interfaces/bots/doctor/router.py`
- `app/bootstrap/runtime.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_booking_linked_opens_12b1.py`

## Tests added/updated

- Added: `tests/test_booking_linked_opens_12b1.py`
  - covers admin `open_recommendation` and `open_care_order` no-placeholder behavior
  - covers doctor `open_recommendation` and `open_care_order` no-placeholder/minimal behavior
  - verifies back button remains present in linked panels
  - verifies bounded missing-state behavior for absent linked recommendation/care order

## Environment / execution notes

- No migrations were added in this PR.
- Full suite execution may still depend on local environment and optional services; targeted test execution was used for this PR scope.

## Known non-goals intentionally left for 12B-2

- Document delivery seam hardening (`open/download`) remains for 12B-2.
- No patient-facing document surface changes.
- No integration UI expansion (calendar/sheets) in this PR.
