# PR S13-A1 Report — Admin Google Calendar mirror awareness surface

## 1. What changed
- Added a bounded admin command `/admin_calendar` that renders a compact read-only awareness panel for Google Calendar projection state.
- The panel explicitly states that **DentFlow bookings are the source of truth** and Google Calendar is a mirror/projection.
- The panel shows projection summary counts (mapped / pending / failed), a bounded worker-mode hint, and a recent mapped booking snippet list when available.
- Added bounded fallback behavior:
  - service unavailable -> localized unavailable message,
  - no mappings -> localized empty state,
  - runtime/projection read exceptions are handled without leaking raw stack traces.

## 2. Exact files changed
- `app/interfaces/bots/admin/router.py`
- `app/application/integration/google_calendar_projection.py`
- `app/infrastructure/db/google_calendar_projection_repository.py`
- `app/bootstrap/runtime.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_admin_calendar_awareness_s13a.py`
- `docs/report/PR_S13_A1_REPORT.md`

## 3. How projection summary/read state is obtained
- Added narrow read-model types:
  - `CalendarProjectionSummary`
  - `CalendarProjectionRecentMapping`
- Added thin read service:
  - `GoogleCalendarProjectionReadService`
- Added tiny repository read helpers:
  - `get_calendar_projection_summary(clinic_id)`
  - `list_recent_calendar_mappings(clinic_id, limit=5)`
- Summary query sources data from existing projection mapping table (`integration.google_calendar_booking_event_map`) and booking scope (`booking.bookings`) to compute compact mapped/pending/failed counts.
- Recent mappings are read from existing mapping persistence only; no live Google Calendar pull is used.

## 4. How source-of-truth semantics are communicated
- The `/admin_calendar` panel includes localized explicit text that DentFlow booking state is source of truth and Google Calendar is read-only mirror/projection.
- The new surface is read-only: no edit/create actions are introduced.

## 5. Tests added/updated
- Added focused tests in `tests/test_admin_calendar_awareness_s13a.py` for:
  1. `/admin_calendar` panel rendering
  2. explicit mirror/source-of-truth statement
  3. empty state handling
  4. unavailable service fallback
  5. summary + recent mapping rendering
  6. non-admin guard behavior

## 6. Environment / execution notes
- Targeted tests were run for the new awareness surface.
- No migrations were added or required.

## 7. Explicit non-goals left for S13-A2 and S13-C
- No full calendar grid UI.
- No two-way Google Calendar editing.
- No booking-state-machine changes.
- No worker topology redesign.
- No generic observability platform.
- No live Google Calendar fetch as source-of-truth.
