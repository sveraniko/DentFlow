# CONVERGENCE PACK DELTA AUDIT — 2026-04-20 (Post PR 12A-5)

## 1) Executive verdict

- **Enough current information to begin convergence pack implementation?** **Yes.**
- **Should the team run another broad audit first?** **No.**

The codebase has enough verified current-state evidence to freeze a bounded convergence plan immediately. The correct path is to execute a narrow **12B convergence pack** focused on cross-role booking-linked opens and document delivery seams (without architecture redesign), then move to **13A visible integrations** (admin calendar mirror and operator-facing catalog sync surfaces) using already-integrated backend/projection services. The prior broad-audit uncertainty around projector runtime integration is now outdated and should not block execution.

---

## 2) Verified current truths

### 2.1 Truly present in current code

- **Projector worker runtime is integrated in main worker entrypoint and dedicated module.**
  - `WORKER_MODE=projector|reminder|all` dispatch is implemented in `app/worker.py`.
  - `run_projector_worker_forever()` wires `ProjectorWorkerRuntime` + default projector registry.
  - Dedicated entrypoint `app/projector_worker.py` calls projector runtime directly.
  - Verified by projector/worker tests including registry composition and worker mode dispatch.

- **Google Calendar projection backend exists as one-way booking mirror service with mapping persistence.**
  - Projection service handles booking events, visible-status filters, upsert/cancel logic, payload hash dedupe, and failure status persistence.
  - Repository implementation persists to `integration.google_calendar_booking_event_map` and resolves booking projection joins.
  - Tests cover create/update/cancel/failure-retry and locale-path handling.

- **12A document generation baseline exists on admin + doctor command surfaces.**
  - Admin: `admin_doc_generate`, `admin_doc_registry_patient`, `admin_doc_open`, `admin_doc_download`, `admin_doc_regenerate`.
  - Doctor: `doc_generate`, `doc_registry_booking`, `doc_open`, `doc_download`, `doc_regenerate`.
  - Export assembly/generation and template resolution seams are implemented in export application services.

- **Generated document registry + media asset registry seams exist and are used in bot routes.**
  - Registry lifecycle supports status transitions and retrieval/listing by patient/chart/booking.
  - Media asset registry resolves stored artifact references.

- **Care catalog sync service exists with XLSX import and Google Sheets download-to-XLSX flow.**
  - Service validates workbook and applies tab updates via repository contract, including transactional apply seam.
  - Google Sheets download helper exists; sync failures are surfaced in `CatalogImportResult`.

- **Admin and doctor booking linked opens for recommendation/care order are still incomplete.**
  - Admin callback path emits hardcoded placeholder text for recommendation/care order linked opens.
  - Doctor callback path renders minimal recommendation title and hardcoded care-order placeholder text.

- **Patient-facing document surface is absent in patient router.**
  - No patient document commands/callback paths are present.

- **Document open/download currently expose artifact references, not real file delivery.**
  - Admin/doctor download commands return `artifact_ref=asset.storage_ref` text output.

### 2.2 Outdated claims from prior reports (explicitly superseded by code)

- **Outdated claim:** projector runtime is not integrated into worker runtime and remains script-only/manual.
  - Found in `docs/report/FULL_PROJECT_STATE_AUDIT.md`.
  - **Current truth:** projector runtime is integrated and dispatchable via `WORKER_MODE` and dedicated entrypoint.

- **Outdated claim:** card runtime / callback codec are not integrated in real admin/doctor/patient routes.
  - Found in `docs/redis_audit_2026-04-19.md`.
  - **Current truth:** admin/doctor/patient routers actively decode `c2|...` callbacks and use runtime/card callback contracts.

- **Still current claim (not outdated):** admin calendar mirror UI surface is missing.
  - Prior audits flag this gap; current admin router still has no calendar command/panel path.

---

## 3) Current convergence gaps (matrix)

## Admin

| Gap | Classification | Evidence | Why it matters now | Pack |
|---|---|---|---|---|
| Booking linked open -> recommendation is placeholder text | **Major gap** | `app/interfaces/bots/admin/router.py` callback branch `open_recommendation` renders `"recommendation :: patient=..."` | Breaks linked-object card contract and i18n discipline on admin critical flow | **12B** |
| Booking linked open -> care order is placeholder text | **Major gap** | `app/interfaces/bots/admin/router.py` callback branch `open_care_order` renders `"care_order :: patient=..."` | Same cross-role convergence break as above | **12B** |
| No admin calendar mirror commands/panel | **Major gap** | No `calendar`/`google` paths in admin router | Integration backend exists but admin cannot operationally view mirrored schedule from bot surface | **13A** |

## Doctor

| Gap | Classification | Evidence | Why it matters now | Pack |
|---|---|---|---|---|
| Booking linked open -> recommendation is minimal title-only text | **Major gap** | `app/interfaces/bots/doctor/router.py` `open_recommendation` returns `recs[0].title` | Incomplete object/open semantics; weak clinical context continuity | **12B** |
| Booking linked open -> care order is placeholder text | **Major gap** | `app/interfaces/bots/doctor/router.py` `open_care_order` renders `"care_order :: patient=..."` | Prevents role parity with patient object surfaces | **12B** |

## Patient

| Gap | Classification | Evidence | Why it matters now | Pack |
|---|---|---|---|---|
| No patient-facing generated-document commands/surface | **Medium tail** | No document command/callback paths in `app/interfaces/bots/patient/router.py` | Product decision required (ship now vs after internal pilot hardening) | **13A** (decision-gated) |

## Document / export

| Gap | Classification | Evidence | Why it matters now | Pack |
|---|---|---|---|---|
| Download/open responses expose storage refs instead of file delivery flow | **Major gap** | Admin/doctor download handlers return `asset.storage_ref`; tests assert this behavior | Operationally brittle and user-visible; blocks credible “document download” UX | **12B** |
| Generation pipeline not worker-queued (synchronous command path) | **Medium tail** | `generate_043_export` called directly in bot command handlers | Acceptable short-term; not a blocker for 12B convergence if delivery seam is fixed | **13A** |

## Integrations

| Gap | Classification | Evidence | Why it matters now | Pack |
|---|---|---|---|---|
| Admin calendar mirror UI absent despite projection backend | **Major gap** | Calendar projection service/repo exist; no admin router calendar UI path | Prevents visible value of AW5/AW6 projection work in operations | **13A** |
| Care catalog sync has service/tests but no admin/operator command surface | **Major gap** | `app/application/care_catalog_sync/*` exists; no sync command paths in admin/doctor router | Integration is not operationally triggerable/observable by staff | **13A** |

## Worker / runtime

| Gap | Classification | Evidence | Why it matters now | Pack |
|---|---|---|---|---|
| One-shot worker bootstrap test still DB-coupled and failing in local env | **Medium tail** | `tests/test_worker.py::test_worker_bootstrap` fails due unmocked clinic repo DB load path | Test fragility can hide regressions in worker bootstrap seam and slows convergence confidence | **12B** |
| Projector runtime integration documentation drift in legacy reports | **Medium tail** | Full-state/redis audits contain stale claims contradicted by current code | Planning noise risk; can trigger wrong-next-step recommendations | **12B** (documentation convergence) |

---

## 4) Mandatory 12B scope

### 12B-1 — Admin/Doctor linked-open convergence for recommendation + care-order

- **Objective**
  - Replace placeholder/minimal linked-open branches in admin/doctor booking card callbacks with real bounded object panels consistent with current card runtime principles.

- **Exact scope**
  - Admin booking callback: implement real open panel for recommendation and care-order.
  - Doctor booking callback: same for recommendation and care-order.
  - Reuse existing recommendation/care-commerce services; no new domain redesign.
  - Enforce localized panel text (remove hardcoded debug placeholders).

- **Exact non-goals**
  - No redesign of card framework.
  - No new recommendation/care domain entities.
  - No broad admin/doctor UI rewrite.

- **Expected files likely touched**
  - `app/interfaces/bots/admin/router.py`
  - `app/interfaces/bots/doctor/router.py`
  - Possibly small adapter/view helper files under `app/interfaces/cards/*`.

- **Required tests to add/update**
  - Extend `tests/test_document_registry_ui_12a4a.py`-style router seam tests with callback paths for `open_recommendation` and `open_care_order` on both roles.
  - Add regression assertions for no raw placeholder text.

- **Migrations needed?** **No**

- **Acceptance criteria**
  - No user-facing `"recommendation :: patient="` or `"care_order :: patient="` outputs in admin/doctor callback flows.
  - Callback returns navigable panel + back behavior remains intact.
  - Added tests pass.

### 12B-2 — Document delivery seam hardening (open/download)

- **Objective**
  - Converge command-level “download/open” semantics from storage-ref exposure to bounded delivery abstraction.

- **Exact scope**
  - Add delivery seam/service for generated assets (e.g., signed URL/local file handoff abstraction, depending on storage provider).
  - Update admin/doctor `*_doc_open` and `*_doc_download` messaging to use delivery output instead of raw storage path.
  - Keep current registry/template/generation flow unchanged.

- **Exact non-goals**
  - No PDF/DOCX engine expansion.
  - No patient document surface yet.
  - No new storage backend rollout.

- **Expected files likely touched**
  - `app/interfaces/bots/admin/router.py`
  - `app/interfaces/bots/doctor/router.py`
  - `app/application/export/services.py` (or adjacent export seam modules)
  - New small delivery helper under `app/application/export/` if needed.

- **Required tests to add/update**
  - Update `tests/test_document_registry_ui_12a4a.py` assertions to verify delivery token/link abstraction instead of bare `storage_ref` echo.

- **Migrations needed?** **No**

- **Acceptance criteria**
  - Download/open commands no longer expose raw internal storage path by default.
  - Existing role guards/visibility checks remain unchanged.
  - Tests updated and passing.

### 12B-3 — Convergence guardrails + outdated-claim cleanup

- **Objective**
  - Remove planning ambiguity by codifying current truths and patching high-noise test/documentation drift.

- **Exact scope**
  - Add/update report/docs to mark projector-integration and card-runtime-integration claims as outdated where necessary.
  - Fix/adjust failing worker bootstrap test seam to avoid accidental real DB dependency in unit test.
  - Keep runtime behavior unchanged.

- **Exact non-goals**
  - No worker architecture redesign.
  - No new runtime modes or infra components.

- **Expected files likely touched**
  - `tests/test_worker.py`
  - One bounded report/doc note under `docs/report/` and/or worker doc notes.

- **Required tests to add/update**
  - `tests/test_worker.py` targeted unit run for bootstrap + mode dispatch.

- **Migrations needed?** **No**

- **Acceptance criteria**
  - Targeted worker test no longer requires live DB for unit path.
  - Convergence docs explicitly mark stale prior claims as outdated.

---

## 5) Recommended 13A follow-up stack

### 13A-1 — Admin calendar mirror (read-only, projection-backed)

- **Objective**
  - Expose visible operational value from existing Google Calendar projection backend in admin bot surface.

- **Exact scope**
  - Add read-only admin calendar mirror command/panel(s) based on projection/mapping data.
  - Show time/doctor/branch/status + DentFlow open action links.
  - Keep one-way DentFlow -> Calendar ownership model explicit.

- **Exact non-goals**
  - No bi-directional calendar edits.
  - No calendar-as-truth behavior.

- **Expected files likely touched**
  - `app/interfaces/bots/admin/router.py`
  - Possibly new read service in `app/application/integration/` and repository query extension.

- **Required tests to add/update**
  - Add router-level tests for admin calendar command/pagination/filter callbacks.

- **Migrations needed?** **No** (unless a missing read index is discovered; default plan assumes no)

- **Acceptance criteria**
  - Admin can view mirrored schedule data without mutating booking truth from calendar surface.

### 13A-2 — Care catalog sync operator surface

- **Objective**
  - Make existing care catalog sync service operationally usable and observable.

- **Exact scope**
  - Add bounded admin/operator command(s) to trigger XLSX/Google Sheets sync and receive summarized result stats.
  - Surface validation/fatal errors from `CatalogImportResult` in operator-safe format.

- **Exact non-goals**
  - No switch of runtime booking/care-order truth to Sheets.
  - No spreadsheet-driven live reservation truth.

- **Expected files likely touched**
  - `app/interfaces/bots/admin/router.py`
  - `app/application/care_catalog_sync/service.py` (minor interface shaping only)
  - possibly wiring/bootstrap modules.

- **Required tests to add/update**
  - New command-handler tests that assert success/failure summaries and role guards.

- **Migrations needed?** **No**

- **Acceptance criteria**
  - Operator can trigger sync and receives deterministic summary/errors in bot.

### 13A-3 — Patient document surface (decision-gated pilot slice)

- **Objective**
  - If approved by product decision, expose minimal patient-safe document access for generated artifacts.

- **Exact scope**
  - Add bounded patient command(s) for list/open/download of patient-owned generated documents with strict visibility controls.
  - Reuse 12B delivery seam.

- **Exact non-goals**
  - No e-signature/legal workflow expansion.
  - No new document families.

- **Expected files likely touched**
  - `app/interfaces/bots/patient/router.py`
  - export access/visibility helper seams.

- **Required tests to add/update**
  - Patient router access tests ensuring only patient-owned docs are visible.

- **Migrations needed?** **No**

- **Acceptance criteria**
  - Patient can only access their own generated docs through controlled delivery path.

---

## 6) Product decisions that require explicit human choice

1. **Patient-facing document delivery in 13A vs defer after pilot**
   - Shipping now expands visible scope and support expectations; deferring keeps focus on staff convergence first.

2. **Admin calendar mirror shape for first slice**
   - **List-oriented command panel** vs richer day-grid-like navigation semantics in bot (complexity and callback load differ materially).

3. **Care catalog sync visibility depth**
   - Command-triggered summary only vs persisted sync-history surface (extra persistence/read-model work).

4. **Document delivery UX mode**
   - Bot message with signed URL / temporary download token vs direct attachment pipeline where supported.

---

## 7) Do-not-touch list (stable during 12B)

- **Worker topology architecture** (`projector` + `reminder` lines, mode dispatch model).
- **Google Calendar projection one-way ownership model** (DentFlow truth, Calendar mirror).
- **Core export assembler/template registry lifecycle semantics** from 12A baseline.
- **Unified card callback contract transport format (`c2|...`) and stale-guard semantics**.
- **Care-commerce runtime truth boundary** (Sheets as catalog authoring baseline; DentFlow DB as runtime order/reservation truth).

---

## 8) Final recommendation

Start with **PR 12B-1** immediately: complete admin/doctor booking linked-open recommendation/care-order convergence. It is the highest-impact cross-role gap still visible in current runtime, requires no migration, and unlocks a cleaner handoff into 12B-2 document delivery hardening and then 13A visible integrations.
