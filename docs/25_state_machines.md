# DentFlow State Machines

> Canonical lifecycle definitions for DentFlow.

## 1. Purpose

This document defines the canonical lifecycle state machines used across DentFlow.

It exists to ensure that:
- one business fact is represented one way;
- handlers do not invent local pseudo-statuses;
- UI labels do not drift away from backend truth;
- analytics, reminders, exports, and projections can trust lifecycle semantics.

---

## 2. State-machine principles

## 2.1 Canonical state is backend truth
Localized labels and UI badges are derived from canonical state keys.

## 2.2 Creation facts and status facts are not always the same
Some facts belong in:
- events,
- history,
- timestamps,
- projections,

rather than in another competing status enum.

## 2.3 Terminal states must be explicit
A lifecycle must clearly define active, terminal and derived/archive semantics.

## 2.4 Transitions must be actor-aware
Where relevant, preserve:
- actor type
- actor id
- timestamp
- reason code
- source surface

## 2.5 Keep status sets small but meaningful
If two states are not operationally different, they probably should not both exist.

---

## 3. Canonical status spelling

Use one stable canonical spelling and one stable reschedule vocabulary everywhere.

No spelling war and no legacy status dialects inside the database, thanks.

---

## 4. BookingSession lifecycle

## States
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

## Notes
- session lifecycle is conversational/orchestration lifecycle;
- it is not the same as final booking lifecycle;
- an expired session must not create a final booking by accident.

---

## 5. SlotHold lifecycle

## States
- `created`
- `active`
- `released`
- `expired`
- `consumed`
- `canceled`

## Notes
- `consumed` means a final booking used the hold;
- `released` means intentionally returned;
- `expired` means TTL ended;
- active holds must not persist forever.

---

## 6. Final Booking lifecycle

This is the canonical lifecycle for the final appointment aggregate.

## 6.1 Persisted states
- `pending_confirmation`
- `confirmed`
- `reschedule_requested`
- `canceled`
- `checked_in`
- `in_service`
- `completed`
- `no_show`

## 6.2 Why this set

This set is intentionally kept stable and limited.

It avoids three problems:
- duplicate “created” vs “pending” truths;
- artificial `rescheduled` final state that is really a history/event fact;
- fake archive states polluting transactional truth.

## 6.3 Lifecycle semantics

### `pending_confirmation`
Booking exists, but operational confirmation is still required.

### `confirmed`
Booking is accepted and expected.

### `reschedule_requested`
A change request exists and requires workflow handling.

### `canceled`
Booking is not expected to occur.

### `checked_in`
Patient arrived and was accepted operationally.

### `in_service`
Actual service has begun.

### `completed`
Visit finished successfully enough to drive downstream flows.

### `no_show`
Expected booking did not occur within clinic rules.

## 6.4 Important non-status facts

The following are tracked as history/events/timestamps, not alternative canonical states:
- booking created
- booking rescheduled
- booking archived for display
- booking exported
- booking synced externally

## 6.5 Typical transitions
- `pending_confirmation -> confirmed`
- `pending_confirmation -> canceled`
- `pending_confirmation -> no_show`
- `confirmed -> reschedule_requested`
- `reschedule_requested -> confirmed` (after successful new slot/time resolution)
- `reschedule_requested -> canceled`
- `confirmed -> checked_in`
- `checked_in -> in_service`
- `in_service -> completed`
- `confirmed -> no_show`

## 6.6 Forbidden transitions
- `canceled -> checked_in`
- `no_show -> in_service`
- `completed -> confirmed`
- `completed -> pending_confirmation`

If a booking needs reopening, do it explicitly through controlled logic or create a new booking linked to history.

---

## 7. WaitlistEntry lifecycle

## States
- `created`
- `active`
- `offered`
- `accepted`
- `declined`
- `expired`
- `fulfilled`
- `canceled`

## Notes
- `fulfilled` means a real booking resulted;
- waitlist should not silently create double-booking.

---

## 8. Reminder lifecycle

Reminder truth belongs to Communication / Reminders.

## 8.1 States
- `scheduled`
- `queued`
- `sent`
- `acknowledged`
- `failed`
- `canceled`
- `expired`

### Optional transport-only status
- `delivered` if a channel/provider can confirm delivery meaningfully

## 8.2 Reminder semantics

### `scheduled`
Reminder exists and is planned.

### `queued`
Reminder is ready for dispatch.

### `sent`
DentFlow completed dispatch attempt successfully.

### `acknowledged`
Recipient completed the expected interaction.

Examples:
- confirmed visit;
- indicated “already on my way”;
- acknowledged pickup readiness;
- accepted the next step.

### `failed`
Dispatch failed materially.

### `canceled`
Reminder became irrelevant before success.

### `expired`
Reminder window ended.

## 8.3 Acknowledgement kinds

Use structured acknowledgement kinds rather than new statuses.
Examples:
- `booking_confirmed`
- `already_on_my_way`
- `reschedule_requested`
- `pickup_confirmed`
- `recommendation_acknowledged`

This is cleaner than breeding extra status enums.

---

## 9. Recommendation lifecycle

## States
- `draft`
- `prepared`
- `issued`
- `viewed`
- `acknowledged`
- `accepted`
- `declined`
- `expired`
- `withdrawn`

---

## 10. CareOrder lifecycle

## States
- `draft`
- `created`
- `awaiting_confirmation`
- `confirmed`
- `awaiting_payment`
- `paid`
- `awaiting_fulfillment`
- `ready_for_pickup`
- `issued`
- `fulfilled`
- `canceled`
- `expired`

---

## 11. CareReservation lifecycle

## States
- `created`
- `active`
- `released`
- `consumed`
- `expired`
- `canceled`

---

## 12. SyncJob lifecycle

Optional but useful as first-class operational state.

## States
- `created`
- `running`
- `completed`
- `partial_success`
- `failed`
- `canceled`

---

## 13. Derived/visual statuses are not canonical state

Views may show:
- “today”
- “late confirmation risk”
- “needs pickup”
- “overdue follow-up”

These are projections.
They are not replacements for canonical state.

---

## 14. Summary

The canonical lifecycle map is built around:

- small, stable status enums;
- explicit history and event facts;
- one final booking state model;
- reminders with acknowledgement semantics instead of status spam;
- recommendations and care orders with their own proper lifecycles.

This is what keeps DentFlow coherent under real operational load.
