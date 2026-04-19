# Booking Card Profile

> Canonical booking card profile for the DentFlow unified card system.

## 1. Purpose

This document defines the **booking card profile** as the central operational card in DentFlow.

If the unified card system provides the shared shell, and card profiles define the payloads and actions of different object families, then this document exists because the booking card is not just another profile.

It is the **main operational object** of the system.

Everything important in DentFlow touches booking:

- patient journey
- admin scheduling
- doctor queue
- check-in
- in-service progression
- completion
- reminders
- reschedule handling
- no-show
- chart entry
- recommendations
- care orders
- owner operational visibility
- calendar projection

Because of that, the booking card must be designed with maximum clarity now, not patched later.

This document must make it impossible for implementation to drift into:
- one booking card for admin,
- another random one for doctor,
- a third crippled one for patient,
- and a fourth “quick fix” one in owner alert drill-down.

The shell is shared.
The booking profile is canonical.

---

## 2. Booking card thesis

The booking card is the **operational spine** of DentFlow.

Its job is to answer, quickly and correctly:

- what booking is this?
- who is the patient?
- who is the doctor?
- what service is booked?
- where and when is it happening?
- what is its state?
- what must happen next?
- what related objects matter right now?
- which actions are valid for the current role?

It must do this:

- compactly
- safely
- role-aware
- source-aware
- status-aware
- without turning into a chart
- without turning into a schedule spreadsheet
- without turning into a debug console

---

## 3. Profile identity

Canonical identity:
- `booking_id`

Strong contextual anchors:
- `patient_id`
- `doctor_id`
- `service_id`
- `branch_id`
- `clinic_id`

Optional linked contexts:
- `chart_id`
- `encounter_id`
- `recommendation_id`
- `care_order_id`
- `admin_escalation_id`
- reminder state summary / reminder issue summary

The booking card must remain the booking card.
It may link outward, but must not be replaced by its linked objects.

---

## 4. Primary role variants

The same booking card shell exists for all roles, but role variants differ.

## 4.1 Patient booking card
Purpose:
- understand own booking
- confirm / reschedule / cancel
- see next step
- see branch/doctor/service clearly

## 4.2 Admin booking card
Purpose:
- operate booking
- confirm
- check-in
- handle reschedule
- cancel
- open patient
- see queue-critical context

## 4.3 Doctor booking card
Purpose:
- understand current/upcoming visit
- open patient context
- move booking into operational states
- jump into chart summary/encounter baseline

## 4.4 Owner booking card
Purpose:
- limited drill-down from metrics/alerts
- understand what happened
- no routine operational mutation by default

This role separation must remain explicit.
The booking card is shared, but not identical in action scope.

---

## 5. Core design principles

## 5.1 Compact first
The booking card must open in a scan-friendly compact mode.

## 5.2 One booking = one operational object
No status-specific reinventions of the whole card.
Status changes re-render the same object profile.

## 5.3 Action validity must be canonical
Buttons must reflect true valid actions for:
- current status
- current role
- current source context

## 5.4 Related objects are linked, not merged
The booking card may link to:
- patient card
- chart summary
- recommendation
- care order
- reminder issue
but must not swallow them into a giant monster card.

## 5.5 Booking card must stay useful under pressure
This is not a decorative panel.
This is the object people will use when the clinic is busy and annoyed.

---

## 6. Compact mode

Compact mode is the primary operational view.

## 6.1 Compact mode must show

At minimum:

- booking time / date
- patient display name
- doctor display name (unless the source context already makes doctor obvious and repetition truly adds no value)
- service label
- branch
- booking status
- compact flags/chips
- 1–3 high-value actions depending on role

### Strongly recommended compact meta lines
- confirmation state hint if relevant
- check-in / in-service hint if relevant
- reschedule requested marker if relevant
- no-show marker if relevant

## 6.2 Compact mode should answer instantly
- what appointment is this?
- what state is it in?
- what should I do next?

## 6.3 Compact mode must NOT show
- chart text
- long patient notes
- detailed reminder logs
- large care order detail
- giant history blocks
- internal technical IDs as primary visible text

---

## 7. Expanded mode

Expanded mode reveals more operational detail while staying in the same object context.

## 7.1 Expanded mode may show
- everything from compact mode
- booking source/channel
- patient contact hint (role-safe)
- reminder summary
- reschedule context summary
- linked recommendation summary
- linked care order summary
- chart summary entry
- reminder issue summary if relevant
- status history snippet if useful and compact
- more actions than compact mode

## 7.2 Expanded mode still must remain bounded
Expanded mode is not a dump of all fields from all linked tables.

It must not become:
- full patient card
- chart
- care order detail card
- admin issue dashboard
- owner analytics page

---

## 8. Header design

The header must communicate identity fast.

Recommended structure:
- line 1: time/date + patient or service emphasis depending on role/source
- line 2: doctor/service/branch compact summary
- badge row: status + critical chips

### Example compact header emphasis
**Patient source**
- emphasize date/time + doctor/service

**Doctor source**
- emphasize time + patient + service

**Admin source**
- emphasize time + patient + doctor + service

**Owner source**
- emphasize time + patient + state + branch

Do not make one rigid string for every context if it harms scan speed.
But keep formatting consistent.

---

## 9. Status chip model

Booking status is one of the most important visible signals.

The card must use compact, visually consistent status chips for canonical booking states such as:
- `pending_confirmation`
- `confirmed`
- `reschedule_requested`
- `checked_in`
- `in_service`
- `completed`
- `canceled`
- `no_show`

### Additional compact operational chips may include
- reminder problem
- no-response
- waitlist linked
- recommendation issued
- care pickup linked
- chart opened

These must stay bounded.
No badge soup.

---

## 10. Reminder state on booking card

Reminder truth is separate, but booking card may show compact reminder context where relevant.

Allowed baseline summary signals:
- confirmation pending
- reminder sent
- reminder acknowledged
- reminder failed
- no-response escalated

### Important
The booking card may show reminder state hints.
It must not become the reminder control center.

If detailed reminder debugging is needed, open a linked issue or reminder detail object later.

---

## 11. Related object links

Booking card may link outward to key related objects.

Recommended linked actions:
- `Пациент`
- `Карта`
- `Рекомендации`
- `Уход`
- `Проблема`
- `Напоминания` (only if later such detail layer exists cleanly)

### Rule
These are linked opens, not embedded full detail.
Booking remains the center.

---

## 12. Patient-facing booking card

This variant must stay calm, clear, and bounded.

## 12.1 Compact content
- date/time
- doctor
- service
- branch
- status
- short next-step note

## 12.2 Expanded content
- branch details
- recommendation to confirm if needed
- linked recommendations or care-order hint if relevant
- compact reminder/support note if useful

## 12.3 Patient actions
At baseline:
- `Подтвердить`
- `Перенести`
- `Отменить`
- `Назад`

Optional later:
- `Связаться`
- `Открыть рекомендации`
- `Открыть уход`

### Patient card must NOT show
- internal reminder failure reasons
- staff notes
- operational escalation language
- warehouse/care internal states

---

## 13. Admin-facing booking card

This is arguably the most operationally dense version.

## 13.1 Compact content
- time
- patient
- doctor
- service
- branch
- status
- flags
- confirmation/problem hint

## 13.2 Expanded content
- patient contact hint
- reminder/no-response hint
- care pickup relation if relevant
- chart summary entry if policy allows
- compact recent change/history context
- next-step operational action block

## 13.3 Admin actions
Recommended baseline:
- `Подтвердить`
- `Пришел`
- `Перенос`
- `Отменить`
- `Пациент`
- `Карта`
- `Уход` if relevant

### Optional admin actions later
- manual reminder send
- reminder issue open
- slot reassignment tools

### Admin card must NOT become
- giant workdesk dashboard inside one card
- chart editor
- warehouse issue console

---

## 14. Doctor-facing booking card

This version is built for visit execution, not scheduling at large.

## 14.1 Compact content
- time
- patient
- service
- branch if relevant
- current status
- active flags
- chart summary hint

## 14.2 Expanded content
- patient quick identity block
- recommendation/care hint if relevant
- chart summary open action
- encounter entry/open action
- minimal linked objects needed for current visit

## 14.3 Doctor actions
Recommended baseline:
- `В работе`
- `Завершить`
- `Пациент`
- `Карта`

If `checked_in` is allowed doctor-side in your accepted workflow, expose it carefully.
If admin owns it, do not duplicate carelessly.

### Doctor card must NOT become
- full chart editor
- full patient dossier
- owner metrics pane

---

## 15. Owner-facing booking card

Owner sees bookings primarily through metrics/alerts, not through endless operational browsing.

## 15.1 Compact content
- time/date
- patient name (or masked/compact as policy requires)
- doctor
- service
- branch
- state
- alert context if opened from alert

## 15.2 Expanded content
- compact booking journey summary
- status history summary
- reminder issue summary
- branch/doctor context
- linked object entries only where truly useful

## 15.3 Owner actions
Baseline should be conservative:
- `Открыть`
- maybe `Пациент` if policy allows
- maybe `Карта` summary if policy allows later
- no routine mutation buttons by default

### Owner card must NOT become
- admin scheduling panel
- doctor operations surface

---

## 16. Source-context-specific behavior

The booking card must adapt slightly to source context while preserving the same shell.

### 16.1 From admin today
Emphasize:
- immediate action
- confirmation/check-in
- branch
- time

### 16.2 From doctor queue
Emphasize:
- patient
- service
- in-service / complete action
- chart entry

### 16.3 From patient own bookings
Emphasize:
- confirmation
- reschedule/cancel
- location and time clarity

### 16.4 From owner alert
Emphasize:
- why this booking matters to the alert
- no-show/reschedule/backlog context

### 16.5 From patient card
Emphasize:
- booking’s relation to patient history
- less need to repeat patient identity loudly

This is source-aware rendering, not a different profile.

---

## 17. Compact action density

Compact booking card should never drown in buttons.

Recommended compact action limit:
- 2 primary actions
- maybe 1 contextual quick open
- `Подробнее` if needed

Examples:

### Patient compact
- `Подтвердить`
- `Подробнее`

### Admin compact
- `Подтвердить`
- `Пришел`
- `Подробнее`

### Doctor compact
- `В работе`
- `Подробнее`

The rest belongs in expanded mode.

---

## 18. Expanded action density

Expanded mode may show more actions, but still must stay bounded.

Suggested grouping:
- primary operational actions
- linked object actions
- contextual helper actions
- navigation actions

Do not scatter actions randomly across the text.
Do not create a twelve-button carnival.

---

## 19. Time and timezone presentation

Booking card is one of the most timezone-sensitive objects in the whole system.

### Rule
Visible booking time must use:
- branch timezone if available
- else clinic timezone
- else app default

Never raw UTC in visible card text.

### Why
If booking card shows wrong day/time,
the whole system feels broken no matter how clever the backend is.

---

## 20. Booking card and chart boundary

Booking and chart are linked but distinct.

### Booking card may show:
- chart summary entry
- current encounter open hint
- diagnosis/treatment summary hint later if compact and role-safe

### Booking card must NOT become:
- chart summary dump
- diagnosis/treatment text wall
- encounter note reader

The booking card’s job is to move the visit forward, not replace charting.

---

## 21. Booking card and recommendation boundary

Booking may link to recommendations, but:
- recommendation remains its own object
- booking card may show recommendation summary or count
- booking card may open recommendation card

It must not embed recommendation detail as if they were the same thing.

---

## 22. Booking card and care-order boundary

Booking may link to care orders or care pickups.

Allowed:
- compact care order hint
- open linked care order card

Not allowed:
- embedded stock/order internals in booking card
- turning booking card into care pickup console

---

## 23. Status-history and event-history presentation

Booking card may show a compact history summary if useful.

Examples:
- confirmed at
- reschedule requested
- checked in
- completed

But it must remain:
- short
- human-readable
- relevant

Do not dump raw event ledger into the card.

---

## 24. Reminder issue and no-response presentation

Admin/owner variants may show:
- reminder failed
- no-response escalated
- confirmation pending too long

This is useful.
But presentation must remain compact.

Examples:
- chip
- one-line issue summary
- `Открыть проблему`

Do not pour the reminder engine into the booking card.

---

## 25. Media usage in booking card

Booking is not primarily a media object.
So media in booking card should stay minimal.

Possible allowed cases later:
- branch/location image
- doctor avatar/photo
- patient photo hint through linked patient card, not direct heavy media
- recommendation/care linked media via linked cards

### Baseline rule
Booking card does not need heavy direct media behavior.
Do not force it.

---

## 26. Empty and edge states

Booking card must handle safely:

- booking missing
- booking stale
- booking terminal state
- role not allowed
- linked object missing
- reminder issue resolved elsewhere
- recommendation/care link no longer valid

These must degrade safely and compactly.

---

## 27. Booking card and Google Calendar projection

Booking card remains the operational truth object.

Google Calendar may mirror the schedule, but:
- calendar event is not the booking card
- booking card is opened in DentFlow
- calendar should deep-link/reference booking card where helpful

This must stay explicit.

---

## 28. Booking card anti-patterns

The following are forbidden:

- booking card as giant schedule spreadsheet
- booking card as chart replacement
- booking card with raw UTC times
- booking card with ten equal-priority actions
- booking card that reveals wrong linked patient through weak callback
- booking card whose Back returns to random home
- booking card that hides invalid action states instead of validating them
- booking card that mixes owner/admin/doctor actions with no role boundary

These are exactly the ways a core object profile gets ruined.

---

## 29. Summary

The booking card profile is the central operational card in DentFlow.

It must:
- represent one booking cleanly
- adapt by role and source context
- stay compact first and expandable second
- expose valid next actions only
- link to patient/chart/recommendation/care objects without collapsing into them
- present time in local clinic/branch semantics
- remain callback-safe, role-safe, and source-aware

This card is too important to be improvised later.

That is why it is defined now and in detail.
