# P0-08A4C4 Matrix Status Report

Date: 2026-04-29

## P0-08A4C4 matrix

### Service
- PatientMediaService exists: yes
- register_telegram_asset: yes
- attach_media_to_owner: yes
- register_and_attach_telegram_media: yes
- list_owner_media: yes
- set_primary_owner_media: yes
- remove_owner_media_link: yes
- get_patient_avatar: yes
- get_product_cover: yes

### Validation
- media_type: yes
- owner_type: yes
- role: yes
- visibility: yes
- owner-role compatibility: yes
- negative size/sort rejected: yes

### Behavior
- product_cover default primary/visible: yes
- patient_avatar default primary/staff_only: yes
- clinical_photo doctor_only: yes
- Telegram file IDs stored only: yes
- no Telegram/S3 calls: yes

### Truth boundary
- no UI: yes
- no schema changes: yes
- no Alembic/migrations: yes

### Regression
- C4 tests: pass
- C3/C2/C1 tests: pass
- B4/B3/B2/B1 tests: pass/skipped (16 passed, 7 skipped)
- A4A/A3/A2/A1 tests: pass
- care/recommendation: n/a (not isolated as a dedicated counter in this matrix run)
- patient/booking: n/a as separate counter (booking-related C2 tests included and passed)

## Evidence

### Core implementation
- `app/application/patient/media.py` contains `PatientMediaService` and all required methods, validations, role-owner rules, default visibility and primary behavior.

### Boundary confirmation
- `docs/report/P0_08A4C4_PATIENT_MEDIA_SERVICE_REPORT.md` states service-only scope, no DB schema/Alembic/migrations, and no Telegram/S3/object-storage live calls.

### Test commands/results used for this matrix
- `pytest -q tests/test_p0_08a4c4_patient_media_service.py` → 6 passed
- `pytest -q tests/test_p0_08a4c1_patient_profile_preference_services.py tests/test_p0_08a4c2_family_booking_selector_services.py tests/test_p0_08a4c3_pre_visit_questionnaire_service.py` → 26 passed
- `pytest -q tests/test_p0_08a4b1_patient_profile_family_repositories.py tests/test_p0_08a4b2_pre_visit_questionnaire_repository.py tests/test_p0_08a4b3_media_repository.py tests/test_p0_08a4b4_repository_db_smoke.py` → 16 passed, 7 skipped
- `pytest -q tests/test_p0_08a4a_baseline_schema_models.py tests/test_p0_08a3_baseline_schema_contract_docs.py tests/test_p0_08a2_db_service_gap_audit_docs.py tests/test_p0_08a1_patient_profile_family_media_docs.py` → 24 passed
- `pytest -q tests/test_p0_08a4c1_patient_profile_preference_services.py tests/test_p0_08a4c2_family_booking_selector_services.py tests/test_p0_08a4c3_pre_visit_questionnaire_service.py tests/test_p0_08a4c4_patient_media_service.py` → 32 passed
