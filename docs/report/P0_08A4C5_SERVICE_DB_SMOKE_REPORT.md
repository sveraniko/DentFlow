# P0-08A4C5 Service DB Smoke Report

## Summary
Implemented DB-backed service smoke gate for patient profile/preference/family-selector/questionnaire/media services using real PostgreSQL repositories and mandatory test DB harness checks.

## Files changed
- `tests/test_p0_08a4c5_service_db_smoke.py`
- `app/application/patient/profile.py`
- `docs/report/P0_08A4C5_SERVICE_DB_SMOKE_REPORT.md`

## DB lane execution
- DSN env: `DENTFLOW_TEST_DB_DSN`
- DSN used in run: `postgresql+asyncpg://dentflow:dentflow@127.0.0.1:5432/dentflow_test`
- Status: executed (not skipped)
- Harness safety checks enforced host=localhost/127.0.0.1 and DB name includes test/sandbox/tmp.

## Service results
- PatientProfileService DB result: PASS (create/update/normalize/invalid-email and created_at preservation).
- PatientPreferenceService DB result: PASS (notification + branch preference + invalid branch validation with ClinicReferenceService).
- PatientFamilyService DB result: PASS (relationship add/list/deactivate with default flags and consent).
- BookingPatientSelectorService DB result: PASS (telegram multiple/single/no-match and phone single/minimal-name-required).
- PreVisitQuestionnaireService DB result: PASS (start/save/list/update/delete/complete/latest + JSONValue round-trip + deterministic answer ids).
- PatientMediaService DB result: PASS (register/upsert by telegram unique id, avatar/product attach, primary switching, remove link with asset retained).

## Cross-service compatibility
PASS: selector resolution, preferences, questionnaire latest lookups, and media lookups still work after all operations.

## Partial profile update behavior
Fixed in `PatientProfileService.save_profile_details`: omitted params now preserve existing values (no silent null overwrite during partial saves).

## No external API calls
No Telegram Bot API calls, no Google API calls, and no S3/object storage calls were introduced or used in this smoke test.

## No Alembic / migrations
No Alembic revision or migration files were added.

## Tests run with commands/results
- `pytest -q tests/test_p0_08a4c5_service_db_smoke.py` — PASS
- `python -m compileall app tests scripts` — PASS
- `pytest -q tests/test_p0_08a4c4_patient_media_service.py` — PASS
- `pytest -q tests/test_p0_08a4c3_pre_visit_questionnaire_service.py` — PASS
- `pytest -q tests/test_p0_08a4c2_family_booking_selector_services.py` — PASS
- `pytest -q tests/test_p0_08a4c1_patient_profile_preference_services.py` — PASS
- `pytest -q tests/test_p0_08a4b4_repository_db_smoke.py` — PASS
- `pytest -q tests/test_p0_08a4b3_media_repository.py` — PASS
- `pytest -q tests/test_p0_08a4b2_pre_visit_questionnaire_repository.py` — PASS
- `pytest -q tests/test_p0_08a4b1_patient_profile_family_repositories.py` — PASS
- `pytest -q tests/test_p0_08a4a_baseline_schema_models.py` — PASS
- `pytest -q tests/test_p0_08a3_baseline_schema_contract_docs.py` — PASS
- `pytest -q tests/test_p0_08a2_db_service_gap_audit_docs.py` — PASS
- `pytest -q tests/test_p0_08a1_patient_profile_family_media_docs.py` — PASS
- `pytest -q tests/test_p0_07c_manual_pre_live_checklist.py` — PASS
- `pytest -q tests -k "care or recommendation"` — PASS
- `pytest -q tests -k "patient and booking"` — PASS

## Grep checks
- service smoke/harness grep — PASS
- service class grep — PASS
- smoke constants grep — PASS
- migration keyword grep — PASS (only no-migration/report mentions)

## Defects found/fixed
- Fixed profile partial save overwrite risk in `PatientProfileService` by preserving existing values for omitted fields.

## Carry-forward
- P0-08B self profile wizard
- P0-08C family/dependents UI
- P0-08D booking patient selector UI integration
- P0-08E notification settings UI
- P0-08F branch preference UI
- P0-08M media upload/admin flows

## GO/NO-GO for P0-08B
GO (DB-backed service smoke executed and passed with required DB lane).
