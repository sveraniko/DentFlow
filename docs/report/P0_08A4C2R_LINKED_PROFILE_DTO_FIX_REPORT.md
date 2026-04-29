# P0_08A4C2R Linked Profile DTO / DB-Service Contract Fix Report

## Summary
Implemented a dedicated linked-profile DTO and aligned repository/service contract so linked profile metadata is preserved end-to-end.

## Files changed
- app/domain/patient_registry/models.py
- app/domain/patient_registry/__init__.py
- app/infrastructure/db/patient_repository.py
- app/application/patient/family.py
- tests/test_p0_08a4c2_family_booking_selector_services.py
- tests/test_p0_08a4b1_patient_profile_family_repositories.py
- docs/report/P0_08A4C2R_LINKED_PROFILE_DTO_FIX_REPORT.md

## Root cause
`DbPatientRegistryRepository.list_linked_profiles_for_telegram` selected relationship/self flags in SQL, but mapped rows into `Patient`, which cannot store linked-profile metadata due to frozen/slots dataclass shape.

## DTO contract
Added `LinkedPatientProfile` as a domain read model with relationship/self/default/phone/telegram fields.

## Repository behavior
`list_linked_profiles_for_telegram` now returns `list[LinkedPatientProfile]` and projects:
- self row (`relationship_type='self'`, `is_self=true`)
- related rows from `patient_relationships`
- default booking + notification flags
- best active primary phone
- telegram id from active telegram contacts when present
- sorting: self first, default-booking next, display name ascending

## Service mapping behavior
`PatientFamilyService` now maps from linked-profile rows directly and preserves relationship/default/notification/phone/telegram fields. It keeps fallback behavior for older fake objects via `getattr` compatibility.

## Tests run
- `python -m compileall app tests scripts`
- `pytest -q tests/test_p0_08a4c2_family_booking_selector_services.py`
- `pytest -q tests/test_p0_08a4c1_patient_profile_preference_services.py`
- `pytest -q tests/test_p0_08a4b1_patient_profile_family_repositories.py`
- `pytest -q tests/test_p0_08a4b4_repository_db_smoke.py`
- `pytest -q tests -k "patient and booking"`
- `pytest -q tests -k "care or recommendation"`

## Grep checks
- `rg "LinkedPatientProfile|is_default_notification_recipient|is_default_for_booking|telegram_user_id" app tests docs/report`
- `rg "list_linked_profiles_for_telegram" app/infrastructure/db/patient_repository.py app/application/patient/family.py tests`

## No migrations confirmation
No migrations or Alembic files were added/changed.

## GO/NO-GO for P0-08A4C3
GO: linked profile contract mismatch is fixed and covered by service/repository-facing tests.
