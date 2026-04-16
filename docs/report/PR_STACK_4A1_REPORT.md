# PR Stack 4A1 Report — Reminder Planning Integrity

## 1. Objective
Implement a narrow integrity fix to ensure booking mutations and reminder plan mutations are coherent, prevent post-commit reminder-planning failures from surfacing as user-visible errors after booking state has already changed, and cancel all still-unsent scheduled reminders regardless of whether `scheduled_for` is in the past or future.

## 2. Docs Read
Read and applied (requested precedence order):
- `README.md`
- `docs/18_development_rules_and_baseline.md`
- `docs/10_architecture.md`
- `docs/12_repo_structure_and_code_map.md`
- `docs/25_state_machines.md`
- `docs/30_data_model.md`
- `docs/35_event_catalog.md`
- `docs/23_policy_and_configuration_model.md`
- `docs/80_integrations_and_infra.md`
- `docs/85_security_and_privacy.md`
- `docs/90_pr_plan.md`
- `docs/95_testing_and_launch.md`
- `docs/report/PR_STACK_4A_REPORT.md`
- `booking_docs/*`

## 3. Scope Implemented
- Moved reminder plan create/cancel/replace integration for finalize/reschedule/cancel/completed/no_show into the same booking transaction boundary.
- Added transaction-aware reminder planning/cancellation methods in application service layer.
- Added booking transaction methods that write/cancel reminder jobs in `communication.reminder_jobs` within the same DB transaction.
- Updated reminder cancellation semantics to cancel **all** `status='scheduled'` jobs for a booking (not only those with `scheduled_for > now`).
- Strengthened tests for reminder planning failure rollback and stale scheduled reminder cleanup semantics.

## 4. Chosen Reminder-Planning Integrity Strategy
**Option A: Transaction-bound reminder planning**.

Reminder planning/cancel/replacement now executes inside the booking mutation transaction for all relevant booking lifecycle operations in this stack. If reminder planning raises, the transaction rolls back and booking/session/history changes do not commit.

## 5. Transaction / Outcome Handling Notes
- Finalize now plans reminders in-transaction after booking/session/hold writes and before transaction exit.
- `request_booking_reschedule`, `cancel_booking`, `reschedule_booking`, `complete_booking`, and `mark_booking_no_show` now cancel/replace reminder plans inside the same transaction as booking status/time updates.
- This removes the prior post-commit side effect pattern that could leave committed booking changes with a raised reminder-planning exception.
- Raw exceptions can still surface, but they no longer occur after booking state was already committed in these paths.

## 6. Scheduled Cleanup Rule
In Stack 4A1, reminder cleanup rule is:
- On cancel/replace flows, cancel **all** reminder rows where `booking_id = ?` and `status = 'scheduled'`, regardless of `scheduled_for` timestamp.

Rationale:
- In current Stack 4A baseline there is no delivery engine; therefore `scheduled` means unsent.
- Past-due scheduled rows are still unsent work and must be canceled to avoid stale sends in future delivery stacks.

## 7. Files Added
- `docs/report/PR_STACK_4A1_REPORT.md`

## 8. Files Modified
- `app/application/booking/orchestration.py`
- `app/application/communication/reminders.py`
- `app/infrastructure/db/booking_repository.py`
- `app/infrastructure/db/communication_repository.py`
- `tests/test_booking_orchestration.py`

## 9. Commands Run
- `pytest -q tests/test_booking_orchestration.py`
- `pytest -q tests/test_booking_patient_flow_stack3c1.py`

## 10. Test Results
- `tests/test_booking_orchestration.py`: passed (21 tests)
- `tests/test_booking_patient_flow_stack3c1.py`: passed (13 tests)

## 11. Remaining Known Limitations
- Reminder delivery execution is still intentionally not implemented in this stack.
- Acknowledgement UI/actions are still intentionally not implemented.
- Retry/escalation engines are still intentionally not implemented.

## 12. Deviations From Docs (if any)
- No intentional deviations from the requested architectural truth boundaries.

## 13. Readiness Assessment for PR Stack 4B
Ready for Stack 4B work with integrity precondition addressed:
- Booking/reminder planning no longer follows an unprotected post-commit side effect pattern in covered lifecycle operations.
- Unsent scheduled reminder cleanup semantics are safe for introducing delivery behavior next.
- Reminder truth remains in `communication` and booking truth remains in `booking.bookings`.
