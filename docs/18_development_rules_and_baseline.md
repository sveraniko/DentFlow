# DentFlow Development Rules and Baseline Discipline

> Engineering rules, implementation constraints, baseline discipline, and repository guardrails for DentFlow.

## 1. Purpose of this document

This document defines how DentFlow must be developed during active implementation.

Its purpose is to prevent the most common forms of project degradation:

- architecture drift caused by isolated feature work;
- uncontrolled migration chains during active domain modeling;
- duplicated business rules across bots and handlers;
- delayed integration of core capabilities that should exist from the start;
- hardcoded UI and language assumptions;
- ad hoc technical decisions that later force large rewrites;
- “temporary shortcuts” that become permanent system damage.

This document must be treated as an **engineering contract** for the repository.

It is not optional guidance.
It is a practical rule set for how DentFlow is built while the system is still forming.

This document complements:

- `README.md`
- `docs/10_architecture.md`
- `docs/15_ui_ux_and_product_rules.md`
- `docs/17_localization_and_i18n.md`
- `docs/20_domain_model.md`
- `booking_docs/*`

If implementation conflicts with this document, implementation must be corrected.

---

## 2. Development stance

DentFlow must be built as a **Telegram-first, phone-first, modular clinic operating system**.

This has direct implementation consequences:

- core architecture must stay layered and modular from day one;
- booking is a first-class subsystem, not an add-on;
- search is a first-class subsystem, not a future convenience;
- voice-assisted retrieval is not a “nice later feature”, but an early productivity surface;
- localization is not a later rewrite, but a built-in product capability;
- Google Sheets sync is not a hack around the system, but an integration surface with clear ownership rules;
- analytics and owner insight are architecturally planned from the beginning, even if all dashboards are not exposed on day one.

DentFlow must be developed as a system that can grow without collapsing under its own patchwork.

---

## 3. Core engineering principles

## 3.1 Docs-first, then code

Major implementation work must be anchored in documentation first.

This means:

- architectural decisions must map to documented bounded contexts and layers;
- domain entities must map to `docs/20_domain_model.md`;
- booking behavior must map to `booking_docs/*`;
- UI behavior must map to `docs/15_ui_ux_and_product_rules.md`;
- i18n behavior must map to `docs/17_localization_and_i18n.md`.

Code must not become the place where product decisions are invented retroactively.

## 3.2 One source of truth per concern

Every concern must have a clearly defined source of truth.

Examples:

- patient truth lives in the patient/core context;
- booking truth lives in booking/scheduling contexts;
- search index is not source of truth;
- analytics projections are not source of truth;
- Google Sheets is not source of truth unless explicitly defined for a specific import/sync workflow;
- UI state is not source of truth.

If ownership is ambiguous, the design is wrong and must be clarified before expanding the feature.

## 3.3 Layering is mandatory

DentFlow must preserve a layered structure:

- interfaces;
- application orchestration;
- bounded contexts / domain modules;
- infrastructure and persistence;
- projections / analytics / search read models.

Handlers must not become miniature systems that contain business logic, persistence logic, formatting logic and analytics logic all mixed together.

## 3.4 Simplicity in visible behavior, discipline in internal boundaries

Telegram-facing behavior must stay simple.
Internal implementation must stay explicit and separated.

A fast chat flow does not justify architecture shortcuts.

---

## 4. Repository-wide implementation rules

## 4.1 No random feature grafting

A new feature must not be implemented as a free-floating set of handlers and tables.

Every non-trivial change must answer:

- which bounded context owns it;
- what aggregate or entity it belongs to;
- what events it emits or consumes;
- what UI surfaces it changes;
- whether localization is required;
- whether analytics/read-model impact exists;
- whether search impact exists;
- whether synchronization/integration impact exists.

If these answers are missing, the implementation is premature.

## 4.2 No hidden architecture

Critical architectural behavior must not live only in code comments or in someone's memory.

If an implementation introduces:

- a new context;
- a new state machine;
- a new event contract;
- a new sync surface;
- a new owner metric;
- a new search rule;
- a new multilingual surface;

then the related documentation must be updated in the same implementation cycle.

## 4.3 No hardcoded strings in product flows

User-facing strings must not be hardcoded into handlers or service methods.

All user-visible content must go through the localization system defined in `docs/17_localization_and_i18n.md`.

This applies to:

- buttons;
- panels;
- prompts;
- confirmations;
- reminders;
- errors;
- owner/admin summaries where localization is required.

## 4.4 No duplicated business rules across roles

The same business rule must not be reimplemented separately in:

- patient bot handlers;
- admin bot handlers;
- owner bot handlers;
- doctor flows;
- ad hoc helper scripts.

Business rules must live in domain/application services and be reused across interfaces.

## 4.5 No search-as-truth

Search exists to accelerate retrieval.
It must not become the canonical storage of patient, booking, or commerce state.

If the search index fails, core flows must degrade, not collapse.

## 4.6 No analytics-on-transactional-hot-path

Heavy reporting logic must not run directly against live transactional flows in a way that risks degrading core system responsiveness.

Analytics and owner views must rely on projections, read models, or curated queries designed for that purpose.

---

## 5. Baseline migration discipline

This is one of the most important implementation rules in the project.

## 5.1 During active development, baseline is edited in place

While DentFlow is still in active domain shaping and before a stable milestone is declared, schema work must follow **baseline-only discipline**.

This means:

- do not create long chains of incremental migrations for every schema tweak;
- edit and maintain the baseline schema instead;
- regenerate or rebuild the environment from baseline as needed;
- keep the schema coherent and readable.

The goal is to avoid a graveyard of throwaway migrations caused by constantly changing understanding.

## 5.2 Clean rebuild must always work

At any point during active development, a clean environment rebuild from baseline must work.

This includes:

- database creation;
- schema creation;
- required seed/bootstrap setup where applicable;
- search/index bootstrap where applicable;
- worker/service startup against the fresh environment.

A repo that only works on the author's half-mutated local database is not a working repo.

## 5.3 No migration noise during exploratory shaping

While the system is still being actively rethought:

- do not generate migration-per-field-change churn;
- do not leave abandoned migrations in history;
- do not rely on “we will squash later” as a default excuse.

If the model is still moving, update baseline.
When the model stabilizes, then formal forward migrations can begin.

## 5.4 Stable milestone changes the policy

Once a stable implementation milestone is declared, forward migrations may become the normal mechanism.

At that point:

- baseline is frozen for that milestone;
- new changes are represented as proper migrations;
- migration history becomes part of the operational contract.

That policy shift must be explicit, not accidental.

## 5.5 Data backfills are not excuses for dirty schema history

If a feature needs initial data, projections, or bootstrap content, use:

- seed scripts;
- sync/bootstrap jobs;
- projection builders;
- explicit data migration utilities if the project is already past baseline phase.

Do not pollute active baseline development with throwaway operational hacks.

---

## 6. Booking-first implementation rule

Booking is a first-class subsystem.

This means:

- booking behavior must not be scattered across generic chat handlers;
- slot logic must not be casually redefined in unrelated flows;
- booking state must be governed by documented rules;
- booking docs are authoritative for booking-specific behavior.

The `booking_docs/` package must be treated as an implementation contract for:

- booking flow;
- booking domain model;
- slot ranking;
- booking state machine;
- booking Telegram UI contract;
- booking integrations and operational behavior;
- booking test scenarios.

If generic architecture docs and booking docs diverge, they must be reconciled immediately.

---

## 7. Search and voice are early surfaces, not deferred luxuries

## 7.1 Search must exist early

Patient search is one of the core operational surfaces of DentFlow.

This means search must be designed and introduced early enough to influence:

- patient identity modeling;
- normalization rules;
- indexing strategy;
- quick-access UX;
- owner/admin/doctor operational flows.

Search must not be bolted on after the rest of the product is already cemented.

## 7.2 Voice-assisted retrieval must exist early

DentFlow must support voice-assisted retrieval early, especially for operational flows like:

- find patient;
- open booking;
- locate record;
- quickly attach an action to a found patient.

This does **not** mean building a universal voice agent from day one.

It means introducing focused voice-assisted actions where they reduce friction immediately.

## 7.3 Fallback behavior is mandatory

If voice transcription fails or search confidence is low:

- the system must fall back to clarifying choices;
- the system may request manual refinement;
- the system must not silently choose a risky result.

---

## 8. Google Sheets sync rule

Google Sheets integration must be designed early where it supports real clinic operations.

However, a sheet must not silently become canonical truth unless explicitly intended.

Recommended stance:

- transactional truth lives in DentFlow core contexts;
- Sheets may serve as import, export, operator-edit, reporting, or limited sync surfaces;
- ownership and direction of sync must be explicit per use case.

Every Sheets integration must define:

- what data is synced;
- who owns the truth;
- direction of sync;
- frequency/timing;
- conflict rules;
- failure behavior;
- audit expectations.

“Let's just read it from Sheets for now” is not a valid architecture strategy.

---

## 9. UI/UX rules are implementation constraints

The UI contract is not design garnish.
It is part of product architecture.

Implementation must obey `docs/15_ui_ux_and_product_rules.md`, including:

- one active panel;
- no duplicate active surfaces for the same job;
- clean chat discipline;
- compact messages;
- consistent action placement;
- phone-first interactions;
- multifunction controls only when documented and consistent;
- voice/search available in core operational surfaces.

If an implementation creates chat clutter or panel duplication, it is defective even if the code “works”.

---

## 10. Localization is a development rule, not a later task

Implementation must obey `docs/17_localization_and_i18n.md`.

This means:

- Russian and English support are expected from the start for product surfaces;
- all user-facing strings must be localizable;
- locale-aware formatting must be respected;
- language switching must remain possible without code surgery;
- adding Georgian or Polish later must be a content/config extension, not a rewrite.

No new feature is complete if it introduces a user-facing flow that only exists in one language by hardcoded accident.

---

## 11. Event and projection discipline

DentFlow must be event-aware where it matters.

This does not require premature distributed-system theater.
It does require discipline.

## 11.1 Important state changes should emit events

Examples include:

- patient created or updated;
- booking created, held, confirmed, rescheduled, canceled, completed;
- recommendation issued;
- care order reserved, issued, canceled, fulfilled;
- reminder scheduled, sent, failed, acknowledged;
- locale changed;
- sync completed or failed.

## 11.2 Projections must be derived, not improvised

Search indexes, analytics views, owner summaries and similar read surfaces should be treated as projections/read models derived from core truth.

They must not become hand-maintained secondary truths.

## 11.3 Idempotency matters

Consumers of important events must be written with idempotent expectations where practical.

Repeated delivery must not create duplicate reservations, duplicate notifications, duplicate owner alerts, or duplicate projections.

---

## 12. Allowed simplification vs forbidden simplification

## 12.1 Allowed simplification

These are valid simplifications during v1 if explicitly documented:

- narrower UI coverage;
- reduced analytics breadth;
- fewer reminder variants;
- reduced recommendation complexity;
- reduced sync directions;
- partial owner reporting;
- compact state models where complexity is genuinely unnecessary.

## 12.2 Forbidden simplification

These are not acceptable “temporary shortcuts”:

- hardcoded language strings in handlers;
- putting business rules directly in Telegram handlers;
- using search index as canonical state;
- relying on manual unstated spreadsheet truth;
- bypassing baseline discipline with migration spam;
- cloning logic across patient/admin/owner flows;
- introducing new UI patterns that ignore one-panel discipline;
- treating booking as generic chat state instead of a subsystem;
- postponing search/voice until too much depends on bad assumptions.

---

## 13. CODEX implementation contract

This section exists because coding agents tend to be productive in the same way a power tool is productive: useful, fast, and fully capable of ruining the wall if left unsupervised.

CODEX must follow these rules:

### 13.1 Respect authoritative docs

CODEX must treat the following as implementation constraints:

- `README.md`
- `docs/10_architecture.md`
- `docs/15_ui_ux_and_product_rules.md`
- `docs/17_localization_and_i18n.md`
- `docs/20_domain_model.md`
- `booking_docs/*`

### 13.2 Do not invent parallel patterns

If the repo already has a pattern for:

- panel rendering;
- callbacks;
- context ownership;
- localization;
- search orchestration;
- projections;
- sync handling;

CODEX must extend the existing pattern rather than inventing a new local style.

### 13.3 Do not spawn migration clutter

During active baseline phase, CODEX must update baseline artifacts instead of generating serial migration churn.

### 13.4 Do not silently broaden scope

If a requested implementation would require undocumented architectural changes, CODEX must surface that fact in its report rather than smuggling in hidden structural decisions.

### 13.5 Leave the repo in a coherent state

A change is not complete if it leaves:

- half-wired handlers;
- untranslated strings;
- broken rebuilds;
- partial schema changes;
- undocumented new states;
- stale projections;
- dead callback paths.

---

## 14. Definition of done for non-trivial changes

A non-trivial implementation change should normally be considered done only if:

- bounded-context ownership is clear;
- schema/baseline is coherent;
- user-facing strings are localizable;
- UI behavior respects product rules;
- booking/search/i18n impacts are considered where relevant;
- analytics/projection impacts are considered where relevant;
- rebuild/bootstrap still works;
- docs are updated if the change alters product or architecture behavior.

---

## 15. What this document deliberately does not define

This document does not define:

- final PR stack sequencing;
- implementation waves;
- sprint plans;
- detailed test matrix;
- deployment topology specifics;
- final observability stack;
- every event payload shape.

Those belong in dedicated documents.

This document defines the discipline under which those implementation details must be produced.

---

## 16. Summary

DentFlow must be built with discipline from the start.

The repo must preserve:

- documentation-driven implementation;
- bounded-context ownership;
- baseline-only schema discipline during active shaping;
- early search and voice-assisted retrieval;
- early multilingual capability;
- early Sheets integration where justified;
- Telegram-first UX consistency;
- projection-based analytics and owner insight;
- clear separation between truth, search, analytics and sync surfaces.

The system is allowed to be ambitious.
It is not allowed to become structurally sloppy.
