# DentFlow Infrastructure & Integrations

> Runtime topology, storage model, integration surfaces, deployment policy, and operational foundations for DentFlow.

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
- branch owner views;
- branch-aware admin and doctor day semantics.

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
- recommendation
- care commerce
- media/docs
- integration

## 5.2 Derived surfaces
- search indices
- analytics projections
- owner views
- generated documents
- Sheets-driven master-data replicas
- Google Calendar schedule projection
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
- patient lookup;
- doctor lookup;
- service lookup;
- voice-assisted retrieval;
- transliteration and fuzzy behavior.

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
- product media

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
- care catalog authoring
- controlled sync

Forbidden use:
- secret canonical truth for bookings or patients
- live order/reservation truth
- schedule truth

Each Sheets flow must define:
- direction
- scope
- ownership
- cadence
- conflict behavior
- failure visibility

### Explicit source-of-truth rule
For care-commerce:
- Sheets/XLSX = master-data authoring truth for products, i18n, recommendation links, branch availability baseline
- DentFlow DB = runtime truth for care orders, reservations, issue/fulfill, active reserved quantity

That boundary must remain explicit.

### Care Catalog Google Sheets sync (operator runbook baseline)
- Template pack:
  - `docs/templates/google_sheets/care_catalog/`
- Required tab names for import compatibility:
  - `products`, `product_i18n`, `branch_availability`, `recommendation_sets`, `recommendation_set_items`, `recommendation_links`, `settings`
- Access expectations:
  - in current simple export mode, sheet must be shareable/exportable to the sync runner;
  - private OAuth/service-account hardening is a future task unless already configured in deployment.
- Operator/admin command:
  - `/admin_catalog_sync sheets <url_or_id>`
  - `/admin_catalog_sync xlsx <server_local_path>`
- CLI command:
  - `python scripts/sync_care_catalog.py --clinic-id clinic_main sheets --sheet <url_or_id>`
  - `python scripts/sync_care_catalog.py --clinic-id clinic_main xlsx --path <path>`
  - `python scripts/sync_care_catalog.py --clinic-id clinic_main json --path seeds/care_catalog_demo.json`

---

## 11. Google Calendar integration stance

Google Calendar is a **visual schedule projection**, not booking truth.

Good use:
- day/week/month view
- doctor load visualization
- branch load visualization
- schedule awareness for admin/reception

Forbidden use:
- becoming source of truth for bookings
- being used for bidirectional schedule edits in v1
- replacing DentFlow workdesk actions

### Explicit rule
- DentFlow = truth and actions
- Google Calendar = mirror / projection

The recommended baseline is:
- one-way DentFlow -> Google Calendar sync
- external mapping between booking and calendar event ids
- operator returns to DentFlow for real actions

### Current bounded operator surfaces (Stack 13 closure)
- `/admin_catalog_sync sheets <url_or_id>` and `/admin_catalog_sync xlsx <server_local_path>` provide bounded catalog import execution.
- `/admin_calendar` provides bounded read-only mirror awareness.
- `/admin_integrations` provides a compact integration control index for these operator surfaces and truth boundaries.

Non-goals remain explicit:
- no Calendar-as-truth,
- no Calendar-to-DentFlow sync path,
- no Sheets/XLSX runtime order/booking truth,
- no generic observability platform.

---

## 12. External adapters stance

DentFlow may later integrate with systems such as 1C-like software.

This must happen through:
- explicit adapter layer
- external id maps
- sync jobs
- structured payloads

DentFlow should be adapter-ready.
It should not become a clone of every external system it might ever meet.

---

## 13. AI infrastructure stance

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

## 14. Configuration boundaries

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

## 15. Seed/bootstrap infrastructure

Before Sheets sync exists, DentFlow must support:
- script-based seed imports
- reference-data loading
- fake patient/demo booking fixtures
- projection rebuilds
- demo media/doc references
- care catalog workbook import examples

Bootstrap is not optional.
Without realistic seeded data, many subsystems will look “fine” only because reality never touched them.

---

## 16. Observability basics

DentFlow must at minimum provide visibility for:
- bot uptime
- DB health
- search health
- worker failures
- reminder failures
- projection lag
- sync job status
- document generation failures
- calendar projection failures
- AI service errors if enabled

---

## 17. Graceful degradation

If:
- search fails -> fallback lookup mode
- AI fails -> raw owner projections still available
- Sheets sync fails -> core truth unaffected
- Google Calendar sync fails -> booking truth and workdesk still operate
- document export fails -> structured data still exists
- care-commerce sync/input fails -> existing runtime orders/reservations still survive

This separation is intentional.
Core truth must be the hardest thing to lose.

---

## 18. Summary

DentFlow infrastructure is built around:

- one clinic per deployment;
- optional branches;
- Postgres as truth;
- search as projection;
- workers for async execution;
- object storage for files;
- export generation from structured facts;
- Sheets as controlled master-data authoring;
- Google Calendar as schedule mirror;
- external systems as controlled adapters;
- AI as scoped assistance;
- observable and degradable operations.

That is how the system remains operationally sane.
