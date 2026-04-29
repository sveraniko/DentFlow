# P0-08A2 DB/Service Gap Audit + Baseline Schema Plan

Date: 2026-04-29  
Status: Audit + planning only (no DB/schema implementation in A2)

**No Alembic and no migrations were created in A2.**  
All future DB changes are described as **baseline schema update** work.

## A. Current DB/service inventory

| Area | Current table/model | Service/repository support | R/W support | Usable for patient-facing profile UI? | Gaps |
|---|---|---|---|---|---|
| patients | `core_patient.patients` / `Patient` | `PatientRegistryService`, `DbPatientRegistryRepository` | Read + write | Partial | No email/address/emergency contact/profile completion fields; no guardian data. |
| patient_contacts | `core_patient.patient_contacts` / `PatientContact` | `upsert_contact`, `find_by_exact_contact`, DB persist/load | Read + write | Partial | Contact typing works (`phone`,`telegram`) but no relationship semantics, no explicit recipient priority for guardian flows. |
| patient_preferences | `core_patient.patient_preferences` / `PatientPreference` | `upsert_preferences`, DB persist/load | Read + write | Partial | Covers channel toggles and language, but no explicit quiet-hours timezone, no guardian override layer, no branch defaults. |
| patient_flags | `core_patient.patient_flags` / `PatientFlag` | add/deactivate/list + DB persist/load | Read + write | Limited | Clinical/internal flags exist; not profile-completion or family authority semantics. |
| patient_photos | `core_patient.patient_photos` / `PatientPhoto` | add/set-primary/get-primary + DB persist/load | Read + write | Partial | Has minimal photo pointer fields, but missing generic media metadata/visibility/actor provenance. |
| patient_medical_summaries | `core_patient.patient_medical_summaries` / `PatientMedicalSummary` | upsert/get + DB persist/load | Read + write | Limited | Good for summary text, but not structured questionnaire answers. |
| patient_external_ids | `core_patient.patient_external_ids` / `PatientExternalId` | upsert/list/find + DB persist/load | Read + write | Limited | Good for integrations; not profile identity block for patient self-service. |
| booking patient resolution | n/a table-level (uses patient tables) + `BookingPatientResolutionService` | finder protocol, exact contact + external id methods | Read only resolution | Partial | No built-in multi-profile selector orchestration and guardian routing logic. |
| reminder preferences | mostly `patient_preferences` | used through patient preference reads and communication layer | Read + write (indirect) | Partial | No explicit per-patient vs per-guardian reminder recipient strategy. |
| export/document services | `media_docs.document_templates`, `media_docs.generated_documents`, `media_docs.media_assets` domain models | `DocumentTemplateRegistryService`, `GeneratedDocumentRegistryService` | Read + write | Partial | Pipeline exists, but patient identity/guardian document block sources incomplete. |
| care product data | `care_commerce.products` (+ link tables) | `DbCareCommerceRepository` | Read + write | N/A direct profile | Product-level `media_asset_id` exists, but no shared media-link abstraction yet. |
| recommendation data | `recommendation.recommendations` | `DbRecommendationRepository` | Read + write | N/A direct profile | No direct family/profile augmentation fields; telegram mapping via contacts may become ambiguous in multi-linked family model. |

## B. Profile support gap

Classification against required profile fields:

- **Already supported**
  - `full_name` / `display_name` (`full_name_legal`, `display_name` in patients).
  - phone (`patient_contacts` with `contact_type='phone'`).
  - Telegram binding (`patient_contacts` with `contact_type='telegram'`; also access layer has telegram bindings by actor).
  - preferred language (`patient_preferences.preferred_language`).
  - date of birth (`patients.birth_date`).
  - sex (`patients.sex_marker`).

- **Partially supported**
  - clinic-visible notes: contact-level notes and flag notes exist, but no dedicated profile notes field with clear UI semantics.

- **Missing**
  - email (unless stored as contact type ad hoc; no explicit model contract in profile flow).
  - address.
  - emergency contact.
  - profile completion status fields.

- **Unclear**
  - canonical “display vs legal name update policy” for patient self-edits and verification lifecycle.

## C. Family/dependents support gap

Current state:
- One Telegram user can technically be linked to multiple patients because `patient_contacts` uniqueness is `(patient_id, contact_type, normalized_value)` during upsert, which does **not** enforce global uniqueness for telegram contact per clinic.
- This appears intentionally permissive for family use cases, but currently lacks explicit relationship, consent, and authority semantics.

Gap conclusions:
- Missing relationship types (`self/spouse/child/parent/other`) as first-class link records.
- Missing guardian/representative entity and consent/authority lifecycle.
- Missing default contact recipient policy per linked patient.

Baseline proposal (future):
- Add a family linkage baseline schema update (e.g., `core_patient.patient_relationships` and/or `core_patient.patient_guardians`) with:
  - owner patient;
  - linked managing actor/patient;
  - relationship type enum;
  - authority scope and consent flags;
  - default recipient priority.

## D. Booking patient selector gap

Needed for `Кого записываем?` flow:
- Selector data source for all linked patient profiles under one managing Telegram user.
- Skip selector when exactly one linked profile.
- Unknown patient minimal-name fallback remains required when no linked profile resolves.
- Child profile should default to guardian contact for reminders and callbacks.
- Reuse profile phone if available; avoid asking again in quick path.
- If Telegram link absent, fallback to phone matching should still work.

Current missing pieces:
- No dedicated selector service that resolves linked profiles + relationship context.
- No child/guardian communication policy at booking orchestration level.

## E. Notification settings support gap

Current `patient_preferences` supports:
- `preferred_reminder_channel`
- `allow_sms`
- `allow_telegram`
- `allow_call`
- `allow_email`
- `contact_time_window`
- `preferred_language`

Gap vs target:
- Telegram/SMS/call toggles: mostly covered.
- Quiet hours: partially covered via `contact_time_window` but timezone semantics are unclear.
- Per-patient settings: supported.
- Per-guardian settings: missing as separate override/recipient layer.

Baseline schema update plan (future):
- Extend preference model with recipient target strategy (`patient_only`, `guardian_only`, `both`), quiet-hours timezone, and optional branch-specific reminder preference scope if needed.

## F. Branch preference support gap

Current state:
- Booking session stores `branch_id` for transaction flow.
- Patient preferences do not include default branch preference fields.

Needed baseline schema update:
- `default_branch_id` (nullable FK-style reference intent).
- `allow_any_branch` (bool).
- UI binds this to profile preferences and booking slot prefilter.

## G. Documents/questionnaire support gap

Current export/document capabilities:
- Template registry and generated-document lifecycle exist.
- Can link generated docs to patient/booking/chart.

Minimum profile/questionnaire data needed but incomplete:
- 043 export identity block: legal full name, DOB, sex, contact phone, possibly address and document identifiers.
- Pre-visit questionnaire: structured answers (allergies, chronic conditions, meds, pregnancy when relevant, consent flags).
- Consent forms: signer identity and signer role (self vs guardian/representative).
- Guardian block for children: missing explicit source in current patient model.

Classification:
- Existing data source: names, DOB, sex, phone, partial clinical summary text.
- Missing patient fields: address, email (formal), emergency contact, guardian authority fields.
- Missing questionnaire fields: structured question/answer records and versioned questionnaire forms.

## H. Media support gap

Current media/photo state:
- `patient_photos` exists with `media_asset_id`, `external_ref`, `is_primary`, `captured_at`, `source_type`.
- Care products have single `media_asset_id` pointer.
- Export/doc domain includes `MediaAsset` concept and generated doc file assets.

Assessment:
- `patient_photos` is not enough for full patient-avatar + clinical-photo + metadata/visibility/governance needs.
- Missing generic owner-link abstraction across patient/care/document/recommendation/booking.
- Missing explicit Telegram media identity fields and storage provider normalization in patient photo persistence layer.

Needed baseline media model (future baseline schema update):
- `media_assets`
  - `storage_provider`
  - `mime_type`
  - `size_bytes`
  - `telegram_file_id`
  - `telegram_file_unique_id`
  - `object_key`
  - `uploaded_by_actor_id`
- `media_links`
  - `owner_type`
  - `owner_id`
  - `role`
  - `visibility`

Do **not** implement in A2.

## I. Baseline schema update proposal

### Profile
- Add profile-completion and contact-profile fields (email, address, emergency contact, clinic note target).  
Why: support patient-facing profile and document identity completeness.  
Owner service: `PatientProfileService` (future).  
Affected UI PR: P0-08B.  
Risk: medium (new nullable fields + validation policy).  
Backward compatibility: safe in current baseline via nullable/additive rollout.

### Family
- Add `patient_relationships` / `patient_guardians` baseline tables.  
Why: encode authority and relationship semantics missing in raw shared contacts.  
Owner service: `PatientFamilyService`.  
Affected UI PR: P0-08C and P0-08D.  
Risk: medium-high (consent semantics).  
Backward compatibility: additive, existing contact lookup can coexist until cutover.

### Preferences
- Extend preferences with guardian-recipient strategy and explicit quiet-hours timezone.  
Why: reminders must respect who receives what and when.  
Owner service: `PatientPreferenceService`.  
Affected UI PR: P0-08E.  
Risk: low-medium.  
Backward compatibility: default policy preserves current behavior.

### Branch
- Add `default_branch_id`, `allow_any_branch` on patient preference surface.  
Why: stable branch routing and optional free branch choice.  
Owner service: `PatientPreferenceService` + booking selector integration.  
Affected UI PR: P0-08F.  
Risk: low.  
Backward compatibility: nullable defaults.

### Questionnaire
- Add baseline questionnaire storage (`pre_visit_questionnaires` and/or `patient_questionnaire_answers`).  
Why: structured reusable inputs for export/consent and pre-visit workflows.  
Owner service: `PreVisitQuestionnaireService`.  
Affected UI PR: P0-08G.  
Risk: medium.  
Backward compatibility: additive, can start with new submissions only.

### Media
- Add generic `media_assets` + `media_links` baseline tables as shared media foundation.  
Why: unify avatar, product media, document attachments, and clinical visibility rules.  
Owner service: `PatientMediaService` (+ shared media infra).  
Affected UI PR: P0-08M1, P0-08M2, P0-08M3.  
Risk: medium.  
Backward compatibility: bridge path from existing `patient_photos` and product pointer field.

## J. Service implementation plan

- **PatientProfileService**
  - Responsibility: patient-facing profile CRUD, completion calculation, validation boundaries.
  - Repositories: patient registry repo + preference repo + optional questionnaire projection read.
  - API methods: `get_profile`, `update_profile`, `get_completion_status`.
  - First UI consumer: P0-08B profile self wizard.

- **PatientFamilyService**
  - Responsibility: link/unlink dependents, relationship type, guardian authority/consent.
  - Repositories: patient relationship/guardian repos + patient contacts.
  - API methods: `list_linked_profiles`, `add_relationship`, `set_default_contact_recipient`, `validate_authority`.
  - First UI consumer: P0-08C family/dependents.

- **PatientPreferenceService**
  - Responsibility: per-patient reminder + branch preferences.
  - Repositories: patient preferences repo.
  - API methods: `get_preferences`, `update_notification_preferences`, `update_branch_preferences`.
  - First UI consumer: P0-08E and P0-08F.

- **PatientMediaService**
  - Responsibility: avatar and patient media link lifecycle with visibility policy.
  - Repositories: `media_assets` + `media_links` + legacy `patient_photos` bridge.
  - API methods: `attach_avatar`, `list_patient_media`, `set_primary_avatar`, `set_visibility`.
  - First UI consumer: P0-08M3.

- **BookingPatientSelectorService**
  - Responsibility: resolve “Кого записываем?” candidates and fallback strategy.
  - Repositories: patient contacts + family links + booking patient resolution.
  - API methods: `resolve_selector_context`, `choose_patient_for_booking`, `fallback_unknown_patient`.
  - First UI consumer: P0-08D.

- **PreVisitQuestionnaireService**
  - Responsibility: questionnaire templates/answers lifecycle and profile/export projection.
  - Repositories: questionnaire tables + patient medical summary + export assembly reads.
  - API methods: `start_questionnaire`, `save_answer`, `complete_questionnaire`, `build_export_projection`.
  - First UI consumer: P0-08G.

## K. P0-08 implementation split

Refined next stack:
- P0-08A3 baseline schema update plan finalization
- P0-08B profile self wizard
- P0-08C family/dependents
- P0-08D booking patient selector + unknown minimal name fallback
- P0-08E notification settings
- P0-08F branch preference
- P0-08G document/questionnaire bridge
- P0-08M0 TradeFlow media manager audit
- P0-08M1 generic media baseline
- P0-08M2 product media admin
- P0-08M3 patient avatar upload
