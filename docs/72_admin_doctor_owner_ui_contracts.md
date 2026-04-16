# DentFlow Admin, Doctor, and Owner UI Contracts

> Contract-level Telegram UI rules for admin, doctor, and owner surfaces.

## 1. Purpose

This document defines the UI interaction contracts for the non-patient role surfaces of DentFlow.

It exists because high-level flow maps are not enough.
Without contract-level rules, CODEX will improvise:
- callback shapes,
- panel duplication,
- quick-card layouts,
- navigation patterns,
- action placement.

That is how clean systems become junk drawers.

---

## 2. Shared contract rules

All three role surfaces must respect:

- one active panel per job;
- search-first entry where operationally relevant;
- compact cards;
- no repeated stale keyboards;
- no giant menu labyrinth;
- action density without clutter;
- localization;
- explicit destructive/privileged actions.

---

## 3. Admin UI contracts

## 3.1 Admin entry panels
Canonical admin root surfaces:
- `admin_today_panel`
- `admin_search_panel`
- `admin_confirmations_panel`
- `admin_waitlist_panel`
- `admin_care_pickups_panel`
- `admin_exceptions_panel`

## 3.2 Admin patient quick card

Minimum content:
- patient display name
- patient photo preview if available
- primary contact
- active flags
- next booking / last booking
- branch context if relevant

Primary actions:
- open booking
- create booking
- send reminder/message
- open chart summary
- open media
- open care order state

## 3.3 Admin booking quick card

Minimum content:
- patient
- doctor
- service
- branch
- scheduled time
- status
- reminder state summary

Primary actions:
- confirm
- reschedule
- cancel
- mark checked in
- message patient
- open patient

## 3.4 Confirmation queue card

Show:
- patient
- time
- doctor
- status
- reminder ack/failure hint
- risk flags

Primary actions:
- confirm now
- open patient
- reschedule
- cancel
- escalate to call/manual follow-up

## 3.5 Care pickup card

Show:
- patient
- order/reservation reference
- pickup branch
- status
- product summary

Primary actions:
- mark ready
- issue
- cancel/release if allowed
- open patient

---

## 4. Doctor UI contracts

## 4.1 Doctor entry panels
Canonical doctor root surfaces:
- `doctor_queue_panel`
- `doctor_search_panel`
- `doctor_current_patient_panel`
- `doctor_recommendation_panel`

## 4.2 Doctor queue card

Minimum content:
- patient name
- photo preview
- booking time
- service/reason
- key operational flags
- media indicator

Primary actions:
- open patient
- open booking
- mark in service
- open media
- add note
- issue recommendation

## 4.3 Doctor patient summary card

Show only what is useful for care:
- identity
- reason/complaint summary
- last visit summary
- medical summary flags
- current booking
- available media/docs references

Primary actions:
- open encounter summary
- add quick note
- issue recommendation
- complete encounter

## 4.4 Doctor quick note contract

Supported note types:
- complaint update
- finding summary
- diagnosis summary
- treatment note
- follow-up note

UI rules:
- fast capture
- short structured type selection first
- text or controlled voice-assisted input second
- no giant form dump in the active visit flow

---

## 5. Owner UI contracts

## 5.1 Owner entry panels
Canonical owner root surfaces:
- `owner_digest_panel`
- `owner_today_panel`
- `owner_doctor_metrics_panel`
- `owner_service_metrics_panel`
- `owner_branch_metrics_panel`
- `owner_care_panel`
- `owner_alerts_panel`
- `owner_ai_query_panel`

## 5.2 Owner digest card

Must summarize:
- today’s bookings
- pending confirmations
- yesterday’s completions
- no-shows/cancellations
- urgent anomalies
- care or reminder issues if material

Primary actions:
- open today panel
- open doctor metrics
- open alerts
- ask AI follow-up

## 5.3 Owner metrics card

Should show:
- metric name
- current value
- comparison value or trend marker
- scope (clinic / branch / doctor / service)
- freshness indicator

Primary actions:
- drill down
- compare
- explain with AI if enabled

## 5.4 Owner alert card

Show:
- alert type
- severity
- scope
- why it triggered
- timestamp/freshness

Primary actions:
- inspect underlying metric
- mark reviewed if supported
- ask AI to explain pattern

---

## 6. Callback namespace guidance

Recommended callback namespace examples:
- `admin:today:open`
- `admin:booking:confirm`
- `admin:booking:check_in`
- `doctor:queue:open_booking`
- `doctor:booking:start_service`
- `owner:digest:open_today`
- `owner:metric:open_doctor`
- `owner:ai:ask_followup`

Keep callbacks compact and semantically obvious.

---

## 7. Search-first contract

Admin and doctor surfaces should expose search near the top.
Search entry should support:
- text
- phone fragment
- voice-assisted retrieval

Owner search is not the same thing.
Owner should search metrics, alerts, scopes, and explanations, not broad patient lists by default.

---

## 8. Action placement rules

## 8.1 Primary actions
Place most likely next action first.

## 8.2 Destructive actions
Destructive actions should be visually secondary and confirmation-protected where appropriate.

## 8.3 Navigation
Provide compact local back/return controls.
Do not create giant mutable menu stacks.

---

## 9. Multi-function controls

DentFlow allows multi-function controls only when:
- behavior is documented;
- user value is clear;
- ambiguity is low.

Example:
- single tap changes a value;
- follow-up free input can express `+2`, `-2`, `0` or similar power behavior.

Where used, the behavior must be:
- stable;
- documented;
- role-appropriate.

No surprise magic.

---

## 10. Reminder acknowledgement UI

Because reminders are operationally important, admin and owner surfaces must be able to see acknowledgement outcomes such as:
- confirmed
- already on my way
- no response
- failed delivery
- reschedule requested

This belongs in quick-card summaries, not buried in logs.

---

## 11. Summary

Admin, doctor and owner UI contracts must be:
- compact;
- role-specific;
- panel-disciplined;
- search-aware;
- callback-consistent;
- localized;
- explicit about primary action.

That is how the non-patient surfaces stay operational instead of degenerating into chat rubble.
