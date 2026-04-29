# P0-08A4C3 PreVisitQuestionnaireService Report

## Summary
Implemented service-layer foundation for pre-visit questionnaires with validation, deterministic answer upsert IDs, lifecycle operations, and latest lookup delegation.

## Files changed
- app/application/patient/questionnaire.py
- app/application/patient/__init__.py
- app/domain/patient_registry/models.py
- tests/test_p0_08a4c3_pre_visit_questionnaire_service.py

## Service methods added
- start_questionnaire, get_questionnaire, list_questionnaires
- save_answer, save_answers, list_answers, delete_answer
- complete_questionnaire
- get_latest_for_booking, get_latest_for_patient

## Questionnaire lifecycle behavior
- Start creates `in_progress` questionnaires with generated `pvq_` IDs.
- Get/list delegate to repository.
- Complete delegates with clock-injected `completed_at`; returns None when missing.

## Answer validation/idempotency behavior
- Validates answer type, visibility, non-empty keys, JSON serializability.
- Normalizes question key by trimming and replacing whitespace runs with `_`.
- Uses deterministic ID: `pvqa_{questionnaire_id}_{normalized_question_key}` with SHA1 fallback.
- Re-saving same questionnaire/question key upserts same answer identity.
- Domain contract updated so `answer_value` is typed as JSON-compatible `JSONValue` (dict/list/scalars/null).

## Latest lookup behavior
- Booking and patient latest lookups delegate to repository with optional type filter validation.

## Tests run with exact commands/results
- `python -m compileall app tests scripts` → success (all files compiled)
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

## No Alembic / no migrations confirmation
- No migration or Alembic files were created or modified.

## Defects found/fixed
- Updated `answer_value` type contract from dict-only annotation to JSON-compatible union matching service/runtime behavior.
- Added test coverage for string/list/int/bool `answer_value` acceptance.

## Carry-forward
- P0-08A4C4 PatientMediaService
- P0-08A4C5 service DB smoke
- future P0-08G document/questionnaire UI bridge

## GO/NO-GO for P0-08A4C4
GO
