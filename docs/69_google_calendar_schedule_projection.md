# Google Calendar Schedule Projection

> Canonical projection model for mirroring DentFlow schedule data into Google Calendar.

## 1. Purpose

This document defines how Google Calendar should be used alongside DentFlow.

Its role is to make explicit:

- why Google Calendar is useful for the clinic;
- what exactly is projected from DentFlow into Calendar;
- what remains canonical truth in DentFlow;
- how the projection should behave on create/update/cancel/reschedule;
- which roles benefit from Calendar and how;
- what must not be done in v1.

This document exists to prevent a common mistake:
turning Calendar from a **visual operational aid** into a second booking backend.

That must not happen.

---

## 2. Core thesis

# DentFlow is truth.  
# Google Calendar is a visual mirror.

This is the non-negotiable rule.

### DentFlow remains canonical for:
- booking creation
- booking status
- patient linkage
- doctor linkage
- branch linkage
- reminders
- waitlist
- reschedule requests
- cancellations
- arrivals/check-in
- event history

### Google Calendar is used for:
- day/week/month view
- spatial schedule awareness
- doctor load overview
- branch load overview
- quick visual navigation

Calendar is therefore:
- a **projection**
- a **mirror**
- an **operational visual layer**

It is not:
- booking source of truth
- scheduling engine
- reminder engine
- status truth
- patient record

---

## 3. Why Calendar is useful

Admin/reception work is uniquely hard because it spans:

- many patients
- many doctors
- one or more branches
- today
- tomorrow
- the whole week
- pending confirmations
- reschedules
- no-shows
- care pickups

Telegram workdesk is excellent for:
- actions
- details
- compact cards
- patient lookup
- issue handling

But calendar is excellent for:
- spatial layout of time
- dense visual load
- overlap awareness
- branch/doctor schedule scanning

That is why the two layers should coexist.

---

## 4. Product model

The correct product model is:

## 4.1 DentFlow workdesk
Used for:
- action
- detail
- truth
- mutation
- status changes
- patient open
- care pickups
- reminder issue handling

## 4.2 Google Calendar
Used for:
- view
- scan
- orientation
- branch/doctor schedule overview

### In one sentence
# Calendar = eyes  
# DentFlow = hands

That is the intended balance.

---

## 5. Projection strategy

The baseline strategy must be:

# One-way sync: DentFlow -> Google Calendar

This is the correct starting point.

### Why one-way
Because two-way sync immediately introduces:
- drift
- ambiguity
- partial update failures
- timezone bugs
- hidden overwrite conflicts
- mysterious admin confusion

None of that is needed in the baseline.

### Therefore
In v1:
- booking is changed in DentFlow
- calendar is updated to mirror it
- actions still happen in DentFlow

---

## 6. Scope of the projection

The schedule projection should be limited to booking-related operational visibility.

At baseline, the projection should include:
- confirmed bookings
- pending_confirmation bookings
- reschedule_requested bookings
- optionally checked_in / in_service / completed if useful for the mirror model
- maybe canceled/no_show as updated/struck-through or color-changed events if operationally helpful

It should not try to project:
- waitlist as fake bookings
- chart notes
- recommendation details
- care-commerce order detail
- owner analytics into event descriptions

Keep projection tight.

---

## 7. Event projection lifecycle

Calendar projection should respond to booking truth changes.

At minimum:

## 7.1 On booking created
Create calendar event if booking state is calendar-visible.

## 7.2 On booking confirmed
Update calendar event status/visual representation.

## 7.3 On booking reschedule requested
Update event status/description/visual marker as needed.
Do not move the event to a new slot unless the booking itself has been rescheduled in DentFlow truth.

## 7.4 On booking rescheduled
Move/update calendar event to new date/time and metadata.

## 7.5 On booking canceled
Update or cancel/remove calendar event according to chosen baseline rule.

## 7.6 On booking checked_in / in_service / completed
Optionally update visual state if that helps operations.
Do not overcomplicate if it adds little value.

## 7.7 On booking no_show
Update visual state if useful for admin visibility.

The key rule:
Calendar must follow canonical booking events, not invent them.

---

## 8. Calendar identity model

Each projected booking event must be traceable back to DentFlow.

Recommended required metadata:
- `booking_id`
- `clinic_id`
- `doctor_id`
- `branch_id`
- calendar event id / external id mapping

This mapping should live canonically in integration state, not as guesswork in code.

Possible model:
- one dedicated mapping table for external calendar ids
or
- an external id mapping mechanism already used elsewhere

The important part is:
projection must be updatable, not fire-and-forget.

---

## 9. Calendar segmentation model

There are several valid projection shapes.

## 9.1 One calendar per clinic
Simple, but can become noisy.

## 9.2 One calendar per branch
Better branch-level separation.

## 9.3 One calendar per doctor
Very good for doctor load and doctor-specific visibility.

## 9.4 Hybrid: branch + doctor calendars
Most flexible, but more objects to manage.

### Recommended baseline
Start with one of these two:

#### Option A. One calendar per doctor
Best if doctor load and doctor-specific schedule scanning matter most.

#### Option B. One calendar per branch
Best if reception/admin works primarily branch-first.

### Recommended practical direction
For DentFlow baseline, the safest and most useful default is:

# one calendar per doctor

Because:
- bookings are naturally doctor-linked
- load is easier to visualize
- filters are easier mentally
- admin can overlay calendars as needed

Branch remains visible in event metadata.

If branch-first clinics later need a different view, this can expand.

---

## 10. Event content model

Calendar event content must be useful, but bounded.

## 10.1 Event title
Title should be compact and readable.

Recommended title structure:
`10:30 • Patient Name • Service • Dr. Name`

Or if calendar already implies doctor:
`10:30 • Patient Name • Service`

The exact format may vary, but keep it short.

## 10.2 Event description
Description may include:
- booking_id
- branch label
- patient phone tail if policy-safe
- current booking status
- short internal note/reference
- DentFlow link/reference hint

Description must NOT include:
- chart text
- diagnosis
- treatment plan
- reminder internals
- sensitive clinical details

## 10.3 Color/state representation
Use color or status decoration for operational clarity.

Recommended examples:
- pending_confirmation = yellow/orange
- confirmed = blue/green
- reschedule_requested = orange
- canceled = gray/red
- no_show = dark red
- checked_in / in_service = purple
- completed = muted green

This is optional in exact implementation but strongly useful.

---

## 11. Timezone model

Calendar projection must be timezone-aware.

The source of truth remains stored in UTC in DentFlow.
Calendar projection must convert correctly to the relevant timezone.

Recommended resolution order:
1. branch timezone
2. else clinic timezone
3. else application default timezone

This must be consistent with:
- admin workdesk local-day semantics
- doctor queue local-day semantics
- owner today snapshot semantics

Calendar must not reintroduce UTC confusion into user-visible schedule.

---

## 12. Role usage model

## 12.1 Admin / reception
Primary beneficiary.

Uses Calendar for:
- day/week scanning
- doctor load awareness
- quick orientation

Uses DentFlow for:
- confirming
- rescheduling
- canceling
- opening patient
- check-in
- handling issues

## 12.2 Doctor
Optional beneficiary.

May use a mirrored schedule for awareness,
but DentFlow doctor surface remains operational truth.

## 12.3 Owner
May use Calendar as secondary visual layer,
but owner truth remains digest/snapshot/alerts in DentFlow.

Calendar is not the owner dashboard.

---

## 13. Deep-link / return-to-DentFlow rule

Calendar must not become a dead-end.

Recommended baseline:
- event description includes DentFlow reference
- if platform/linking allows, add a direct DentFlow deep link or operator-readable action reference
- admin opens DentFlow to act, not Calendar

The projection should always guide the operator back to the real workdesk.

---

## 14. What must NOT happen in v1

This section is critical.

## 14.1 No two-way editing
Do not allow:
- drag/drop in Calendar to silently reschedule booking truth
- editing event title to modify booking
- direct cancellation in Calendar as booking truth

That is a later, dangerous feature if ever needed.

## 14.2 No calendar-only truth
Do not let a booking exist only in Calendar mirror.

## 14.3 No chart leaks into event descriptions
Calendar is not a chart viewer.

## 14.4 No fake waitlist bookings
Waitlist remains a separate operational queue in DentFlow.

---

## 15. Failure handling model

Projection failure must be visible but bounded.

Examples:
- event creation failed
- event update failed
- mapping lost
- calendar auth expired

Recommended handling:
- log failure
- surface as integration/sync issue
- allow retry
- do not mutate booking truth based on Calendar failure

Booking truth must survive integration failure.

---

## 16. Sync direction and retry

Baseline direction:
- DentFlow -> Google Calendar

A projection sync job or worker should:
- create missing event
- update changed event
- cancel/remove/update hidden state for invalidated event
- retry safely

Projection retry must be idempotent enough.

This should use explicit external mapping, not fuzzy event matching by text.

---

## 17. Data minimization and privacy

Calendar projection must respect privacy.

Allowed:
- patient display name if clinic policy allows
- service label
- doctor label
- branch label
- compact status
- booking reference

Be careful with:
- full phone numbers
- notes
- internal operational comments

Forbidden:
- chart notes
- diagnoses
- treatment details
- recommendation/care details unrelated to schedule

Calendar is operational visibility, not medical record display.

---

## 18. Relationship to admin workdesk

This document complements `68_admin_reception_workdesk.md`.

### Workdesk answers:
- what to do
- how to act
- what queue needs attention

### Calendar projection answers:
- what the schedule looks like in time-space

The two layers must remain coordinated but distinct.

---

## 19. Future extension path

Later, if absolutely justified, the system may evolve toward:
- richer calendar filtering
- controlled two-way sync for limited actions
- branch calendars in addition to doctor calendars
- availability overlays
- quick DentFlow action links

But those are later concerns.

The v1 baseline should remain:
- one-way
- safe
- explicit
- helpful

---

## 20. Summary

Google Calendar in DentFlow must be treated as:

- a projection
- a mirror
- a visual schedule layer

DentFlow remains:
- source of truth
- action surface
- status engine
- patient and booking truth

This allows the admin to:
- see the clinic schedule clearly,
- act in the correct place,
- avoid sync ambiguity,
- and keep the whole system reliable.

That is the correct architecture.
