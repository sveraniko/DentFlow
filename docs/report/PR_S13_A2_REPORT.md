# PR S13-A2 Report — Calendar awareness hardening and projection boundary clarity

## 1. What changed after S13-A1
- Hardened `/admin_calendar` wording so projection status is explicit and bounded:
  - projection configuration now renders as **configured / not configured / unknown** from bot runtime env hint.
  - mapped and pending counts are shown in a compact summary.
  - failed projection mapping count is shown explicitly.
  - recent projection activity now shows latest known mapping sync timestamp, or unknown/unavailable when not present.
- Replaced worker-mode hint wording with explicit runtime truth:
  - **worker liveness is not available from bot runtime**.
- Kept source-of-truth boundary explicit and stable:
  - DentFlow booking data remains source of truth.
  - Google Calendar remains read-only projection mirror.
- Expanded focused regression tests for status rendering, failure/unknown boundaries, mirror-only copy guardrails, admin guard, and migration absence expectation.

## 2. Exact files changed
- `app/interfaces/bots/admin/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_admin_calendar_awareness_s13a.py`
- `docs/71_role_scenarios_and_acceptance.md`
- `docs/report/PR_S13_A2_REPORT.md`

## 3. How status clarity was improved
- Added explicit projection configuration line driven by `INTEGRATIONS_GOOGLE_CALENDAR_ENABLED` environment value:
  - true-like values -> configured
  - false-like values -> not configured
  - missing/ambiguous -> unknown
- Split summary into bounded pieces:
  - mapped + pending projection counts
  - failed mappings count
- Added recent-activity line:
  - latest `last_synced_at` from recent mapping rows if available
  - otherwise explicit unknown/unavailable text

## 4. Worker/runtime state: what can and cannot be known
- The admin bot can show projection data snapshots via read service.
- The admin bot **cannot** reliably determine current worker process liveness.
- Surface now explicitly states: worker liveness is not available from bot runtime.
- No worker topology, healthcheck subsystem, or dashboard was added.

## 5. ADM-009 closure status
- ADM-009 is now updated to **Implemented (bounded awareness surface)** in docs truth.
- Closure scope is bounded to read-only awareness and mirror/source-of-truth clarity.

## 6. Docs truth update
- Updated `docs/71_role_scenarios_and_acceptance.md` minimally:
  - scenario ADM-009 status and evidence lines
  - summary matrix row for ADM-009

## 7. Tests added/updated
Updated `tests/test_admin_calendar_awareness_s13a.py` to cover:
1. configured status rendering
2. not configured status rendering
3. unknown status rendering
4. mapped/pending/failure count rendering
5. recent mapping + recent projection activity rendering
6. unknown recent activity bounded text
7. worker liveness unknown runtime-truth text
8. mirror/source-of-truth copy guardrails (no “sync from Calendar”)
9. non-admin guard remains intact
10. no migration files introduced in this bounded PR scope

## 8. Environment and execution notes
- Tests were run as targeted pytest scope for S13-A2 files.
- No Google Calendar calls were made.
- No worker runtime was started.
- No migrations were created.

## 9. Explicit non-goals left for S13-C
- No full calendar grid UI.
- No two-way Calendar editing.
- No Calendar-to-DentFlow sync path.
- No persistent job-history dashboard.
- No worker liveness subsystem.
- No projection backend redesign.
