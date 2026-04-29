# P0-08A3 Patient Profile / Family / Media Baseline Schema & Service Contract

Date: 2026-04-29  
Status: Contract finalization for next PR implementation (A4)

## A. Baseline schema update summary

- P0-08A3 is documentation and contract finalization only.
- **No migrations in A3.**
- In explicit terms: no migrations are created in this A3 PR.
- **No DB implementation in A3.**
- P0-08A4 will update baseline schema/model files directly as a **baseline schema update**.
- Alembic is out of scope during active development baseline; **No Alembic** changes are included here.
- This contract is implementation-ready input for Codex in P0-08A4 repository/model work.

## B. Current reused tables

| Table/model | Contract stance | Notes |
|---|---|---|
| `core_patient.patients` | extend later | Keep as identity root; extend via profile details + relationship context instead of overloading booking path. |
| `core_patient.patient_contacts` | extend later | Keep as contact source; add recipient strategy via relationship/preference contract. |
| `core_patient.patient_preferences` | extend later | Keep existing preference toggles; extend with notification/branch fields in A4 contract below. |
| `core_patient.patient_flags` | keep as-is | Internal/clinical flags continue unchanged in A4. |
| `core_patient.patient_photos` | bridge later | Keep for backward compatibility during media cutover; bridge to `media_assets` + `media_links`. |
| `core_patient.patient_medical_summaries` | keep as-is | Remains summary channel; questionnaire answers live in dedicated baseline tables. |
| `core_patient.patient_external_ids` | keep as-is | Continues external system identity mapping. |
| existing export/document tables | bridge later | Continue current generation pipeline; bind new profile/questionnaire sources incrementally. |
| care product data | bridge later | Existing product pointers remain; new media link model becomes canonical attach layer. |
| recommendations | replace later | Existing recommendation media relation can be moved to generic `media_links` owner model. |

## C. Proposed baseline tables / fields

### C1. Patient profile details

**Proposed table:** `core_patient.patient_profile_details`

Required contract fields:
- `patient_id`
- `clinic_id`
- `email`
- `address_line1`
- `address_line2`
- `city`
- `postal_code`
- `country_code`
- `emergency_contact_name`
- `emergency_contact_phone`
- `profile_completion_state`
- `profile_completed_at`
- `updated_at`

Rationale: these fields are not shoved blindly into booking flow because quick booking must remain low-friction and conversion-first. Profile completeness is maintained outside fast booking and only reused when available.

### C2. Patient relationships / family

**Proposed table:** `core_patient.patient_relationships`

Required contract fields:
- `relationship_id`
- `clinic_id`
- `manager_patient_id`
- `related_patient_id`
- `relationship_type` (`self` / `spouse` / `child` / `parent` / `other`)
- `authority_scope`
- `is_default_for_booking`
- `is_default_notification_recipient`
- `consent_status`
- `starts_at`
- `expires_at`
- `created_at`
- `updated_at`

Contract rules:
- One Telegram account resolves linked profiles by joining Telegram contact binding to manager identity and then listing active relationships in clinic scope.
- Children/dependents are represented as `relationship_type='child'` rows where `manager_patient_id` is guardian/manager and `related_patient_id` is dependent profile.
- Guardian contact is selected from active relationship entries with `is_default_notification_recipient=true`; fallback is manager contact when explicit default not set.

### C3. Preference extensions

**Decision:** field extension to `core_patient.patient_preferences` (not separate table).

Required extension fields:
- `notification_recipient_strategy`
- `quiet_hours_start`
- `quiet_hours_end`
- `quiet_hours_timezone`
- `default_branch_id`
- `allow_any_branch`

Justification:
- Preference retrieval is already centralized in `patient_preferences`.
- These fields are preference-surface concerns, not high-cardinality child records.
- Single-row-per-patient semantics simplify booking/reminder reads and avoid an unnecessary join-only companion table.

### C4. Pre-visit questionnaire

**Proposed table:** `core_patient.pre_visit_questionnaires`
- `questionnaire_id`
- `clinic_id`
- `patient_id`
- `booking_id` (nullable)
- `questionnaire_type`
- `status`
- `version`
- `completed_at`
- `created_at`
- `updated_at`

**Proposed table:** `core_patient.pre_visit_questionnaire_answers`
- `answer_id`
- `questionnaire_id`
- `question_key`
- `answer_value`
- `answer_type`
- `visibility`
- `created_at`
- `updated_at`

Document generation bridge: generated document builders read latest applicable questionnaire + answers by patient/booking, then map keys into template variables.

### C5. Media assets / media links

**Proposed table:** `media_assets`
- `media_id`
- `storage_provider` (`telegram` / `object_storage` / `local`)
- `media_type` (`photo` / `video` / `document`)
- `mime_type`
- `size_bytes`
- `telegram_file_id`
- `telegram_file_unique_id`
- `object_key`
- `uploaded_by_actor_id`
- `created_at`
- `updated_at`

**Proposed table:** `media_links`
- `link_id`
- `media_id`
- `owner_type` (`care_product` / `patient_profile` / `booking` / `clinical_note` / `recommendation` / `care_order` / `document`)
- `owner_id`
- `role` (`product_cover` / `product_gallery` / `product_video` / `patient_avatar` / `clinical_photo` / `document_attachment`)
- `visibility` (`patient_visible` / `staff_only` / `doctor_only` / `admin_only`)
- `sort_order`
- `is_primary`
- `created_at`
- `updated_at`

Media contract notes:
- `patient_avatar` is optional.
- `clinical_photo` is separate from patient avatar role.
- Product media is patient-visible by default (`patient_visible`).
- `telegram_file_id` is canonical for Telegram storage; expiring download URL is not canonical.

## D. Domain model contracts

- **PatientProfileDetails**
  - required: `patient_id`, `clinic_id`, `profile_completion_state`, `updated_at`
  - optional: `email`, address fields, emergency contact, `profile_completed_at`
  - enums: `profile_completion_state`

- **PatientRelationship**
  - required: `relationship_id`, `clinic_id`, `manager_patient_id`, `related_patient_id`, `relationship_type`, `consent_status`, `created_at`, `updated_at`
  - optional: `authority_scope`, default flags, `starts_at`, `expires_at`
  - enums: `relationship_type`, `consent_status`

- **PatientPreference (updated)**
  - required: existing preference keys + `notification_recipient_strategy`, `allow_any_branch`
  - optional: `quiet_hours_start`, `quiet_hours_end`, `quiet_hours_timezone`, `default_branch_id`
  - enums: `notification_recipient_strategy`

- **PreVisitQuestionnaire**
  - required: `questionnaire_id`, `clinic_id`, `patient_id`, `questionnaire_type`, `status`, `version`, `created_at`, `updated_at`
  - optional: `booking_id`, `completed_at`
  - enums: `questionnaire_type`, `status`

- **PreVisitQuestionnaireAnswer**
  - required: `answer_id`, `questionnaire_id`, `question_key`, `answer_value`, `answer_type`, `visibility`, `created_at`, `updated_at`
  - optional: none
  - enums: `answer_type`, `visibility`

- **MediaAsset**
  - required: `media_id`, `storage_provider`, `media_type`, `created_at`, `updated_at`
  - optional: `mime_type`, `size_bytes`, `telegram_file_id`, `telegram_file_unique_id`, `object_key`, `uploaded_by_actor_id`
  - enums: `storage_provider`, `media_type`

- **MediaLink**
  - required: `link_id`, `media_id`, `owner_type`, `owner_id`, `role`, `visibility`, `created_at`, `updated_at`
  - optional: `sort_order`, `is_primary`
  - enums: `owner_type`, `role`, `visibility`

## E. Repository contracts

### Patient profile
- `get_profile_details(patient_id)`
- `upsert_profile_details(...)`
- `get_profile_completion(patient_id)`

### Family
- `list_linked_profiles_for_telegram(clinic_id, telegram_user_id)`
- `list_relationships(patient_id)`
- `upsert_relationship(...)`
- `deactivate_relationship(...)`

### Preferences
- `get_patient_preferences(...)`
- `update_notification_preferences(...)`
- `update_branch_preferences(...)`

### Questionnaire
- `start_questionnaire(...)`
- `save_answer(...)`
- `complete_questionnaire(...)`
- `get_latest_for_booking(...)`

### Media
- `create_media_asset(...)`
- `attach_media(...)`
- `list_media(owner_type, owner_id, role=None)`
- `set_primary_media(...)`
- `remove_media_link(...)`

## F. Service contracts

- **PatientProfileService**
  - responsibility: profile read/update and completion-state calculation
  - methods: `get_profile`, `update_profile`, `get_completion`
  - first UI consumer: P0-08B self profile wizard
  - validation rules: contact format checks, completion transitions, clinic scope ownership

- **PatientFamilyService**
  - responsibility: dependent linking and relationship authority lifecycle
  - methods: `list_linked_profiles`, `create_or_update_relationship`, `deactivate_relationship`, `get_default_guardian_contact`
  - first UI consumer: P0-08C family/dependents
  - validation rules: no self-cycles (except `self`), active date windows, consent required for guardian authority scopes

- **PatientPreferenceService**
  - responsibility: notification + branch preference management
  - methods: `get_preferences`, `update_notifications`, `update_branch_defaults`
  - first UI consumer: P0-08E notification settings and P0-08F branch preference
  - validation rules: quiet-hours coherence, timezone presence when quiet hours set, branch belongs to clinic or any-branch override

- **BookingPatientSelectorService**
  - responsibility: booking-time patient target resolution and selector policy
  - methods: `resolve_candidates_for_telegram`, `choose_default_patient`, `resolve_contact_target`
  - first UI consumer: P0-08D booking patient selector
  - validation rules: exactly-one auto-select; guardian fallback for child; unknown identity fallback sequence

- **PreVisitQuestionnaireService**
  - responsibility: questionnaire session lifecycle and answer persistence
  - methods: `start`, `save_answer`, `complete`, `get_latest_for_booking`
  - first UI consumer: P0-08G documents/questionnaire bridge
  - validation rules: questionnaire status transitions, answer key whitelist per version/type

- **PatientMediaService**
  - responsibility: media asset/link lifecycle and role/visibility guards
  - methods: `create_asset`, `attach`, `list`, `set_primary`, `detach`
  - first UI consumer: P0-08M2 product media admin, then P0-08M3 patient avatar upload
  - validation rules: owner_type/role compatibility matrix, single-primary per owner+role, visibility policy enforcement

## G. Booking integration contract

Future booking behavior:
- If Telegram resolves one linked profile: skip `Кого записываем?`.
- If Telegram resolves multiple profiles: show `Кого записываем?`.
- If unknown: ask phone; if phone not found, ask minimal name.
- If selected patient has phone: do not ask phone again unless editing contact.
- If selected patient is child: use guardian/manager contact by default.
- Branch preference: apply `default_branch_id` if multiple branches; allow “any branch”.

## H. Document generation integration contract

- Profile fields used by documents: legal/display names, DOB, sex marker, phone, email (if present), address block (if present), emergency contact (optional), clinic/patient identity keys.
- Questionnaire answer feed: latest completed questionnaire for booking/patient, mapped by `question_key` and questionnaire `version`.
- Guardian block for children: derive from active `patient_relationships` with child relation + valid authority scope and consent.
- Optional vs required:
  - required for base identity: patient name + clinic scope + booking/patient link.
  - optional unless template policy says required: email/address/emergency fields and non-core questionnaire answers.

## I. Media implementation phases

- **P0-08M0** TradeFlow media manager audit
- **P0-08M1** generic media baseline implementation
- **P0-08M2** product media admin
- **P0-08M3** patient avatar upload
- **P0-08M4** doctor/admin booking card avatar display

## J. Implementation order

1. P0-08A4 baseline schema/model implementation
2. P0-08A5 repository/service foundation
3. P0-08B self profile wizard
4. P0-08C family/dependents
5. P0-08D booking patient selector
6. P0-08E notification settings
7. P0-08F branch preference
8. P0-08G documents/questionnaire bridge
9. P0-08M0 media manager audit
10. P0-08M1 media baseline
11. P0-08M2 product media admin
12. P0-08M3 patient avatar

## K. Out-of-scope confirmation

- A3 does not implement schema files, repository code, services, UI, media upload, or router splitting.
- A3 does not modify live bot behavior.
- A3 provides the baseline schema update contract only.
