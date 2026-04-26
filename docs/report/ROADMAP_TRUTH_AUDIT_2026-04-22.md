# DentFlow roadmap truth audit — PR plan vs scenarios vs governance after PAT/ADM/DOC/Stack13 closure

Date: 2026-04-26 (audit of closure state as of 2026-04-22 reports + current runtime truth)

## 1. Executive verdict

- **Is the core DentFlow role-flow layer closed enough to move on?** **Yes (bounded).**
  - PAT scenarios are closed in bounded runtime scope.
  - ADM/DOC closure packs indicate closure of their bounded scenario scope, with remaining depth intentionally deferred.
  - Owner baseline (digest/today/alerts) exists but full owner analytics surface is not complete.
- **Is Stack 13 closed?** **Yes (bounded convergence closure).**
  - Calendar awareness (`/admin_calendar`), catalog sync operator commands (`/admin_catalog_sync`), and integration index (`/admin_integrations`) are present in runtime and reflected in Stack-13 PR/convergence reports.
- **Are there blockers before Owner layer?** **No hard blockers.**
  - Remaining gaps are mostly owner-depth/gov-console depth and pilot-hardening controls, not broken foundational role continuity.

**Recommended next phase:** **Owner layer (Option 1)** as the primary next bounded phase. The patient/admin/doctor operational continuity and Stack-13 integration operator surfaces are now sufficiently closed for progression; the most structurally missing planned scope is owner-side analytics breadth (doctor/service/branch/care-performance views and bounded drilldown surfaces) and owner-governance visibility. This yields the highest roadmap-truth alignment gain without reopening already-closed operational stacks.

---

## 2. PR plan reconciliation matrix

| Plan section / Stack | Intended outcome | Current status | Evidence | Next action |
|---|---|---|---|---|
| Stack 0-2 foundation/reference/patient registry | Runtime skeleton + access/policy/reference + canonical patient base | **Done** | Runtime bootstrap, access/clinic refs, patient registry/search surfaces, broad test suite coverage | Keep stable; no rework |
| Stack 3 booking core | Session/slot/hold/final booking lifecycle | **Done** | Patient/admin/doctor booking flows and orchestration services; PAT/ADM/DOC closure reports | Regression-only maintenance |
| Stack 4 reminder/communication | Reminder jobs, ack, failure visibility | **Done (bounded)** | Communication services + admin issues/confirmations + reminder worker topology docs and code | Keep bounded; pilot hardening later |
| Stack 5 search/voice | Patient/doctor/service search + voice retrieval | **Done (bounded)** | Search services/backends, voice mode/service, admin/doctor voice handlers and tests | Optional quality hardening only |
| Stack 6 role surfaces (admin/doctor) | Workdesk + doctor queue/operations | **Done (bounded closure)** | ADM-A* and DOC-A* closure reports + current routers include linked-open actionability | No reopen; only bugfixes |
| Stack 7 clinical baseline | Chart/encounter/diagnosis/plan/media baseline | **Partial but sufficient for current bounded scope** | Doctor chart/encounter routes and clinical services; DOC closure notes bounded depth | Defer deep EMR-style expansion |
| Stack 8 events/projections | Outbox + projectors + projection runtime | **Done** | Outbox/projector runner/registry and dedicated worker entrypoints | Keep stable |
| Stack 9 owner analytics baseline | Digest/today/alerts baseline | **Done (baseline only)** | Owner router exposes digest/today/alerts; owner projector exists | Extend in next phase (owner layer) |
| Stack 10 recommendations | Recommendation lifecycle and flows | **Done (bounded)** | Patient/doctor/admin recommendation flows + services + closure reports | Incremental UX only |
| Stack 11 care-commerce | Catalog + reserve/pickup + lifecycle | **Done (bounded)** | Care-commerce services, patient reserve/pickup continuity, admin pickup handling, CC + PAT-A8 reports | Governance/reporting depth can be next-later |
| Stack 12 document generation / 043 export | Generated docs + 043 export baseline | **Done (staff baseline), Partial (program depth)** | Export assembly/render/services + admin/doctor generate/open/download + 12B reports | Keep staff baseline; defer patient-facing doc delivery program |
| Stack 13 sheets/adapters/integration ops | Sync jobs, Sheets integration, calendar awareness, admin integration index | **Done (bounded convergence)** | S13-A1/A2/B/C reports; admin router has `/admin_calendar`, `/admin_catalog_sync`, `/admin_integrations`; docs/90 already marks completion | No redesign; only operational runbook polish if needed |
| Stack 14 owner AI-assisted layer | Grounded owner summaries/Q&A | **Missing** | No owner AI routes/surfaces in owner runtime; not present in closure packs | Candidate for later after owner core metrics panels |
| Stack 15 pilot hardening | smoke + fixtures + rollback confidence | **Partial** | Docs exist; targeted tests abundant, but no explicit full pilot-go/no-go hardening closure report | Secondary after owner layer or short hardening slice |

Docs truth update need from this matrix:
- Keep Stack 13 as closed bounded (already reflected).
- Add explicit bounded-not-full note for Stack 12 and Stack 9/owner scope in roadmap truth narrative to prevent over-claiming closure.

---

## 3. Scenario reconciliation matrix

| Scenario group | Status | Confidence | Remaining gaps | Next action |
|---|---|---|---|---|
| PAT | **Implemented (bounded closed)** | High | PAT-DOC patient-facing document delivery remains missing by design; richer preference modeling still deferred | Keep regression coverage; do not reopen PAT branch |
| ADM | **Implemented (bounded closed)** | Medium-high | Some governance-console depth and richer issue lifecycle observability can still improve, but core continuity is closed in A1/A2/A3 packs | Treat as closed baseline; only targeted defects |
| DOC | **Implemented (bounded closed)** | Medium-high | Deep clinical workplace remains intentionally out-of-scope; current doctor flow is operational, not full EMR | Treat as closed baseline; defer deep clinical expansion |
| OWNER | **Partial** | High | Owner has digest/today/alerts, but planned doctor/service/branch/care-performance surfaces are incomplete; no owner AI layer | **Primary next phase: owner layer** |

Docs/runtime alignment notes:
- PAT/ADM/DOC closure reports are generally aligned with current runtime.
- OWNER remains the most material planned-vs-runtime delta.

---

## 4. Governance/reference reconciliation matrix

| Governance area | Status | Evidence | Risk if deferred | Recommendation |
|---|---|---|---|---|
| Patient base governance | **Implemented for operations / Partial for governance reporting** | Admin patient search/open/workdesk is real; governance doc itself marks partial for broader oversight | Medium (leadership visibility gaps, not runtime breakage) | Add owner-facing registry oversight in owner wave |
| Doctor/staff roster visibility | **Implemented read-only / Partial management** | Clinic reference reads exist; no rich lifecycle/offboarding console | Major if clinic team churn increases | Add bounded roster oversight in owner/governance follow-up |
| Role/access bindings & composite roles | **Partial** | Canonical roles are admin/doctor/owner; composite policy mostly documented, not fully surfaced operationally | Medium | Freeze policy in owner/governance docs and add limited visibility UI later |
| Care catalog authoring via Sheets/XLSX | **Implemented (bounded)** | Sync service, parser, admin sync command, integration index all present | Low | Keep bounded; no generic sync platform rewrite |
| Google Calendar mirror governance | **Implemented (bounded)** | One-way projection service + admin awareness panel + integration index + docs guardrails | Low | Keep one-way mirror, avoid bidirectional scope creep |
| Generated document governance | **Implemented (staff baseline)** | Admin/doctor generate/open/download and generated document registry | Medium (if over-extended now) | Defer full document-program expansion |
| Patient-facing document governance | **Missing** | Explicitly called out missing in scenario/governance docs | Medium | Defer unless pilot requires it explicitly |
| Owner/lead-doctor oversight model | **Partial** | Owner has digest/today/alerts only; no broader governance console | Major for roadmap completion | Address in next owner layer |

---

## 5. Real remaining gaps

Only evidence-backed readiness gaps are listed.

1) **Owner analytics surface depth gap (planned vs runtime)**
- **Severity:** major
- **Evidence:** Owner router currently exposes digest/today/alerts/open-alert only; no dedicated doctor/service/branch/care-performance surface commands.
- **Why it matters:** This is the largest remaining roadmap truth mismatch after PAT/ADM/DOC/S13 closure.
- **Recommended timing:** **Next (primary phase).**

2) **Owner governance visibility gap (roster/patient-base oversight as owner-facing control)**
- **Severity:** major
- **Evidence:** Governance doc marks owner/chief-doctor governance console as partial; runtime has no dedicated owner governance commands.
- **Why it matters:** Pilot leadership oversight remains fragmented into admin operational surfaces.
- **Recommended timing:** Next (owner phase), bounded.

3) **Stack 12 breadth gap: patient-facing document delivery program not implemented**
- **Severity:** medium
- **Evidence:** Staff-side document flows implemented; patient-facing doc delivery marked missing in acceptance/governance docs.
- **Why it matters:** Not a blocker for moving phases, but important to keep explicitly out of “closed” claims.
- **Recommended timing:** Later bounded phase (only if pilot policy requires).

4) **Pilot hardening consolidation gap (single go/no-go package still partial)**
- **Severity:** medium
- **Evidence:** Strong targeted tests exist across modules; no explicit end-of-wave pilot hardening closure pack tying smoke/rollback/runbook into one bounded acceptance checkpoint.
- **Why it matters:** Launch confidence can be overstated without a consolidated gate.
- **Recommended timing:** After owner layer or as short follow-up.

5) **Staff lifecycle mutation/offboarding governance controls**
- **Severity:** medium
- **Evidence:** Governance scenario GOV-004 is missing; runtime has read/reference surfaces but no lifecycle mutation flow.
- **Why it matters:** Operational risk grows with real staffing changes.
- **Recommended timing:** Post-owner or owner-governance extension (bounded).

---

## 6. Safe-to-defer list

These are explicitly **not worth doing now** unless pilot-specific evidence forces them:

- Rich patient preference model beyond current quick-book heuristics.
- Broad test-file reorganization.
- Patient-facing document delivery channel program.
- Full worker liveness dashboard / generalized observability platform.
- Generic notification platform rewrite.
- Full Telegram calendar grid / two-way calendar editing.
- Generic adapter platform framework.
- Deep EMR-style chart workplace expansion beyond current bounded doctor scope.

---

## 7. Recommended next PR stack

Primary phase selected: **1) Owner layer**

### NEXT-A — Owner metrics surface completion (doctor/service/branch/care-performance bounded panels)
- **Objective:** Close core owner planned-vs-runtime analytics surface gap.
- **Exact scope:**
  - add bounded owner commands/panels for doctor metrics, service metrics, branch split, and care-performance summary;
  - reuse existing owner projection tables/services where possible;
  - keep compact Telegram cards and explicit date/window scope.
- **Non-goals:**
  - no BI platform;
  - no cross-clinic federation;
  - no owner AI yet.
- **Likely files touched:**
  - `app/interfaces/bots/owner/router.py`
  - `app/application/owner/service.py`
  - `app/projections/owner/*` (read-side only if needed)
  - `locales/en.json`, `locales/ru.json`
- **Tests likely touched/added:**
  - owner router scenario tests (new owner metrics commands)
  - owner projection/read-service tests
- **Migrations needed?** **No** (prefer existing projections first).
- **Acceptance criteria:**
  - owner can open doctor/service/branch/care-performance summaries in bot;
  - panels are localized/compact and aligned with source-of-truth constraints;
  - no regression in existing digest/today/alerts.

### NEXT-B — Owner governance visibility shell (read-only oversight)
- **Objective:** Provide bounded owner-level governance visibility without mutation complexity.
- **Exact scope:**
  - add owner read-only oversight surfaces for patient base snapshot and staff roster/access-binding snapshot;
  - include explicit “read-only governance” framing to avoid accidental mutation semantics.
- **Non-goals:**
  - no staff offboarding mutation workflows;
  - no role model redesign;
  - no admin workdesk rewrite.
- **Likely files touched:**
  - `app/interfaces/bots/owner/router.py`
  - `app/application/clinic_reference.py` and/or owner read service glue
  - optional read queries in infrastructure repos
- **Tests likely touched/added:**
  - owner oversight command tests + role guards
- **Migrations needed?** **No**.
- **Acceptance criteria:**
  - owner can inspect bounded governance snapshots from owner bot;
  - no mutation controls exposed;
  - docs remain aligned on composite-role policy.

### NEXT-C — Owner truth alignment + bounded launch-readiness checkpoint
- **Objective:** Lock docs/runtime truth for owner completion and establish minimal pilot gate before broader expansion.
- **Exact scope:**
  - update `docs/71`, `docs/73`, and (if needed) `docs/90` owner sections to reflect delivered owner surfaces;
  - add a small owner + integration sanity smoke bundle (targeted tests only);
  - write one bounded launch-readiness note focused on owner + integration operational confidence.
- **Non-goals:**
  - no full pilot program rewrite;
  - no new integration platform;
  - no broad QA overhaul.
- **Likely files touched:**
  - docs truth files + owner tests
- **Tests likely touched/added:**
  - focused owner command/metrics sanity tests
  - targeted integration truth checks already existing style
- **Migrations needed?** **No**.
- **Acceptance criteria:**
  - owner section status is no longer the major roadmap mismatch;
  - test evidence exists for newly added owner panels;
  - no over-claiming of full pilot completion.

---

## 8. Final recommendation

Proceed with a **bounded Owner layer stack next** (NEXT-A then NEXT-B then NEXT-C). Do **not** reopen PAT/ADM/DOC/Stack-13 foundations, and do **not** jump to broad rewrites or parallel mega-tracks. This sequence closes the largest remaining roadmap truth gap while preserving already-converged operational layers.
