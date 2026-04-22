# PR ADM-A1B Report — Admin issues ownership lifecycle in `/admin_issues`

## What changed
- Implemented callback-driven issue ownership lifecycle in `/admin_issues` for booking-linked operational issues:
  - `take` → marks issue escalation `in_progress` and assigns admin actor.
  - `resolve` → marks issue escalation `resolved` while preserving resolver in escalation payload.
- Kept existing reminder retry behavior intact for `reminder_failed` (`aw4i:retry:*`).
- Added bounded issue-status merge logic in admin queue rendering so UI reflects effective status from durable escalation truth (`open` / `in_progress` / `resolved`) rather than projection status alone.
- Added bounded stale/unsupported lifecycle handling for handcrafted callbacks.
- Added compact RU/EN admin copy for lifecycle actions and bounded failure paths.

## Exact files changed
- `app/application/booking/telegram_flow.py`
- `app/interfaces/bots/admin/router.py`
- `tests/test_admin_aw4_surfaces.py`
- `locales/en.json`
- `locales/ru.json`
- `docs/report/PR_ADM_A1B_REPORT.md`

## Durable issue ownership truth model (no migrations)
- Reused existing `booking.admin_escalations` through `BookingPatientFlowService` helpers:
  - `get_issue_escalation(...)`
  - `get_or_create_issue_escalation(...)`
  - `take_issue_escalation(...)`
  - `resolve_issue_escalation(...)`
- Used deterministic issue-linked escalation IDs: `aes_issue_<issue_type>_<issue_ref_id>`.
- Stored issue linkage in `payload_summary` (no schema changes):
  - `issue_type`
  - `issue_ref_id`
  - `booking_id`
  - `reminder_id` (for reminder failures)
- No projection table writes were introduced as authoritative lifecycle state.

## Effective queue state merge/rendering
- `/admin_issues` now reads projection rows and merges each row with durable escalation status when available.
- Queue filtering (`open` / `in_progress` / `resolved` / `all`) is applied against the effective merged status in UI rendering.
- Lifecycle buttons are shown only for supported booking-linked issue types:
  - `confirmation_no_response`
  - `reminder_failed`
- Unsupported issue kinds intentionally render without dead lifecycle buttons.

## Tests added/updated
- Updated `tests/test_admin_aw4_surfaces.py` with focused coverage for:
  1. lifecycle actions visibility for supported issue types,
  2. take path and in-progress visibility,
  3. resolve path behavior,
  4. retry + lifecycle coexistence,
  5. unsupported issue kinds not rendering dead lifecycle buttons,
  6. stale/unsupported handcrafted callback safety,
  7. queue continuity/back behavior.
- Existing targeted admin queue tests remain passing.

## Environment / execution
- Ran focused tests for touched admin queue surfaces successfully.
- Full test suite not run in this bounded PR.
- No environment blocker prevented targeted execution.

## Explicit non-goals intentionally left for ADM-A1C
- No admin patient-search continuity expansion.
- No linked recommendation/care polish beyond existing bounded behavior.
- No calendar-awareness UX additions.
- No owner/doctor flow changes.
- No escalation platform redesign beyond bounded issue lifecycle helpers.
- No migrations.
