# DentFlow Repository Structure and Code Map

> Canonical repository layout and code-boundary guide for DentFlow.

## 1. Purpose

This document defines how the DentFlow repository should be structured so that implementation stays aligned with the architecture.

It exists to prevent:
- random folder growth;
- handler-centric business logic;
- duplicated callbacks and UI fragments;
- translation/resource chaos;
- hidden domain ownership.

---

## 2. Repository goals

The repo must make these things obvious:

- where Telegram interfaces live;
- where domain logic lives;
- where application workflows live;
- where persistence code lives;
- where projections live;
- where fixtures and imports live;
- where translation resources live;
- where docs map to code.

---

## 3. Recommended top-level shape

```text
DentFlow/
  README.md
  SYNC_NOTES.md
  docs/
  booking_docs/

  app/
    bootstrap/
    config/
    common/
    interfaces/
    application/
    domain/
    infrastructure/
    projections/
    integrations/
    ai/

  migrations/
  seeds/
  scripts/
  tests/
  locales/
```

---

## 4. Directory responsibilities

## 4.1 `app/bootstrap/`
Startup wiring only.

Examples:
- app initialization
- dependency graph wiring
- runtime entry registration

No domain logic here.

## 4.2 `app/config/`
Typed config loaders and config schemas.

Examples:
- environment loading
- grouped config objects
- feature flags
- provider settings

This folder is configuration plumbing, not a policy database substitute.

## 4.3 `app/common/`
Truly shared low-level building blocks only.

Examples:
- base types
- shared errors
- time helpers
- id helpers
- pagination primitives

Do not hide domain logic here under the excuse that “everything uses it.”

## 4.4 `app/interfaces/`
All interface-layer code.

Suggested split:
```text
app/interfaces/
  bots/
    patient/
    admin/
    doctor/
    owner/
  callbacks/
  renderers/
  input_parsers/
```

These layers translate Telegram actions into application commands/queries.

They must stay thin.

## 4.5 `app/application/`
Use cases and orchestration.

Suggested split:
```text
app/application/
  booking/
  patient/
  communication/
  search/
  clinical/
  recommendation/
  care_commerce/
  owner/
  export/
  integration/
```

This layer coordinates domain services, repositories, policies and events.

## 4.6 `app/domain/`
Canonical domain logic by bounded context.

Suggested split:
```text
app/domain/
  clinic_reference/
  access_identity/
  policy_config/
  patient_registry/
  booking/
  communication/
  search/
  clinical/
  recommendations/
  care_commerce/
  media_docs/
  analytics/
  owner_insights/
  integrations/
```

Use this layer for:
- entities
- aggregates
- value objects
- domain services
- invariants
- lifecycle transitions

## 4.7 `app/infrastructure/`
Concrete adapters and persistence concerns.

Suggested split:
```text
app/infrastructure/
  db/
  search/
  cache/
  storage/
  workers/
  outbox/
  telemetry/
```

## 4.8 `app/projections/`
Projection builders and read-model refresh logic.

Suggested split:
```text
app/projections/
  search/
  analytics/
  owner/
  export/
```

## 4.9 `app/integrations/`
Explicit adapters only.

Examples:
- Google Sheets
- external clinic systems
- messaging providers
- AI providers if implemented as adapters here

## 4.10 `app/ai/`
Optional AI orchestration layer.

Use this for:
- grounding preparation
- prompt assembly
- response validation
- AI-specific policy checks

Do not spread direct AI calls across handlers.

---

## 5. Suggested code ownership map

| Concern | Code home |
|---|---|
| PatientBot handlers | `app/interfaces/bots/patient/` |
| AdminBot handlers | `app/interfaces/bots/admin/` |
| Doctor UI handlers | `app/interfaces/bots/doctor/` |
| Owner UI handlers | `app/interfaces/bots/owner/` |
| Booking workflows | `app/application/booking/` |
| Booking aggregate rules | `app/domain/booking/` |
| Reminder scheduling | `app/application/communication/` + `app/domain/communication/` |
| Patient identity logic | `app/domain/patient_registry/` |
| Search ranking and normalization | `app/domain/search/` + `app/projections/search/` |
| Owner metrics logic | `app/projections/analytics/` + `app/projections/owner/` |
| Export rendering orchestration | `app/application/export/` + `app/infrastructure/storage/` |
| Integration sync jobs | `app/integrations/` + `app/infrastructure/workers/` |

---

## 6. Callback and action naming

Telegram callback naming must stay consistent.

Recommended pattern:

```text
<context>:<surface>:<action>
```

Examples:
- `booking:patient:start`
- `booking:patient:select_slot`
- `booking:admin:confirm`
- `booking:admin:mark_checked_in`
- `owner:dashboard:open_today`
- `care:patient:reserve_pickup`

### Rules
- no anonymous callbacks
- no handler-local random naming
- no mixed tense conventions
- no embedding whole JSON state in callback payloads if avoidable

---

## 7. Panel and renderer structure

Panel rendering should be centralized enough to prevent duplicate formatting styles.

Suggested shape:
```text
app/interfaces/renderers/
  patient/
  admin/
  doctor/
  owner/
  shared/
```

Renderers should:
- render one panel well;
- receive view-models, not raw ORM clutter;
- keep localization and panel structure consistent.

---

## 8. Localization resources

Translations should live in:

```text
locales/
  ru/
  en/
  ka/   # later
  pl/   # later
```

Suggested split:
```text
locales/ru/
  common.json
  patient.json
  admin.json
  doctor.json
  owner.json
  errors.json
```

No hardcoded user-visible strings in handlers.

---

## 9. Seeds and fixtures structure

Recommended structure:

```text
seeds/
  reference/
  demo/
  clinics/
  patients/
  bookings/
  clinical/
  care/
```

And:

```text
scripts/
  import_reference_data.py
  import_demo_patients.py
  import_demo_bookings.py
  rebuild_search_projections.py
  rebuild_owner_projections.py
```

Keep seed flows explicit and reproducible.

---

## 10. Tests structure

Recommended structure:

```text
tests/
  unit/
  integration/
  e2e/
  smoke/
  fixtures/
```

Suggested split by domain:
```text
tests/unit/booking/
tests/unit/patient_registry/
tests/integration/communication/
tests/e2e/bots/
tests/smoke/
```

---

## 11. Repo rules for CODEX

CODEX must not:
- invent a second layout pattern inside one subsystem;
- place business logic in handlers;
- create translation files ad hoc in random places;
- create callback naming styles that conflict with the contract;
- mix domain objects and transport DTOs in the same folder because it was “faster.”

CODEX must align implementation folders with this code map unless an explicit architectural change is approved.

---

## 12. Summary

DentFlow repo structure must reflect the architecture:

- interfaces thin;
- application orchestrates;
- domain owns truth;
- infrastructure adapts;
- projections derive;
- integrations stay explicit;
- translations stay centralized;
- seeds and tests stay reproducible.

This is how the repo remains understandable after the code stops fitting in one person’s short-term memory.
