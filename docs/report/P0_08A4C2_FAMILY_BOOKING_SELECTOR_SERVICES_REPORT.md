# P0-08A4C2 — Family + Booking Selector Services Report

## Summary
Implemented service-layer foundations for `PatientFamilyService` and `BookingPatientSelectorService` with application result dataclasses and service-unit tests. No UI, router, Telegram handler, or DB schema changes were made.

## Files changed
- `app/application/patient/family.py`
- `app/application/patient/__init__.py`
- `tests/test_p0_08a4c2_family_booking_selector_services.py`

## PatientFamilyService methods
- `list_linked_profiles_for_telegram`
- `list_relationships`
- `add_relationship`
- `deactivate_relationship`

## BookingPatientSelectorService methods
- `resolve_for_telegram`
- `resolve_for_phone`
- `select_patient`

## Relationship validation rules
- Allowed `relationship_type`: `self`, `spouse`, `child`, `parent`, `other`
- Allowed `consent_status`: `active`, `revoked`, `expired`
- `manager_patient_id != related_patient_id` unless `relationship_type == "self"`
- `expires_at > starts_at` when both are present

## Selector modes
- `phone_required`
- `minimal_name_required`
- `single_match`
- `multiple_profiles`
- `no_match`

## Tests run with exact commands/results
- `python -m compileall app tests scripts` → passed
- `pytest -q tests/test_p0_08a4c2_family_booking_selector_services.py` → 7 passed
- `pytest -q tests/test_p0_08a4c1_patient_profile_preference_services.py` → 8 passed
- `pytest -q tests/test_p0_08a4b4_repository_db_smoke.py` → 1 skipped (DB DSN dependent)
- `pytest -q tests/test_p0_08a4b3_media_repository.py` → 5 passed, 3 skipped
- `pytest -q tests/test_p0_08a4b2_pre_visit_questionnaire_repository.py` → 5 passed, 3 skipped
- `pytest -q tests/test_p0_08a4b1_patient_profile_family_repositories.py` → 5 passed
- `pytest -q tests/test_p0_08a4a_baseline_schema_models.py` → 6 passed
- `pytest -q tests/test_p0_08a3_baseline_schema_contract_docs.py` → 6 passed
- `pytest -q tests/test_p0_08a2_db_service_gap_audit_docs.py` → 6 passed
- `pytest -q tests/test_p0_08a1_patient_profile_family_media_docs.py` → 6 passed
- `pytest -q tests/test_p0_07c_manual_pre_live_checklist.py` → 6 passed
- `pytest -q tests -k "care or recommendation"` → 230 passed, 1 skipped
- `pytest -q tests -k "patient and booking"` → 106 passed

## Grep checks
- `rg "PatientFamilyService|BookingPatientSelectorService|LinkedPatientOption|BookingPatientSelectionResult" app tests docs`
- `rg "Кого записываем|phone_required|minimal_name_required|multiple_profiles|single_match" app tests docs`
- `rg "alembic|migration|revision" app tests docs/report/P0_08A4C2_FAMILY_BOOKING_SELECTOR_SERVICES_REPORT.md`

## No Alembic / no migrations confirmation
No Alembic or migration files were added.

## Defects found/fixed
- None beyond service-layer implementation and test coverage additions.

## Carry-forward
- P0-08A4C3 questionnaire service
- P0-08A4C4 media service
- P0-08A4C5 service DB smoke
- P0-08D booking UI integration

## GO/NO-GO for P0-08A4C3
GO (service-layer C2 scope complete; no schema/UI/router side effects introduced).
