# PR PAT-A1-1A Report — Explicit review panel before booking finalize

## What changed
- Stopped automatic booking finalization inside patient contact submission handler.
- Added a dedicated `_render_review_finalize_panel(...)` in patient router to show a user-visible review summary and explicit confirm CTA.
- Added `book:confirm:<session_id>` callback handler that validates session ownership and only then calls finalize.
- Updated resume behavior: `review_finalize` now renders the same review panel helper instead of old text-only resume message.
- Kept existing finalize outcome mapping (`invalid_state`, `slot_unavailable`, `conflict`, `escalated`) and stale callback alert behavior.
- Added minimal i18n keys for review panel copy and confirm CTA in EN/RU.
- Added a focused patient-router test proving contact submission no longer auto-finalizes and renders a review panel with explicit confirm CTA.

## Exact files changed
- `app/interfaces/bots/patient/router.py`
- `app/application/booking/telegram_flow.py`
- `tests/test_booking_patient_flow_stack3c1.py`
- `tests/test_booking_patient_review_confirm_pat_a1_1a.py`
- `locales/en.json`
- `locales/ru.json`

## Tiny read seam for slot/review rendering
- Added a tiny read seam on `BookingFlowReadRepository`: `get_availability_slot(slot_id)`.
- Exposed bounded accessors in `BookingPatientFlowService`:
  - `get_booking_session(...)`
  - `get_availability_slot(...)`
- No broad review model layer was introduced.

## Tests added/updated
- **Added:** `tests/test_booking_patient_review_confirm_pat_a1_1a.py`
  - verifies contact submission stops at review panel
  - verifies review panel has `book:confirm:<session_id>` action
  - verifies no finalize call happens during contact submission
- **Updated:** `tests/test_booking_patient_flow_stack3c1.py`
  - repo fake now includes `get_availability_slot(...)` seam.

## Environment/runtime test constraints
- No environment blockers encountered for the targeted test slice executed in this PR.

## Explicit non-goals intentionally left for later PRs
- **PAT-A1-1B**
  - broader hardening test wave beyond this narrow functional proof
  - broader callback/error edge-case matrix expansion for review/finalize
- **PAT-A1-2 / PAT-A1-3**
  - `/start` entry redesign and first-run intent UX polish
  - success message humanization wave (service/doctor/branch labels in final success text)
  - reminder engine behavior changes
  - admin/doctor/owner flow redesign
  - migrations and schema changes
