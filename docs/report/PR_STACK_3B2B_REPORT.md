# PR Stack 3B2B Report: Booking Hold Switch Integrity

## 1. Objective
Deliver a narrow orchestration integrity pass that guarantees one active hold per booking session, makes same-session slot reselection atomic, prevents orphaned active holds during slot switching, and tightens `review_ready` preconditions to require a real active selected hold.

## 2. Docs Read
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/10_architecture.md
4. docs/12_repo_structure_and_code_map.md
5. docs/25_state_machines.md
6. docs/20_domain_model.md
7. docs/30_data_model.md
8. docs/35_event_catalog.md
9. docs/90_pr_plan.md
10. docs/report/PR_STACK_3A_REPORT.md
11. docs/report/PR_STACK_3B1_REPORT.md
12. docs/report/PR_STACK_3B2_REPORT.md
13. docs/report/PR_STACK_3B2A_REPORT.md
14. booking_docs/40_booking_state_machine.md
15. booking_docs/booking_test_scenarios.md

## 3. Scope Implemented
- Added DB-level active-hold-per-session guard in baseline schema.
- Added transaction helper for loading active holds by booking session under lock.
- Updated `select_slot_and_activate_hold` to support atomic same-session slot switching and deterministic same-slot reuse behavior.
- Tightened `mark_session_review_ready` to validate selected hold existence, ownership, active state, and slot coherence.
- Strengthened cancel/expire robustness to release/expire all active holds for a session in-transaction.
- Added behavior-focused tests for reselection integrity, active-hold uniqueness outcomes, and review-ready hold-state checks.

## 4. Session Hold Integrity Strategy
- Slot selection now first inspects active holds on the target slot and rejects only if another session owns an active hold.
- In the same transaction, all active holds for the current session are loaded and any active hold on a different slot is transitioned via `SlotHoldStateService` to `released` before the new selection is activated.
- Same-session/same-slot with an already active hold now reuses the active hold directly (no duplicate hold creation).
- Same-session/same-slot with only terminal historical hold continues to create a fresh hold record.
- Session selected fields are updated only after hold state is coherent.

## 5. DB Guard Strategy
Baseline DDL now includes a partial unique index:
- `uq_slot_holds_active_session` on `booking.slot_holds(booking_session_id)` where `status='active'`.

This complements existing guards:
- `uq_slot_holds_active_slot`
- `uq_bookings_live_slot`

Together, slot-truth now includes both slot-level and session-level active-hold constraints.

## 6. ReviewReady Validation Tightening
`mark_session_review_ready` now requires:
- `selected_slot_id` and `selected_hold_id` present,
- selected hold exists,
- selected hold belongs to the same session,
- selected hold is `active`,
- selected hold `slot_id` matches `selected_slot_id`,
- existing patient/contact preconditions remain enforced.

If hold state is stale/terminal/mismatched, the command returns typed `InvalidStateOutcome`.

## 7. Files Added
- `docs/report/PR_STACK_3B2B_REPORT.md`

## 8. Files Modified
- `app/infrastructure/db/bootstrap.py`
- `app/infrastructure/db/booking_repository.py`
- `app/application/booking/orchestration.py`
- `tests/test_booking_db_guards.py`
- `tests/test_booking_orchestration.py`

## 9. Commands Run
- `pytest -q tests/test_booking_orchestration.py tests/test_booking_db_guards.py tests/test_booking_state_engine.py tests/test_booking_db_repository.py tests/test_booking_application_foundation.py`

## 10. Test Results
- Targeted booking integrity pack passed.
- Result: `29 passed, 0 failed`.

## 11. Remaining Known Limitations
- No Telegram booking flow wiring was added (intentional non-goal).
- No reminder scheduling/execution changes were added (intentional non-goal).
- No Stack 3C scope expansion was introduced.

## 12. Deviations From Docs (if any)
- None intentional.

## 13. Readiness Assessment for PR Stack 3C
- **Ready on this integrity gate:** same session slot reselection no longer silently leaves multiple active holds, `review_ready` now verifies real active hold truth, and baseline DB includes explicit one-active-hold-per-session protection.
