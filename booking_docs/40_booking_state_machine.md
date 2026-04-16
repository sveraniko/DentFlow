# Booking State Machine

## 1. Purpose

This document defines booking-specific lifecycle behavior.

It covers:
- conversational booking session lifecycle;
- slot hold lifecycle;
- final booking lifecycle alignment with project-wide canonical states.

---

## 2. BookingSession states

Canonical session states:
- `initiated`
- `in_progress`
- `awaiting_slot_selection`
- `awaiting_contact_confirmation`
- `review_ready`
- `completed`
- `canceled`
- `expired`
- `abandoned`
- `admin_escalated`

### Key transition examples
- `initiated -> in_progress`
- `in_progress -> awaiting_slot_selection`
- `awaiting_slot_selection -> awaiting_contact_confirmation`
- `awaiting_contact_confirmation -> review_ready`
- `review_ready -> completed`
- active states -> `canceled`
- active states -> `expired`
- active states -> `admin_escalated`

Session lifecycle is not the same as final booking lifecycle.

---

## 3. SlotHold states

- `created`
- `active`
- `released`
- `expired`
- `consumed`
- `canceled`

### Notes
- `consumed` means a final booking used the hold;
- `expired` is TTL expiry;
- `released` is intentional release;
- active hold must never live forever.

---

## 4. Final Booking states

Canonical persisted booking statuses:
- `pending_confirmation`
- `confirmed`
- `reschedule_requested`
- `canceled`
- `checked_in`
- `in_service`
- `completed`
- `no_show`

### Transition examples
- `pending_confirmation -> confirmed`
- `pending_confirmation -> canceled`
- `pending_confirmation -> no_show`
- `confirmed -> reschedule_requested`
- `reschedule_requested -> confirmed`
- `reschedule_requested -> canceled`
- `confirmed -> checked_in`
- `checked_in -> in_service`
- `in_service -> completed`
- `confirmed -> no_show`

### Important note
`booking.rescheduled` is an event/history fact.
It is not a separate permanent final booking status.

---

## 5. Waitlist states

- `created`
- `active`
- `offered`
- `accepted`
- `declined`
- `expired`
- `fulfilled`
- `canceled`

---

## 6. Stale callback rule

Any stale Telegram callback must:
- be detected;
- avoid mutating wrong live state;
- guide the user back into the current active panel/session.

No old button should be allowed to corrupt live booking truth.

---

## 7. Summary

Booking state discipline in DentFlow is based on:
- clear session state;
- clear hold state;
- one canonical final booking status model;
- explicit stale callback handling.
