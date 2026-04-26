# STACK-13 convergence audit — integration readiness after PAT / ADM / DOC scenario closure (2026-04-22)

## 1. Executive verdict

- **Ready to enter Stack 13 implementation now?** **Yes**.
- **Is Stack 13 mostly implemented already?** **Partial (backend-heavy foundations are already implemented)**.
- **Is a PR stack still needed?** **Yes (bounded, operational convergence PRs)**.

DentFlow already contains substantial Stack-13 groundwork in code reality: one-way Google Calendar projection service + projector wiring + DB mapping persistence; care-catalog XLSX/Google Sheets sync with parser/validation and atomic DB apply path; worker mode topology (`projector` / `reminder` / `all`) and runtime dispatch; and staff-side generated-document generation/open/download flows. What remains is not foundation rebuild, but operational convergence: first-class admin/operator surfaces for calendar awareness and catalog sync execution/visibility, plus bounded sync-job observability/retry ergonomics. Claims that workers/projector are “not integrated” are stale against current code.

---

## 2. Stack 13 truth matrix

| Area | Status | Confidence | Evidence | Needed next action |
|---|---|---|---|---|
| Google Calendar projection backend | **Implemented** | high | `app/application/integration/google_calendar_projection.py`; `app/infrastructure/db/google_calendar_projection_repository.py`; AW5/AW5A/AW6 reports | Do **not** rebuild projection model; keep one-way truth boundary |
| Google Calendar real gateway | **Implemented** | high | `app/integrations/google_calendar.py` (`RealGoogleCalendarGateway`, factory with misconfig handling); AW5A report | Keep as adapter baseline; only incremental observability hardening |
| Google Calendar worker/runtime | **Implemented** | high | `app/projections/runtime/registry.py` registers integration projector; `app/worker.py` mode dispatch; `app/projector_worker.py`; `scripts/process_outbox_events.py` | Do **not** re-architect worker topology |
| Admin calendar mirror awareness | **Partial** | high | `docs/71` keeps ADM-009 Partial; admin router has no calendar command/panel path | Add bounded read-only admin calendar awareness surface |
| Google Sheets / care catalog sync backend | **Implemented** | high | `app/application/care_catalog_sync/*`; `scripts/sync_care_catalog.py`; `DbCareCommerceRepository.apply_catalog_sync_transaction(...)`; CC2/CC2A reports | Do **not** rebuild parser/import foundations |
| Operator/admin sync trigger surface | **Missing** | high | No admin/doctor sync commands in bot routers; sync currently script/service driven | Add minimal admin/operator command surface to trigger XLSX/Sheets sync |
| Sync result/status visibility | **Partial** | medium-high | Sync returns structured result object and script output, but no in-app run history/status panel | Add bounded run result card/history (lightweight) |
| External adapter readiness | **Partial** | medium | Clear adapter boundaries exist (calendar gateway, integration config, service protocols), but no generalized adapter ops/status layer | Keep bounded: add explicit job/result/reporting seams, not platform rewrite |
| Generated document delivery | **Implemented (staff baseline)** | high | admin/doctor `*_doc_generate/open/download/regenerate`; export services + document/media repositories; 12B2 report | No Stack-13 rebuild; maintain staff baseline |
| Contextual admin/doctor docs surfaces | **Implemented (bounded)** | high | `app/interfaces/bots/admin/router.py`, `app/interfaces/bots/doctor/router.py`, `docs/71` ADM-DOC/DOC-DOC scenarios | Optional UX polish only; not Stack-13 blocker |
| Worker topology/runtime | **Implemented** | high | `app/worker.py` mode dispatch incl `all`; `ProjectorWorkerRuntime`; reminder runtime + health inspector; worker tests and 12B3 | Reject stale “worker not integrated” findings |
| Docs truth alignment | **Partial** | medium-high | `docs/71` already improved vs older audits, but Stack-13 backend-vs-surface split still needs explicit convergence statement | Tiny docs truth sweep after Stack-13 PRs |

---

## 3. Already implemented — do not rebuild

1. **Google Calendar projection foundation is already real and persisted**: booking-event handling, payload hashing/idempotence, mapping persistence, failure states/retry candidates, cancel handling. (Code + AW5/AW5A/AW6 reports)
2. **Real Google Calendar adapter path exists** with explicit disabled/misconfigured/real gateway factory behavior.
3. **Projector runtime is integrated into worker runtime**, including default projector registry with Google Calendar projector, plus `WORKER_MODE=projector|reminder|all` dispatch.
4. **Care-catalog sync foundation exists**: XLSX reader, workbook parser/validation, Google Sheets export-download sync path, structured result model.
5. **Atomic catalog apply exists** via transactional `apply_catalog_sync_transaction` in DB repository.
6. **Generated document baseline for staff exists** (admin/doctor generation, registry/open, Telegram file download where provider supports local file), with document/media registries in DB.
7. **Admin/doctor contextual linked recommendation/care-order panels are already converged enough** for bounded operational continuity (post 12B series).

**Conclusion:** Stack-13 should not re-open core projection architecture, worker architecture, or catalog-import architecture.

---

## 4. Real Stack 13 gaps

### Gap G1 — No first-class admin calendar awareness surface
- **Severity:** major
- **Evidence:** ADM-009 remains Partial in `docs/71`; admin router lacks dedicated calendar awareness command/panel.
- **Why it matters:** backend mirror value is operationally under-exposed; admins cannot easily anchor calendar awareness back into DentFlow action surface.
- **Fix timing:** **Stack 13**.

### Gap G2 — Catalog sync is backend/script-capable but not operator-usable in bot UX
- **Severity:** blocker (for practical Stack-13 closure)
- **Evidence:** sync service and script exist; no admin/operator command path to run/inspect sync from operational surface.
- **Why it matters:** controlled master-data sync exists technically but is not first-class for day-to-day operators.
- **Fix timing:** **Stack 13**.

### Gap G3 — Sync run visibility/retry ergonomics are thin
- **Severity:** major
- **Evidence:** calendar has mapping statuses + retry script; catalog sync returns rich result but lacks persisted/operator-visible run status panel.
- **Why it matters:** explicit sync jobs should be controllable and observable (success/failure/retry boundaries) without shell-only operations.
- **Fix timing:** **Stack 13** (bounded observability, not full platform).

### Gap G4 — Adapter readiness is present but operational contract is under-documented at runbook level
- **Severity:** medium
- **Evidence:** adapter boundaries are in code/docs, but there is no compact unified “integration operations truth” in bot/admin surface.
- **Why it matters:** pilot operations need clear retry/replay boundaries and known failure semantics.
- **Fix timing:** **Stack 13** (small doc + surface alignment), avoid framework rewrite.

### Gap G5 — Docs truth needs a tiny post-implementation sweep
- **Severity:** minor
- **Evidence:** scenario docs are mostly aligned, but Stack-13 convergence state (implemented backend vs missing operational surfaces) is not yet consolidated in one definitive doc.
- **Why it matters:** prevents stale planning loops and rebuild proposals.
- **Fix timing:** **Stack 13 tail or immediate post-Stack-13**.

---

## 5. Recommended Stack 13 PR stack

### S13-A — Admin calendar awareness surface (read-only, projection-backed)
- **Objective:** expose operational value of existing calendar projection without changing truth boundaries.
- **Exact scope:**
  - add bounded admin command/panel for calendar mirror awareness (read-only summary + guidance back to DentFlow booking actions),
  - optionally show recent projection sync state snippets from existing mapping data.
- **Non-goals:**
  - no two-way calendar editing,
  - no booking mutation from calendar,
  - no calendar subsystem redesign.
- **Files likely touched:**
  - `app/interfaces/bots/admin/router.py`
  - optional helper in `app/application/integration/*` or read method in `app/infrastructure/db/google_calendar_projection_repository.py`
  - locales for admin calendar labels/messages.
- **Tests likely touched/added:**
  - targeted admin router tests (calendar command/panel authorization/rendering)
  - bounded integration-read tests if new read query added.
- **Migrations needed?** **No**.
- **Acceptance criteria:**
  - admin can open a clear calendar-awareness panel from bot,
  - panel keeps one-way mirror semantics explicit,
  - no impact on booking truth behavior.

### S13-B — Operator catalog sync command surface + deterministic result reporting
- **Objective:** make existing catalog sync practically usable by operators/admins.
- **Exact scope:**
  - add admin/operator command(s) to trigger sync from XLSX path or Google Sheet URL/ID,
  - render structured result summary (tabs, counts, warnings/errors/fatal) in localized bounded format,
  - preserve existing parser/atomic apply behavior.
- **Non-goals:**
  - no replacement of sync engine,
  - no “Sheets as runtime truth” behavior,
  - no giant catalog CRUD UI.
- **Files likely touched:**
  - `app/interfaces/bots/admin/router.py` (primary)
  - maybe `app/bootstrap/runtime.py` wiring if sync service dependency is injected into router
  - optional thin formatter helper in `app/application/care_catalog_sync/*`.
- **Tests likely touched/added:**
  - admin router command tests for trigger/response formatting and guardrails,
  - focused service seam tests for command integration.
- **Migrations needed?** **No**.
- **Acceptance criteria:**
  - operator can trigger sync from bot surface,
  - operator receives deterministic status summary,
  - failed sync does not mutate unrelated runtime truths.

### S13-C — Explicit sync-job observability/retry boundary polish
- **Objective:** make sync jobs first-class enough for pilot operations without platform rewrite.
- **Exact scope:**
  - unify/report practical retry boundaries for calendar + catalog sync,
  - expose minimal status/result visibility (latest run/outcome and retry hint path),
  - align docs with implemented operational contract.
- **Non-goals:**
  - no generalized job orchestrator platform,
  - no broad adapter framework rewrite,
  - no deep worker re-architecture.
- **Files likely touched:**
  - `scripts/retry_google_calendar_projection.py` (possibly minor output/contract polish)
  - `scripts/sync_care_catalog.py` (possibly summary contract polish)
  - admin router/reporting helper paths
  - docs truth files (`docs/71`, maybe `docs/80` small deltas only) after implementation.
- **Tests likely touched/added:**
  - targeted command/formatter tests,
  - focused script behavior tests if existing test style supports it.
- **Migrations needed?** **No** (unless team explicitly chooses persisted sync-run table; this audit recommends avoiding it in Stack 13).
- **Acceptance criteria:**
  - staff can tell if last sync attempt succeeded/failed,
  - retry entrypoints are explicit and bounded,
  - no ambiguity about source-of-truth boundaries.

---

## 6. What should be deferred

1. Owner AI summaries and broader owner intelligence expansion (Stack 14/owner layer).
2. Patient-facing document delivery program (policy/UX/security decision still needed; staff baseline already exists).
3. Broad notification framework rewrite.
4. Broad adapter platform rewrite / generalized connector framework.
5. Full test-suite reorganization.
6. Full async queueing redesign of document generation pipeline (current sync command path is acceptable for bounded staff baseline).

---

## 7. Next phase recommendation

After bounded Stack-13 convergence, proceed to **Stack 14 (owner layer)** if pilot operations are stable. If operator readiness still shows instability (especially around sync operational handling), run a short **pilot hardening** slice first focused on runbooks and observability, then move to Stack 14.

---

## 8. Final recommendation

Start Stack-13 PRs immediately. **Begin with S13-B first** (catalog sync trigger/result surface), because it turns an already-implemented backend into real operator capability and closes the largest practical convergence gap fastest; then do S13-A (calendar awareness), then S13-C (explicit sync-job observability polish + docs truth sweep). Do **not** start with adapter-platform redesigns, worker rewrites, or patient-facing document expansion.
