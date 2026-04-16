# Booking MVP Plan

## 1. Purpose

This document defines the MVP boundary for the booking subsystem.

The goal is to deliver a booking layer that is:
- operationally real;
- aligned with DentFlow architecture;
- usable by patients and clinic staff;
- measurable;
- not overloaded with future complexity.

---

## 2. MVP scope

MVP must include:

- new patient booking
- returning patient booking
- doctor-code route
- slot proposals and hold
- final booking creation
- confirmation reminder chain
- reschedule request
- cancel flow
- admin escalation
- patient resolution through canonical Patient Registry
- reminder ownership through Communication
- booking analytics hooks

---

## 3. Explicitly in-scope reminder behavior

Booking MVP is not “done” if it only creates bookings.

It must also support:
- booking confirmation request
- pre-visit reminder baseline
- action-required acknowledgement where enabled
- no-response visibility for clinic staff

This is part of the value, not optional decoration.

---

## 4. Explicitly out of scope for booking-only MVP

Out of booking-only MVP if needed:
- full care-commerce
- full charting
- full owner AI
- cross-clinic federation
- heavy external adapters
- giant document suite

These can come later without violating the booking core.

---

## 5. Core success criteria

Booking MVP succeeds when:
- patients can actually secure appointments;
- admins can manage real booking state;
- reminders keep the booking operationally alive;
- patient resolution does not create duplicate truth;
- status transitions remain canonical;
- realistic seeded data does not destroy usability.

---

## 6. Summary

Booking MVP is:
- booking-first;
- reminder-aware;
- patient-registry-aligned;
- admin-rescuable;
- search-compatible;
- measurable.

That is enough to be valuable without pretending the whole clinic stack is complete.
