# P0-08A4B2 — Pre-visit questionnaire repository foundation report

## Summary
Implemented repository-only support for pre-visit questionnaires in `DbPatientRegistryRepository`, including lifecycle CRUD/upsert/complete methods, answer CRUD/upsert/delete methods, and latest questionnaire lookups for booking/patient with required ordering.

## Files changed
- `app/infrastructure/db/patient_repository.py`
- `tests/test_p0_08a4b2_pre_visit_questionnaire_repository.py`

## Repository methods added
- `get_pre_visit_questionnaire`
- `list_pre_visit_questionnaires`
- `upsert_pre_visit_questionnaire`
- `complete_pre_visit_questionnaire`
- `list_pre_visit_questionnaire_answers`
- `upsert_pre_visit_questionnaire_answer`
- `upsert_pre_visit_questionnaire_answers`
- `delete_pre_visit_questionnaire_answer`
- `get_latest_pre_visit_questionnaire_for_booking`
- `get_latest_pre_visit_questionnaire_for_patient`
- private helper: `_get_latest_pre_visit_questionnaire`

Also added private mapping helpers:
- `_map_pre_visit_questionnaire`
- `_map_pre_visit_questionnaire_answer`

## Questionnaire lifecycle behavior
- Questionnaire upsert is idempotent by `questionnaire_id` (`ON CONFLICT (questionnaire_id)`).
- On conflict, `created_at` is preserved from existing row and `updated_at` is set to `NOW()`.
- Completion sets:
  - `status = 'completed'`
  - `completed_at = COALESCE(:completed_at, NOW())`
  - `updated_at = NOW()`
- Completion returns updated row or `None` if not found.

## Answer persistence behavior
- Answer upsert is idempotent by `answer_id` (`ON CONFLICT (answer_id)`).
- On conflict, updates `question_key`, `answer_value`, `answer_type`, `visibility` and updates `updated_at=NOW()` while preserving original `created_at`.
- `answer_value` is serialized via `json.dumps(...)` and cast to `JSONB` in SQL.
- `upsert_pre_visit_questionnaire_answers` performs batched sequential upserts and returns persisted rows.
- Delete method removes by `(questionnaire_id, question_key)` and returns boolean based on rowcount.

## Latest lookup behavior
Both latest methods order using:
1. `completed_at DESC NULLS LAST`
2. `updated_at DESC`
3. `created_at DESC`

Optional `questionnaire_type` filter is supported.

## DB-backed tests executed or skipped
- DB-backed tests are present and auto-skip when `DENTFLOW_TEST_DB_DSN` is missing.
- In this run, DB-backed tests were skipped (3 skipped) because DSN was not configured.

## No Alembic / no migrations confirmation
- No Alembic revisions or migration files were created.
- Repository/tests include explicit no-Alembic guard assertions.

## Tests run with exact commands/results
- `python -m compileall app tests scripts` → pass
- `pytest -q tests/test_p0_08a4b2_pre_visit_questionnaire_repository.py` → 4 passed, 3 skipped
- `pytest -q tests/test_p0_08a4b1_patient_profile_family_repositories.py` → 5 passed
- `pytest -q tests/test_p0_08a4a_baseline_schema_models.py` → 6 passed
- `pytest -q tests/test_p0_08a3_baseline_schema_contract_docs.py` → 6 passed
- `pytest -q tests/test_p0_08a2_db_service_gap_audit_docs.py` → 6 passed
- `pytest -q tests/test_p0_08a1_patient_profile_family_media_docs.py` → 6 passed
- `pytest -q tests/test_p0_07c_manual_pre_live_checklist.py` → 6 passed
- `pytest -q tests -k "care or recommendation"` → 230 passed, 1 skipped, 597 deselected
- `pytest -q tests -k "patient and booking"` → 105 passed, 723 deselected

## Grep checks
- `rg "get_pre_visit_questionnaire|upsert_pre_visit_questionnaire|complete_pre_visit_questionnaire|list_pre_visit_questionnaire_answers" app tests` → repository methods and tests found.
- `rg "_map_pre_visit_questionnaire|_map_pre_visit_questionnaire_answer|answer_value|question_key" app tests` → mapping helpers and JSON answer handling found.
- `rg "alembic|migration|revision" app tests docs/report/P0_08A4B2_PRE_VISIT_QUESTIONNAIRE_REPOSITORY_REPORT.md` → no migration artifacts added; only policy/assertion references.

## Defects found/fixed
- Fixed test module import path from `app.settings` to `app.config.settings`.
- Reworked async DB tests to use `asyncio.run(...)` to avoid `pytest-asyncio` dependency in this environment.

## Carry-forward
- P0-08A4B3: media repository (not included here by scope).
- P0-08A4B4: full repository DB smoke lane.

## GO/NO-GO for P0-08A4B3
GO — repository layer for pre-visit questionnaires is in place with contract-level coverage and no migration changes.
