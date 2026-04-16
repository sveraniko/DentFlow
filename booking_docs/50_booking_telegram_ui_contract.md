# Booking Telegram UI Contract

## 1. Purpose

This document defines the Telegram interaction contract for booking.

It exists to ensure the booking flow remains:
- native to Telegram;
- compact;
- resumable;
- low-noise;
- safe against stale callbacks.

---

## 2. Core UI principles

- one question at a time
- compact inline choices
- limited free-text input
- message editing / panel replacement where appropriate
- no WebApp dependency for MVP
- no giant slot dumps
- no booking flow clutter museum

---

## 3. Step contract

Typical booking sequence:
1. service/problem choice
2. date or urgency choice
3. time window choice
4. doctor preference or doctor code if needed
5. slot proposals
6. contact confirmation
7. review / final confirm

Each step should have:
- one active panel;
- one obvious next action;
- compact fallback options.

---

## 4. Slot proposal panel

### Required behavior
- show 3 to 5 best slot buttons max
- allow `more options`
- allow `change date/time/doctor`
- allow cancel

### Slot label example
`Wed 9 Apr · 17:20`

---

## 5. Contact confirmation panel

The bot may ask for:
- contact share
- phone input fallback
- confirmation of known contact

This step must stay short.
Booking is not a giant intake form.

---

## 6. Review panel

Should show:
- service/problem
- doctor
- branch if relevant
- time
- contact snapshot
- concise note if entered

Primary actions:
- confirm booking
- edit previous choice
- cancel

---

## 7. Stale callback handling

If user clicks stale slot/confirm buttons:
- detect mismatch;
- explain briefly;
- reopen current active panel;
- never mutate unrelated live state.

---

## 8. Confirmation and reminder-action UI

Action-required booking reminders should support compact CTA buttons such as:
- `Confirm`
- `Already on my way`
- `Need to reschedule`
- `Cancel`

These actions should feed reminder acknowledgement and booking follow-up logic without inventing hidden statuses.

---

## 9. Analytics hooks

Suggested UI action events:
- booking_started
- service_selected
- date_preference_selected
- time_window_selected
- doctor_preference_selected
- doctor_code_entered
- slot_list_shown
- slot_selected
- hold_created
- contact_confirmed
- booking_confirmed
- booking_canceled
- waitlist_requested
- admin_escalation_requested

---

## 10. Summary

DentFlow booking UI must be:
- Telegram-native;
- compact;
- resumable;
- stale-safe;
- reminder-aware;
- conversion-friendly.
