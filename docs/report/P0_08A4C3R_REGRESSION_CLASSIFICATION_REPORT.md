# P0-08A4C3R Regression Classification Report

## Summary
P0-08A4C3 acceptance commands were re-run exactly. Required C3/C2/C1/B/A tests pass (with expected DB-related skips in existing smoke tests), and the acceptance selector `patient and booking` is green.

## Root cause of red matrix
The red matrix line (`381 passed, 6 failed, 2 skipped`) corresponds to a broader non-acceptance selector pattern (`patient or booking`) rather than the requested acceptance selector (`patient and booking`).

## Wrong selector usage
- Expected acceptance selector: `pytest -q tests -k "patient and booking"`
- Broader selector (non-acceptance): `pytest -q tests -k "patient or booking"`
- Current acceptance selector status: PASS (`107 passed, 757 deselected, 2 warnings`)

## Exact failed tests if any
- For required acceptance commands in this run: **none failed**.
- Therefore, no C3-related failure fixes were required beyond contract cleanup.

## Fixes applied
1. Updated `PreVisitQuestionnaireAnswer.answer_value` domain contract from dict-only annotation to JSON-compatible type alias:
   - `JSONValue = dict[str, object] | list[object] | str | int | float | bool | None`
   - `answer_value: JSONValue`
2. Added service test coverage asserting allowed `answer_value` types (string, list, int, bool).
3. Updated matrix/report docs to include exact commands + exact results and explicit selector classification.

## answer_value type contract update
- Service behavior already accepts JSON-serializable values and rejects non-serializable values.
- Domain type now matches service behavior and repository JSONB persistence expectation.

## Tests run with exact commands/results
- `python -m compileall app tests scripts` → success
- `pytest -q tests/test_p0_08a4c3_pre_visit_questionnaire_service.py` → `9 passed in 0.34s`
- `pytest -q tests/test_p0_08a4c2_family_booking_selector_services.py` → `9 passed in 0.31s`
- `pytest -q tests/test_p0_08a4c1_patient_profile_preference_services.py` → `8 passed in 0.19s`
- `pytest -q tests/test_p0_08a4b4_repository_db_smoke.py` → `1 skipped in 1.95s`
- `pytest -q tests/test_p0_08a4b3_media_repository.py` → `5 passed, 3 skipped in 0.64s`
- `pytest -q tests/test_p0_08a4b2_pre_visit_questionnaire_repository.py` → `5 passed, 3 skipped in 0.82s`
- `pytest -q tests/test_p0_08a4b1_patient_profile_family_repositories.py` → `6 passed in 0.81s`
- `pytest -q tests/test_p0_08a4a_baseline_schema_models.py` → `6 passed in 0.10s`
- `pytest -q tests/test_p0_08a3_baseline_schema_contract_docs.py` → `6 passed in 0.05s`
- `pytest -q tests/test_p0_08a2_db_service_gap_audit_docs.py` → `6 passed in 0.05s`
- `pytest -q tests/test_p0_08a1_patient_profile_family_media_docs.py` → `6 passed in 0.06s`
- `pytest -q tests/test_p0_07c_manual_pre_live_checklist.py` → `6 passed in 0.05s`
- `pytest -q tests -k "care or recommendation"` → `230 passed, 1 skipped, 633 deselected, 2 warnings in 12.72s`
- `pytest -q tests -k "patient and booking"` → `107 passed, 757 deselected, 2 warnings in 6.19s`

## Grep checks
- `rg "answer_value: dict\[str, object\]|JSONValue|answer_value: object" app/domain app/application tests`
- `rg "381 passed|6 failed|patient or booking|patient and booking" docs/report/P0_08A4C3_PRE_VISIT_QUESTIONNAIRE_SERVICE_REPORT.md P0-08A4C3-matrix.md`

## GO/NO-GO for P0-08A4C4
**GO**
