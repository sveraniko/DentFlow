# DentFlow Testing and Launch

> Smoke flows, acceptance criteria, pilot launch strategy, rollback thinking, and operational readiness for DentFlow.

## 1. Purpose of this document

This document defines how DentFlow should be tested, accepted, piloted, and launched.

Its purpose is to:

- define the minimum test strategy required before real clinic usage;
- identify the critical smoke flows that must work end-to-end;
- establish acceptance criteria by subsystem and milestone;
- define pilot-launch rules and staged rollout logic;
- define rollback and recovery expectations;
- reduce the risk of discovering critical workflow failures only after real patients and clinic staff start using the system.

This document complements:

- `README.md`
- `docs/10_architecture.md`
- `docs/15_ui_ux_and_product_rules.md`
- `docs/17_localization_and_i18n.md`
- `docs/18_development_rules_and_baseline.md`
- `docs/20_domain_model.md`
- `docs/25_state_machines.md`
- `docs/30_data_model.md`
- `docs/35_event_catalog.md`
- `docs/40_search_model.md`
- `docs/50_analytics_and_owner_metrics.md`
- `docs/60_care_commerce.md`
- `docs/70_bot_flows.md`
- `docs/80_integrations_and_infra.md`
- `docs/85_security_and_privacy.md`
- `docs/90_pr_plan.md`
- `docs/92_seed_data_and_demo_fixtures.md`
- `booking_docs/*`
- `booking_docs/booking_test_scenarios.md`

This document is **not**:
- a unit-test implementation guide;
- a CI/CD configuration file;
- a legal clinic operations policy;
- a cloud SRE manual.

This document defines the operational quality gate of DentFlow.

---

## 2. Launch philosophy

DentFlow is not a toy bot.
It is a clinic operating system.

That means launch discipline must reflect reality:

- booking failures damage trust immediately;
- patient lookup failures slow the clinic;
- reminder failures create no-shows;
- chart/document failures create legal and operational pain;
- role/access failures create security risk;
- owner analytics failures may be survivable;
- owner AI hallucinations are bad, but not as bad as broken booking truth.

Therefore launch must be staged.

### Core principle:
**Do not launch by faith. Launch by controlled confidence.**

---

## 3. Quality gates

DentFlow launch readiness should be evaluated across five quality gates:

1. **Foundational correctness**
2. **Operational flow correctness**
3. **Role-surface usability**
4. **Security/privacy sanity**
5. **Pilot survivability**

A feature is not launch-ready because code exists.
A feature is launch-ready when it survives realistic, role-based, end-to-end use.

---

## 4. Test layers

DentFlow should be tested across multiple layers.

## 4.1 Layer A. Unit and service-level tests

Purpose:
- validate core domain/application behavior in isolation.

Examples:
- booking transition validation
- slot hold expiry logic
- reminder status changes
- recommendation lifecycle transitions
- reservation consumption logic
- translation fallback resolution
- search normalization/transliteration helpers

These tests are necessary, but not sufficient.

---

## 4.2 Layer B. Integration tests

Purpose:
- validate collaboration between modules and persistence surfaces.

Examples:
- booking creation writes canonical DB state and outbox event
- reminder worker reacts to booking.confirmed
- search projection updates after patient.updated
- care reservation created after care_order confirmed
- document generation reads correct structured data
- owner projection refresh consumes expected events

---

## 4.3 Layer C. End-to-end flow tests

Purpose:
- validate that a role can complete a meaningful flow end-to-end.

Examples:
- patient books appointment and receives confirmation
- admin finds patient and reschedules visit
- doctor opens upcoming patient and completes encounter
- owner sees booking reflected in digest/projection
- recommendation leads to reserve-for-pickup flow

These are critical for DentFlow.

---

## 4.4 Layer D. Smoke tests

Purpose:
- quickly determine whether the system is alive enough to proceed.

Smoke tests must be fast, targeted, and meaningful.
They are not decoration.

---

## 4.5 Layer E. Pilot runtime validation

Purpose:
- validate behavior in real clinic rhythm with real interruptions, real staff habits, and real confusion.

This is where many “technically working” systems reveal their social incompetence.

---

## 5. Test environments

## 5.1 Local development
Used for:
- fast iteration
- seed data
- isolated service tests
- UI/flow debugging

Must support:
- clean baseline rebuild
- fixture/seed loading
- role simulation
- basic search/projection support

## 5.2 Shared staging / pre-pilot
Used for:
- end-to-end flows
- realistic seeded scenarios
- role walkthroughs
- document generation checks
- integration dry-runs
- access-policy sanity checks

## 5.3 Pilot environment
Used for:
- limited real clinic usage
- selected staff
- selected flow scope
- controlled real patient exposure
- visible rollback path

### Important rule
Do not use production as the place where the architecture reveals its first opinion.

---

## 6. Baseline smoke suite

This suite should exist before any real pilot.

## 6.1 Bootstrap smoke
Must prove:
- application starts
- DB connection works
- baseline schema is valid
- workers start
- search service reachable if enabled
- seed/bootstrap commands work

## 6.2 Role routing smoke
Must prove:
- PatientBot routes correctly
- Admin/doctor/owner surfaces route correctly
- unauthorized roles do not receive privileged surfaces

## 6.3 Localization smoke
Must prove:
- RU works
- EN works
- switching language does not destroy core flow state
- key panels/buttons/errors are localized

## 6.4 Search smoke
Must prove:
- patient lookup works
- doctor lookup works
- service lookup works
- voice-assisted lookup path reaches structured result or safe fallback

## 6.5 Booking smoke
Must prove:
- booking can be created
- confirmation can be processed
- cancel works
- reschedule works
- slot truth remains coherent

## 6.6 Reminder smoke
Must prove:
- reminder job is created
- reminder dispatch path executes
- acknowledgement path works
- failure path is visible

## 6.7 Owner smoke
Must prove:
- owner digest generates
- today snapshot renders
- major booking counts appear sane

## 6.8 Document smoke
Must prove:
- document generation request works
- generated asset is stored and retrievable
- failure is visible if generation breaks

## 6.9 Security smoke
Must prove:
- role restriction is not bypassed trivially
- cross-clinic leakage does not occur in obvious surfaces
- sensitive files are not publicly exposed by default

---

## 7. Canonical end-to-end smoke flows

The following flows are considered launch-critical.

## Flow S1. New patient booking end-to-end
1. Patient enters bot
2. Selects service/problem
3. Selects slot
4. Enters minimum identity/contact
5. Booking is created
6. Patient receives confirmation
7. Admin sees booking
8. Reminder gets scheduled

Pass if:
- no hidden state break occurs
- booking appears consistently across role surfaces
- reminder is scheduled
- localization is correct for selected language

---

## Flow S2. Returning patient quick booking
1. Existing patient identified
2. Patient rebooks
3. Booking appears in admin/doctor surfaces
4. Reminder path works

Pass if:
- existing patient is reused correctly
- no duplicate accidental patient record is created unless justified by explicit logic
- search/lookup remains coherent

---

## Flow S3. Admin search and patient open
1. Admin searches by name / phone fragment
2. Finds patient
3. Opens patient quick card
4. Opens active booking
5. Takes action

Pass if:
- search returns relevant result
- patient photo/flags show correctly if available
- role sees only allowed fields

---

## Flow S4. Booking reschedule
1. Booking exists
2. Patient or admin requests reschedule
3. New slot selected
4. Old slot released
5. New slot confirmed
6. Reminders updated

Pass if:
- lifecycle is coherent
- no duplicate active booking occurs
- slot availability stays correct

---

## Flow S5. Doctor operational visit
1. Doctor sees upcoming patient
2. Opens patient/booking
3. Marks in service
4. Adds summary/note
5. Completes encounter/visit

Pass if:
- doctor flow is fast and usable
- state changes are traceable
- completion can trigger downstream logic

---

## Flow S6. Post-visit recommendation
1. Booking completed
2. Recommendation issued
3. Patient receives recommendation
4. Patient views/acknowledges/accepts or declines

Pass if:
- recommendation lifecycle remains coherent
- role views remain aligned
- owner metrics can later observe outcome

---

## Flow S7. Care reserve-and-pickup
1. Recommendation or care product choice exists
2. Patient creates reserve/pickup flow
3. Admin prepares/marks ready
4. Patient pickup/issue recorded
5. Order fulfilled

Pass if:
- order and reservation states remain aligned
- admin sees operationally useful queue
- owner metrics update cleanly

---

## Flow S8. Owner digest and metrics
1. Operational events occur
2. Projections update
3. Owner opens digest/today snapshot
4. Key metrics are visible and sane

Pass if:
- counts are explainable
- no obvious divergence from transactional truth
- no silent projection collapse

---

## Flow S9. Form-043-style document export
1. Patient/chart/encounter data exists
2. User with privilege requests export
3. Document generation runs
4. Output artifact is created
5. Access is controlled

Pass if:
- generated export uses real structured facts
- missing sections fail gracefully or render clearly
- document access respects permissions

---

## 8. Booking-specific test alignment

DentFlow-wide smoke tests must remain aligned with `booking_docs/booking_test_scenarios.md`.

General rule:
- booking package defines detailed booking tests;
- this document defines project-wide launch-critical test gates;
- any major divergence must be reconciled immediately.

Booking cannot have one truth in product docs and another in launch validation.

---

## 9. Acceptance criteria by subsystem

## 9.1 Booking subsystem acceptance
Acceptable when:
- patient booking works end-to-end
- admin control works
- confirmation/cancel/reschedule are coherent
- slot holds do not leak into broken state
- no-show/cancel are distinguishable
- realistic seeded data does not break UX

Not acceptable when:
- booking only works on empty data
- reschedule creates slot chaos
- role views disagree on booking truth

## 9.2 Search subsystem acceptance
Acceptable when:
- patient/admin/doctor lookup is fast enough for real use
- transliteration/typo tolerance is useful
- voice-assisted retrieval works in narrow scope
- fallback path exists when search confidence is low

Not acceptable when:
- search is technically present but operationally useless
- false positives create dangerous ambiguity
- search leaks data across clinic boundaries

## 9.3 Clinical subsystem acceptance
Acceptable when:
- chart anchors exist
- encounter flow is usable
- doctor can add meaningful structured content
- media/imaging references are usable
- clinical detail is not overexposed to non-clinical roles

Not acceptable when:
- doctor flow becomes paperwork punishment
- encounter truth is hidden in random notes
- document export cannot find needed structured facts

## 9.4 Recommendation and care-commerce acceptance
Acceptable when:
- recommendation flow is coherent
- care reserve/pickup works
- admin can fulfill without confusion
- patient flow feels medically relevant, not spammy

Not acceptable when:
- commerce feels detached from care context
- reservations and orders drift apart
- attach-rate metrics cannot be trusted

## 9.5 Owner analytics acceptance
Acceptable when:
- digest is understandable
- today snapshot is sane
- major KPIs map back to known truths
- anomalies are plausible and inspectable

Not acceptable when:
- owner layer behaves like a random number generator
- metrics visibly diverge from operations
- AI summary invents unsupported explanations

## 9.6 Integration and document acceptance
Acceptable when:
- document export works from structured truth
- sync jobs are visible and controlled
- failure states are visible
- no silent overwrite of canonical truth occurs

Not acceptable when:
- sheets/external adapters mutate truth silently
- document generation is fragile and opaque
- privileges around export are loose

---

## 10. Seed data requirements for realistic testing

DentFlow must be tested on realistic fake data, not on an empty toy world.

Minimum seeded realism should include:
- multiple doctors
- multiple services
- multiple branches if supported
- mixed-language patient names
- repeated surnames
- patients with and without prior visits
- patients with flags
- completed bookings
- canceled bookings
- no-show cases
- reminder history
- recommendations
- care orders
- patient photos
- media links / CT external references

### Why this matters
A system that only looks clean with three fake rows is not a system.
It is a demo hallucination.

---

## 11. Pilot launch strategy

Launch should be staged.

## 11.1 Phase P0. Internal walkthrough
Participants:
- builder(s)
- product owner
- one or two trusted power users

Goal:
- validate flows conceptually and operationally
- catch obvious UX stupidity
- verify seeded data realism
- verify role boundaries

## 11.2 Phase P1. Closed staff pilot
Participants:
- selected admin
- selected doctor
- selected owner
- minimal scope

Recommended scope:
- booking
- confirmation/reminders
- search
- doctor queue
- owner digest baseline

Goal:
- validate real clinic usage rhythm
- identify role friction
- observe where staff ignore or misuse flows
- measure operational breakpoints

## 11.3 Phase P2. Controlled real-patient pilot
Participants:
- selected real patients
- selected staff
- limited time window or service line

Recommended scope:
- a subset of booking scenarios
- reminders
- photo/media intake if ready
- minimal recommendation flow if stable

Goal:
- validate trust and usability with actual patients
- verify clinic-side handling under real interruptions

## 11.4 Phase P3. Expanded pilot
Broaden:
- services
- doctors
- scheduling density
- owner usage
- care-commerce if stable
- document generation if stable

## 11.5 Phase P4. Full operational launch
Only after:
- critical flows are stable
- rollback thinking exists
- key failure patterns are known
- staff can actually use it without daily rescue missions

---

## 12. Pilot scope control

During pilot, explicitly define:

- which roles are active
- which clinics/branches are active
- which services are allowed
- which booking modes are allowed
- whether care-commerce is enabled
- whether document export is enabled
- whether AI owner layer is enabled
- whether Sheets sync is enabled
- who can escalate problems
- what counts as stop condition

This prevents “soft launch” from becoming “accidental full launch with plausible deniability.”

---

## 13. Stop criteria

Pilot or launch should pause if any of the following occur materially:

- booking truth is inconsistent across surfaces
- reschedules create slot corruption
- cross-clinic or cross-role data leakage is observed
- reminder system fails at meaningful rate
- patient lookup becomes unreliable in real use
- owner metrics diverge badly from actual clinic reality
- exported documents are wrong in material patient details
- unauthorized access is possible
- role routing is broken in ways that expose data
- AI output is materially misleading in owner-critical use

Some problems are annoying.
Some problems mean “stop and fix”.
DentFlow must know the difference.

---

## 14. Rollback strategy

Rollback thinking must exist before full pilot expansion.

## 14.1 Functional rollback categories

### Soft rollback
Disable:
- care-commerce
- owner AI
- Sheets sync
- external adapters
- document export
- voice-assisted retrieval

while keeping booking core alive.

### Operational rollback
Switch clinic back to:
- admin-driven booking
- simplified reminder mode
- reduced doctor-side features
- reduced owner surfaces

while preserving data already captured.

### Full rollback
If necessary:
- stop live usage
- preserve DB state
- preserve audit trails
- preserve generated documents
- preserve logs required for diagnosis
- return clinic to fallback manual process

## 14.2 Rollback principle
Core booking and patient truth should be the last thing to lose.
Peripheral convenience layers should be easiest to disable.

---

## 15. Recovery and replay expectations

DentFlow should support recovery from:
- failed workers
- delayed projections
- search rebuilds
- sync failures
- document generation failures

### Minimum expectations
- search can be rebuilt
- owner projections can be refreshed
- outbox consumers can catch up
- document generation can retry
- failed sync jobs are visible and retryable
- reminders do not silently vanish without trace

---

## 16. Launch checklist structure

A real launch checklist should eventually exist as an operational artifact.
At minimum it should cover:

### Technical readiness
- services up
- DB healthy
- workers healthy
- search healthy
- storage reachable
- secrets/config valid
- observability live

### Product readiness
- booking flows smoke pass
- search smoke pass
- reminder smoke pass
- role routing pass
- localization pass
- owner digest pass if enabled
- export pass if enabled

### Data readiness
- seed/bootstrap handled
- doctors/services/branches correct
- pilot staff roles correct
- test junk removed or clearly isolated

### Security readiness
- privileged roles verified
- access boundaries checked
- generated documents protected
- signed URLs/config checked
- staging data does not contaminate live environment

### Operational readiness
- support path known
- stop criteria known
- rollback path known
- responsible people assigned

---

## 17. AI-specific launch rules

AI-assisted surfaces must be held to separate caution.

## AI may launch only if:
- underlying projections are stable
- prompts are grounded in trusted data
- output is inspectable
- output is clearly explainable
- owner can distinguish metrics from explanation

## AI must not launch if:
- it depends on unstable or incomplete projections
- it has no reliable data boundaries
- it invents causal stories from noise
- it is treated as business truth instead of assistant interpretation

---

## 18. Definition of launch-ready

A DentFlow release is launch-ready when:

- baseline rebuild works;
- seed and staging realism exist;
- critical smoke flows pass end-to-end;
- role surfaces are coherent;
- booking truth is stable;
- search is operationally useful;
- reminders are reliable enough;
- sensitive data exposure is controlled;
- owner metrics are sane if enabled;
- rollback path exists;
- pilot scope is explicit.

A release is **not** launch-ready because:
- code compiles,
- handlers exist,
- screenshots look pretty,
- an AI coding agent said it “implemented everything.”

That is not readiness.
That is theater.

---

## 19. Summary

DentFlow must be launched like a real operational system:

- with smoke flows;
- with seeded realism;
- with explicit acceptance criteria;
- with staged pilot rollout;
- with stop criteria;
- with rollback thinking;
- with clear distinction between core truth and optional convenience layers.

The right launch sequence is:

- foundation confidence,
- booking confidence,
- search confidence,
- doctor/admin operational confidence,
- owner visibility confidence,
- then broader feature expansion.

The goal is not to appear launched.

The goal is to survive contact with a real clinic.
