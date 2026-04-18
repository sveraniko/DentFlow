# DentFlow Event Catalog

> Canonical event language for DentFlow.

## 1. Purpose

This document defines the core DentFlow event catalog so subsystems can react without hidden coupling.

It exists to make sure:
- important business facts are emitted consistently;
- projections and reminders are driven by clear signals;
- booking, reminders, analytics, export and integrations do not invent their own secret side-effect pathways.

---

## 2. Event principles

## 2.1 Events report facts
An event means something already happened or was accepted as truth.

## 2.2 Events do not replace canonical storage
Transactional truth remains in canonical tables.

## 2.3 Payloads should be useful but minimized
IDs, timestamps, status and compact typed summaries are preferred.
Do not spray raw medical text everywhere.

## 2.4 Consumers must be idempotent
Duplicate processing must not cause:
- double reminders;
- duplicate projections;
- duplicate care reservations;
- duplicate owner alerts.

---

## 3. Canonical envelope

Recommended logical event envelope:
- `event_id`
- `event_name`
- `event_version`
- `occurred_at`
- `produced_at`
- `producer_context`
- `clinic_id`
- `entity_type`
- `entity_id`
- `correlation_id` nullable
- `causation_id` nullable
- `actor_type` nullable
- `actor_id` nullable
- `payload`

---

## 4. Core event families

1. patient events
2. booking-session events
3. slot-hold events
4. booking events
5. reminder/communication events
6. clinical events
7. recommendation events
8. care-commerce events
9. document/media events
10. search projection events
11. sync/integration events
12. owner projection events

---

## 5. Patient events

- `patient.created`
- `patient.updated`
- `patient.contact_added`
- `patient.contact_updated`
- `patient.preference_updated`
- `patient.flag_set`
- `patient.flag_cleared`
- `patient.photo_updated`

Key consumers:
- search projection
- booking read models
- reminder routing
- export/doc generation
- integration mapping

---

## 6. Booking-session and hold events

- `booking_session.initiated`
- `booking_session.completed`
- `booking_session.abandoned`
- `booking_session.expired`
- `booking_session.admin_escalated`

- `slot_hold.created`
- `slot_hold.released`
- `slot_hold.expired`
- `slot_hold.consumed`
- `slot_hold.canceled`

Key consumers:
- booking funnel analytics
- waitlist/availability handling
- operational monitoring

---

## 7. Final booking events

Canonical booking events include:

- `booking.created`
- `booking.pending_confirmation`
- `booking.confirmed`
- `booking.reschedule_requested`
- `booking.rescheduled`
- `booking.canceled`
- `booking.checked_in`
- `booking.in_service_started`
- `booking.completed`
- `booking.no_show_marked`

### Important note
`booking.rescheduled` is an event/history fact.
It does not require a permanent alternative final booking status enum.

Key consumers:
- reminder scheduling/cancellation
- search recent-state projections
- owner metrics
- chart/encounter bootstrap
- recommendation and care triggers
- export pipelines
- integration adapters

---

## 8. Reminder and communication events

Canonical communication events include:

- `reminder.scheduled`
- `reminder.queued`
- `reminder.sent`
- `reminder.delivery_confirmed` (optional by channel)
- `reminder.acknowledged`
- `reminder.failed`
- `reminder.canceled`
- `reminder.expired`

### Acknowledgement payload guidance
`reminder.acknowledged` should carry an `acknowledgement_kind` such as:
- `booking_confirmed`
- `already_on_my_way`
- `reschedule_requested`
- `pickup_confirmed`
- `recommendation_acknowledged`

This supports action-required reminders without breeding multiple fake reminder-state models.

---

## 9. Clinical events

- `chart.opened`
- `clinical_history.updated`
- `encounter.created`
- `encounter.note_added`
- `diagnosis.recorded`
- `treatment_plan.created`
- `treatment_plan.updated`
- `odontogram.updated`
- `imaging_reference.added`

Key consumers:
- export/document projections
- integrations
- analytics enrichment where appropriate

---

## 10. Recommendation events

- `recommendation.created`
- `recommendation.prepared`
- `recommendation.issued`
- `recommendation.viewed`
- `recommendation.acknowledged`
- `recommendation.accepted`
- `recommendation.declined`
- `recommendation.expired`
- `recommendation.withdrawn`

---

## 11. Care-commerce events

- `care_product.created`
- `care_product.updated`
- `care_order.created`
- `care_order.confirmed`
- `care_order.payment_required`
- `care_order.paid`
- `care_order.ready_for_pickup`
- `care_order.issued`
- `care_order.fulfilled`
- `care_order.canceled`
- `care_reservation.created`
- `care_reservation.released`
- `care_reservation.expired`
- `care_reservation.consumed`

---

## 12. Document and media events

- `media_asset.uploaded`
- `generated_document.created`
- `generated_document.completed`
- `generated_document.failed`

---

## 13. Search projection events

Mostly internal/projection-level:
- `search_projection.patient_rebuilt`
- `search_projection.doctor_rebuilt`
- `search_projection.service_rebuilt`

These are not business truth, but they can help operations/monitoring.

---

## 14. Integration and sync events

- `sync_job.created`
- `sync_job.started`
- `sync_job.completed`
- `sync_job.partial_success`
- `sync_job.failed`
- `external_id_map.updated`

---

## 15. Owner projection events

Optional/internal:
- `owner_projection.daily_metrics_refreshed`
- `owner_projection.alert_generated`

These are derived signals, not canonical business truth.

---

## 16. Producer-consumer guardrails

## 16.1 Booking produces booking facts
Booking does not own communication truth, but it must emit clean booking facts that Communication can consume.

## 16.2 Communication produces reminder facts
Communication does not mutate booking truth directly without explicit workflow logic.

## 16.3 Search consumes minimized facts
Search projection payloads must stay lean.

## 16.4 Owner insights consume projections
Owner AI and owner digests should consume trusted projections, not raw transactional chaos.

---

## 17. Outbox expectation

Important transactional changes should be published through an outbox or equivalent reliable publication mechanism.

This is especially important for:
- booking transitions
- reminder scheduling
- chart/export triggers
- owner projections
- sync jobs

---

## 18. Summary

DentFlow event language is built around:

- one canonical booking vocabulary;
- one canonical reminder vocabulary;
- minimized payloads;
- projection-friendly signals;
- idempotent consumers;
- reliable publication.

This is what keeps later modules from being stitched together with hidden magic.
