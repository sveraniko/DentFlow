# DentFlow Booking Package

> Authoritative booking subsystem documentation for DentFlow.

## 1. Purpose

This folder defines the booking subsystem in enough detail that implementation does not need to improvise core booking behavior.

It covers:
- product flow
- booking domain model
- routing and slot ranking
- state machine
- Telegram booking UI contract
- operational integration seams
- schema design
- API contracts
- test scenarios
- MVP boundaries

---

## 2. Booking package status

The booking package is authoritative for **booking-specific depth**.

However it must remain aligned with project-wide canonical decisions from:
- `README.md`
- `docs/20_domain_model.md`
- `docs/25_state_machines.md`
- `docs/30_data_model.md`
- `docs/35_event_catalog.md`

If a booking doc conflicts with those canonical decisions, the conflict must be resolved.
The package is not allowed to fork reality.

---

## 3. Frozen booking-package decisions

## 3.1 Final aggregate
Canonical final aggregate = `Booking`.

## 3.2 Final table
Canonical final table = `booking.bookings`.

## 3.3 Final booking statuses
- `pending_confirmation`
- `confirmed`
- `reschedule_requested`
- `canceled`
- `checked_in`
- `in_service`
- `completed`
- `no_show`

## 3.4 Patient ownership
Booking references canonical patients via `patient_id`.
Booking does not own a separate patient registry.

## 3.5 Reminder ownership
Booking triggers reminder behavior.
Communication owns canonical reminder truth.

## 3.6 Deployment stance
Booking is designed for a single-clinic deployment by default.
`branch_id` is optional inside that deployment.
Cross-clinic aggregation belongs to later federation/integration, not booking core.

---

## 4. Document map

- `10_booking_flow_dental.md`  
  product and flow behavior for dental booking

- `20_booking_domain_model.md`  
  conceptual booking entities and ownership

- `30_booking_routing_and_slot_ranking.md`  
  doctor and slot ranking logic

- `40_booking_state_machine.md`  
  booking-specific lifecycle and conversational state rules

- `50_booking_telegram_ui_contract.md`  
  booking-specific Telegram interaction contract

- `60_booking_integrations_and_ops.md`  
  booking integration seams with reminders, admin flow, scheduling and reporting

- `90_booking_mvp_plan.md`  
  booking MVP boundary

- `booking_db_schema.md`  
  schema blueprint

- `booking_api_contracts.md`  
  service/API contract blueprint

- `booking_test_scenarios.md`  
  booking test scenarios and smoke coverage

---

## 5. Duplicate file policy

There is intentionally no duplicate alias for the booking flow file.
The canonical booking flow doc is:

- `10_booking_flow_dental.md`

One source of truth is enough.
