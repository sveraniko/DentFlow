# PR Stack 3B2 Report: Booking Orchestration Core

## 1. Objective
Implement transaction-scoped booking orchestration services on top of Stack 3A persistence and Stack 3B1 lifecycle state services, including slot-truth protections, typed command outcomes, and core booking/session/hold commands.

## 2. Docs Read
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/10_architecture.md
4. docs/12_repo_structure_and_code_map.md
5. docs/25_state_machines.md
6. docs/20_domain_model.md
7. docs/30_data_model.md
8. docs/35_event_catalog.md
9. docs/40_search_model.md
10. docs/22_access_and_identity_model.md
11. docs/23_policy_and_configuration_model.md
12. docs/70_bot_flows.md
13. docs/80_integrations_and_infra.md
14. docs/85_security_and_privacy.md
15. docs/90_pr_plan.md
16. docs/report/PR_STACK_3A_REPORT.md
17. docs/report/PR_STACK_3B1_REPORT.md
18. booking_docs/10_booking_flow_dental.md
19. booking_docs/20_booking_domain_model.md
20. booking_docs/30_booking_routing_and_slot_ranking.md
21. booking_docs/40_booking_state_machine.md
22. booking_docs/booking_api_contracts.md
23. booking_docs/booking_test_scenarios.md

## 3. Precedence Decisions
- Lifecycle mutation authority was kept in Stack 3B1 state services and not duplicated in orchestration.
- Slot-truth status sets for live booking occupancy were aligned with canonical final booking statuses and PR instructions.
- Patient truth remained fully externalized to `core_patient` via booking-facing patient resolution service (no booking-local patient table/model introduced).

## 4. Orchestration Commands Added
- `start_booking_session`
- `update_session_context`
- `resolve_patient_for_session`
- `select_slot_and_activate_hold`
- `release_or_expire_hold_for_session`
- `mark_session_review_ready`
- `finalize_booking_from_session`
- `cancel_session`
- `expire_session`
- `escalate_session_to_admin`
- `create_waitlist_entry`
- `request_booking_reschedule`
- `cancel_booking`

## 5. Transaction Boundary Strategy
- Added transaction-scoped load/lock methods in DB unit-of-work:
  - `get_booking_session_for_update`
  - `get_slot_hold_for_update`
  - `get_booking_for_update`
  - `get_availability_slot_for_update`
  - `get_waitlist_entry_for_update`
  - `find_slot_hold_for_update`
  - active hold/live booking slot scans under transaction.
- All multi-entity orchestration commands run inside one transaction context.
- Stack 3B1 state services were extended with `*_in_transaction(...)` methods so orchestration can preserve lifecycle authority and still stay atomic.

## 6. Slot-Truth Protection Strategy
- Added DB partial unique index for one active hold per slot:
  - `uq_slot_holds_active_slot` on `booking.slot_holds(slot_id)` where `status='active'`.
- Added DB partial unique index for one live booking per slot:
  - `uq_bookings_live_slot` on `booking.bookings(slot_id)` where status in:
    `pending_confirmation`, `confirmed`, `reschedule_requested`, `checked_in`, `in_service`.
- Orchestration also checks live bookings + active holds in-transaction before hold activation/finalization.

## 7. Typed Outcome Design
- Added explicit typed orchestration outcomes:
  - `OrchestrationSuccess`
  - `NoMatchOutcome`
  - `AmbiguousMatchOutcome`
  - `SlotUnavailableOutcome`
  - `ConflictOutcome`
  - `EscalatedOutcome`
  - `InvalidStateOutcome`
- Used in session/hold/finalization and escalation flows to avoid dict-based implicit returns.

## 8. Policy Integration Notes
- Booking creation uses `booking.confirmation_required` policy resolution.
- Review readiness consults `booking.contact_confirmation_required`; defaults to falsy when not configured.
- Reminder execution is intentionally not implemented in this stack.

## 9. Files Added
- `app/application/booking/orchestration.py`
- `app/application/booking/orchestration_outcomes.py`
- `tests/test_booking_orchestration.py`
- `tests/test_booking_db_guards.py`
- `docs/report/PR_STACK_3B2_REPORT.md`

## 10. Files Modified
- `app/application/booking/state_services.py`
- `app/infrastructure/db/booking_repository.py`
- `app/infrastructure/db/bootstrap.py`
- `app/application/booking/__init__.py`
- `app/bootstrap/runtime.py`

## 11. Commands Run
- `pytest -q tests/test_booking_state_engine.py tests/test_booking_orchestration.py tests/test_booking_db_guards.py tests/test_booking_db_repository.py tests/test_booking_application_foundation.py`

## 12. Test Results
- Targeted stack tests passed locally for lifecycle, orchestration behavior, rollback behavior, and DB guard declarations.

## 13. Known Limitations / Explicit Non-Goals
- No Telegram flow orchestration/UI implemented.
- No reminder scheduling/execution implemented.
- No slot ranking/routing heuristics implemented.
- No reschedule replacement-slot orchestration implemented.
- No check-in/in-service/completed operational flows added beyond core transition support.

## 14. Deviations From Docs (if any)
- `booking.contact_confirmation_required` is consulted as an optional policy key even though not present in default baseline values; behavior safely falls back to false.

## 15. Readiness Assessment for PR Stack 3C
- Ready for stack 3C flow wiring:
  - command surface is explicit and typed,
  - lifecycle authority remains centralized in state services,
  - slot truth has DB + transactional guards,
  - finalization path is atomic and canonical.
