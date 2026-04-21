# Booking Flow for DentFlow Dental

## 1. Purpose

This document defines the patient-facing and clinic-facing booking behavior for the dental vertical.

The goal is to make booking:

- fast enough for Telegram;
- structured enough for real clinic operations;
- respectful of premium doctor rules;
- compatible with reminders, admin rescue, owner metrics and future charting.

---

## 2. Product principles

## 2.1 Booking is booking-first, not form-first
The patient wants an appointment, not an interrogation.

## 2.2 Problem-oriented entry is valid
Patients may start from:
- pain
- hygiene
- consultation
- braces/orthodontics
- implant/prosthetic consultation
- pediatric care
- “other”

## 2.3 The patient should not browse the entire schedule manually
The system should rank and present a small best set of slots.

## 2.4 Reminder and confirmation are part of booking
Booking is not finished when a row is created.
It is operationally alive through reminders, acknowledgements and possible rescue.

## 2.5 Repeat patients should move faster
Known patient context should shorten the path.

---

## 3. Core routes

## Route A. General booking
User chooses problem/service, system routes to best eligible doctor/slot.

## Route B. Returning patient continuity
System recognizes a likely prior patient and offers continuity with previous doctor where appropriate.

## Route C. Doctor-code route
User provides a doctor access code, limiting routing to that doctor according to policy.

## Route D. Admin-assisted route
Used when automation cannot or should not complete booking.

---

## 4. Recommended patient flow

1. enter booking
2. choose problem or service
3. choose date preference / urgency
4. choose time window
5. choose doctor preference if needed
6. see ranked slot proposals
7. select slot
8. confirm minimal identity/contact
9. review
10. booking created in `pending_confirmation` or `confirmed` according to policy
11. reminder/confirmation chain begins

---

## 5. Identity and patient resolution

Booking must support:
- new patients
- existing patients
- Telegram-known patients
- phone-based matching
- admin-assisted resolution

Important rule:
booking does not own a second patient registry.
It resolves or creates canonical patient truth through Patient Registry.

---

## 6. Urgent cases

Urgent dental complaints may:
- narrow slot ranking horizon;
- relax soft preferences;
- escalate to admin if no acceptable urgent slot exists.

This is structured routing, not diagnosis.

---

## 7. Slot proposal behavior

The user should usually see:
- 3 to 5 good slot options;
- not a raw schedule dump.

Slot proposals must reflect:
- service compatibility
- doctor policy
- urgency
- time preference
- branch/location where relevant

---

## 8. Booking confirmation and reminder logic

DentFlow booking assumes reminders are part of the booking experience.

Recommended reminder chain may include:
- booking created / confirmation needed
- 24h reminder
- same-day reminder
- action-required confirmation step
- no-response escalation if policy requires it

Important:
canonical reminder truth lives in Communication / Reminders, not inside booking tables.

### Action-required reminder pattern
Where enabled, a reminder may ask the patient to choose one action:

- confirm
- already on my way
- reschedule
- cancel

This produces useful operational signal and reinforces commitment.

### Reminder acknowledgement (`ack`) pattern
For reminder types that expose `ack` (for example pre-visit / day-of / recall reminders), `ack` is a one-tap non-destructive acknowledgement meaning “received/understood.”

`ack` is not equivalent to attendance confirmation:
- `confirm` is a confirmation-required action and may mutate booking lifecycle state according to policy.
- `ack` records reminder acknowledgement only and does not mutate booking status.

After accepted `ack`, patient flow returns to canonical booking continuity. By default, `ack` does not introduce additional future-reminder suppression logic.

---

## 9. Reschedule behavior

Reschedule should behave as:

1. request reschedule
2. select new slot
3. atomically secure new slot
4. release old slot
5. update booking history and reminders

No invisible overwrite hacks.

---

## 10. Cancel behavior

Cancel should:
- be explicit;
- preserve history;
- not be confused with no-show;
- free capacity;
- optionally feed waitlist/rescue logic.

---

## 11. Waitlist behavior

Waitlist should support:
- same doctor preference
- general service fallback
- time-window preference

Waitlist offers should be explicit and time-bounded.

---

## 12. Branch handling

In v1, booking is single-clinic by default.

`branch_id` may still be used to:
- route to one of a clinic’s branches;
- support branch-specific analytics;
- support branch-specific pickup or visit logistics later.

This does not mean shared multi-clinic booking core.

---

## 13. Admin fallback and rescue

Automation must escalate when needed, for example:
- no valid urgent slot
- repeated validation failures
- premium/policy conflict
- schedule inconsistency
- ambiguous identity resolution

Escalation payload should be structured, not a vague “user needs help”.

---

## 14. Analytics hooks

Booking should emit facts for:
- booking starts
- slot list shown
- hold created
- booking created
- booking confirmed
- booking reschedule requested
- booking rescheduled
- booking canceled
- no-show marked
- waitlist flow entered
- admin escalation triggered

---

## 15. Canonical final status reminder

Use this canonical final booking status set everywhere:
- `pending_confirmation`
- `confirmed`
- `reschedule_requested`
- `canceled`
- `checked_in`
- `in_service`
- `completed`
- `no_show`

---

## 16. Summary

DentFlow dental booking is:
- guided;
- ranking-driven;
- reminder-aware;
- continuity-friendly;
- premium-capacity-aware;
- patient-registry-aligned;
- admin-rescuable;
- search-compatible;
- owner-measurable.
