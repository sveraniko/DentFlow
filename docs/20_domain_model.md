# DentFlow Domain Model

> Project-wide domain model for DentFlow.

## 1. Purpose

This document defines the high-level domain model of DentFlow.

Its goals are to:

- identify the core bounded contexts;
- define canonical entities and ownership;
- remove ambiguity between project-wide docs and booking-specific docs;
- establish naming and reference rules;
- prepare implementation, storage, events, search, analytics and integrations.

This document is not:
- a SQL schema;
- a migration history;
- a DTO catalog;
- a handler map.

Those belong elsewhere.

---

## 2. Modeling principles

## 2.1 Domain first
Model the business reality first, not Telegram payloads or ORM convenience.

## 2.2 One owner per truth
Every important concern must have one canonical owner.

## 2.3 Stable internal identifiers
Names, phones and Telegram handles are not stable IDs.

## 2.4 Cross-context collaboration by ID, contract and event
Do not share deep mutable object graphs between contexts.

## 2.5 Projections are derived
Search docs, owner digests, exports, and sync payloads are derived, not canonical truth.

## 2.6 Booking alignment rule
Booking docs may go deeper, but they may not contradict project-wide canonical decisions.

---

## 3. Bounded contexts

DentFlow is organized around these contexts:

1. Clinic Reference
2. Access and Identity
3. Policy and Configuration
4. Patient Registry
5. Booking and Scheduling
6. Communication and Reminders
7. Search and Voice Retrieval
8. Clinical Chart
9. Recommendations
10. Care Commerce
11. Media and Documents
12. Analytics
13. Owner Insights
14. Integrations and External Sync

---

## 4. Core reference context

## 4.1 `Clinic`
Represents the deployment’s clinic identity.

Key attributes:
- `clinic_id`
- `code`
- `display_name`
- `timezone`
- `default_locale`
- `status`

## 4.2 `Branch`
Optional internal branch of the clinic.

Key attributes:
- `branch_id`
- `clinic_id`
- `display_name`
- `address_text`
- `timezone`
- `status`

## 4.3 `Doctor`
Clinic bookable/clinical professional reference.

Key attributes:
- `doctor_id`
- `clinic_id`
- `branch_id` (nullable or multi-branch via relation later)
- `display_name`
- `specialty_code`
- `public_booking_enabled`
- `status`

## 4.4 `Service`
Bookable clinic service or visit type.

Key attributes:
- `service_id`
- `clinic_id`
- `code`
- `title_key`
- `duration_minutes`
- `specialty_required`
- `status`

## 4.5 `DoctorAccessCode`
Controlled direct doctor access code.

Key attributes:
- `doctor_access_code_id`
- `clinic_id`
- `doctor_id`
- `code`
- `status`
- `expires_at`
- `max_uses`
- `service_scope`
- `branch_scope`

---

## 5. Access and Identity context

Authoritative detail lives in `docs/22_access_and_identity_model.md`.

Key entities:
- `ActorIdentity`
- `TelegramBinding`
- `StaffMember`
- `ClinicRoleAssignment`
- `DoctorProfile`
- `OwnerProfile`
- `ServicePrincipal`

This context owns:
- staff identity
- role bindings
- Telegram-to-staff bindings
- privileged eligibility metadata

This context does not own patient identity.

---

## 6. Policy and Configuration context

Authoritative detail lives in `docs/23_policy_and_configuration_model.md`.

Key entities:
- `PolicySet`
- `PolicyValue`
- `FeatureFlag`

This context owns:
- clinic policies
- branch policies
- doctor booking policies
- reminder policies
- export policies
- AI/integration toggles

---

## 7. Patient Registry context

## 7.1 Purpose
Owns canonical patient identity and lightweight operational patient profile.

## 7.2 Core aggregate: `Patient`
Key attributes:
- `patient_id`
- `clinic_id`
- `patient_number` (nullable at create)
- `full_name_legal`
- `first_name`
- `last_name`
- `middle_name` (nullable)
- `display_name`
- `birth_date` (nullable early)
- `sex_marker` (nullable)
- `status`
- `created_at`
- `updated_at`
- `first_seen_at`
- `last_seen_at`

## 7.3 Supporting entities
- `PatientContact`
- `PatientPreference`
- `PatientFlag`
- `PatientPhoto`
- `PatientMedicalSummary`
- `PatientExternalId`

## 7.4 Important rule
Patient Registry is the **only canonical patient truth**.

Booking may use:
- `patient_id`;
- patient lookup projections;
- booking-session contact snapshots.

Booking must not own a second patient registry.

---

## 8. Booking and Scheduling context

Booking detail is elaborated in `booking_docs/*`.

## 8.1 Core aggregates

### `BookingSession`
Represents in-progress booking interaction.

Key attributes:
- `booking_session_id`
- `clinic_id`
- `branch_id` (nullable)
- `telegram_user_id`
- `resolved_patient_id` (nullable)
- `route_type`
- `service_id`
- `doctor_id` (nullable)
- `doctor_code_raw` (nullable)
- `requested_date_type`
- `requested_date`
- `time_window`
- `urgency_type`
- `selected_slot_id` (nullable)
- `selected_hold_id` (nullable)
- `contact_phone_snapshot` (nullable)
- `status`
- `expires_at`
- `created_at`
- `updated_at`

### `AvailabilitySlot`
Concrete bookable time interval.

Key attributes:
- `slot_id`
- `clinic_id`
- `branch_id` (nullable)
- `doctor_id`
- `service_scope`
- `start_at`
- `end_at`
- `status`
- `source_ref`
- `visibility_policy`

### `SlotHold`
Temporary slot lock.

Key attributes:
- `slot_hold_id`
- `clinic_id`
- `slot_id`
- `booking_session_id`
- `telegram_user_id`
- `status`
- `expires_at`
- `created_at`

### `Booking`
Canonical final appointment aggregate.

Key attributes:
- `booking_id`
- `clinic_id`
- `branch_id` (nullable)
- `patient_id`
- `doctor_id`
- `service_id`
- `slot_id` (nullable if schedule source varies)
- `booking_mode`
- `source_channel`
- `scheduled_start_at`
- `scheduled_end_at`
- `status`
- `reason_for_visit_short`
- `patient_note` (nullable)
- `confirmation_required`
- `confirmed_at` (nullable)
- `canceled_at` (nullable)
- `checked_in_at` (nullable)
- `in_service_at` (nullable)
- `completed_at` (nullable)
- `no_show_at` (nullable)
- `created_at`
- `updated_at`

### `WaitlistEntry`
Demand without immediate slot.

Key attributes:
- `waitlist_entry_id`
- `clinic_id`
- `branch_id` (nullable)
- `patient_id` (nullable before resolution)
- `telegram_user_id` (nullable)
- `service_id`
- `doctor_id` (nullable)
- `date_window`
- `time_window`
- `status`
- `created_at`

### `BookingHistoryEntry`
Immutable transition/history record for booking lifecycle.

## 8.2 Important rules
- final booking confirmation must validate slot truth atomically;
- the final aggregate is `Booking`, not a split between booking and appointment;
- `patient_id` points to Patient Registry truth;
- reminders are triggered by booking facts, not owned inside booking.

---

## 9. Communication and Reminders context

## 9.1 Purpose
Owns reminder truth and communication execution state.

## 9.2 Core entities
- `ReminderJob`
- `MessageDelivery`
- `ReminderAcknowledgement` (optional as dedicated entity or embedded relation)

## 9.3 Important rule
Booking does not own notification truth.

Booking may trigger:
- reminder creation;
- reminder cancellation;
- reminder reschedule.

Communication owns:
- reminder lifecycle;
- delivery attempts;
- acknowledgement;
- failure visibility.

---

## 10. Search and Voice Retrieval context

## 10.1 Purpose
Owns search projections and retrieval assistance.

## 10.2 Core entities
- `PatientSearchProjection`
- `DoctorSearchProjection`
- `ServiceSearchProjection`
- `VoiceSearchAttempt` (optional short-lived artifact)

## 10.3 Important rule
Search is derived and rebuildable.

---

## 11. Clinical Chart context

## 11.1 Purpose
Owns structured clinical facts.

## 11.2 Core aggregates
- `PatientChart`
- `ClinicalEncounter`
- `EncounterNote`
- `Diagnosis`
- `TreatmentPlan`
- `OdontogramSnapshot`
- `ImagingReference`
- `MedicalHistoryEntry`

## 11.3 Important rule
This context stores runtime clinical facts.
Export documents are projections from these facts.

---

## 12. Recommendations context

## 12.1 Purpose
Owns structured next-step recommendations.

## 12.2 Core entities
- `Recommendation`
- `RecommendationAction`
- `RecommendationSource`

Recommendations may be:
- doctor-issued
- admin-issued
- auto-triggered by rules

---

## 13. Care Commerce context

## 13.1 Purpose
Owns care-product flows tied to aftercare and treatment support.

## 13.2 Core aggregates
- `CareProduct`
- `CareOrder`
- `CareOrderItem`
- `CareReservation`
- `RecommendationProductLink`

## 13.3 Important rule
Care Commerce is its own bounded context.
It is related to care, but it does not own patient or booking truth.

---

## 14. Media and Documents context

## 14.1 Purpose
Owns media asset registry and generated document artifacts.

## 14.2 Core entities
- `MediaAsset`
- `DocumentTemplate`
- `GeneratedDocument`
- `DocumentAccessRecord` (optional)
- `ExternalMediaReference` (optional modeling style)

---

## 15. Analytics context

## 15.1 Purpose
Owns event-derived metrics and operational projections.

## 15.2 Core entities
- `AnalyticsEventLedger`
- `DailyBookingMetrics`
- `DoctorPerformanceProjection`
- `RetentionProjection`
- `CareAttachRateProjection`

Analytics does not own canonical operational truth.

---

## 16. Owner Insights context

## 16.1 Purpose
Owns owner-facing management views.

## 16.2 Core entities
- `OwnerDailyDigest`
- `OwnerLiveSnapshot`
- `OwnerAlert`
- `OwnerQuestionAnswer` (if stored)
- `OwnerFederatedSourceRef` (future federation support)

Owner Insights consumes analytics and selected projections.
It does not replace them.

---

## 17. Integrations and External Sync context

## 17.1 Purpose
Owns adapters, sync jobs, and external identity mapping.

## 17.2 Core entities
- `ExternalSystem`
- `ExternalIdMap`
- `SyncJob`
- `SyncRunResult`

Important use cases:
- Google Sheets controlled sync
- external clinic system adapters
- future owner federation adapters
- export/import pipelines

---

## 18. Naming rules

Use:
- `Booking` as the canonical final appointment aggregate;
- one stable cancellation spelling everywhere;
- one stable reschedule vocabulary everywhere;
- `patient_id` for canonical patient references;
- `clinic_id` always;
- `branch_id` where branch scope exists.

---

## 19. Cross-context reference rules

Preferred reference style:
- by stable ID
- with read-model/projection when fast display is needed
- with events for downstream reactions

Examples:
- Booking -> Patient Registry via `patient_id`
- ReminderJob -> Booking via `booking_id`
- CareOrder -> Recommendation via `recommendation_id`
- GeneratedDocument -> Patient/Chart/Encounter via IDs
- Search projection -> rebuild from canonical sources

---

## 20. Summary

DentFlow domain model is built around:

- one clinic per deployment;
- optional branches;
- explicit access and policy contexts;
- Patient Registry as canonical patient truth;
- Booking as the canonical final appointment aggregate;
- Communication as canonical reminder truth;
- structured clinical facts;
- export/document projections;
- analytics and owner layers as derived views.

This is the model that implementation must obey.
