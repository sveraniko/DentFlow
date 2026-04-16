# 30_booking_routing_and_slot_ranking.md

## Purpose

This document defines how the system chooses candidate doctors and ranks available slots.

This is one of the most important parts of the booking subsystem because it determines:
- conversion,
- doctor load distribution,
- premium capacity protection,
- continuity for repeat patients,
- operational efficiency for the clinic.

---

## Routing principle

The user should not manually navigate the clinic schedule.

The system should do the routing work.

That means the engine must:
1. identify eligible doctors,
2. filter by policy,
3. filter by user constraints,
4. rank candidate slots,
5. show only the best 3 to 5 options.

---

## Routing routes

## Route A. Public general booking
Used when the user has no specific doctor requirement.

### Behavior
- route by service compatibility,
- apply public booking rules,
- exclude protected doctors if configured,
- rank by convenience and clinic optimization,
- return a short list of best slots.

This is the default route.

---

## Route B. Repeat-patient route
Used when patient history exists and the user indicates they want their previous doctor.

### Behavior
- attempt continuity with last doctor,
- if no matching slot exists, offer:
  - other dates,
  - waitlist,
  - fallback to other eligible doctors.

The system should support continuity, but not create a dead end.

---

## Route C. Doctor-code route
Used when the user has a valid doctor code.

### Behavior
- validate code,
- lock doctor context,
- search only that doctor’s slots,
- preserve service and time compatibility,
- never silently spill into other doctors without explicit fallback.

---

## Candidate doctor filtering

Before slot ranking, doctors must be filtered.

### Base filters
- doctor is active,
- doctor has required specialty,
- doctor is available in the relevant clinic/location,
- doctor supports the selected service,
- doctor is bookable under the selected route.

### Additional route filters

#### For public booking
- `bookable_publicly = true`
- `premium_protected = false` unless policy allows limited public exposure
- public quota not exhausted

#### For repeat patient
- doctor may be allowed even if not broadly public, depending on continuity policy

#### For doctor code
- code owner doctor only

---

## Public doctor exposure policy

The clinic must control whether high-demand doctors appear in general search.

### Recommended controls
- `bookable_publicly`
- `premium_protected`
- `public_quota_limit`
- `public_quota_window`
- `repeat_patient_priority`

### Example policy
Doctor Ksenia:
- active = true
- bookable_publicly = false
- premium_protected = true
- repeat_patient_priority = true

Result:
- not shown to generic traffic,
- available to repeat patients,
- available via valid access code,
- available to admins.

This protects premium capacity without blocking legitimate continuity.

---

## Candidate slot filtering

After doctor filtering, candidate slots must be filtered.

### Base slot filters
- slot status is `free`,
- slot duration fits service requirements,
- slot belongs to an eligible doctor,
- slot visibility policy allows the current route,
- slot time is not in the past.

### User preference filters
- requested date or date window,
- requested time-of-day window,
- urgent-case horizon,
- doctor-specific context,
- clinic/location restrictions if any.

---

## Ranking objectives

Slot ranking must optimize for both user convenience and clinic operations.

### User-facing objectives
- nearest acceptable appointment,
- time window match,
- continuity when desired,
- reduced decision load.

### Clinic-facing objectives
- balanced doctor load,
- protected premium capacity,
- reduced idle time,
- appropriate skill matching,
- handling urgent cases first when required.

---

## Ranking score model

A weighted score approach is recommended.

### Example ranking factors
Each candidate slot may receive a score based on:

1. `service_match_score`
2. `specialty_match_score`
3. `date_match_score`
4. `time_window_score`
5. `urgency_score`
6. `continuity_score`
7. `doctor_policy_score`
8. `load_balancing_score`
9. `premium_capacity_penalty`
10. `location_score`

### Example interpretation
- better service match = higher score
- closer to requested date = higher score
- previous doctor match = higher score for repeat route
- overloaded premium doctor = lower score in public route
- underutilized eligible doctor = slightly higher score

---

## Practical ranking rules

### Rule 1. Public route should prefer “good enough soonest”
Do not overfit.
The user usually wants a convenient near slot, not mathematically perfect scheduling poetry.

### Rule 2. Repeat route should prefer continuity first
If user wants their previous doctor, give continuity priority, but keep fallback options.

### Rule 3. Doctor-code route must not leak
If code route is active, do not mix in other doctors without explicit user action.

### Rule 4. Urgent route should reduce strictness
For urgent pain, nearest eligible slot should outrank softer time preferences.

### Rule 5. Protect top doctors in public route
Premium-protected doctors should receive a large negative weight or be excluded entirely.

---

## Suggestion output pattern

The engine should return a ranked slice, not a full availability dump.

### Recommended output
- 3 to 5 slot suggestions,
- stable order,
- deterministic pagination via “next slice”,
- include slot ID and presentation metadata.

### Example
1. 2026-04-10 17:20 / Doctor A / score 0.94
2. 2026-04-10 18:00 / Doctor B / score 0.91
3. 2026-04-11 16:40 / Doctor C / score 0.88

Telegram should only render the user-facing text, not the scoring internals.

---

## “More options” behavior

The “More options” button must not open a calendar.

It should request the next ranked page of candidate slots under the same constraints.

### Important
If the user repeatedly presses “More options”, after several pages the system may prompt:
- change date,
- change time,
- change doctor preference.

This avoids infinite browsing.

---

## No-slot behavior

If no slots satisfy the constraints, the engine should not just fail.

### Fallback options
- broaden date window,
- broaden time-of-day,
- switch to other eligible doctors,
- offer waitlist,
- escalate to admin.

### Example
If repeat-patient path finds no slots with the last doctor:
- offer next date window with same doctor,
- offer waitlist,
- offer general booking with other doctors.

---

## Urgent routing

Urgent flows should use a separate strategy.

### Urgent examples
- tooth pain,
- swelling,
- post-op problem.

### Urgent routing rules
- prefer earliest possible slot over preferred time-of-day,
- allow admin escalation quickly,
- optionally route to urgent-capable doctors only.

---

## Deterministic behavior

Ranking must be deterministic for identical input within a short time window.
Otherwise the UI will feel inconsistent and buggy.

### Required properties
- same constraints -> same first slice unless availability changed,
- pagination uses stable continuation token or offset strategy,
- expired holds may reshuffle candidates only when truly necessary.

---

## Observability

Routing decisions should be observable for debugging and tuning.

### Recommended logging fields
- session_id
- route_type
- service_id
- doctor_preference_type
- requested_date
- time_window
- candidate_count_before_policy
- candidate_count_after_policy
- returned_slot_ids
- fallback_reason if no slots

This will matter later when humans wonder why the bot did not offer Ksenia at 17:00. Because humans always do.

---

## Reuse beyond dental

The routing engine should be reusable.

### Generic abstraction
- resources
- services
- availability
- route policy
- access code
- ranking strategy

The dental clinic config is just one specialization of the engine.
