# P0-08A2 DB/Service Gap + Baseline Schema Plan Report

Date: 2026-04-29

## Summary
P0-08A2 audited current patient/booking/export/care/recommendation DB-service surfaces and produced a concrete baseline schema update + service rollout plan for P0-08 profile/family/selector/preferences/questionnaire/media scope.

## Files inspected
- `docs/74_patient_profile_family_media_architecture.md`
- `docs/report/P0_08A1_PATIENT_PROFILE_FAMILY_MEDIA_FOUNDATION_REPORT.md`
- `docs/30_data_model.md`
- `docs/65_document_templates_and_043_mapping.md`
- `docs/85_security_and_privacy.md`
- `app/application/patient/registry.py`
- `app/application/booking/patient_resolution.py`
- `app/infrastructure/db/patient_repository.py`
- `app/infrastructure/db/repositories.py`
- `app/infrastructure/db/booking_repository.py`
- `app/infrastructure/db/care_commerce_repository.py`
- `app/infrastructure/db/recommendation_repository.py`
- `app/application/export/*`
- `app/interfaces/bots/patient/router.py`
- `seeds/stack2_patients.json`

## Existing DB/service inventory
See detailed matrix in `docs/75_patient_profile_family_media_gap_audit.md` section A.

## Main gaps found
- Missing explicit family authority/consent relationship model.
- Missing profile fields for documents/completion (address/email/emergency contact/completion state).
- Booking selector orchestration is not yet modeled for multi-profile dependent flows.
- Notification settings missing guardian-recipient and quiet-hours timezone semantics.
- Branch defaults missing on patient preference layer.
- Questionnaire data is not structured/versioned for export bridges.
- Current `patient_photos` and product media pointers are insufficient as unified media governance model.

## Baseline schema update proposal
A2 proposes only **baseline schema update** items (profile, family, preferences, branch, questionnaire, media) and explicitly defers implementation to next PRs.

## Service implementation plan
A2 defines future services:
- `PatientProfileService`
- `PatientFamilyService`
- `PatientPreferenceService`
- `PatientMediaService`
- `BookingPatientSelectorService`
- `PreVisitQuestionnaireService`

## No-migration confirmation
- No Alembic files created.
- No migrations created.
- A2 is docs/tests planning only.

## Tests run
- `python -m compileall app tests scripts`
- `pytest -q tests/test_p0_08a2_db_service_gap_audit_docs.py`
- `pytest -q tests/test_p0_08a1_patient_profile_family_media_docs.py`
- `pytest -q tests/test_p0_07c_manual_pre_live_checklist.py`
- `pytest -q tests/test_p0_07b3_consolidated_mutation_pre_live_gate.py`
- `pytest -q tests/test_p0_07b2_recommendation_care_mutation_pre_live.py`
- `pytest -q tests/test_p0_07b1_booking_mutation_pre_live.py`
- `pytest -q tests/test_p0_07a_patient_read_surfaces_pre_live.py`
- `pytest -q tests -k "care or recommendation"`
- `pytest -q tests -k "patient and booking"`

## Grep checks
- `rg "baseline schema update|No Alembic|no migrations|migration" docs/75_patient_profile_family_media_gap_audit.md docs/report/P0_08A2_DB_SERVICE_GAP_BASELINE_PLAN_REPORT.md tests/test_p0_08a2_db_service_gap_audit_docs.py`
- `rg "PatientProfileService|PatientFamilyService|PatientPreferenceService|PatientMediaService|BookingPatientSelectorService|PreVisitQuestionnaireService" docs tests`
- `rg "media_assets|media_links|patient_relationship|patient_guardian|default_branch_id|pre_visit_questionnaire" docs tests`
- `rg "profile UI implemented|media upload implemented|family cabinet implemented|Alembic migration" docs`

## DB skip classification
If DB integration tests are skipped due to missing `DENTFLOW_TEST_DB_DSN`, this is non-blocking for A2 doc acceptance when P0-07C-RUN remains already passed; skips must still be reported honestly.

## GO/NO-GO for next P0-08 step
**GO** to P0-08A3 baseline schema update plan finalization.
