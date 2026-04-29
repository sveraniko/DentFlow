# P0-08A4C3 PreVisitQuestionnaireService Report

## Summary
Implemented service-layer foundation for pre-visit questionnaires with validation, deterministic answer upsert IDs, lifecycle operations, and latest lookup delegation.

## Files changed
- app/application/patient/questionnaire.py
- app/application/patient/__init__.py
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

## Latest lookup behavior
- Booking and patient latest lookups delegate to repository with optional type filter validation.

## Tests run with exact commands/results
(see terminal run list below)

## Grep checks
(see terminal run list below)

## No Alembic / no migrations confirmation
- No migration or Alembic files were created or modified.

## Defects found/fixed
- Added missing service-layer validation and stable answer ID handling for idempotent upserts.

## Carry-forward
- P0-08A4C4 PatientMediaService
- P0-08A4C5 service DB smoke
- future P0-08G document/questionnaire UI bridge

## GO/NO-GO for P0-08A4C4
GO
