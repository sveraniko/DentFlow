# P0-08A4C1 PatientProfileService + PatientPreferenceService Report

## Summary
Implemented service-layer foundations for patient profile details/completion and patient preference notification/branch settings with validation and repository delegation.

## Files changed
- app/application/patient/profile.py
- app/application/patient/__init__.py
- tests/test_p0_08a4c1_patient_profile_preference_services.py
- docs/report/P0_08A4C1_PATIENT_PROFILE_PREFERENCE_SERVICES_REPORT.md

## PatientProfileService methods
- `get_profile_details`
- `save_profile_details`
- `get_profile_completion_state`
- `compute_profile_completion_state`

## Profile completion rules
- missing: when name/phone identity is not available.
- minimal: when stable identity exists but no details payload exists.
- partial: when any details fields are present but not enough required fields for completion.
- completed: explicit completion state or required detail fields (`email`, `address_line1`, `city`, `country_code`) present.

## PatientPreferenceService methods
- `get_preferences`
- `update_notification_settings`
- `update_branch_preference`
- `validate_quiet_hours`
- `validate_notification_recipient_strategy`

## Notification validation rules
- preferred channel allowed: `telegram`, `sms`, `call`, `email`, `none`.
- recipient strategy allowed: `self`, `guardian`, `guardian_or_self`, `clinic_manual`.
- quiet hours format required: `HH:MM` with range checks `00:00`..`23:59`.
- timezone validated with `zoneinfo.ZoneInfo` when provided.

## Branch preference validation rules
- `allow_any_branch=False` requires non-null `default_branch_id`.
- when reference service is provided and `default_branch_id` set, branch must resolve in clinic.
- delegation to repository `update_branch_preferences` on success.

## Tests run with exact commands/results
- `python -m compileall app tests scripts` → PASS
- `pytest -q tests/test_p0_08a4c1_patient_profile_preference_services.py` → PASS (8 passed)
- `pytest -q tests/test_p0_08a4b4_repository_db_smoke.py` → SKIP (1 skipped; DB DSN not configured)
- `pytest -q tests/test_p0_08a4b3_media_repository.py` → PASS (5 passed, 3 skipped)
- `pytest -q tests/test_p0_08a4b2_pre_visit_questionnaire_repository.py` → PASS (5 passed, 3 skipped)
- `pytest -q tests/test_p0_08a4b1_patient_profile_family_repositories.py` → PASS
- `pytest -q tests/test_p0_08a4a_baseline_schema_models.py` → PASS
- `pytest -q tests/test_p0_08a3_baseline_schema_contract_docs.py` → PASS
- `pytest -q tests/test_p0_08a2_db_service_gap_audit_docs.py` → PASS
- `pytest -q tests/test_p0_08a1_patient_profile_family_media_docs.py` → PASS
- `pytest -q tests/test_p0_07c_manual_pre_live_checklist.py` → PASS
- `pytest -q tests -k "care or recommendation"` → PASS (230 passed, 1 skipped)
- `pytest -q tests -k "patient and booking"` → PASS (105 passed)

## Grep checks
- `rg "PatientProfileService|PatientPreferenceService|update_notification_settings|update_branch_preference|validate_quiet_hours" app tests docs`
- `rg "alembic|migration|revision" app tests docs/report/P0_08A4C1_PATIENT_PROFILE_PREFERENCE_SERVICES_REPORT.md`

## No Alembic / no migrations confirmation
No Alembic files, migration directories, or revision files were created by this task.

## Defects found/fixed
- Initial async test style required `pytest-asyncio` plugin; converted service tests to synchronous harness with `asyncio.run` to avoid plugin dependency.

## Carry-forward
- P0-08A4C2 family + booking selector services
- P0-08A4C3 questionnaire service
- P0-08A4C4 media service
- P0-08A4C5 service DB smoke

## GO/NO-GO for P0-08A4C2
GO: C1 acceptance for service layer and tests is satisfied; safe to proceed to C2.
