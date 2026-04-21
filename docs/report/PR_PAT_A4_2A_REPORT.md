# PR PAT-A4-2A Report — Patient reschedule slot selection flow

## What changed
- Replaced `rsch:start:*` placeholder continuation with a real slot-selection panel for active `reschedule_booking_control` sessions.
- Extended patient runtime flow state with `reschedule_booking_id` so the source booking context is preserved during reschedule slot-selection/review.
- Updated `book:slot:*` callback handling to support both new-booking and reschedule route types, with route-type-specific callback validation.
- Kept reschedule sessions in `reschedule_booking_control` after slot selection (no contact prompt fallback), then rendered a dedicated reschedule review panel.
- Added a bounded reschedule confirm CTA callback (`rsch:confirm:*`) that responds with localized placeholder feedback (non-crashing, non-dead behavior) pending PAT-A4-2B.
- Added compact localized copy for reschedule slot prompt, review panel, labels, and confirm-step placeholder in `en` and `ru` locales.

## Exact files changed
- `app/interfaces/bots/patient/router.py`
- `app/application/booking/telegram_flow.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_patient_reschedule_start_pat_a4_1.py`
- `docs/report/PR_PAT_A4_2A_REPORT.md`

## How source booking context is preserved
- On entering reschedule mode via `_start_reschedule_mode_and_render_panel(...)`, runtime patient flow state now stores:
  - `booking_session_id` (reschedule session id)
  - `booking_mode = "reschedule_booking_control"`
  - `reschedule_booking_id` (source booking id being moved)
- This context is used in `_render_reschedule_review_panel(...)` to render current booking datetime vs selected new slot datetime without schema/database changes.

## How reschedule slot selection differs from new-booking slot selection
- New booking:
  - `book:slot:*` success -> mode changes to `existing_booking_control` -> contact prompt shown.
- Reschedule booking:
  - `book:slot:*` success -> mode remains `reschedule_booking_control` -> dedicated reschedule review panel shown.
  - No contact prompt is shown.
- Slot callback validation now uses route-type-aware allowed set:
  - `service_first` for new booking
  - `reschedule_booking_control` for reschedule

## Tests added/updated
- Updated `tests/test_patient_reschedule_start_pat_a4_1.py` with targeted assertions for PAT-A4-2A:
  1. Source booking id is persisted in flow state when reschedule mode starts.
  2. `rsch:start:*` opens real slot selection panel text instead of placeholder.
  3. Selecting a slot in reschedule flow does not show contact prompt and lands in reschedule review panel.
- Existing PAT-A4-1 safety tests (stale callback, bounded contact behavior, no migrations) remain intact.

## Environment / test execution note
- Ran focused pytest execution for the modified patient reschedule test module successfully in this environment.
- Full-suite execution was intentionally not run to keep this PR narrow and bounded to PAT-A4-2A acceptance criteria.

## Explicit non-goals left for PAT-A4-2B / PAT-A4-2C
- No final atomic reschedule completion (old-slot release / new-slot commit) in this PR.
- No reminder engine redesign.
- No booking state machine redesign.
- No broadening scope to doctor/branch/service changes.
- No admin/doctor/owner flow changes.
- No migrations.
