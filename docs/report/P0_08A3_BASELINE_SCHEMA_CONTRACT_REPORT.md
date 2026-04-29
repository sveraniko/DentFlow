# P0-08A3 Baseline Schema Contract Finalization Report

Date: 2026-04-29  
Status: Done (documentation contract only)

## Summary
P0-08A3 converted the A2 gap audit into a concrete baseline schema/service contract for A4 implementation. This PR adds no schema code and no service/UI/media implementation.

## Files changed
- `docs/76_patient_profile_family_media_baseline_contract.md` (new)
- `docs/75_patient_profile_family_media_gap_audit.md` (link update)
- `docs/74_patient_profile_family_media_architecture.md` (link update)
- `tests/test_p0_08a3_baseline_schema_contract_docs.py` (new)

## Baseline contract created
The new contract defines concrete A4-ready tables, domain models, repository contracts, service contracts, booking selector behavior, document integration, and phased media delivery.

## Proposed baseline tables
- `core_patient.patient_profile_details`
- `core_patient.patient_relationships`
- `core_patient.pre_visit_questionnaires`
- `core_patient.pre_visit_questionnaire_answers`
- `media_assets`
- `media_links`
- Extensions to `core_patient.patient_preferences`

## Service contracts
- PatientProfileService
- PatientFamilyService
- PatientPreferenceService
- BookingPatientSelectorService
- PreVisitQuestionnaireService
- PatientMediaService

## Booking selector contract
Defined exact flow for one-profile auto-skip, multi-profile `Кого записываем?`, unknown fallback (phone -> minimal name), child guardian default contact, and branch preference behavior.

## Media contract
Defined generic media baseline with provider/type/ownership/role/visibility contracts, Telegram canonical ID policy, and phase roadmap through P0-08M4.

## No-migration confirmation
- No Alembic.
- no migrations.
- No baseline schema update implementation in A3.
- UI work is out of scope in A3.
- Media upload work is out of scope in A3.

## Tests run
- `python -m compileall app tests scripts`
- `pytest -q tests/test_p0_08a3_baseline_schema_contract_docs.py`
- `pytest -q tests/test_p0_08a2_db_service_gap_audit_docs.py`
- `pytest -q tests/test_p0_08a1_patient_profile_family_media_docs.py`
- `pytest -q tests/test_p0_07c_manual_pre_live_checklist.py`
- `pytest -q tests -k "care or recommendation"`
- `pytest -q tests -k "patient and booking"`

## Grep checks
- `rg "patient_profile_details|patient_relationships|pre_visit_questionnaires|media_assets|media_links" docs tests`
- `rg "baseline schema update|No Alembic|no migrations|migration" docs/76_patient_profile_family_media_baseline_contract.md docs/report/P0_08A3_BASELINE_SCHEMA_CONTRACT_REPORT.md tests/test_p0_08a3_baseline_schema_contract_docs.py`
- `rg "Alembic migration exists" docs`

## GO/NO-GO for P0-08A4
**GO** for P0-08A4 baseline schema/model implementation. Contract is concrete and includes no prohibited implementation claims.
