# Booking Domain Model

## 1. Purpose

This document defines the conceptual domain model for the booking subsystem.

It exists to ensure implementation builds the correct objects and boundaries instead of improvising them from UI flow alone.

---

## 2. Key booking-domain rule

Booking is a dedicated bounded context, but it is **not** allowed to own:
- a second patient registry;
- a second reminder system;
- a clinic-wide policy store.

Booking references and collaborates with those contexts.

---

## 3. Core booking entities

## 3.1 `BookingSession`
Represents an in-progress Telegram booking interaction.

Responsibilities:
- keep wizard state;
- keep temporary choices;
- allow pause/resume;
- hold ephemeral contact snapshots;
- connect to slot proposals and holds.

Suggested fields:
- `booking_session_id`
- `clinic_id`
- `branch_id` nullable
- `telegram_user_id`
- `resolved_patient_id` nullable
- `status`
- `route_type`
- `service_id`
- `urgency_type`
- `requested_date_type`
- `requested_date`
- `time_window`
- `doctor_preference_type`
- `doctor_id` nullable
- `doctor_code_raw` nullable
- `selected_slot_id` nullable
- `selected_hold_id` nullable
- `contact_phone_snapshot` nullable
- `notes` nullable
- `expires_at`
- `created_at`
- `updated_at`

## 3.2 `AvailabilitySlot`
Represents a bookable capacity interval.

Suggested fields:
- `slot_id`
- `clinic_id`
- `branch_id` nullable
- `doctor_id`
- `start_at`
- `end_at`
- `status`
- `visibility_policy`
- `service_scope`
- `source_ref`
- `updated_at`

## 3.3 `SlotHold`
Represents a temporary slot lock.

Suggested fields:
- `slot_hold_id`
- `clinic_id`
- `slot_id`
- `booking_session_id`
- `telegram_user_id`
- `status`
- `expires_at`
- `created_at`

## 3.4 `Booking`
Represents the final appointment aggregate.

Suggested fields:
- `booking_id`
- `clinic_id`
- `branch_id` nullable
- `patient_id`
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

## 3.5 `WaitlistEntry`
Represents demand without immediate capacity.

Suggested fields:
- `waitlist_entry_id`
- `clinic_id`
- `branch_id` nullable
- `patient_id` nullable
- `telegram_user_id` nullable
- `service_id`
- `doctor_id` nullable
- `date_window`
- `time_window`
- `status`
- `created_at`
- `updated_at`

## 3.6 `AdminEscalation`
Represents handoff from automated booking to clinic staff.

Suggested fields:
- `admin_escalation_id`
- `clinic_id`
- `booking_session_id`
- `patient_id` nullable
- `reason_code`
- `priority`
- `status`
- `payload_summary`
- `created_at`
- `updated_at`

---

## 4. External references booking relies on

Booking depends on:
- `patient_id` from Patient Registry
- doctor/service/branch references from Clinic Reference
- booking/reminder policies from Policy/Configuration
- reminder orchestration from Communication / Reminders

---

## 5. Canonical final booking statuses

- `pending_confirmation`
- `confirmed`
- `reschedule_requested`
- `canceled`
- `checked_in`
- `in_service`
- `completed`
- `no_show`

Use events/history for:
- created
- rescheduled
- archived

---

## 6. Invariants

- final booking confirmation must verify slot truth atomically;
- slot holds must expire predictably;
- a final booking must point to canonical patient truth;
- booking does not own reminder execution truth;
- route policy must respect doctor and clinic configuration;
- branch scope, if used, must remain clinic-local.

---

## 7. Summary

The booking domain model is built around:
- sessions;
- slots;
- holds;
- final bookings;
- waitlist;
- admin escalation;

with explicit references to canonical patient, policy and reminder contexts.
