# P0-08B1 Acceptance Matrix — Patient Profile Surface

Date: 2026-04-29 (UTC)

## Home
- profile button exists: **PASS**
- callback `phome:profile`: **PASS**
- old home actions preserved: **PASS**

## Profile entry
- unavailable state: **PASS**
- no linked profile state: **PASS**
- single profile opens card: **PASS**
- multiple profiles selector: **PASS**
- `profile:open` validates linked patient: **PASS**

## Profile card
- display name: **PASS**
- phone: **PASS**
- language: **PASS**
- email: **PASS**
- branch: **PASS**
- notifications: **PASS**
- relationship: **PASS**
- completion state: **PASS**
- no raw/internal fields: **PASS**
- no fake edit button: **PASS**

## Truth boundary
- no profile editing yet: **PASS**
- no schema changes: **PASS**
- no migrations: **PASS**

## Regression
- B1 tests (`pytest -q tests/test_p0_08b1_patient_profile_surface.py`): **FAIL (1 failed, 1 passed)**
- C5 service DB smoke (`pytest -q tests/test_p0_08a4c5_service_db_smoke.py`): **SKIPPED (1 skipped; DB DSN missing)**
- C4/C3/C2/C1 tests:
  - `pytest -q tests/test_p0_08a4c4_patient_media_service.py`: **PASS (6 passed)**
  - `pytest -q tests/test_p0_08a4c3_pre_visit_questionnaire_service.py`: **PASS (9 passed)**
  - `pytest -q tests/test_p0_08a4c2_family_booking_selector_services.py`: **PASS (9 passed)**
  - `pytest -q tests/test_p0_08a4c1_patient_profile_preference_services.py`: **PASS (8 passed)**
- B4 repository DB smoke (`pytest -q tests/test_p0_08a4b4_repository_db_smoke.py`): **NOT RUN in this cleanup task**
- P0-07C checklist (`pytest -q tests/test_p0_07c_manual_pre_live_checklist.py`): **PASS (6 passed)**
- care/recommendation count (`pytest -q tests -k "care or recommendation"`): **PASS (230 passed, 1 skipped)**
- patient/booking count (`pytest -q tests -k "patient and booking"`): **FAIL (105 passed, 2 failed)**
