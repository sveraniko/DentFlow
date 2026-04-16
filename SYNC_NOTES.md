# DentFlow Synchronization Notes

> Sync pass performed to remove ambiguity before implementation.

## Closed blockers

This sync package closes the following blocker classes:

1. stale README references and missing authority map;
2. duplicate booking flow file;
3. booking/core divergence on entity naming;
4. booking/core divergence on final booking status enum;
5. duplicate patient ownership risk;
6. duplicate reminder ownership risk;
7. missing explicit access/auth model;
8. missing explicit policy/config model;
9. missing explicit 043/export mapping;
10. missing repo/code map;
11. missing seed/fixtures spec;
12. missing contract-level UI document for admin/doctor/owner surfaces.

---

## Canonical decisions now frozen

### Final booking aggregate
- canonical name: `Booking`
- canonical final table: `booking.bookings`

### Final booking status enum
- `pending_confirmation`
- `confirmed`
- `reschedule_requested`
- `canceled`
- `checked_in`
- `in_service`
- `completed`
- `no_show`

### Patient ownership
- canonical truth: `Patient Registry`
- booking uses `patient_id` and context projections
- booking does not own a second patient registry

### Reminder ownership
- canonical truth: `Communication / Reminders`
- booking triggers reminder scheduling intent/events
- booking does not own a second reminder table

### Deployment stance
- single-clinic per deployment by default
- `branch_id` optional inside a clinic deployment
- future cross-clinic owner aggregation is federation/integration, not shared booking core

### 043 stance
- structured facts stored in runtime model
- 043-style documents generated as export/projection
- runtime UI must not mirror a paper spreadsheet

---

## Deleted duplicate

Removed from canonical package:
- duplicate booking-flow alias file

The canonical file is:
- `booking_docs/10_booking_flow_dental.md`

---

## Expected effect on CODEX

After this sync, CODEX should no longer need to improvise the following:
- whether patient truth lives in booking or core patient registry;
- whether reminders live in booking or communication;
- whether “appointments” and “bookings” are two entities or one;
- which cancellation spelling is canonical;
- which reschedule vocabulary is canonical;
- where access/auth data belongs;
- where clinic/doctor reminder and booking policies belong;
- how 043 export relates to the runtime data model;
- how admin/doctor/owner Telegram contracts should behave.

The project is still complex.
It is now much less ambiguous.
