# P0-08A4A Baseline Schema + Domain Models Report

## Summary
- Implemented baseline schema definitions in `app/infrastructure/db/bootstrap.py` for patient profile/family/questionnaire/media link scope.
- Added/extended domain dataclasses for patient registry and media domain.
- Applied compatibility update in `DbPatientRegistryRepository.load` for expanded `PatientPreference` fields.

## Files changed
- `app/infrastructure/db/bootstrap.py`
- `app/domain/patient_registry/models.py`
- `app/domain/patient_registry/__init__.py`
- `app/domain/media/models.py`
- `app/domain/media/__init__.py`
- `app/infrastructure/db/patient_repository.py`
- `docs/76_patient_profile_family_media_baseline_contract.md`
- `tests/test_p0_08a4a_baseline_schema_models.py`

## Baseline schema tables added
- `core_patient.patient_profile_details`
- `core_patient.patient_relationships`
- `core_patient.pre_visit_questionnaires`
- `core_patient.pre_visit_questionnaire_answers`
- `media_docs.media_links`

## Existing `media_assets` reconciliation
- Reused existing `media_docs.media_assets` CREATE TABLE statement.
- Preserved compatibility fields and added baseline fields (`media_type`, `mime_type`, `size_bytes`, `telegram_file_id`, `telegram_file_unique_id`, `object_key`, `uploaded_by_actor_id`).
- Confirmed no duplicate `CREATE TABLE IF NOT EXISTS media_docs.media_assets` definition.

## Domain models added
- Patient registry domain:
  - `PatientProfileDetails`
  - `PatientRelationship`
  - `PreVisitQuestionnaire`
  - `PreVisitQuestionnaireAnswer`
- Media domain:
  - `MediaAsset`
  - `MediaLink`

## PatientPreference extension
- Added optional fields:
  - `notification_recipient_strategy`
  - `quiet_hours_start`
  - `quiet_hours_end`
  - `quiet_hours_timezone`
  - `default_branch_id`
  - `allow_any_branch`
- Updated repository load SELECT + mapping with safe defaults for compatibility.

## No Alembic / no migrations confirmation
- No Alembic revision files were created.
- No migration files were added.
- This change is baseline schema definition update only.

## Tests run
- `python -m compileall app tests scripts`
- `pytest -q tests/test_p0_08a4a_baseline_schema_models.py`
- `pytest -q tests/test_p0_08a3_baseline_schema_contract_docs.py`
- `pytest -q tests/test_p0_08a2_db_service_gap_audit_docs.py`
- `pytest -q tests/test_p0_08a1_patient_profile_family_media_docs.py`
- `pytest -q tests/test_p0_07c_manual_pre_live_checklist.py`
- `pytest -q tests -k "care or recommendation"`
- `pytest -q tests -k "patient and booking"`

## Grep checks
- baseline object names present in app/docs/tests.
- new field names present in app/docs/tests.
- single `media_assets` table create statement confirmed.
- no migration/revision implementation artifacts added.

## Carry-forward
- P0-08A4B: repositories
- P0-08A4C: services
- P0-08A4D: DB smoke

## GO/NO-GO for P0-08A4B
- **GO**: baseline schema + domain model prerequisites are in place for repository implementation.
