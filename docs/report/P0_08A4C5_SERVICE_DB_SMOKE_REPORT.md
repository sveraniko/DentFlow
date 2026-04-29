# P0-08A4C5 Service DB Smoke Report

## Summary
DB-backed service smoke gate for patient profile/preference/family-selector/questionnaire/media services executed against real PostgreSQL (`dentflow_test` on 127.0.0.1:5432) using mandatory test DB harness with safety guards.

## Files changed
- `tests/test_p0_08a4c5_service_db_smoke.py` — fixed Branch constructor (`name` → `display_name`/`address_text`), replaced non-existent `find_profiles_by_phone` with `find_patients_by_exact_contact`, corrected seed phone number
- `tests/test_p0_08a4c3_pre_visit_questionnaire_service.py` — excluded `.venv` from migration glob guard
- `docs/report/P0_08A4C5_SERVICE_DB_SMOKE_REPORT.md`
- `docs/report/P0_08A4C5_MATRIX_2026-04-29.md`

## DB lane execution
- DSN env: `DENTFLOW_TEST_DB_DSN`
- DSN used in run: `postgresql+asyncpg://dentflow:dentflow@127.0.0.1:5432/dentflow_test`
- Status: **executed (not skipped)**
- Harness safety checks enforced host=127.0.0.1 and DB name includes "test".
- seed-demo bootstrap ran before assertions (5 seed packs loaded).

## Service results
- PatientProfileService DB result: **PASS** (create/update/normalize/invalid-email and created_at preservation).
- PatientPreferenceService DB result: **PASS** (notification + branch preference + invalid branch validation with ClinicReferenceService).
- PatientFamilyService DB result: **PASS** (relationship add/list/deactivate with default flags and consent).
- BookingPatientSelectorService DB result: **PASS** (telegram multiple/single/no-match and phone single/minimal-name-required).
- PreVisitQuestionnaireService DB result: **PASS** (start/save/list/update/delete/complete/latest + JSONValue round-trip + deterministic answer ids).
- PatientMediaService DB result: **PASS** (register/upsert by telegram unique id, avatar/product attach, primary switching, remove link with asset retained).

## Cross-service compatibility
PASS: selector resolution, preferences, questionnaire latest lookups, and media lookups still work after all operations.

## No external API calls
No Telegram Bot API calls, no Google API calls, and no S3/object storage calls were introduced or used in this smoke test.

## No Alembic / migrations
No Alembic revision or migration files were added.

## Tests run with commands/results
- `python -m compileall app tests scripts` — clean
- `pytest -q tests/test_p0_08a4c5_service_db_smoke.py` — **1 passed** (7.89s)
- `pytest -q tests/test_p0_08a4b4_repository_db_smoke.py` — **1 passed** (7.94s)
- `pytest -q tests/test_p0_08a4c4_patient_media_service.py` — PASS
- `pytest -q tests/test_p0_08a4c3_pre_visit_questionnaire_service.py` — PASS
- `pytest -q tests/test_p0_08a4c2_family_booking_selector_services.py` — PASS
- `pytest -q tests/test_p0_08a4c1_patient_profile_preference_services.py` — PASS
- C4/C3/C2/C1 combined: **32 passed** in 1.68s
- `pytest -q tests -k "care or recommendation"` — **231 passed**
- `pytest -q tests -k "patient and booking"` — **107 passed**

## Defects found/fixed
1. **Branch constructor mismatch (test bug)** — `test_p0_08a4c5` used `name="Central"` but `Branch` dataclass expects `display_name`/`address_text`. Fixed to `display_name="Central", address_text="Central Office"`.
2. **Non-existent `find_profiles_by_phone` (service/repository contract mismatch)** — `_PatientLookup` in the test called `patient_repo.find_profiles_by_phone()` which doesn't exist on `DbPatientRegistryRepository`. Replaced with the actual DB lookup function `find_patients_by_exact_contact(db_config, contact_type="phone", ...)`.
3. **Seed phone data mismatch (test data bug)** — Test expected `+995555000111` for `patient_giorgi_beridze` but seed data has `+7 (999) 777-10-10`. Corrected phone to `+79997771010`.
4. **`.venv` in migration glob guard (test bug)** — `test_no_migrations_or_router_changes` in C3 scanned site-packages picking up sqlalchemy/pydantic migration files. Added `.venv` to skip dirs.

## Carry-forward
- P0-08B self profile wizard
- P0-08C family/dependents UI
- P0-08D booking patient selector UI integration
- P0-08E notification settings UI
- P0-08F branch preference UI
- P0-08M media upload/admin flows

## GO/NO-GO for P0-08B
**GO** — DB-backed service smoke executed and passed with real PostgreSQL. Report and matrix are now consistent.
