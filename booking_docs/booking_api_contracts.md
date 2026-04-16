# Booking API Contracts

## 1. Purpose

This document defines the recommended service/API contracts for the booking subsystem.

The contracts may later be implemented as:
- internal application services,
- REST endpoints,
- command/query handlers,
- RPC-style calls.

The transport may change.
The semantics should remain stable.

---

## 2. Contract principles

- Telegram handlers stay thin
- sessions orchestrate the wizard
- slot truth is validated server-side
- writes should be idempotent where race conditions exist
- final booking aggregate remains canonical
- patient resolution uses Patient Registry
- reminder truth is handled through Communication

---

## 3. Core contract groups

## 3.1 Session lifecycle
- `start_booking_session`
- `cancel_booking_session`
- `resume_booking_session`
- `expire_booking_session`

## 3.2 Session input collection
- `set_booking_service`
- `set_booking_urgency`
- `set_booking_date_preference`
- `set_booking_time_window`
- `set_doctor_preference`
- `validate_doctor_code`
- `set_contact_snapshot`

## 3.3 Slot search and hold
- `get_slot_proposals`
- `broaden_slot_search`
- `create_slot_hold`
- `release_slot_hold`

## 3.4 Final booking actions
- `confirm_booking`
- `request_reschedule`
- `reschedule_booking`
- `cancel_booking`
- `mark_checked_in`
- `mark_in_service`
- `complete_booking`
- `mark_no_show`

## 3.5 Waitlist and escalation
- `join_waitlist`
- `offer_waitlist_slot`
- `create_admin_escalation`

---

## 4. Example contract semantics

## `start_booking_session`
Input:
- `clinic_id`
- `telegram_user_id`
- optional `branch_id`

Output:
- `booking_session_id`
- current `status`
- current active panel surface

## `confirm_booking`
Input:
- `booking_session_id`
- `idempotency_key`

Behavior:
- validate session state
- validate selected slot / hold
- resolve or create canonical patient in Patient Registry
- create final `Booking`
- emit booking events
- trigger reminder scheduling intent

Output:
- `booking_id`
- `status`
- `scheduled_start_at`
- reminder summary hint if desired

## `request_reschedule`
Input:
- `booking_id`
- actor context

Output:
- booking status -> `reschedule_requested`

## `reschedule_booking`
Input:
- `booking_id`
- new slot selection
- idempotency key

Behavior:
- atomically secure new slot
- update booking schedule
- write history/event
- reset status to appropriate active state, usually `confirmed`
- update reminders

## `cancel_booking`
Input:
- `booking_id`
- actor context
- optional reason

Behavior:
- set `status = canceled`
- release capacity
- emit booking event
- update reminders

---

## 5. Error contract guidance

Use explicit error families such as:
- `booking_session_not_found`
- `booking_session_expired`
- `invalid_doctor_code`
- `slot_not_available`
- `booking_not_found`
- `booking_already_canceled`
- `invalid_booking_transition`
- `patient_resolution_failed`
- `reminder_schedule_failed_nonblocking` (if exposed as warning)

---

## 6. Idempotency guidance

Important write operations should support idempotency, especially:
- `confirm_booking`
- `reschedule_booking`
- `cancel_booking`
- `mark_checked_in`
- `mark_in_service`
- `complete_booking`

The goal is to prevent duplicate bookings and duplicate state transitions under retries or Telegram weirdness.

---

## 7. Summary

Booking contracts are:
- session-centric for flow orchestration;
- server-validated for slot truth;
- canonical around `Booking`;
- aligned with Patient Registry and Communication rather than duplicating them.
