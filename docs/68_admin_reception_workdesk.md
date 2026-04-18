# Admin Reception Workdesk

> Canonical product and operational model for the administrator / reception workdesk in DentFlow.

## 1. Purpose

This document defines the **admin / reception workdesk layer** for DentFlow.

Its role is to make explicit:

- where and how the administrator sees bookings;
- which tasks belong to the admin workdesk;
- which tasks belong to doctor surfaces;
- which tasks belong to owner surfaces;
- what DentFlow must show in Telegram workdesk;
- how Google Calendar may complement the admin role without becoming source of truth;
- what actions are allowed and which remain out of scope.

This document exists because booking itself is already a strong subsystem, but a booking engine is not the same thing as a usable reception workdesk.

DentFlow must not leave the administrator with:
- a powerful backend engine,
- five partial panels,
- and no coherent place to actually run the clinic day.

---

## 2. Core thesis

The administrator is the heaviest operational role in the system.

### Patient
Sees:
- own booking
- own recommendation
- own care order

### Doctor
Sees:
- own queue
- own patient
- own chart summary

### Owner
Sees:
- digest
- today snapshot
- alerts
- aggregates

### Administrator / reception
Sees and manages:
- everyone
- all doctors
- all branches
- today
- upcoming week
- pending confirmations
- reschedule requests
- cancellations
- waitlist
- arrivals / check-ins
- care pickups
- communication issues
- operational bottlenecks

This means the admin role requires its own workdesk model.

It must not be treated as:
- a random collection of commands,
- a weaker owner view,
- or “just use Google Sheets.”

---

## 3. Core principle

# DentFlow is the operational source of truth.  
# Google Calendar is a visual projection.  
# Sheets are for master data authoring, not live booking truth.

This rule must stay explicit.

### DentFlow truth
- bookings
- statuses
- patients
- reminders
- waitlist
- care orders / pickups
- operational actions

### Google Calendar
- day/week/month spatial schedule view
- visual load awareness
- branch/doctor schedule projection

### Google Sheets
- master data / bulk authoring / sync surfaces
- not runtime booking truth

If those roles are mixed, the admin layer becomes unreliable.

---

## 4. What the admin workdesk is for

The admin workdesk exists to let the clinic answer these questions quickly:

- Who is coming today?
- Who still has not confirmed?
- Which doctor is overloaded or idle?
- Which bookings need reschedule handling?
- Who already arrived?
- Which patient should be checked in now?
- Which care pickups are waiting?
- Which reminder failures or no-response cases need action?
- What is happening in this branch today?
- What is happening across branches this week?

The workdesk must optimize for:
- speed
- clarity
- compactness
- phone-first usage
- high interruption tolerance

It must not optimize for:
- giant forms
- decorative dashboards
- exhaustive detail on first screen

---

## 5. Role boundaries

## 5.1 What admin may see
At baseline, admin may see:
- patient operational profile
- booking records
- doctor and branch schedule context
- reminder state
- waitlist status
- care order/pickup state
- communication issues
- operational alerts tied to bookings

Admin should not need:
- raw deep chart text
- doctor-only clinical working detail
- owner-only business analytics in raw form

## 5.2 What admin may do
At baseline, admin may:
- confirm booking
- open booking detail
- open patient quick card
- open chart summary if policy/role allows operational viewing
- mark arrival / checked-in
- open reschedule request
- cancel booking
- act on waitlist
- open care pickup flow
- open communication issue detail
- open calendar mirror if linked

Admin may later support more, but this is the operational minimum.

## 5.3 What admin should not become
Admin workdesk must not become:
- owner analytics console
- doctor clinical workplace
- warehouse system
- giant CRM with every historical artifact on screen

---

## 6. Primary workdesk sections

The admin workdesk should have explicit top-level operational sections.

## 6.1 Today
Primary day view for:
- bookings today
- arrivals
- immediate actions
- current clinic pulse

## 6.2 Confirmations
Focused queue for:
- pending confirmations
- no-response cases
- reminder issues
- bookings needing manual follow-up

## 6.3 Reschedules
Focused queue for:
- reschedule requested
- bookings needing operator intervention

## 6.4 Waitlist
Focused queue for:
- active waitlist entries
- available-slot promotion cases

## 6.5 Patients
Operational patient open/search entrypoint.
Not a giant CRM.
Fast find and open.

## 6.6 Care pickups
Focused queue for:
- ready for pickup
- issue / fulfill actions
- branch pickup context

## 6.7 Issues
Communication failures, non-response escalations, reminder problems, and other bounded operational problems.

---

## 7. Today workdesk model

The `Today` surface is the main workdesk surface.

It should answer:
- who is coming
- who has arrived
- what still needs operator action
- what doctor/branch is busy

### Recommended content blocks
- pending confirmations today
- arrivals / checked-in
- upcoming bookings
- overdue manual actions
- care pickups today
- open operational alerts

### Required filters
- branch
- doctor
- status
- time window (optional if compact enough)

### Recommended grouping
- by time
- optionally by doctor within time block
- branch-aware if multi-branch deployment later matters

The surface must remain compact enough for Telegram.

---

## 8. Booking list and booking card

The booking list is the admin’s core list view.

A booking row/card should show at minimum:
- time
- patient display name
- doctor display name
- service label
- branch
- current status
- compact flags
- quick actions

### Quick actions may include
- confirm
- open
- mark arrived
- reschedule
- cancel
- open patient
- open care order / pickup if relevant

The card must not be buried under:
- chart paragraphs
- long descriptions
- technical IDs as primary display
- owner-style analytics data

---

## 9. Patient quick card for admin

The admin patient quick card exists for operations, not psychotherapy.

At minimum it should show:
- display name
- patient number if available
- compact contact hint
- photo/presence indicator
- active flags
- current/upcoming booking snippet
- current care order snippet if relevant

Optional:
- quick chart summary link
- reminder issue indicator

It must stay compact and operational.

---

## 10. Confirmation queue

This is a dedicated operational queue.

It should contain bookings where:
- confirmation is still needed
- no-response follow-up is needed
- reminder action failed or did not resolve the booking
- manual contact is required

### Why separate queue matters
If confirmations are only embedded inside the full booking list,
the admin loses one of the most important tasks in the noise.

### Minimum admin actions
- open booking
- confirm manually
- open reminder issue detail
- reschedule path
- cancel path
- mark manual contact attempted later if modeled

---

## 11. Reschedule queue

This queue exists because reschedule handling is not the same thing as general booking browsing.

It should contain:
- bookings in `reschedule_requested`
- maybe other operator-held move cases if explicitly modeled

### Minimum actions
- open booking
- inspect current doctor/service/time
- initiate reschedule handling
- cancel if needed

The detailed slot-replacement UX may remain later if not yet built,
but the queue concept itself must exist.

---

## 12. Waitlist queue

Waitlist is an operator tool, not background magic.

The admin should be able to see:
- patient
- preferred doctor/service
- preferred time window
- status
- source/priority
- quick open actions

### Minimum actions
- open entry
- connect candidate slot if supported later
- cancel/close entry if needed

This layer may remain simple in baseline,
but the queue itself must be visible.

---

## 13. Arrival / check-in model

The admin is the most natural owner of arrivals/check-in.

### Minimum behavior
- open booking
- mark checked-in
- see checked-in state reflected immediately
- doctor queue reacts accordingly

This action should remain in DentFlow truth, not just in calendar notes.

---

## 14. Care pickup queue

Because the clinic may dispense products at pickup,
the admin needs a dedicated care queue.

This should show:
- patient
- branch
- care order status
- pickup readiness
- issue / fulfill actions

This is not a warehouse queue.
It is a compact front-desk operational queue.

---

## 15. Communication issues queue

Admin must see cases where the automation did not fully resolve the flow.

Examples:
- reminder failed
- no-response escalation
- unsupported delivery target
- stale queued reminder recovery case
- booking confirmation backlog issue

This queue is important because the clinic must always know:
what still needs human intervention.

---

## 16. Search as a workdesk tool

Admin workdesk is not only lists.
Search is a first-class operational tool.

The admin must be able to search:
- patient
- doctor
- service

And search results must open directly into:
- patient quick card
- booking list filtered by patient
- doctor operational detail if useful

Voice-assisted retrieval can help here,
but the workdesk must not depend on voice.

---

## 17. Google Calendar as projection

Google Calendar should support the admin role, but not replace DentFlow.

## 17.1 Correct model
### DentFlow
- truth
- actions
- statuses
- reminders
- waitlist
- care pickups

### Google Calendar
- visual schedule mirror
- day/week/month awareness
- doctor/branch load visualization

## 17.2 Why Calendar is useful
The admin often needs:
- a spatial understanding of the day/week
- load distribution by doctor
- branch capacity overview

A calendar is good at this.

## 17.3 Why Calendar must not be truth
If booking truth moves into Calendar:
- sync divergence begins
- statuses drift
- reminders drift
- action history becomes unreliable

This must not happen.

## 17.4 Recommended integration strategy
Start with:
- one-way DentFlow -> Google Calendar projection
- deep links or references back into DentFlow workdesk
- no bidirectional scheduling edits initially

This is the safe model.

---

## 18. Google Sheets and the admin role

Google Sheets may help with:
- master data
- bulk review
- imports
- certain support workflows

But it must not become:
- the daily booking control surface
- the live appointment truth
- the reminder recovery console

Admin workdesk remains inside DentFlow.

---

## 19. Workdesk UX principles

The admin workdesk must follow these rules:

- one-active-panel discipline
- compact panels
- minimal text walls
- frequent actions close to the list/card
- safe role guards
- localized RU + EN
- branch-aware where needed
- not reliant on giant scrolling history dumps

This is a working surface, not a report.

---

## 20. Branch-aware semantics

Because admins may manage one or more branches,
the workdesk must support branch awareness from the beginning.

At minimum:
- filters by branch
- visible branch on booking/care pickup rows
- local-day semantics by branch/clinic timezone
- branch-aware care pickup handling

This aligns with both:
- booking work
- care work
- eventual calendar projection

---

## 21. Local-day semantics

Admin workdesk must not use raw UTC day slicing for visible “today”.

Visible workday semantics must use:
- branch timezone if relevant
- else clinic timezone
- else app default

This is critical for:
- today queue
- pending confirmations today
- care pickups today
- owner snapshot alignment later

The admin should not live inside UTC unless the clinic is on a spaceship.

---

## 22. What the admin workdesk does not need

At baseline, admin workdesk does **not** need:
- full chart authoring
- diagnosis/treatment plan editing
- owner metrics wall
- giant care catalog editor
- warehouse system
- document export studio
- AI assistant panel

Those belong to other layers.

---

## 23. Relationship to other role surfaces

## 23.1 Patient
Patient sees:
- own booking
- own recommendations
- own care orders

## 23.2 Doctor
Doctor sees:
- own queue
- own patient
- own chart summary

## 23.3 Owner
Owner sees:
- digest
- today snapshot
- alerts
- metrics

## 23.4 Admin
Admin sees:
- operational clinic truth
- queues
- pending actions
- branch-aware schedule view
- communication issues
- care pickups

This role boundary must remain explicit.

---

## 24. Future extensions

Later, the workdesk may grow into:
- calendar mirror integration
- richer waitlist tooling
- richer reminder recovery actions
- branch switching shortcuts
- compact doctor workload heatmap
- quick slot-fill suggestions

But baseline must stay operationally tight first.

---

## 25. Summary

The DentFlow admin reception workdesk is the operational center for:
- bookings
- confirmations
- reschedules
- waitlist
- arrivals
- care pickups
- communication issues

It must remain:

- truth-driven by DentFlow
- compact in Telegram
- branch-aware
- role-safe
- separate from owner, doctor, and patient surfaces
- compatible with Google Calendar as a visual mirror, not a truth source

This is where the clinic actually runs.

If this layer is vague, the whole system feels incomplete no matter how strong the engine underneath is.
