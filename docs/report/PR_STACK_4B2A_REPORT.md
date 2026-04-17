# PR Stack 4B2A Report — Reminder Action Atomicity

## 1. Objective
Deliver a narrow transactional integrity fix so interactive reminder actions no longer perform booking mutation first and reminder acknowledgement as a loose follow-up side effect. Booking action acceptance and reminder acknowledgement are now executed inside one transaction boundary for coherent success/failure behavior.

## 2. Docs Read
1. `README.md`
2. `docs/18_development_rules_and_baseline.md`
3. `docs/10_architecture.md`
4. `docs/12_repo_structure_and_code_map.md`
5. `docs/25_state_machines.md`
6. `docs/30_data_model.md`
7. `docs/35_event_catalog.md`
8. `docs/80_integrations_and_infra.md`
9. `docs/85_security_and_privacy.md`
10. `docs/90_pr_plan.md`
11. `docs/95_testing_and_launch.md`
12. `docs/report/PR_STACK_4A_REPORT.md`
13. `docs/report/PR_STACK_4A1_REPORT.md`
14. `docs/report/PR_STACK_4B1_REPORT.md`
15. `docs/report/PR_STACK_4B2_REPORT.md`
16. `booking_docs/*` (targeted: readme/domain/state/contracts/tests)

## 3. Scope Implemented
- Reworked reminder action handling to execute validation, booking mutation bridge call, and reminder acknowledgement under a shared DB transaction.
- Added transaction-aware reminder methods on the booking unit-of-work to lock/read and acknowledge reminder rows in `communication` schema within the same transaction used for booking mutations.
- Added transaction-entry methods on booking orchestration for `confirm`, `reschedule request`, and `cancel` so reminder callbacks can use canonical booking transitions without nested/independent transactions.
- Updated runtime wiring and communication exports accordingly.
- Expanded reminder action tests for atomic rollback behavior and duplicate/stale safety.

## 4. Reminder Action Atomicity Strategy
Chosen strategy: **transaction-bound reminder action bridge**.

Flow now:
1. Open one booking repository transaction.
2. Lock/read reminder (`FOR UPDATE`) and validate actionability/message identity.
3. For booking actions, run canonical booking orchestration transition **inside same transaction**.
4. Acknowledge reminder in same transaction.
5. Commit once.

Consequence: if acknowledgement write fails, the booking mutation in that callback path is rolled back; no committed half-success with post-booking failure.

## 5. Transaction Boundary Notes
- Added tx methods in `DbBookingUnitOfWork`:
  - `get_reminder_for_update_in_transaction`
  - `mark_reminder_acknowledged_in_transaction`
  - `has_sent_delivery_for_provider_message_in_transaction`
- Added tx-entry methods in `BookingOrchestrationService`:
  - `confirm_booking_in_transaction`
  - `request_booking_reschedule_in_transaction`
  - `cancel_booking_in_transaction`
- Existing public orchestration methods still open transactions and delegate to these tx-entry methods, preserving previous API behavior.

## 6. Duplicate/Stale Safety Notes
- Already acknowledged/canceled/failed/expired reminders remain stale-safe.
- Duplicate confirm/cancel/reschedule callback on same reminder remains safe because first accepted action acknowledges reminder and subsequent callback sees stale terminal reminder status.
- Message mismatch validation still blocks invalid callbacks.

## 7. Files Added
- `docs/report/PR_STACK_4B2A_REPORT.md`

## 8. Files Modified
- `app/application/communication/actions.py`
- `app/application/booking/orchestration.py`
- `app/infrastructure/db/booking_repository.py`
- `app/bootstrap/runtime.py`
- `app/application/communication/__init__.py`
- `tests/test_reminder_actions_stack4b2.py`

## 9. Commands Run
- `pytest -q tests/test_reminder_actions_stack4b2.py tests/test_booking_orchestration.py`
- `pytest -q tests/test_runtime_wiring.py tests/test_reminder_delivery_stack4b1.py`

## 10. Test Results
- `tests/test_reminder_actions_stack4b2.py`: pass
- `tests/test_booking_orchestration.py`: pass
- `tests/test_runtime_wiring.py`: pass
- `tests/test_reminder_delivery_stack4b1.py`: pass

## 11. Remaining Known Limitations
- This stack does not add retry/escalation engines, provider fallback, or new callback UX.
- Atomicity is at the current single-database transaction level; cross-system delivery/provider effects are out of scope.

## 12. Deviations From Docs (if any)
- No intentional deviations.

## 13. Readiness Assessment for Booking Base RC1
For reminder callback action integrity specifically, readiness is improved:
- booking action + reminder acknowledgement are no longer loose post-commit side effects in the callback path.
- duplicate/stale behavior remains safe.

Booking-base RC1 readiness still depends on broader stacks outside this PR, but the specific 4B2 atomicity gap targeted here is addressed.
