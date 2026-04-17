# PR Stack 8A Report — Event / Projection Foundation

## 1. Objective
Implement canonical internal outbox/projector foundation with transaction-safe event emission, projector checkpoints, analytics raw ledger, incremental patient search projection updates, replay tooling, and the Stack 7A1 carry-forward doctor queue local-day fix.

## 2. Docs Read
- README.md
- docs/18_development_rules_and_baseline.md
- docs/10_architecture.md
- docs/12_repo_structure_and_code_map.md
- docs/35_event_catalog.md
- docs/report/PR_STACK_7A_REPORT.md
- docs/report/PR_STACK_7A1_REPORT.md

## 3. Precedence Decisions
- Kept baseline-only DB discipline by editing `app/infrastructure/db/bootstrap.py` in-place.
- Maintained transactional truth as primary and projections as derived/rebuildable.
- Implemented DB-backed outbox only (no external event bus).

## 4. Outbox Schema Summary
- Added `system_runtime.event_outbox` with monotonic PK, stable event id, envelope metadata, payload JSON, status, and failure fields.
- Added `system_runtime.projector_checkpoints` and `system_runtime.projector_failures`.
- Added `analytics_raw.event_ledger` compact append-only analytics event table.

## 5. Event Envelope Strategy
- Added canonical typed envelope (`EventEnvelope`) and builder (`build_event`) in `app/domain/events.py`.
- Explicit serializer/deserializer via `to_record` / `from_record`.

## 6. Emitted Event Coverage
Implemented core emission in mutation paths for:
- Patient: created/updated/contact/preference/flag/photo events.
- Booking: created and status-derived booking events (confirmed, reschedule requested, canceled, checked in, in service started, completed, no-show marked).
- Reminder: scheduled/sent/acknowledged/failed/canceled.

Clinical and reference events are left for follow-up expansion.

## 7. Projector Framework Design
- Added `ProjectorRunner` processing outbox events in order.
- Per-projector checkpoint persistence.
- Stop-on-failure behavior and outbox failure marking.

## 8. Analytics Ledger Strategy
- Added `AnalyticsEventLedgerProjector` to write compact, dedupe-safe rows to `analytics_raw.event_ledger` keyed by `event_id`.

## 9. Search Projector Strategy
- Added incremental `PatientSearchProjector` for patient-family events.
- Existing full rebuild path remains via `SearchProjectionRebuilder` + rebuild scripts.

## 10. Replay / Run Tooling
- Added `scripts/process_outbox_events.py` to process pending outbox through configured projectors.
- Added `scripts/replay_projector.py` to inspect/reset projector checkpoints.

## 11. Carry-Forward Timezone Fix Notes
- Implemented local-day window logic (`DoctorTimezoneFormatter.local_day_utc_window`).
- `DoctorOperationsService.list_today_queue(...)` now derives UTC query windows from branch→clinic→app-default timezone resolution.
- `get_next_patient(...)` now benefits from corrected queue window.

## 12. Files Added
- app/domain/events.py
- app/infrastructure/outbox/repository.py
- app/projections/runtime/projectors.py
- app/projections/runtime/__init__.py
- app/projections/analytics/event_ledger_projector.py
- app/projections/analytics/__init__.py
- app/projections/search/patient_event_projector.py
- scripts/process_outbox_events.py
- scripts/replay_projector.py
- tests/test_event_projection_stack8a.py
- docs/report/PR_STACK_8A_REPORT.md

## 13. Files Modified
- app/infrastructure/db/bootstrap.py
- app/application/timezone.py
- app/application/doctor/operations.py
- app/application/clinic_reference.py
- app/application/booking/state_services.py
- app/application/booking/orchestration.py
- app/infrastructure/db/booking_repository.py
- app/infrastructure/db/communication_repository.py
- app/infrastructure/db/patient_repository.py
- app/projections/search/__init__.py
- tests/test_db_bootstrap.py
- tests/test_doctor_operational_stack6a.py

## 14. Commands Run
- `python -m py_compile ...`
- `pytest -q tests/test_event_projection_stack8a.py tests/test_doctor_operational_stack6a.py tests/test_db_bootstrap.py`

## 15. Test Results
- Added stack-specific unit coverage for envelope roundtrip, projector checkpoint/failure behavior, DB baseline declarations, and doctor queue timezone window behavior.

## 16. Known Limitations / Explicit Non-Goals
- No owner dashboards/UI.
- No external event bus.
- No broad product analytics UX.
- Clinical and doctor/service event catalog coverage is partial in this stack.

## 17. Deviations From Docs (if any)
- None intentional; where coverage is partial it is documented as limitation.

## 18. Readiness Assessment for PR Stack 9A
- Event/outbox/projector backbone is in place for incremental expansion.
- Patient search incremental projection and analytics raw ledger foundations are operational.
- Additional event catalog coverage can now be layered without architectural rewrites.
