# Booking Integrations and Operations

## 1. Purpose

This document defines how booking interacts with:
- schedule truth;
- patient context;
- reminder orchestration;
- admin rescue;
- analytics;
- branch context;
- later external integrations.

It exists so CODEX does not invent hidden seams.

---

## 2. Schedule source

Booking must consume authoritative schedule/availability truth.
The Telegram layer must not invent slot reality.

Required schedule inputs:
- doctor availability
- service compatibility
- branch availability if used
- blocked time
- existing booking load
- active holds

---

## 3. Patient context source

Booking may use patient context for:
- repeat-doctor suggestion
- prior visit continuity
- reminder preferences
- repeat no-show flags

But booking must still work if patient history is missing.
It must degrade gracefully to generic flow.

---

## 4. Reminder integration

Booking is one of the main producers of reminder demand.

### Canonical rule
Booking triggers reminders.
Communication owns reminder truth.

### Booking-triggered reminder examples
- confirmation request
- 24h reminder
- same-day reminder
- reschedule acknowledgement
- cancellation acknowledgement
- waitlist offer

### Action-required pattern
Where policy enables it, reminder CTA should support:
- confirm
- already on my way
- request reschedule
- cancel

This gives the clinic a care signal and a discipline signal.

### Non-response handling
Policy may require:
- admin attention
- alternative reminder
- call-follow-up workflow
- no-show risk tagging

---

## 5. Admin escalation

Escalation triggers may include:
- no urgent slot
- no acceptable slot after fallback
- ambiguous identity
- premium doctor conflict
- repeated flow failure
- policy exception

Escalation payload should include:
- booking session summary
- contact snapshot
- requested service/problem
- urgency
- current selected constraints
- reason code

---

## 6. Branch handling

Booking remains single-clinic by default.

If branches are enabled inside the clinic deployment:
- booking should carry `branch_id` where relevant;
- slot ranking should respect branch context;
- analytics should support branch splits.

This is still not a shared multi-clinic booking core.

---

## 7. Reporting hooks

Booking should feed analytics for:
- starts
- completions
- drop-off
- no-slot rates
- doctor-code usage
- repeat-patient continuity
- confirmation rate
- no-show rate
- reminder acknowledgement effects
- branch splits where used

---

## 8. External integration readiness

Booking must stay compatible with:
- owner projections
- search projections
- export generation
- future Sheets sync
- future external system adapter flows

That does not mean those adapters own booking truth.

---

## 9. Summary

Booking integrates with:
- schedule truth;
- patient context;
- reminder orchestration;
- admin rescue;
- branch-aware analytics;
- later adapters.

The key discipline is simple:
booking owns bookings, not everything around them.
