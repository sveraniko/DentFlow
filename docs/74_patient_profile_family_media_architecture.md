# P0-08 Patient Profile / Family / Media Architecture Foundation

Date: 2026-04-29
Status: Architecture foundation only (no implementation in this PR)

## A. Current state

### Existing patient registry tables/services found by code inspection
- Patient persistence is already present in `DbPatientRegistryRepository` and loads/saves from:
  - `core_patient.patients`
  - `core_patient.patient_contacts`
  - `core_patient.patient_preferences`
  - `core_patient.patient_flags`
  - `core_patient.patient_photos`
  - `core_patient.patient_medical_summaries`
  - `core_patient.patient_external_ids`
- Booking patient resolution service exists (`BookingPatientResolutionService`) and supports exact contact and external-id matching.
- Current bot routing already exposes patient booking surfaces but does not provide a full Profile and family cabinet yet.

### Current quick booking behavior
- Quick booking remains short and conversion-oriented.
- Current flow centers on phone/contact resolution first, not full profile collection.

### Current patient matching behavior by Telegram/phone
- Matching is done by exact normalized contact and external system IDs.
- If contact identity resolves uniquely, booking can proceed without extra profile questions.
- Minimal name fallback is used only when patient identity is unknown/unresolved.

### Missing patient-facing cabinet surfaces
- Profile and family cabinet: not implemented yet.
- Notification settings: not implemented yet.
- Branch preference UI: not implemented yet.
- Patient avatar/photo flow for patient self-service: not implemented yet.

## B. Product principles
- Fast booking remains short.
- Unknown patient asks minimal name only.
- Full profile completion is separate from booking.
- Family/dependents are managed outside booking, then selected during booking.
- Notification settings and branch preference live in profile settings.
- Documents/pre-visit questionnaire use profile data but do not block fast booking unless clinic policy requires it.

## C. Patient profile fields

### Minimal booking identity
- `display_name` / `full_name`
- `phone`
- Telegram binding
- `preferred_language`

### Profile completion
- `date_of_birth`
- `sex`
- `email` (if needed)
- `address` (if documents require it)
- `emergency_contact_person` (if needed)
- clinic-visible notes

### Medical/pre-visit questionnaire
- allergies
- chronic diseases
- medications
- pregnancy status (if relevant)
- reason for visit
- consent flags

## D. Family/dependents

### Core model
- Telegram account manages multiple patient profiles.
- Relationship values:
  - `self`
  - `spouse`
  - `child`
  - `parent`
  - `other`
- Guardian/representative model is required for children.
- Notification recipient can be patient or guardian.

### Booking selector
- If only one linked patient profile exists, skip selector.
- If multiple linked profiles exist, show: `Кого записываем?`
- If unknown, ask phone first, then minimal name if not resolved.
- If child profile is selected, guardian contact is default communication target.

## E. Notification settings
- Per linked patient profile:
  - preferred channel
  - Telegram allowed
  - SMS allowed
  - call allowed
  - quiet hours/contact time window
- Booking reminder defaults are configurable here.
- My Booking should link to notification settings.

## F. Branch preference
- If clinic has one branch, skip branch selector.
- If clinic has multiple branches:
  - use profile `default_branch_id` if present;
  - allow `any branch`;
  - booking slot picker filters by branch.
- Profile settings include:
  - `default_branch_id`
  - branch preference label

## G. Documents/pre-visit questionnaire bridge
- Document generation should combine:
  - patient profile
  - booking
  - doctor/clinic
  - questionnaire
- After booking success, prompt: `Заполнить профиль / анкету перед визитом`.
- Do not force document-grade fields into quick booking.

## H. Media architecture

Define generic abstractions:
- `MediaAsset`
- `MediaLink`

### Storage providers
- `telegram`
- `object_storage`
- `local/dev`

### Media owners
- `care_product`
- `patient_profile`
- `booking`
- `clinical_note`
- `recommendation`
- `care_order`
- `document`

### Roles
- `product_cover`
- `product_gallery`
- `product_video`
- `patient_avatar`
- `clinical_photo`
- `document_attachment`

### Telegram-first storage rule
- Store Telegram `file_id` and `file_unique_id` as canonical external references.
- Store `mime_type`, `size`, `media_type`, `uploaded_by_actor_id` metadata.
- Do not store temporary/expiring Telegram download URL as canonical.
- `object_storage` can be added later without changing owner-facing flows.

### Visibility and privacy
- Product media: visible to patient.
- Patient avatar: visible to clinic staff and patient.
- Clinical photos: restricted to doctor/admin clinical roles.
- Documents: restricted by document policy.

### Patient avatar policy
- `patient_avatar` is optional and not forced.
- After booking/profile completion, softly prompt avatar upload.
- For children, guardian may upload avatar.
- If missing avatar, staff sees initials/name/time/service fallback.

## I. Product media admin flow (future, not implemented now)
- Admin opens product card.
- Clicks `+ Медиа`.
- Uploads photo/video.
- Chooses role:
  - cover
  - gallery
  - video
- Sets cover.
- Deletes media.
- Reorders gallery.

This flow is planned only; media upload is not implemented in this PR.

## J. TradeFlow media reuse plan
- P0-08M0: audit TradeFlow media manager.
- Reuse concepts:
  - upload flow
  - cover/gallery roles
  - callback structure
  - storage provider abstraction
- Do not copy TradeFlow code blindly.
- Adapt to DentFlow owner types and privacy rules.

## K. Proposed P0-08 implementation stack
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

## L. A2 follow-up reference
- A2 gap audit lives in `docs/75_patient_profile_family_media_gap_audit.md`.
- No schema changes are implemented in A2.
- Future schema work is tracked as **baseline schema update** work, not migrations.

- A3 baseline contract: `docs/76_patient_profile_family_media_baseline_contract.md`.
