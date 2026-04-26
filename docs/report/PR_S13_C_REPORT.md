# PR S13-C Report — Stack 13 integration control index, truth closure, and bounded observability

## 1) What changed
- Added a bounded admin integration control index command: `/admin_integrations`.
- The command renders a compact operator index for:
  1. care catalog sync surface,
  2. Google Calendar mirror awareness surface,
  3. worker/runtime truth note.
- Added explicit source-of-truth guardrails in index copy:
  - DentFlow booking data is source of truth,
  - Google Calendar is read-only mirror,
  - Google Sheets/XLSX are import authoring surfaces, not runtime order/booking truth.
- Added bounded wiring hints only (available/unavailable) for catalog and calendar surfaces based on runtime wiring.
- No live Google Calendar calls are made by this index.
- No catalog sync execution is performed by this index.
- No worker liveness claims are introduced.

## 2) Exact files changed
- `app/interfaces/bots/admin/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_admin_integrations_s13c.py`
- `docs/80_integrations_and_infra.md`
- `docs/73_governance_and_reference_ops.md`
- `docs/90_pr_plan.md`
- `docs/report/PR_S13_C_REPORT.md`

## 3) Command syntax added
- `/admin_integrations`

Indexed existing command surfaces:
- `/admin_catalog_sync sheets <url_or_id>`
- `/admin_catalog_sync xlsx <server_local_path>`
- `/admin_calendar`

## 4) Integration/operator surfaces now indexed
- Care catalog sync (bounded command surface).
- Google Calendar mirror awareness (bounded read-only panel).
- Worker/runtime truth note (workers exist; liveness unavailable from bot runtime unless dedicated healthcheck subsystem exists).

## 5) Source-of-truth boundaries now stated in bot surface
- DentFlow booking data is source of truth.
- Google Calendar is read-only mirror.
- Google Sheets/XLSX are import authoring surfaces and are not runtime booking/order truth.

## 6) Docs truth updates
- `docs/80_integrations_and_infra.md`: added current bounded Stack-13 operator surfaces and non-goals.
- `docs/73_governance_and_reference_ops.md`: updated governance status/evidence for catalog sync and calendar mirror to implemented (bounded), including `/admin_integrations`.
- `docs/90_pr_plan.md`: updated Stack 13 outcome/status as completed bounded convergence.

## 7) Tests added/updated
Added `tests/test_admin_integrations_s13c.py` covering:
1. `/admin_integrations` is admin-guarded.
2. Catalog command hints are listed.
3. Calendar command hint is listed.
4. DentFlow source-of-truth + Calendar mirror boundary is explicit.
5. Sheets/XLSX import-only boundary is explicit.
6. Copy does not imply Calendar->DentFlow sync.
7. Wiring hints are bounded when optional services are absent.
8. No migrations introduced.

## 8) Environment / execution notes
- Focused tests were run in the local repo environment.
- No external Google calls were required.
- No worker processes were started.
- No migrations were created.

## 9) Stack 13 closure statement
- **Yes — Stack 13 is now closed in bounded scope.**
- Closure is explicitly limited to operational convergence surfaces and docs truth alignment, without introducing a broad observability platform or integration-platform redesign.
