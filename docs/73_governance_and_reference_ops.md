# 73) Governance and reference operations

> Governance, registry, and master-data operating model for DentFlow.
>
> This document exists because operational scenarios and governance scenarios are not the same thing.
> A clinic may have a good booking flow and still have chaos around patients, staff, catalogs, access rights, and exported artifacts.

## 1. Purpose

This document defines the current and target operating model for:

- patient base visibility and control;
- doctor/staff registry visibility and change management;
- clinic references and role bindings;
- care catalog authoring via XLSX / Google Sheets;
- Google Calendar as a schedule mirror;
- generated document governance;
- owner and lead-doctor oversight questions.

This file should be read together with:

- `docs/71_role_scenarios_and_acceptance.md` for end-user and staff journeys;
- `docs/68_admin_reception_workdesk.md` for admin operational workdesk logic;
- `docs/69_google_calendar_schedule_projection.md` for calendar mirror rules;
- `docs/65_document_templates_and_043_mapping.md` for document/export intent;
- `docs/shop/62_care_catalog_workbook_spec.md` for care catalog authoring rules.

---

## 2. Core thesis

Three rules must remain explicit:

1. **DentFlow is source of truth for runtime operations.**
2. **Google Calendar is a visual mirror.**
3. **Google Sheets is a structured authoring surface for selected master data, not a second runtime.**

If those boundaries blur, the clinic ends up with:
- duplicate truths,
- stale spreadsheets,
- broken access control,
- and arguments about which screen is “the real one.”

That circus is not a product strategy.

---

## 3. Where truth lives

| Object family | Canonical truth | Allowed companion surface | What it is **not** |
|---|---|---|---|
| Bookings | DentFlow DB + booking state machine | Telegram patient/admin/doctor surfaces; Calendar mirror | not Google Calendar truth |
| Patients / patient base | DentFlow patient registry + search/read models | admin workdesk, patient card, future exports/snapshots | not a Google Sheet |
| Doctors / staff roster | DentFlow reference + access identity model | admin reference views, future governance views/exports | not Google Calendar truth, not ad hoc sheet truth |
| Branches / services / clinic references | DentFlow references | admin reference commands, future governance views | not a manual chat note |
| Care catalog | DentFlow runtime catalog after import/sync | XLSX / Google Sheets authoring workbook | not live order truth |
| Care orders / pickups | DentFlow DB | patient care surface, admin pickup workdesk | not Sheets |
| Reminders | DentFlow communication/reminder layer | patient/admin/owner visibility | not booking-state duplicate truth |
| Generated documents | DentFlow generated artifact registry | admin/doctor open/download; future patient delivery | not primary clinical truth |
| Schedule visualization | Google Calendar projection | visual awareness for admin/staff | not DentFlow replacement |

---

## 4. Authority and persona model

### 4.1 Current canonical role codes

Current runtime role codes are:
- `admin`
- `doctor`
- `owner`

There is **no separate canonical `lead_doctor` role code** in current runtime.

### 4.2 Recommended interpretation of “lead doctor”

The product should currently interpret “lead doctor” as a **composite actor/persona**, not as a magical separate bot species.

This means one real person may carry:
- doctor capabilities,
- owner-style visibility,
- and, if the business wants it later, selected governance capabilities.

### 4.3 Recommended v1 product stance

For the current phase:
- keep role surfaces logically separated;
- allow one person to hold multiple role assignments;
- do **not** invent a separate “chief doctor bot” until there is a real product reason.

Reason:
- the architecture already supports distinct role surfaces;
- a premature extra bot would multiply menus, confusion, and maintenance cost.

---

## 5. Scenario format used in this document

Each governance scenario contains:

- **Scenario ID**
- **Governed object / topic**
- **Primary actor(s)**
- **Purpose**
- **Current operating model**
- **Current implementation status**
- **Evidence**
- **Known gaps / comments**

Status meanings remain the same as in `docs/71_role_scenarios_and_acceptance.md`:
- Implemented
- Partial
- Missing
- Unknown

---

## 6. Governance and reference scenarios

### GOV-001 — Clinic references read surface
- **Governed object / topic:** clinic, branches, doctors, services references.
- **Primary actor(s):** Admin.
- **Purpose:** let staff inspect the current clinic reference model from Telegram.
- **Current operating model:** read-only reference access through admin commands.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/admin/router.py` (`/clinic`, `/branches`, `/doctors`, `/services`); `app/application/clinic_reference/*`.
- **Known gaps / comments:** this is a read surface, not yet a mutation surface.

### GOV-002 — Patient base operational registry
- **Governed object / topic:** patient base / clinic client registry.
- **Primary actor(s):** Admin.
- **Purpose:** search, open, and act on patients as operational objects.
- **Current operating model:** patient base is kept in DentFlow; admin opens it via search and workdesk views.
- **Current implementation status:** **Implemented (bounded visibility)** for admin operational use plus owner read-only snapshot (`/owner_patients`); **Partial** as a broader governance/reporting + mutation surface.
- **Evidence:** `app/interfaces/bots/admin/router.py` (`/admin_patients`, `/search_patient` and patient card/open flows); search/read-model docs and reports.
- **Known gaps / comments:**
  - owner/chief-doctor-wide registry oversight is now available only as bounded read-only snapshot (`/owner_patients`), not as a full governance console;
  - patient-base export/report snapshots may still be useful as a separate artifact, but they must remain snapshots, not truth.

### GOV-003 — Doctor / staff roster read surface
- **Governed object / topic:** doctor/staff roster.
- **Primary actor(s):** Admin, Owner (future), composite lead-doctor persona (future).
- **Purpose:** inspect who is active in the clinic and what references currently exist.
- **Current operating model:** admin can inspect doctors through clinic reference views; owner has a bounded read-only `/owner_staff` access snapshot.
- **Current implementation status:** **Implemented (bounded read-only visibility)** via admin reference reads and owner `/owner_staff`; **Partial** as a broader management surface.
- **Evidence:** `app/interfaces/bots/admin/router.py` (`/doctors`); `app/interfaces/bots/owner/router.py` (`/owner_staff`); clinic reference docs.
- **Known gaps / comments:**
  - there is still no dedicated mutation/offboarding workflow;
  - owner-facing roster is visibility-only (no lifecycle actions).

### GOV-004 — Staff lifecycle mutation and offboarding
- **Governed object / topic:** add doctor, deactivate doctor, offboard staff, rebind roles/access when someone leaves.
- **Primary actor(s):** Owner, future governance-capable admin, possibly composite lead-doctor persona by business policy.
- **Purpose:** prevent “doctor left the clinic but still exists everywhere” chaos.
- **Current operating model:** not exposed as a first-class Telegram governance surface.
- **Current implementation status:** **Missing**.
- **Evidence:** role/reference reads exist, but no dedicated mutation/offboarding workflow is exposed in current runtime docs or routers.
- **Known gaps / comments:** this is one of the most important governance holes if the clinic grows beyond a demo environment.

### GOV-005 — Role binding and composite-role policy
- **Governed object / topic:** one actor with multiple role assignments; chief-doctor authority model.
- **Primary actor(s):** Owner, system designer, future governance operator.
- **Purpose:** define whether one person is owner + doctor, admin + doctor, or gets a separate pseudo-role surface.
- **Current operating model:** runtime already supports distinct role codes, but the business policy for composite actors is only partially formalized.
- **Current implementation status:** **Partial**.
- **Evidence:** `app/domain/access_identity/models.py` (`admin`, `doctor`, `owner` only); role-specific routers; docs 70/71.
- **Known gaps / comments:** product should freeze one policy soon:
  - either a person receives multiple existing role assignments,
  - or a dedicated governance surface is introduced later.

### GOV-006 — Care catalog authoring via XLSX / Google Sheets
- **Governed object / topic:** care products, recommendation bundles/links, branch availability baseline.
- **Primary actor(s):** Catalog operator, Admin, Owner.
- **Purpose:** maintain care commerce master data without turning Telegram into an Excel punishment chamber.
- **Current operating model:** workbook/XLSX/Sheets authoring is the intended model; DentFlow DB becomes runtime truth after import/sync.
- **Current implementation status:** **Implemented (bounded operator surface)**.
- **Evidence:** `docs/shop/62_care_catalog_workbook_spec.md`; `app/application/care_catalog_sync/*`; `scripts/sync_care_catalog.py`; `app/interfaces/bots/admin/router.py` (`/admin_catalog_sync`, `/admin_integrations`).
- **Known gaps / comments:** bounded command surface is intentionally used; this is not a generic sync platform or persistent run-history dashboard.

### GOV-007 — Calendar mirror governance
- **Governed object / topic:** Google Calendar schedule mirror.
- **Primary actor(s):** Admin, Owner, composite lead-doctor persona.
- **Purpose:** provide visual time-space awareness without introducing a second scheduling truth.
- **Current operating model:** one-way DentFlow -> Calendar projection.
- **Current implementation status:** **Implemented (bounded mirror awareness)**.
- **Evidence:** `docs/69_google_calendar_schedule_projection.md`; `app/application/integration/google_calendar_projection.py`; `app/interfaces/bots/admin/router.py` (`/admin_calendar`, `/admin_integrations`); projector worker/runtime docs.
- **Known gaps / comments:** awareness remains intentionally read-only and does not imply calendar-origin edits into DentFlow.

### GOV-008 — Generated document governance baseline
- **Governed object / topic:** generated artifacts, export registry, staff access to exports.
- **Primary actor(s):** Admin, Doctor.
- **Purpose:** generate, open, and deliver artifacts without making documents the source of truth.
- **Current operating model:** documents are generated from structured runtime facts and stored as artifacts in the generated-document registry.
- **Current implementation status:** **Implemented**.
- **Evidence:** `docs/65_document_templates_and_043_mapping.md`; `app/application/export/*`; admin/doctor doc commands; PR 12A and 12B reports.
- **Known gaps / comments:** this is a useful baseline, but not yet a complete “document program” with all future families and patient delivery.

### GOV-009 — Patient-facing document delivery
- **Governed object / topic:** aftercare/recommendation/export artifacts delivered directly to the patient.
- **Primary actor(s):** Patient, Admin, Doctor.
- **Purpose:** decide whether generated artifacts become a formal patient-facing communication channel.
- **Current operating model:** staff-side only.
- **Current implementation status:** **Missing**.
- **Evidence:** admin/doctor artifact delivery exists after 12B-2; no patient-facing document delivery surface is evidenced.
- **Known gaps / comments:** product decision required before implementation: direct artifact send, secure link, or curated patient document panel.

### GOV-010 — Owner / chief-doctor governance console
- **Governed object / topic:** clinic-wide registries, staffing, sync health, and governance controls.
- **Primary actor(s):** Owner; potentially composite lead-doctor persona if business wants delegated governance.
- **Purpose:** provide one place for governance questions that are not the same as daily admin workdesk actions.
- **Current operating model:** owner surface currently focuses on digest/snapshot/alerts plus bounded read-only governance snapshots for staff/access (`/owner_staff`), patient base (`/owner_patients`), and clinic references (`/owner_references`).
- **Current implementation status:** **Partial**.
- **Evidence:** `app/interfaces/bots/owner/router.py`; `docs/50_analytics_and_owner_metrics.md`; docs 70/71.
- **Known gaps / comments:**
  - owner today remains oversight-first, not governance-console-first;
  - current owner governance is intentionally read-only and bounded;
  - mutation/offboarding controls remain deferred.

---

## 7. Recommended operating model for the current product phase

### 7.1 Patients

**Recommended rule:**
- keep patient base in DentFlow;
- use admin search/workdesk/patient-card surfaces for day-to-day operations;
- if leadership wants a “table of clients,” generate a registry view or export snapshot from DentFlow.

**Do not do this:**
- maintain the patient base as a Google Sheet.

Reason:
- bookings, reminders, recommendations, and care links all depend on patient truth staying inside DentFlow.

### 7.2 Doctors / staff

**Recommended rule:**
- keep doctor/staff registry and access bindings in DentFlow/access identity model;
- use read-only reference views today;
- later add explicit staff lifecycle management if the clinic needs real hiring/offboarding control inside the product.

**Do not do this:**
- treat Google Calendar or a loose sheet as the authoritative roster.

If leadership wants a “doctor table,” that is legitimate as:
- a read model,
- an export snapshot,
- or a future governance panel.

But it should not become the true runtime source.

### 7.3 Care catalog and products

**Recommended rule:**
- keep care catalog authoring in XLSX / Google Sheets,
- sync into DentFlow,
- then treat DentFlow as runtime truth for availability, reservation, and order lifecycle.

This is exactly the place where Sheets are useful.

### 7.4 Calendar

**Recommended rule:**
- let Calendar show time and load;
- let DentFlow own actions and truth.

Calendar is for eyes.
DentFlow is for hands.
Still true. Reality remains stubborn.

### 7.5 Generated documents

**Recommended rule:**
- keep generation, registry, and artifact delivery inside DentFlow;
- allow exports and snapshots;
- do not let generated documents become the primary clinical truth.

### 7.6 Lead doctor / chief-doctor policy

**Recommended rule for now:**
- treat lead doctor as a composite person with multiple role assignments;
- do not create a separate special bot unless product complexity clearly justifies it.

---

## 8. Operational tables vs source of truth

Leadership may legitimately want “tables” or registry-style views for control.
That is fine.

The important distinction is:

### Valid table use
- patient registry snapshot/report;
- doctor/staff roster snapshot/report;
- care catalog authoring workbook;
- generated document registry;
- owner/admin oversight views.

### Invalid table use
- using a sheet as the live source of booking truth;
- using Calendar as the source of who is booked;
- using an export as the source of patient identity or clinical status.

In short:
- **table/report/export = visibility artifact**
- **DentFlow DB and state machine = truth**

---

## 9. Decisions that should be frozen before the next governance-heavy wave

The following decisions still need explicit product freezing:

1. **Chief doctor authority model**
   - owner + doctor assignment,
   - doctor + selected governance capabilities,
   - or later dedicated governance surface.

2. **Who can mutate staff roster**
   - owner only,
   - owner + selected admin,
   - owner + delegated lead doctor.

3. **Whether owner gets direct patient-base visibility**
   - full registry,
   - only analytics and exceptions,
   - or export/report only.

4. **Whether patient/staff registry exports are needed now**
   - Telegram views only,
   - generated export snapshots,
   - or both.

5. **Whether patient-facing document delivery is next-phase scope**
   - secure link,
   - Telegram attachment,
   - or later.

6. **Whether Sheets operator UI is needed now**
   - script/service only,
   - or explicit bot/operator sync commands with status/history.

---

## 10. Governance coverage snapshot

| Scenario ID | Topic | Status | Primary evidence | Next action |
|---|---|---|---|---|
| GOV-001 | Clinic references read | Implemented | admin router reference commands | keep as read baseline |
| GOV-002 | Patient base operational registry | Implemented / Partial | admin patient/search surfaces | decide whether owner/export registry view is needed |
| GOV-003 | Staff roster read surface | Implemented / Partial | `/doctors` reference view + `/owner_staff` snapshot | add true staff registry only if needed |
| GOV-004 | Staff lifecycle mutation / offboarding | Missing | no dedicated runtime governance surface | design staff governance flow |
| GOV-005 | Composite-role policy / chief doctor model | Partial | role codes + current role routers | freeze policy before widening owner/governance scope |
| GOV-006 | Care catalog authoring via Sheets | Implemented (bounded) | workbook spec + sync services + `/admin_catalog_sync` + `/admin_integrations` | keep command surface compact; no generic sync dashboard |
| GOV-007 | Calendar mirror governance | Implemented (bounded) | projection docs/code + `/admin_calendar` + `/admin_integrations` | keep mirror read-only; no Calendar-to-DentFlow sync |
| GOV-008 | Generated document governance baseline | Implemented | export services + staff doc routes | expand families carefully, do not let docs become truth |
| GOV-009 | Patient-facing document delivery | Missing | staff-only artifact baseline | decide delivery model |
| GOV-010 | Owner / chief-doctor governance console | Partial | owner digest/snapshot/alerts + `/owner_staff` + `/owner_patients` + `/owner_references` | keep bounded read-only scope; defer mutation/editor surfaces |

---

## 11. Practical reading of the current product

If someone asks, “So what do we actually have now?” the honest answer is:

- booking, reminders, admin workdesk, doctor operational surface, owner baseline analytics, care-commerce baseline, and staff-side generated-document baseline are real;
- patient base and clinic references are visible operationally;
- care catalog authoring already has a credible Sheets/XLSX direction;
- Google Calendar projection already has a real backend;
- what is still not frozen is the governance layer around staff lifecycle, owner/chief-doctor authority, patient-facing documents, and operator-facing sync/control surfaces.

That is not a flaw in the product.
It is simply the point in maturation where operations exist before governance is fully formalized.

This document exists so that nobody has to pretend otherwise.
