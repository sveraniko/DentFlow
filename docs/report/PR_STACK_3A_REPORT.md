# PR Stack 3A Report — Booking Persistence Foundation

## 1. Objective
Build the Booking bounded-context persistence foundation: baseline schema, DB-backed repositories, persistence-oriented app services, typed booking-facing patient resolution, booking seed path, and tests.

## 2. Docs Read
Read in requested precedence order (with emphasis on Stack 3A-relevant sections):
- README.md
- docs/18_development_rules_and_baseline.md
- docs/10_architecture.md
- docs/12_repo_structure_and_code_map.md
- docs/20_domain_model.md
- docs/25_state_machines.md
- docs/30_data_model.md
- docs/22_access_and_identity_model.md
- docs/23_policy_and_configuration_model.md
- docs/40_search_model.md
- docs/70_bot_flows.md
- docs/72_admin_doctor_owner_ui_contracts.md
- docs/80_integrations_and_infra.md
- docs/85_security_and_privacy.md
- docs/90_pr_plan.md
- docs/report/PR_STACK_0_REPORT.md
- docs/report/PR_STACK_1_REPORT.md
- docs/report/PR_STACK_2_REPORT.md
- docs/report/PR_STACK_2A_REPORT.md
- docs/report/PR_STACK_2B_REPORT.md
- booking_docs/20_booking_domain_model.md
- booking_docs/40_booking_state_machine.md
- booking_docs/booking_db_schema.md
- booking_docs/booking_api_contracts.md
- booking_docs/booking_test_scenarios.md
- booking_docs/50_booking_telegram_ui_contract.md

## 3. Precedence Decisions
1. Kept canonical final booking table as `booking.bookings` and canonical status vocabulary from README + data model docs.
2. Kept patient truth in `core_patient` only; Booking uses FK/reference to `core_patient.patients(patient_id)` and typed resolution over patient helpers.
3. Followed baseline-only schema editing in `app/infrastructure/db/bootstrap.py` (no migration chain).
4. Used existing repo TEXT/string ID style instead of introducing UUID-only strategy.

## 4. Scope Implemented
- Added baseline booking schema tables and core indexes/checks.
- Added DB-backed booking repository and seed writer.
- Added application services for booking session, slot, hold, booking, waitlist, and escalation.
- Added typed booking-facing patient resolution contract with `no_match`, `exact_match`, `ambiguous_match`.
- Added runtime wiring for booking repository/services and patient resolution integration.
- Added explicit Stack 3A booking seed JSON + script.
- Added/updated tests for schema, repository behavior, statuses/history, typed resolution, and seed path coherence.

## 5. Booking Table / Schema Summary
Added to baseline bootstrap (`booking` schema):
- booking_sessions
- session_events
- availability_slots
- slot_holds
- bookings
- booking_status_history
- waitlist_entries
- admin_escalations

Notable constraints:
- `booking.bookings.status` check limited to canonical final statuses only.
- `booking.bookings.patient_id` FK references `core_patient.patients(patient_id)`.
- No booking-local patient table introduced.

## 6. Repository and Service Summary
Repository:
- `DbBookingRepository` implements upsert/get/list/append operations for all required booking entities and histories.

Application services:
- `BookingSessionService`
- `AvailabilitySlotService`
- `SlotHoldService`
- `BookingService` (with canonical status validation)
- `WaitlistService`
- `AdminEscalationService`

## 7. Patient Resolution Contract Summary
Added booking-facing typed contract:
- `BookingPatientResolutionService`
- Result kinds: `no_match`, `exact_match`, `ambiguous_match`
- Candidate payload includes patient summaries (`patient_id`, `clinic_id`, `display_name`)
- Supports exact contact and external-id resolution paths.

Patient DB helpers now expose multi-row exact-contact/external-id query helpers so ambiguity is preserved.

## 8. Seed / Bootstrap Strategy
- Added `seeds/stack3_booking.json` with coherent synthetic booking entities tied to existing Stack 1/2 references.
- Added `seed_stack3_booking` and `scripts/seed_stack3_booking.py` for explicit loading.
- No runtime auto-seeding added.

## 9. Runtime Integration Notes
`RuntimeRegistry` now instantiates:
- `DbBookingRepository`
- booking services listed above
- booking patient resolution service backed by DB patient finder adapter

No booking UI flow/state-engine was introduced in runtime.

## 10. Files Added
- app/domain/booking/models.py
- app/application/booking/services.py
- app/application/booking/patient_resolution.py
- app/infrastructure/db/booking_repository.py
- seeds/stack3_booking.json
- scripts/seed_stack3_booking.py
- tests/test_booking_application_foundation.py
- tests/test_booking_db_repository.py
- tests/test_booking_seed_bootstrap.py
- docs/report/PR_STACK_3A_REPORT.md

## 11. Files Modified
- app/domain/booking/__init__.py
- app/application/booking/__init__.py
- app/infrastructure/db/bootstrap.py
- app/infrastructure/db/patient_repository.py
- app/bootstrap/runtime.py
- app/bootstrap/seed.py
- tests/test_db_bootstrap.py
- tests/test_runtime.py
- tests/test_patient_db_helpers.py

## 12. Commands Run
- `pytest -q tests/test_db_bootstrap.py tests/test_booking_application_foundation.py tests/test_booking_db_repository.py tests/test_booking_seed_bootstrap.py tests/test_patient_db_helpers.py tests/test_runtime.py`
- `python -m compileall app tests`

## 13. Test Results
- All targeted Stack 3A tests passed locally in this PR work.

## 14. Known Limitations / Explicit Non-Goals
Not implemented in Stack 3A (by design):
- Booking transition/state invariants engine.
- Slot ranking/policy routing engine.
- Booking bot/UI flow implementation.
- Reminder scheduling/execution behavior.
- Search/fuzzy/voice retrieval logic.

## 15. Deviations From Docs (if any)
- None intentional for Stack 3A scope.

## 16. Risks / Follow-ups for PR Stack 3B
1. Stack 3B should formalize transition guardrails and invariant checks (status transitions, slot/hold consistency, idempotency).
2. Add transactional boundaries for multi-step operations (hold->booking finalize).
3. Expand observability events and projection hooks once state engine is introduced.
4. Tighten JSON payload typing for event/escalation payload fields as contracts stabilize.
