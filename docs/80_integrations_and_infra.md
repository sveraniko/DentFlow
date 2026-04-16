# DentFlow Integrations and Infrastructure

> Infrastructure shape, integration surfaces, deployment policy, and operational foundations for DentFlow.

## 1. Purpose

This document defines the infrastructure and integration model of DentFlow.

It exists to make sure the system does not accidentally become:
- a handler pile pretending to be architecture;
- a secret spreadsheet backend;
- a multi-tenant monster before first pilot;
- an integration circus with no clear truth boundaries.

---

## 2. Infrastructure thesis

DentFlow must support:

- Telegram-first role surfaces;
- transactional truth in Postgres;
- fast search;
- worker-driven async tasks;
- media/document handling;
- export generation;
- explicit integrations;
- observability and graceful degradation.

The system should be serious internally without becoming operational theater.

---

## 3. Deployment stance

## 3.1 Default
One DentFlow deployment = one clinic instance.

Benefits:
- simpler isolation;
- simpler operations;
- lower blast radius;
- easier staff understanding;
- better fit for small/private clinics.

## 3.2 Branches
Optional internal branches are supported via `branch_id`.

Use branches for:
- booking routing;
- branch metrics;
- branch pickup;
- branch owner views.

## 3.3 Future federation
Cross-clinic owner aggregation should be a federation/integration concern.

Recommended later pattern:
- each clinic deployment exports owner projections;
- a federation layer aggregates by selected clinic ids;
- owner-wide dashboards read federation projections.

Do not build this complexity into the v1 booking core.

---

## 4. Runtime components

Recommended major runtime components:

1. bot interface runtime(s)
2. primary Postgres
3. search engine / index
4. Redis or equivalent ephemeral state layer
5. worker runtime
6. object/media storage
7. document generation pipeline
8. integration/sync worker layer
9. projection/analytics refresh layer
10. observability stack

---

## 5. Core truth and derived surfaces

## 5.1 Canonical truth
Lives in Postgres logical schemas:
- reference
- access identity
- policy config
- patient
- booking
- communication
- clinical
- care commerce
- media/docs
- integration

## 5.2 Derived surfaces
- search indices
- analytics projections
- owner views
- generated documents
- Sheets exports
- external adapter payloads

These must be rebuildable or at least clearly derivable from truth.

---

## 6. Reminder infrastructure stance

Reminders are core.
Treat them accordingly.

Reminder infra should support:
- scheduled execution
- action-required messages
- acknowledgement capture
- non-response escalation
- failure visibility
- policy-driven timing
- booking-linked and care-linked reminder types

Canonical reminder state lives in Communication, not Booking.

---

## 7. Search infrastructure stance

Search should be its own service/index surface.

It supports:
- patient lookup
- doctor lookup
- service lookup
- voice-assisted retrieval
- transliteration and fuzzy behavior

If search fails:
- clinic operations degrade;
- they do not collapse.

---

## 8. Media and document infrastructure

Use object storage or equivalent for:
- patient photos
- issue photos
- uploaded files
- generated PDFs
- previews

Store metadata in Postgres.

For large CT/imaging artifacts:
- support controlled external URL/reference mode;
- keep metadata and access rules in the system;
- do not force absurd upload-only assumptions.

---

## 9. Export/document pipeline

Document generation should be worker-driven:

1. request generation
2. load structured facts
3. render template
4. store generated artifact
5. register generated document metadata
6. expose through controlled UI

This is how 043-style exports remain supported without dictating runtime UX.

---

## 10. Google Sheets integration stance

Google Sheets is a **controlled integration surface**.

Good uses:
- seed imports
- operator review exports
- selected reference data management
- controlled sync

Forbidden use:
- secret canonical truth for bookings or patients

Each Sheets flow must define:
- direction
- scope
- ownership
- cadence
- conflict behavior
- failure visibility

---

## 11. External adapters stance

DentFlow may later integrate with systems such as 1C-like software.

This must happen through:
- explicit adapter layer
- external id maps
- sync jobs
- structured payloads

DentFlow should be adapter-ready.
It should not become a clone of every external system it might ever meet.

---

## 12. AI infrastructure stance

AI should be implemented as an explicit assistive layer.

Good AI surfaces:
- owner explanation and Q&A
- retrieval assistance
- summarization

Bad AI surfaces:
- unsupervised state mutation
- fake medical decision engine
- raw unrestricted access to everything

AI should consume scoped, grounded data, not accidental data soup.

---

## 13. Configuration boundaries

Infrastructure config groups:
- core app config
- DB config
- search config
- Redis/ephemeral state config
- storage config
- communication provider config
- AI provider config
- integration config
- observability config

Business policy belongs to `docs/23_policy_and_configuration_model.md`, not to random `.env` constants.

---

## 14. Seed/bootstrap infrastructure

Before Sheets sync exists, DentFlow must support:
- script-based seed imports
- reference-data loading
- fake patient/demo booking fixtures
- projection rebuilds
- demo media/doc references

Bootstrap is not optional.
Without realistic seeded data, many subsystems will look “fine” only because reality never touched them.

---

## 15. Observability basics

DentFlow must at minimum provide visibility for:
- bot uptime
- DB health
- search health
- worker failures
- reminder failures
- projection lag
- sync job status
- document generation failures
- AI service errors if enabled

---

## 16. Graceful degradation

If:
- search fails -> fallback lookup mode
- AI fails -> raw owner projections still available
- Sheets sync fails -> core truth unaffected
- document export fails -> structured data still exists
- care-commerce fails -> booking and clinical core survive

This separation is intentional.
Core truth must be the hardest thing to lose.

---

## 17. Summary

DentFlow infrastructure is built around:

- one clinic per deployment;
- optional branches;
- Postgres as truth;
- search as projection;
- workers for async execution;
- object storage for files;
- export generation from structured facts;
- Sheets and external systems as controlled adapters;
- AI as scoped assistance;
- observable and degradable operations.

That is how the system remains operationally sane.
