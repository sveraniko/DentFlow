# DentFlow Architecture

> Canonical architecture map for DentFlow.

## 1. Purpose

This document defines the project-wide architecture of DentFlow.

It establishes:

- architectural boundaries;
- runtime contours;
- source-of-truth rules;
- deployment stance;
- bounded contexts;
- projection strategy;
- integration strategy;
- degradation rules.

This document should be read together with:
- `README.md`
- `docs/18_development_rules_and_baseline.md`
- `docs/20_domain_model.md`
- `docs/22_access_and_identity_model.md`
- `docs/23_policy_and_configuration_model.md`
- `docs/30_data_model.md`
- `docs/80_integrations_and_infra.md`

---

## 2. Architectural thesis

DentFlow is a **Telegram-first clinic operating system**.

It must therefore solve for three realities at once:

1. **phone-first usage**
2. **operational truth and discipline**
3. **future extensibility without collapse**

The architecture must protect the system from two common failures:

- a toy bot that works only on empty data and no real clinic rhythm;
- a bureaucratic monster that tries to clone an enterprise medical suite before the clinic core even works.

---

## 3. Deployment stance

## 3.1 Default deployment model

DentFlow is **single-clinic per deployment by default**.

That means:
- one live deployment belongs to one clinic instance;
- all canonical transactional entities are scoped to one clinic;
- operational complexity stays low;
- failure isolation stays high;
- implementation remains realistic for private clinic usage.

## 3.2 Branch support

`branch_id` is supported as an optional dimension inside a clinic deployment.

Use `branch_id` when:
- the clinic has multiple physical branches;
- booking/search/analytics need branch resolution;
- owner views need per-branch metrics.

Do not treat `branch_id` as justification for premature multi-tenant complexity.

## 3.3 Future owner federation

Cross-clinic owner visibility is a **future federation layer**, not a reason to contaminate the v1 core.

That means:
- owner aggregation across multiple clinic deployments should happen through integration/projection/federation mechanisms;
- booking core remains clinic-local;
- owner-wide analytics may later consume multiple `clinic_id` sources.

---

## 4. Core architectural principles

## 4.1 One source of truth per concern

Canonical ownership must be explicit.

Examples:
- patient identity -> Patient Registry
- final booking truth -> Booking / Scheduling
- reminders -> Communication / Reminders
- clinical chart truth -> Clinical Chart
- care orders -> Care Commerce
- access bindings -> Access and Identity
- operational settings -> Policy and Configuration

## 4.2 Projections are not truth

Search, analytics, owner digests, exports, and adapter payloads are projections or derived views.

They must not quietly become the system of record.

## 4.3 Interface layer must stay thin

Telegram bots are an interface layer.
They do not own business rules, state transitions, or data truth.

## 4.4 Asynchronous work belongs to workers

Anything that does not need to block user trust should be handled asynchronously:
- reminder execution
- projection rebuilds
- export generation
- sync jobs
- owner digest refresh
- waitlist processing
- hold expiry

## 4.5 Explicit settings, not hidden constants

Clinic, branch, doctor, reminder, AI, export, and integration behavior must come from explicit policy/configuration models.

No hardcoded operational religion hidden in handlers.

---

## 5. Runtime contours

DentFlow is structured into role and system contours.

## 5.1 Patient contour
Responsible for:
- guided entry
- booking
- reminders
- follow-up
- media submission
- recommendation response
- care reservation/pickup

## 5.2 Clinic operations contour
Responsible for:
- patient lookup
- booking control
- confirmations
- check-in flow
- schedule operations
- care order handling
- communication exceptions

## 5.3 Doctor contour
Responsible for:
- queue visibility
- patient recognition
- encounter progression
- quick notes
- recommendation issuance
- media access

## 5.4 Owner contour
Responsible for:
- daily digest
- clinic metrics
- branch/service/doctor insights
- anomalies
- AI-assisted explanation over projections

## 5.5 System contour
Responsible for:
- event publication
- reminders
- projections
- exports
- sync
- observability
- media handling

---

## 6. Bounded contexts

The core bounded contexts are:

1. Clinic Reference
2. Access and Identity
3. Policy and Configuration
4. Patient Registry
5. Booking and Scheduling
6. Communication and Reminders
7. Search and Voice Retrieval
8. Clinical Chart
9. Recommendations
10. Care Commerce
11. Media and Documents
12. Analytics
13. Owner Insights
14. Integrations and External Sync

### Key rule
If CODEX cannot answer “which bounded context owns this?”, the implementation is not ready.

---

## 7. Context responsibilities

## 7.1 Clinic Reference
Owns:
- clinic
- branch
- doctor
- service
- doctor access codes
- branch/doctor/service metadata needed across the system

## 7.2 Access and Identity
Owns:
- staff identity
- role bindings
- Telegram role binding
- owner/admin/doctor membership
- privileged action eligibility

## 7.3 Policy and Configuration
Owns:
- clinic settings
- branch settings
- doctor booking policy
- reminder policy
- feature flags
- export policy
- AI toggles
- integration toggles

## 7.4 Patient Registry
Owns:
- canonical patient identity
- contact methods
- reminder preferences
- patient photo metadata
- operational patient flags
- lightweight patient summary

## 7.5 Booking and Scheduling
Owns:
- booking sessions
- availability slots
- slot holds
- final bookings
- waitlist entries
- booking history

Does **not** own a second patient registry.
Does **not** own canonical reminders.

## 7.6 Communication and Reminders
Owns:
- reminder jobs
- reminder state
- delivery attempts
- acknowledgement records
- communication logs

Booking may trigger reminders.
Communication owns reminder truth.

## 7.7 Search and Voice Retrieval
Owns:
- search projections
- normalization
- transliteration
- fuzzy/ranking behavior
- voice-to-query assistance

Does not own transactional truth.

## 7.8 Clinical Chart
Owns:
- chart anchor
- encounter
- notes
- diagnosis
- treatment plan
- odontogram snapshots
- imaging references

## 7.9 Recommendations
Owns:
- recommendation objects
- lifecycle
- recommendation issuance and response

## 7.10 Care Commerce
Owns:
- catalog
- recommendation-to-product links
- care orders
- reservations
- pickup/issue lifecycle

## 7.11 Media and Documents
Owns:
- media asset registry
- generated documents
- templates
- export metadata

## 7.12 Analytics
Owns:
- event-derived projections
- operational KPIs
- branch/service/doctor metrics
- retention and funnel projections

## 7.13 Owner Insights
Owns:
- owner digest
- live snapshot
- anomaly candidates
- explainable management views
- AI-assisted insight layer over trusted projections

## 7.14 Integrations and External Sync
Owns:
- external systems registry
- external ID maps
- sync jobs
- adapters
- import/export contracts

---

## 8. Source-of-truth map

| Concern | Canonical owner | Notes |
|---|---|---|
| Patient identity | Patient Registry | booking references patient by `patient_id` |
| Staff roles | Access and Identity | not derived from Telegram chat presence alone |
| Booking truth | Booking and Scheduling | final table = `booking.bookings` |
| Reminder truth | Communication and Reminders | no duplicate booking reminder system |
| Clinical record truth | Clinical Chart | runtime clinical facts |
| Recommendation truth | Recommendations | may trigger care flows |
| Care order truth | Care Commerce | separate from clinical truth |
| Search | Search projection | derived |
| Owner metrics | Analytics / Owner Insights | derived |
| 043 export | Media and Documents | generated projection |
| External sync state | Integrations and External Sync | adapter-owned sync metadata |

---

## 9. Layer model

DentFlow should preserve a layered structure.

## 9.1 Interface layer
- PatientBot
- ClinicAdminBot
- doctor-side surface
- OwnerBot

## 9.2 Application/orchestration layer
- use cases
- coordinators
- workflow services
- command/query handlers

## 9.3 Domain layer
- bounded contexts
- aggregates
- domain services
- lifecycle validation

## 9.4 Persistence and infrastructure layer
- Postgres
- Redis/ephemeral state
- search engine
- storage
- workers
- outbox
- integration adapters

## 9.5 Projection layer
- search docs
- analytics read models
- owner views
- export snapshots
- sync payload builders

---

## 10. Event-aware architecture

DentFlow is not full distributed theater, but it is event-aware where it matters.

Important business facts should emit events so that:
- reminders are scheduled or canceled cleanly;
- search projections refresh;
- owner projections refresh;
- care/recommendation flows react to visit completion;
- exports and integrations can subscribe later without direct hidden coupling.

Important event-producing areas:
- patient changes
- booking transitions
- reminder lifecycle transitions
- recommendation lifecycle transitions
- care-order lifecycle transitions
- chart/encounter milestones
- sync/document outcomes

---

## 11. Reminder architecture stance

Reminders are a core subsystem, not decorative messaging.

The system must support:
- booking confirmation prompts;
- pre-visit reminders;
- same-day reminders;
- action-required reminders;
- acknowledgement tracking;
- failure visibility;
- per-clinic/per-doctor reminder policy.

DentFlow should support the psychologically useful pattern where some reminders require explicit action, for example:
- confirm
- already on my way
- request reschedule
- cancel

That interaction is not just UX.
It is discipline and operational signal.

Canonical reminder truth still lives in Communication / Reminders.

---

## 12. Export/document architecture stance

DentFlow must support 043-style and related document workflows without forcing runtime users into a paper-layout prison.

Architecture rule:
- runtime collects structured facts;
- export layer maps those facts into document templates;
- generated documents remain controlled artifacts;
- export generation is worker-driven and auditable.

---

## 13. Search architecture stance

Search is a first-class operational capability.

It must be:
- fast;
- clinic-scoped;
- role-aware;
- rebuildable;
- tolerant to transliteration and typing noise;
- usable with voice-assisted retrieval.

Search is derived.
If search goes down, the clinic must still be able to work in degraded mode.

---

## 14. Failure isolation and graceful degradation

The architecture must support graceful degradation.

If search is down:
- lookup degrades, but booking truth survives.

If analytics is late:
- owner views degrade, but clinic operations continue.

If care-commerce is disabled:
- booking and clinical flows still work.

If AI is unavailable:
- owner gets raw projections, not fiction.

If export generation is down:
- runtime truth still exists.

If Sheets sync fails:
- canonical truth still lives in DentFlow.

---

## 15. What architecture explicitly forbids

DentFlow architecture forbids:

- a second patient registry inside booking;
- a second reminder system inside booking;
- shared canonical truth in Google Sheets;
- treating export files as primary truth;
- hardcoded role access in handlers;
- hidden config split between constants, env and random tables;
- letting bots perform domain transitions without service-layer validation;
- multi-clinic complexity inside the v1 booking core.

---

## 16. Summary

DentFlow architecture is built around:

- single-clinic deployments with optional branches;
- explicit context ownership;
- booking truth separate from reminders;
- patient truth separate from booking;
- search, analytics and export as projections;
- role-specific Telegram surfaces;
- explicit access/auth and policy/config models;
- worker-driven async behavior;
- future federation through integrations, not through premature core complexity.

This is how DentFlow remains powerful without becoming structurally stupid.
