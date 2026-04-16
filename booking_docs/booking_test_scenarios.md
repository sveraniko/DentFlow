# Booking Test Scenarios

## 1. Purpose

This document defines booking-specific test scenarios and smoke coverage.

It must stay aligned with:
- project-wide lifecycle rules
- canonical booking statuses
- patient ownership rules
- reminder ownership rules

---

## 2. Mandatory scenario groups

1. session lifecycle
2. slot proposals and holds
3. patient resolution
4. final booking creation
5. confirmation and reminder behavior
6. reschedule and cancel
7. waitlist and escalation
8. stale callback handling
9. search and continuity behavior
10. branch handling if enabled

---

## 3. Mandatory smoke pack

The following scenarios are mandatory for booking smoke readiness.

### BKG-001 New patient booking
- patient starts flow
- selects service/problem
- gets slot proposals
- confirms contact
- final booking created

Expected:
- canonical booking exists
- patient resolved/created in Patient Registry
- reminder scheduling intent exists

### BKG-002 Returning patient continuity booking
- known patient enters flow
- previous doctor continuity offered
- booking completed

Expected:
- patient reused correctly
- continuity logic behaves predictably

### BKG-003 Doctor-code route
- valid code
- route constrained to doctor
- booking completed

Expected:
- no leakage into other doctors without explicit fallback

### BKG-004 Invalid doctor code fallback
- invalid code submitted

Expected:
- safe retry or explicit fallback
- no broken session state

### BKG-005 Slot hold expiry
- hold created
- TTL expires before confirm

Expected:
- hold expires
- user is guided back safely
- no ghost booking created

### BKG-006 Confirmation reminder action
- booking in `pending_confirmation`
- confirmation reminder sent
- patient presses `Confirm`

Expected:
- reminder acknowledgement recorded
- booking moves/continues as intended

### BKG-007 “Already on my way” reminder action
- same-day reminder sent
- patient presses `Already on my way`

Expected:
- reminder acknowledgement kind recorded
- admin/owner views can see the signal

### BKG-008 Reschedule request
- confirmed booking
- reschedule requested
- new slot chosen

Expected:
- old slot released
- new schedule persisted
- history/event trail exists
- reminders updated

### BKG-009 Cancel booking
- confirmed booking canceled

Expected:
- status becomes `canceled`
- capacity released
- reminder chain updated
- no-show not used by mistake

### BKG-010 Mark no-show
- booking not attended
- no-show marked

Expected:
- status becomes `no_show`
- history/event recorded

### BKG-011 Stale callback
- user clicks old slot/confirm callback after session changed

Expected:
- stale action detected
- user guided to current panel
- no corrupted state

### BKG-012 Admin escalation
- no-slot or policy edge case triggered

Expected:
- escalation created with structured payload
- session does not silently disappear

### BKG-013 Waitlist offer and fulfillment
- waitlist entry created
- slot becomes available
- offer accepted

Expected:
- booking created or updated correctly
- waitlist status fulfilled

### BKG-014 Branch-aware booking (if branches enabled)
- booking constrained to branch

Expected:
- branch id preserved
- slot and booking scope aligned

---

## 4. Status vocabulary check

All booking tests must use the canonical final status vocabulary:

- `pending_confirmation`
- `confirmed`
- `reschedule_requested`
- `canceled`
- `checked_in`
- `in_service`
- `completed`
- `no_show`

---

## 5. Ownership check

Booking tests must assume:
- patient truth comes from Patient Registry
- reminder truth comes from Communication
- booking does not own a second patient registry
- booking does not own a second reminder system

---

## 6. Summary

This test pack exists to keep booking aligned with the synchronized DentFlow model, not with historical accidents.
