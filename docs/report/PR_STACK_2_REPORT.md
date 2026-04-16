# PR Stack 2 Report — Patient Registry Core + Stack 1 Persistence Promotion

## 1. Objective
Implement canonical Patient Registry core (`core_patient`) and remove Stack 1 pseudo-foundation shortcuts by promoting runtime and seed behavior to DB-backed flows.

## 2. Docs Read
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/12_repo_structure_and_code_map.md
4. docs/10_architecture.md
5. docs/20_domain_model.md
6. docs/30_data_model.md
7. docs/22_access_and_identity_model.md
8. docs/23_policy_and_configuration_model.md
9. docs/15_ui_ux_and_product_rules.md
10. docs/17_localization_and_i18n.md
11. docs/40_search_model.md
12. docs/70_bot_flows.md
13. docs/72_admin_doctor_owner_ui_contracts.md
14. docs/80_integrations_and_infra.md
15. docs/85_security_and_privacy.md
16. docs/90_pr_plan.md
17. docs/report/PR_STACK_0_REPORT.md
18. docs/report/PR_STACK_1_REPORT.md
19. booking_docs/* (scope-confirmation only; no booking implementation)

## 3. Precedence Decisions
1. Kept one canonical patient truth in `core_patient` and did not add booking-local patient tables.
2. Kept single-clinic default with required `clinic_id` on patient aggregate.
3. Used deterministic exact-resolution helpers (contact normalization + external ID) and explicitly avoided fuzzy search.
4. Applied fallback locale chain in touched role routing path: actor locale → clinic locale → app default.

## 4. Stack 1 Carry-Forward Fixes Completed
- Removed runtime auto-seeding from bootstrap (`RuntimeRegistry` no longer loads `seeds/stack1_seed.json`).
- Promoted runtime wiring to DB loaders for clinic/access/policy repositories.
- Reworked Stack 1 seed script to write through SQL persistence path.
- Renamed logging config field `json` → `json_logs` to avoid field-shadow warning.
- Replaced hardcoded locale fallback in touched routers with app default and clinic-aware fallback where available.

## 5. Scope Implemented
- Added canonical patient domain models and application service for staged enrichment.
- Added baseline SQL for canonical `core_patient` tables.
- Added DB repository loaders for Stack 1 runtime contexts.
- Added DB patient persistence helpers and deterministic lookup helpers.
- Added explicit Stack 2 patient seed fixture + seed script.
- Added tests for Stack 2 schema presence, seed-to-DB path, patient service behavior, runtime anti-auto-seed, runtime DB wiring, and locale fallback chain.

## 6. Files Added
- app/domain/patient_registry/models.py
- app/application/patient/registry.py
- app/infrastructure/db/repositories.py
- app/infrastructure/db/patient_repository.py
- scripts/seed_stack2.py
- seeds/stack2_patients.json
- tests/test_patient_registry.py
- tests/test_patient_db_helpers.py
- tests/test_locale_fallback.py
- tests/test_runtime_seed_behavior.py
- tests/test_runtime_wiring.py
- docs/report/PR_STACK_2_REPORT.md

## 7. Files Modified
- app/infrastructure/db/bootstrap.py
- app/bootstrap/runtime.py
- app/bootstrap/seed.py
- scripts/seed_stack1.py
- app/config/settings.py
- app/bootstrap/logging.py
- app/interfaces/bots/common.py
- app/interfaces/bots/admin/router.py
- app/interfaces/bots/doctor/router.py
- app/interfaces/bots/owner/router.py
- app/interfaces/bots/patient/router.py
- app/domain/patient_registry/__init__.py
- app/application/patient/__init__.py
- tests/test_db_bootstrap.py
- tests/test_stack1_foundation.py
- tests/test_runtime.py
- tests/test_config.py
- Makefile

## 8. Stack 2 Table / Schema Summary
Added canonical `core_patient` baseline tables:
- `core_patient.patients`
- `core_patient.patient_contacts`
- `core_patient.patient_preferences`
- `core_patient.patient_flags`
- `core_patient.patient_photos`
- `core_patient.patient_medical_summaries`
- `core_patient.patient_external_ids`

## 9. Patient Registry Model Summary
Implemented canonical patient aggregate + supporting entities:
- Patient
- PatientContact
- PatientPreference
- PatientFlag
- PatientPhoto
- PatientMedicalSummary
- PatientExternalId

Service supports staged enrichment:
- minimum patient create/update
- contact upsert + normalization
- preference upsert
- flags add/deactivate
- photo add + primary selection
- medical summary upsert
- external ID upsert + deterministic resolution

## 10. DB-backed Repository Promotion Summary
- Runtime now loads Stack 1 contexts from DB-backed repository loaders:
  - `DbClinicReferenceRepository.load`
  - `DbAccessRepository.load`
  - `DbPolicyRepository.load`
- Runtime no longer depends on in-memory seed bootstrap.

## 11. Seed / Bootstrap Strategy
- `scripts/db_bootstrap.py` keeps baseline-first schema creation.
- `scripts/seed_stack1.py` now writes Stack 1 fixture to DB.
- `scripts/seed_stack2.py` seeds patient registry data to DB.
- Seeds are explicit commands; not runtime side effects.

## 12. Runtime Changes
- `RuntimeRegistry` switched from in-memory seed bootstrap to DB data loaders.
- Routers now receive app default locale from runtime settings.
- Admin locale resolution in touched code uses actor locale first, clinic default second, app default fallback third.

## 13. Commands Run
- `pytest -q`
- Multiple `sed -n` / `rg --files` / `rg -n` inspections for docs and code navigation.

## 14. Test Results
- `pytest -q` passed with 4 tests run, 9 skipped in this environment.
- Skips are dependency-related (`aiogram` / `sqlalchemy`) in current execution environment.

## 15. Known Limitations / Explicit Non-Goals
- Booking/session/slot logic not implemented (out of Stack 2 scope).
- Reminder execution engine not implemented (only patient preference data readiness).
- No fuzzy/translit search implementation (only deterministic exact helpers).
- DB integration round-trip tests are partially constrained by environment dependency availability.

## 16. Deviations From Docs (if any)
- None intentional for Stack 2 scope.

## 17. Risks / Follow-ups for PR Stack 3
1. Add high-fidelity integration tests against real Postgres in CI to validate runtime DB loaders and patient persistence end-to-end.
2. Extend runtime use of patient registry services where Stack 3 booking workflows need deterministic patient resolution.
3. Introduce richer policy-driven locale resolution helper shared across all role routers (beyond touched paths).
4. Harden seed idempotency and conflict strategies across future stack fixtures.
