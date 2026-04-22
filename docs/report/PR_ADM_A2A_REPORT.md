# PR ADM-A2A Report — Admin patient-card → active-booking bridge

## What changed
- Added a bounded admin-side resolver that finds the most relevant active/upcoming booking for a patient from patient-card context.
- Wired a first-class patient-card CTA for admin (`CardAction.BOOKINGS`) in `/admin_patients` callback flow.
- Implemented patient-card → canonical admin booking card open path using the existing booking panel and existing booking action keyboard.
- Added bounded no-active-booking behavior with localized feedback (no dead callbacks, no crash).
- Preserved patient-origin continuity metadata when opening booking from patient card by carrying patient source context/ref in callback payload.
- Added focused AW4 tests for:
  - patient card -> active booking in one tap,
  - no-active-booking bounded response,
  - handcrafted stale booking callback bounded safety.

## Exact files changed
- `app/interfaces/bots/admin/router.py`
- `tests/test_admin_aw4_surfaces.py`
- `locales/en.json`
- `locales/ru.json`
- `docs/report/PR_ADM_A2A_REPORT.md`

## How active booking is resolved from patient context
- Resolver reads patient bookings from existing booking reads (`list_bookings_by_patient`).
- Filters by:
  - same clinic,
  - statuses from current live-truth set (`LIVE_EXISTING_BOOKING_STATUSES`),
  - bookings with scheduled datetime.
- Selection priority is deterministic and bounded:
  1. live in-clinic statuses (`checked_in`, `in_service`),
  2. nearest upcoming booking,
  3. most recent past booking still in live set.
- If no candidate exists, resolver returns no-match and admin gets bounded localized alert.

## How patient-card booking action is wired
- In admin runtime card callback for patient profile and `SourceContext.ADMIN_PATIENTS`:
  - `CardAction.BOOKINGS` now resolves active booking and opens booking card,
  - patient panel keyboard now includes explicit **Open active booking** CTA plus Back.

## How patient-origin source context is preserved
- Booking open from patient card keeps `source_context=ADMIN_PATIENTS`.
- Callback metadata carries patient-origin ref (`source_ref` suffix with `|patient:<patient_id>`).
- Booking open callback uses patient-scoped `page_or_index` (`patients_open:<patient_id>`), enabling deterministic patient-context back handling in this bounded flow.

## Tests added/updated
- Updated `tests/test_admin_aw4_surfaces.py`:
  - extended patient search/open card test to open active booking from patient card,
  - added no-active-booking bounded test,
  - added handcrafted stale patient booking callback safety test.

## Environment / execution
- Ran focused changed-area tests for AW4 surface module.
- Full repository suite was not executed in this bounded PR.
- No environment blocker prevented running targeted tests.

## Explicit non-goals intentionally left for ADM-A2B and ADM-A2C
- Back-chain perfection across all patient-origin variants.
- `/search_patient` result-surface harmonization.
- Broad admin workdesk redesign.
- CRM/history/recommendation/care UX expansion.
- Owner/doctor/calendar flow changes.
- Any migrations.
