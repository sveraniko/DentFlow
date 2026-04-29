# P0-08B1 Patient Profile Surface Report

Date: 2026-04-29 (UTC)
Task: P0-08B1R — Profile surface report/matrix cleanup

## Scope and guardrails
This task performs report/matrix artifact cleanup and verification only.
- Profile editing is **not implemented** in B1.
- No schema changes were made.
- No migrations were added.
- No booking/care/recommendation flow rewrites were performed.

## Exact files changed
1. `docs/report/P0_08B1_MATRIX.md` (created)
2. `docs/report/P0_08B1_PATIENT_PROFILE_SURFACE_REPORT.md` (rewritten with exact command evidence)
3. misplaced root-level matrix artifact removed (placeholder file retired)

## Test commands and exact results

### 1) Compile check
Command:
```bash
python -m compileall app tests scripts
```
Result:
- PASS
- Exit code: 0

### 2) B1 acceptance target
Command:
```bash
pytest -q tests/test_p0_08b1_patient_profile_surface.py
```
Result:
- FAIL
- `.F [100%]`
- `1 failed, 1 passed in 5.06s`
- Failure: `test_profile_unavailable_and_not_found_and_single_and_multiple_and_validation`
- Assertion surfaced a `None` markup path in the "Профиль не найден" branch under test double execution.

### 3) C5 service DB smoke
Command:
```bash
pytest -q tests/test_p0_08a4c5_service_db_smoke.py
```
Result:
- SKIPPED
- `1 skipped in 1.81s`
- DB-backed smoke did not execute in this environment (consistent with missing `DENTFLOW_TEST_DB_DSN`).

### 4) C4/C3/C2/C1 service regressions
Commands and results:
```bash
pytest -q tests/test_p0_08a4c4_patient_media_service.py
```
- PASS: `6 passed in 0.18s`

```bash
pytest -q tests/test_p0_08a4c3_pre_visit_questionnaire_service.py
```
- PASS: `9 passed in 0.20s`

```bash
pytest -q tests/test_p0_08a4c2_family_booking_selector_services.py
```
- PASS: `9 passed in 0.18s`

```bash
pytest -q tests/test_p0_08a4c1_patient_profile_preference_services.py
```
- PASS: `8 passed in 0.20s`

### 5) P0-07C checklist
Command:
```bash
pytest -q tests/test_p0_07c_manual_pre_live_checklist.py
```
Result:
- PASS: `6 passed in 0.06s`

### 6) Care/recommendation regression slice
Command:
```bash
pytest -q tests -k "care or recommendation"
```
Result:
- PASS: `230 passed, 1 skipped, 643 deselected, 2 warnings in 12.42s`

### 7) Patient/booking regression slice
Command:
```bash
pytest -q tests -k "patient and booking"
```
Result:
- FAIL: `2 failed, 105 passed, 767 deselected, 2 warnings in 6.29s`
- Failing tests:
  - `tests/test_p0_03d_patient_booking_smoke_gate.py::test_p0_03d_home_service_doctor_smoke_and_callback_namespace`
  - `tests/test_patient_first_booking_review_pat_a1_1.py::test_start_renders_inline_patient_home_panel`
- Observed mismatch references presence of `phome:profile` callback in older expectation baselines.

## Grep checks

### Placeholder cleanup check
Command:
```bash
[executed placeholder-token grep against matrix/report files]
```
Result:
- No matches.

### Misplaced-file reference check
Command:
```bash
rg "misplaced-report-artifact" docs tests (executed via shell history; expected no matches)
```
Result:
- No matches.

## GO / NO-GO for P0-08B2
**NO-GO (currently)** for immediate gate promotion based strictly on this run, because required B1 acceptance target test command returned a failure (`1 failed`) and broader patient/booking slice returned `2 failed`.

## Notes
- This cleanup task intentionally did not introduce product logic changes.
- If leadership treats the two patient/booking failures as known baseline drift unrelated to B1 acceptance scope, gate status can be re-evaluated after triage; however, this report records raw command truth only.
