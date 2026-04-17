# PR_STACK_6A1_REPORT

## 1. Objective
Implement Stack 6A1 targeted integrity/privacy fixes for doctor operational surfaces by removing arbitrary patient access paths and replacing stale startup patient reads with fresh DB-backed reads where doctor operations need current patient truth.

## 2. Docs Read
- README.md
- docs/18_development_rules_and_baseline.md
- docs/10_architecture.md
- docs/12_repo_structure_and_code_map.md
- docs/15_ui_ux_and_product_rules.md
- docs/17_localization_and_i18n.md
- docs/22_access_and_identity_model.md
- docs/20_domain_model.md
- docs/30_data_model.md
- docs/40_search_model.md
- docs/70_bot_flows.md
- docs/72_admin_doctor_owner_ui_contracts.md
- docs/80_integrations_and_infra.md
- docs/85_security_and_privacy.md
- docs/90_pr_plan.md
- docs/95_testing_and_launch.md
- docs/report/PR_STACK_6A_REPORT.md
- BOOKING_BASE_MANIFEST.md (not present)
- booking-base-v1.md (not present)

## 3. Scope Implemented
- Added doctor-safe patient visibility guard for quick-card access paths.
- Replaced doctor quick-card patient snapshot reads from runtime registry with a doctor patient reader abstraction and DB-backed implementation.
- Wired doctor operational router/runtime to use the new reader.
- Ensured `/patient_open` and `id:<patient_id>` quick-hint path both pass doctor visibility checks.
- Extended stack 6A tests for visibility safety and fresh-read behavior.

## 4. Doctor Visibility Rule Chosen
**Option A (Booking-linked visibility).**
A doctor may open a patient quick card only if at least one booking exists for that `(doctor_id, patient_id)` linkage.

Enforcement points:
- `/patient_open <patient_id>` path.
- `id:<patient_id>` quick-hint follow-up path in doctor search.

## 5. Fresh Read Strategy
Implemented a doctor patient read abstraction:
- `DoctorPatientReader` protocol and `DoctorPatientSnapshot` model.
- `DbDoctorPatientReader` for fresh DB reads from canonical `core_patient` tables on every doctor read request.
- `RegistryDoctorPatientReader` fallback implementation (non-DB environments/tests).

Doctor operation cards now build from `DoctorPatientReader.read_snapshot(...)`, not from startup-loaded in-memory `PatientRegistryService` state.

## 6. Queue/Detail/Quick-Card Integration Notes
- Queue and booking detail now build patient display data via the new reader-backed quick-card path.
- Visibility guard is strict for explicit patient opens; queue/detail use linked booking context and bypass redundant visibility checks while still using fresh snapshot reads.
- `/search_patient id:<patient_id>` quick-hint only emits quick-open command if guarded quick-card read succeeds.

## 7. Files Added
- `app/application/doctor/patient_read.py`

## 8. Files Modified
- `app/application/doctor/operations.py`
- `app/application/doctor/__init__.py`
- `app/interfaces/bots/doctor/router.py`
- `app/bootstrap/runtime.py`
- `app/infrastructure/db/patient_repository.py`
- `tests/test_doctor_operational_stack6a.py`
- `tests/test_runtime_wiring.py`
- `locales/en.json`
- `locales/ru.json`

## 9. Commands Run
- `pytest -q tests/test_doctor_operational_stack6a.py tests/test_search_ui_stack5a1a.py tests/test_runtime_wiring.py`

## 10. Test Results
- All targeted doctor operational and wiring tests pass after changes (`14 passed`).
- Added tests for:
  - doctor blocked from unrelated raw patient_id open
  - doctor search quick-hint path does not emit backdoor open command for unrelated patient
  - quick-card reads reflect updated snapshot source (fresh-read behavior)

## 11. Remaining Known Limitations
- Full end-to-end DB integration test that mutates `core_patient` after runtime start and then validates doctor queue/detail in one flow is not yet added in this PR; behavior is validated by abstraction-level tests and runtime wiring.
- No charting introduced (intentionally out of scope).

## 12. Deviations From Docs (if any)
- None identified.

## 13. Readiness Assessment for Stack 7A
Stack 6A1 operational integrity objectives are addressed:
- raw arbitrary `/patient_open <patient_id>` access no longer bypasses doctor linkage,
- quick-hint path does not bypass guard,
- doctor cards are routed through fresh reader abstraction with DB-backed implementation.

This is a suitable base to proceed to Stack 7A charting work without carrying forward known Stack 6A access/staleness risks.
