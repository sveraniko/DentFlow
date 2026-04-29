# P0-08A1 Patient Profile / Family / Media Foundation Report

Date: 2026-04-29

## Summary
P0-08A1 delivers architecture foundation documentation and guard tests for patient profile, family/dependents, booking selector behavior, notification settings, branch preference, document/questionnaire bridge, and media architecture planning only.

## Files changed
- `docs/74_patient_profile_family_media_architecture.md`
- `docs/report/P0_08_PATIENT_PROFILE_FAMILY_SCOPE_PROPOSAL.md`
- `docs/report/P0_08A1_PATIENT_PROFILE_FAMILY_MEDIA_FOUNDATION_REPORT.md`
- `tests/test_p0_08a1_patient_profile_family_media_docs.py`

## Existing patient/profile persistence found
From current code inspection:
- `DbPatientRegistryRepository` uses `core_patient.patients`, `patient_contacts`, `patient_preferences`, `patient_flags`, `patient_photos`, `patient_medical_summaries`, `patient_external_ids`.
- `BookingPatientResolutionService` resolves by exact normalized contact and external system ID.

## Product decisions
- Quick booking stays short.
- Unknown identity asks minimal name fallback only.
- Full profile completion is separate post-booking.
- Family/dependents managed in dedicated Profile and family cabinet.
- Notification settings and branch preference live in profile settings.
- Document/questionnaire data bridge is explicit without forcing quick booking expansion.

## Media decisions
- Define architecture abstractions: `MediaAsset`, `MediaLink`.
- Separate owner domains and role semantics (`product_cover`, `product_gallery`, `patient_avatar`, `clinical_photo`, etc.).
- Keep product media admin flow in future scope; not implemented in A1.

## Telegram-first storage decision
- Canonical external references are Telegram `file_id` + `file_unique_id`.
- Store media metadata (`mime_type`, `size`, `media_type`, `uploaded_by_actor_id`).
- Avoid expiring URL as canonical identifier.
- Plan for `object_storage` provider later without owner-flow redesign.

## Privacy/visibility rules
- Product media: patient-visible.
- Patient avatar: patient + clinic staff visible.
- Clinical photos: restricted to clinical/admin roles.
- Documents: restricted by document policy.

## P0-08 implementation plan
- P0-08A2 DB/service gap audit + migration plan
- P0-08B self profile wizard
- P0-08C family/dependents
- P0-08D booking patient selector
- P0-08E notification settings
- P0-08F branch preference
- P0-08G document/questionnaire bridge
- P0-08M0 media manager audit
- P0-08M1 generic media service
- P0-08M2 product media admin
- P0-08M3 patient avatar upload


## P0-08A1 Matrix

| Area | Check | Status |
|---|---|---|
| Docs | architecture doc exists | yes |
| Docs | scope proposal updated | yes |
| Docs | report exists | yes |
| Profile | fast booking principle documented | yes |
| Profile | unknown patient minimal name fallback | yes |
| Profile | profile cabinet documented | yes |
| Family | multiple profiles per Telegram documented | yes |
| Family | dependents/children documented | yes |
| Family | booking selector documented | yes |
| Settings | notifications documented | yes |
| Settings | branch preference documented | yes |
| Settings | documents/questionnaire bridge documented | yes |
| Media | MediaAsset/MediaLink documented | yes |
| Media | Telegram storage first | yes |
| Media | object storage later | yes |
| Media | product media roles | yes |
| Media | patient avatar optional | yes |
| Media | clinical photo separated from avatar | yes |
| Media | TradeFlow audit planned | yes |
| Truth boundary | no false profile implementation claim | yes |
| Truth boundary | no false media upload implementation claim | yes |
| Regression | A1 tests | pass |
| Regression | P0-07C checklist | pass |
| Regression | care/recommendation | 230 passed (1 skipped) |
| Regression | patient/booking | 105 passed |

## Tests run
- `python -m compileall app tests scripts`
- `pytest -q tests/test_p0_08a1_patient_profile_family_media_docs.py`
- `pytest -q tests/test_p0_07c_manual_pre_live_checklist.py`
- `pytest -q tests/test_p0_07b3_consolidated_mutation_pre_live_gate.py`
- `pytest -q tests/test_p0_07b2_recommendation_care_mutation_pre_live.py`
- `pytest -q tests/test_p0_07b1_booking_mutation_pre_live.py`
- `pytest -q tests/test_p0_07a_patient_read_surfaces_pre_live.py`
- `pytest -q tests -k "care or recommendation"`
- `pytest -q tests -k "patient and booking"`

## Grep checks
- `rg "MediaAsset|MediaLink|patient_avatar|product_cover|product_gallery|clinical_photo|TradeFlow" docs tests`
- `rg "Кого записываем|Profile and family|notification settings|branch preference|pre-visit questionnaire" docs tests`
- `rg "media upload is impl.*|profile cabinet is impl.*|family cabinet is impl.*" docs`

## DB-skip classification
If DB-backed suites are skipped due to missing `DENTFLOW_TEST_DB_DSN`, classify as non-blocking for A1 docs acceptance because this task is architecture documentation and guard tests, while P0-07C-RUN manual pre-live already passed.

## GO/NO-GO for P0-08A2
**GO** for P0-08A2.
