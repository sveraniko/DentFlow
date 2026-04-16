# DentFlow Data Model

> Storage-oriented data model strategy for DentFlow.

## 1. Purpose

This document translates DentFlow’s domain model into a storage strategy suitable for implementation.

It exists to ensure that:
- the system is not under-modeled;
- the system is not overbuilt into a medical monster;
- critical ownership boundaries are preserved in storage;
- future fields can be added without ripping apart the whole project.

---

## 2. Design stance

DentFlow must support three layers of patient-related data:

1. **operational profile**
2. **clinical record**
3. **document/export projection**

These layers are connected, but they are not the same table and they are not the same usage surface.

That is how we avoid both:
- toy models that collapse later,
- and xls-shaped medical misery from day one.

---

## 3. Physical storage strategy

## 3.1 Default database strategy
Use one primary Postgres cluster during active development and early implementation.

Logical schema groups:
- `core_reference`
- `access_identity`
- `policy_config`
- `core_patient`
- `booking`
- `communication`
- `clinical`
- `care_commerce`
- `media_docs`
- `integration`
- `analytics_raw`
- `owner_views`

Search index and object storage remain separate infrastructure surfaces.

## 3.2 Deployment stance
Even though runtime is single-clinic per deployment by default:
- `clinic_id` is still present in canonical transactional tables;
- `branch_id` is available where branch resolution matters.

This preserves clean ownership and future federation compatibility.

---

## 4. Patient storage strategy

## 4.1 Canonical patient tables
Recommended core tables:
- `core_patient.patients`
- `core_patient.patient_contacts`
- `core_patient.patient_preferences`
- `core_patient.patient_flags`
- `core_patient.patient_photos`
- `core_patient.patient_medical_summaries`
- `core_patient.patient_external_ids`

### Important rule
There is no second canonical patient registry inside booking.

Booking uses:
- `patient_id` foreign keys;
- projections;
- session snapshots.

A second patient registry inside booking is forbidden.

---

## 5. Booking storage strategy

## 5.1 Canonical final table
Use:
- `booking.bookings`

Do not split final truth into multiple competing final-appointment tables.

## 5.2 Recommended booking tables
- `booking.booking_sessions`
- `booking.session_events`
- `booking.availability_slots`
- `booking.slot_holds`
- `booking.bookings`
- `booking.booking_status_history`
- `booking.waitlist_entries`
- `booking.admin_escalations`

## 5.3 Recommended final booking fields
- `id`
- `clinic_id`
- `branch_id` nullable
- `patient_id` fk -> `core_patient.patients.id`
- `doctor_id`
- `service_id`
- `slot_id` nullable
- `booking_mode`
- `source_channel`
- `scheduled_start_at`
- `scheduled_end_at`
- `status`
- `reason_for_visit_short`
- `patient_note` nullable
- `confirmation_required`
- `confirmed_at` nullable
- `canceled_at` nullable
- `checked_in_at` nullable
- `in_service_at` nullable
- `completed_at` nullable
- `no_show_at` nullable
- `created_at`
- `updated_at`

## 5.4 Canonical final booking status values
- `pending_confirmation`
- `confirmed`
- `reschedule_requested`
- `canceled`
- `checked_in`
- `in_service`
- `completed`
- `no_show`

## 5.5 History
Use history/event tables for:
- create
- confirm
- reschedule
- cancel
- no-show
- check-in
- in-service
- complete

Reschedule is primarily a history/event fact plus updated scheduled fields, not a separate permanent final status bucket.

---

## 6. Reminder storage strategy

## 6.1 Canonical reminder tables
Use:
- `communication.reminder_jobs`
- `communication.message_deliveries`

Optional:
- `communication.reminder_acknowledgements`

## 6.2 Important rule
Do not keep a second canonical reminder table inside booking.

No second reminder-task table as competing truth.

Booking may reference reminder IDs or trigger creation, but reminder lifecycle belongs to `communication`.

## 6.3 Recommended reminder fields
For `reminder_jobs`:
- `id`
- `clinic_id`
- `patient_id`
- `booking_id` nullable
- `care_order_id` nullable
- `recommendation_id` nullable
- `reminder_type`
- `channel`
- `status`
- `scheduled_for`
- `action_required`
- `ack_kind_expected` nullable
- `sent_at` nullable
- `acknowledged_at` nullable
- `expires_at` nullable
- `payload_key`
- `locale_at_send_time`
- `created_at`
- `updated_at`

This directly supports the high-value “please confirm / already on my way” pattern without inventing a shadow booking state model.

---

## 7. Access and identity storage strategy

Authoritative detail lives in `docs/22_access_and_identity_model.md`.

Recommended tables:
- `access_identity.actor_identities`
- `access_identity.telegram_bindings`
- `access_identity.staff_members`
- `access_identity.clinic_role_assignments`
- `access_identity.service_principals`

---

## 8. Policy/config storage strategy

Authoritative detail lives in `docs/23_policy_and_configuration_model.md`.

Recommended tables:
- `policy_config.policy_sets`
- `policy_config.policy_values`
- `policy_config.feature_flags`

Important rule:
business policy does not live only in `.env`.

---

## 9. Clinical storage strategy

Recommended tables:
- `clinical.patient_charts`
- `clinical.medical_history_entries`
- `clinical.presenting_complaints`
- `clinical.clinical_encounters`
- `clinical.encounter_notes`
- `clinical.diagnoses`
- `clinical.treatment_plans`
- `clinical.odontogram_snapshots`
- `clinical.oral_exam_summaries`
- `clinical.imaging_references`
- `clinical.radiation_dose_records` (optional)

## Important rule
The runtime chart stores structured facts.
It does not try to be a literal paper-sheet clone.

---

## 10. Media and document storage strategy

Recommended tables:
- `media_docs.media_assets`
- `media_docs.document_templates`
- `media_docs.generated_documents`

Important behavior:
- file binaries live in object storage or controlled external systems;
- DB stores metadata and references;
- large CT or imaging artifacts may be stored as controlled external references.

---

## 11. Export and 043 strategy

DentFlow should generate 043-style outputs from structured facts.

Recommended approach:
- keep runtime patient/chart/encounter data normalized and usable;
- render 043-style export through document templates;
- support editable export source if clinic workflow requires it.

Do not force the runtime data model to mimic a paper spreadsheet just because the paper exists.

---

## 12. Search storage strategy

Search projections are rebuildable read models.

Recommended search projection tables/indices:
- `search.patient_search_projection`
- `search.doctor_search_projection`
- `search.service_search_projection`

These projections may include:
- name tokens
- transliteration tokens
- phone tokens
- patient number
- branch info
- doctor/service rank helpers
- minimal photo preview reference

They must not contain giant raw clinical note blobs.

---

## 13. Analytics and owner storage strategy

Recommended projection families:
- `analytics_raw.event_ledger`
- `owner_views.daily_metrics`
- `owner_views.doctor_metrics`
- `owner_views.service_metrics`
- `owner_views.retention_metrics`
- `owner_views.care_metrics`
- `owner_views.anomaly_candidates`

This layer is derived.
Do not point owner dashboards directly at transactional hot paths for every heavy calculation.

---

## 14. Integration storage strategy

Recommended tables:
- `integration.external_systems`
- `integration.external_id_maps`
- `integration.sync_jobs`
- `integration.sync_job_results`

This is how DentFlow can later support:
- Google Sheets
- external clinic systems
- owner federation inputs
- export adapters

without poisoning the core.

---

## 15. Seed and fixture readiness

Before Sheets integration exists, the system must support seed/import scripts for:
- clinics/branches
- doctors
- services
- fake patients
- booking history
- visit history
- recommendations
- care products/orders
- media references

A large workflow system tested only on empty data is not a tested system.

---

## 16. Summary

The DentFlow data model is built around:

- Patient Registry as canonical patient truth;
- `booking.bookings` as the canonical final booking table;
- Communication as canonical reminder truth;
- structured clinical facts;
- document/export projections instead of paper-shaped runtime storage;
- explicit access and policy tables;
- rebuildable projections for search and owner views;
- adapter-ready integration tables.

This is the storage shape that keeps DentFlow strong instead of brittle.
