# PR Stack 4A Report — Reminder Scheduling Baseline

## 1. Objective
Implement the canonical reminder scheduling baseline for bookings by introducing communication-owned reminder persistence, policy-aware planning, and booking lifecycle integration hooks that schedule/cancel/replace reminder plans without implementing delivery transport or acknowledgement UX.

## 2. Docs Read
Read and applied (in precedence order):
- `README.md`
- `docs/18_development_rules_and_baseline.md`
- `docs/10_architecture.md`
- `docs/12_repo_structure_and_code_map.md`
- `docs/25_state_machines.md`
- `docs/30_data_model.md`
- `docs/35_event_catalog.md`
- `docs/23_policy_and_configuration_model.md`
- `docs/70_bot_flows.md`
- `docs/80_integrations_and_infra.md`
- `docs/85_security_and_privacy.md`
- `docs/90_pr_plan.md`
- `docs/95_testing_and_launch.md`
- prior stack reports under `docs/report/`
- booking docs under `booking_docs/`

## 3. Precedence Decisions
1. Reminder truth was implemented only in `communication` tables (not inside `booking`) per `README` + data model guidance.
2. Reminder scheduling was integrated at orchestration/application service layer, not bot handler layer.
3. Policy-driven offsets/channel/locale were used via `PolicyResolver` and patient preferences fallback semantics.
4. No delivery execution, retry, acknowledgement UI, or escalation runner was implemented in this stack.

## 4. Reminder Model Summary
Implemented canonical communication reminder model with:
- `communication.reminder_jobs` for scheduled/canceled reminder intent lifecycle (plus future-safe statuses in table check).
- `communication.message_deliveries` baseline persistence table for next-stack delivery tracking.
- Domain models: `ReminderJob`, `MessageDelivery`.
- DB repository: `DbReminderJobRepository` with create/list/cancel operations.

## 5. Scheduling Policy Strategy
Planner/service behavior:
- Uses `booking.confirmation_required` + `booking.confirmation_offset_hours` to schedule confirmation reminder when valid.
- Uses `booking.reminder_offsets_hours` to schedule previsit/day-of reminder jobs.
- Channel resolution:
  - patient preferred channel if allowed by patient channel permissions
  - fallback to clinic policy/default channel (`booking.default_reminder_channel` if set, else `telegram`)
- Locale resolution:
  - patient preferred language when available
  - fallback to clinic default locale (`clinic.default_locale`)

## 6. Booking Integration Points
Integrated reminder planning hooks in booking orchestration:
- finalize booking: create reminder plan for pending/confirmed booking states.
- request reschedule: cancel pending scheduled jobs.
- explicit reschedule operation: cancel + replace reminder plan for new booking time.
- booking cancel: cancel future scheduled jobs.
- completed/no_show transitions: cancel future scheduled jobs.

## 7. Files Added
- `app/domain/communication/models.py`
- `app/application/communication/reminders.py`
- `app/infrastructure/db/communication_repository.py`
- `docs/report/PR_STACK_4A_REPORT.md`

## 8. Files Modified
- `app/domain/communication/__init__.py`
- `app/application/communication/__init__.py`
- `app/infrastructure/db/bootstrap.py`
- `app/application/booking/orchestration.py`
- `app/bootstrap/runtime.py`
- `app/infrastructure/db/patient_repository.py`
- `tests/test_booking_orchestration.py`

## 9. Commands Run
- `pytest -q tests/test_booking_orchestration.py`
- `pytest -q tests/test_booking_patient_flow_stack3c1.py`

## 10. Test Results
- `tests/test_booking_orchestration.py`: passed (19 tests)
- `tests/test_booking_patient_flow_stack3c1.py`: passed (13 tests)

## 11. Known Limitations / Explicit Non-Goals
Not implemented in this stack (intentional):
- reminder message delivery transport (Telegram/SMS/email)
- queue/worker dispatch runtime
- acknowledgement buttons/UI (“on my way”)
- retry/error workflow execution
- non-response escalation execution
- reminder analytics/admin UI

## 12. Deviations From Docs (if any)
- Added orchestration-level helper methods `reschedule_booking`, `complete_booking`, `mark_booking_no_show` to provide deterministic reminder-plan integration paths for lifecycle tests; no handler-level scheduling was introduced.
- `communication.message_deliveries` created as baseline only and intentionally unused at runtime in this stack.

## 13. Readiness Assessment for PR Stack 4B
Ready for 4B delivery execution work:
- canonical reminder jobs are persisted and queryable
- scheduling/cancel/replacement behavior is policy-aware and test-covered
- transport/delivery table baseline exists for delivery attempts
- orchestration emits reminder planning intents without hardcoding in handlers

Primary 4B follow-ons:
- implement worker/dispatcher for due scheduled jobs
- populate `message_deliveries` attempts and provider IDs
- move reminder status from scheduled -> queued/sent/failed transitions
- add operational telemetry for delivery failures and retries
