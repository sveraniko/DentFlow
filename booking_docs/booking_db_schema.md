# Booking DB Schema

## 1. Purpose

This document defines the recommended schema blueprint for the booking subsystem.

It is intended to align:
- booking behavior,
- canonical project-wide modeling,
- implementation-ready storage structure.

This is a schema design document, not final migration SQL.

---

## 2. Canonical schema decisions

- logical schema namespace = `booking`
- final appointment table = `booking.bookings`
- patient truth lives outside booking in `core_patient`
- reminders live outside booking in `communication`
- default deployment is single-clinic with optional branch scope

---

## 3. Recommended table map

### Reference / scheduling
- `doctors`
- `services`
- `doctor_specialties`
- `doctor_access_codes`
- `branches` (if booking-local reference copy is used, otherwise cross-schema reference strategy)

### Session and capacity
- `booking_sessions`
- `session_events`
- `availability_slots`
- `slot_holds`

### Final booking layer
- `bookings`
- `booking_status_history`

### Fallback / ops
- `waitlist_entries`
- `admin_escalations`

### Cross-schema references
- `core_patient.patients`
- `communication.reminder_jobs` (booking references reminder ids if needed, but does not own reminder table)

---

## 4. `booking.booking_sessions`

Suggested columns:
- `id` uuid pk
- `clinic_id` uuid not null
- `branch_id` uuid null
- `telegram_user_id` bigint not null
- `resolved_patient_id` uuid null fk -> `core_patient.patients.id`
- `status` text not null
- `route_type` text not null
- `service_id` uuid null
- `urgency_type` text null
- `requested_date_type` text null
- `requested_date` date null
- `time_window` text null
- `doctor_preference_type` text null
- `doctor_id` uuid null
- `doctor_code_raw` text null
- `selected_slot_id` uuid null
- `selected_hold_id` uuid null
- `contact_phone_snapshot` text null
- `notes` text null
- `expires_at` timestamptz not null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Recommended indexes:
- `(clinic_id, telegram_user_id, updated_at desc)`
- `(status, expires_at)`

---

## 5. `booking.availability_slots`

Suggested columns:
- `id`
- `clinic_id`
- `branch_id` null
- `doctor_id`
- `start_at`
- `end_at`
- `status`
- `visibility_policy`
- `service_scope` jsonb or normalized relation
- `source_ref` text null
- `updated_at`

Recommended indexes:
- `(clinic_id, doctor_id, start_at)`
- `(clinic_id, branch_id, start_at)`
- `(status, start_at)`

---

## 6. `booking.slot_holds`

Suggested columns:
- `id`
- `clinic_id`
- `slot_id`
- `booking_session_id`
- `telegram_user_id`
- `status`
- `expires_at`
- `created_at`

Recommended indexes:
- `(slot_id, status)`
- `(status, expires_at)`

---

## 7. `booking.bookings`

Suggested columns:
- `id`
- `clinic_id`
- `branch_id` null
- `patient_id` uuid not null fk -> `core_patient.patients.id`
- `doctor_id` uuid not null
- `service_id` uuid not null
- `slot_id` uuid null
- `booking_mode` text not null
- `source_channel` text not null
- `scheduled_start_at` timestamptz not null
- `scheduled_end_at` timestamptz not null
- `status` text not null
- `reason_for_visit_short` text null
- `patient_note` text null
- `confirmation_required` boolean not null default true
- `confirmed_at` timestamptz null
- `canceled_at` timestamptz null
- `checked_in_at` timestamptz null
- `in_service_at` timestamptz null
- `completed_at` timestamptz null
- `no_show_at` timestamptz null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Canonical status values:
- `pending_confirmation`
- `confirmed`
- `reschedule_requested`
- `canceled`
- `checked_in`
- `in_service`
- `completed`
- `no_show`

Recommended indexes:
- `(clinic_id, scheduled_start_at)`
- `(clinic_id, patient_id, scheduled_start_at desc)`
- `(clinic_id, doctor_id, scheduled_start_at)`
- `(clinic_id, status, scheduled_start_at)`

---

## 8. `booking.booking_status_history`

Suggested columns:
- `id`
- `booking_id`
- `old_status` null
- `new_status`
- `reason_code` null
- `actor_type` null
- `actor_id` null
- `occurred_at`

This is where reschedule, cancel, check-in and other meaningful transitions remain traceable.

---

## 9. `booking.waitlist_entries`

Suggested columns:
- `id`
- `clinic_id`
- `branch_id` null
- `patient_id` uuid null
- `telegram_user_id` bigint null
- `service_id`
- `doctor_id` uuid null
- `date_window` jsonb or normalized fields
- `time_window` text null
- `priority` int default 0
- `status`
- `source_session_id` uuid null
- `notes` text null
- `created_at`
- `updated_at`

---

## 10. `booking.admin_escalations`

Suggested columns:
- `id`
- `clinic_id`
- `booking_session_id`
- `patient_id` uuid null
- `reason_code`
- `priority`
- `status`
- `assigned_to_actor_id` uuid null
- `payload_summary` jsonb null
- `created_at`
- `updated_at`

---

## 11. What is intentionally not in booking schema

The following are intentionally outside canonical booking schema:
- a second patient registry
- a second reminder task system

Reason:
- patient truth belongs to Patient Registry
- reminder truth belongs to Communication

This is deliberate, not omission.

---

## 12. Summary

The booking schema is built around:
- sessions
- slots
- holds
- final bookings
- waitlist
- admin escalation
- clean cross-schema references to patient and reminder truth

This is the schema shape that keeps booking aligned with the rest of DentFlow.
