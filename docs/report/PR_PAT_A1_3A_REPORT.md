# PR PAT-A1-3A Report — Human-readable patient booking review/success presentation

## What changed

- Added a tiny patient-facing booking presentation seam in `patient/router.py`:
  - `_resolve_service_label(...)` for localized service title resolution with bounded fallback order;
  - `_resolve_booking_timezone_name(...)` + `_zone_or_utc(...)` for branch/clinic timezone label rendering.
- Updated `_render_review_finalize_panel(...)` to present patient-friendly values:
  - service label now resolves via localized `Service.title_key` when available;
  - fallback order is localized title -> fallback locale title -> service code -> raw id -> localized missing marker;
  - datetime now renders in branch/clinic local timezone, not forced UTC;
  - doctor/branch/phone behavior remains compact and human-facing.
- Updated `_render_finalize_outcome(...)` success branch to remove raw identifiers from normal patient output:
  - doctor/branch/datetime now come from booking card presentation labels;
  - service label uses the same localized service helper as review panel;
  - status now uses localized `booking.status.*` key translation;
  - raw `doctor_id`, `service_id`, `branch_id`, and raw status token are no longer shown in the happy path.
- Bounded improvement in `BookingPatientFlowService.build_booking_card()`:
  - `_service_label(...)` no longer leaks internal `title_key` and now uses `service.code` fallback discipline.

## Exact files changed

- `app/interfaces/bots/patient/router.py`
- `app/application/booking/telegram_flow.py`
- `tests/test_patient_first_booking_review_pat_a1_1.py`
- `docs/report/PR_PAT_A1_3A_REPORT.md`

## Presentation helper/seam introduced

Yes — a small explicit seam was added in patient router:

- `_resolve_service_label(...)`
- `_resolve_booking_timezone_name(...)`
- `_zone_or_utc(...)`

No broad framework or role-agnostic rendering abstraction was introduced.

## Service label resolution discipline

Patient review/success now resolve service labels in this order:

1. `i18n.t(service.title_key, locale)` if translated;
2. fallback locale translation from clinic default locale if translated;
3. `service.code`;
4. raw id (`service_id`) as final fallback;
5. localized missing marker when there is no service value.

This prevents `title_key` leakage in patient-facing copy.

## Timezone resolution discipline

Patient review/success datetime labels now resolve timezone in bounded order:

1. branch timezone (if branch exists and has timezone);
2. clinic timezone;
3. UTC fallback.

Rendered output uses local timezone abbreviation/offset in label format (`%Y-%m-%d %H:%M %Z`).

## Tests added/updated

Updated `tests/test_patient_first_booking_review_pat_a1_1.py` with focused assertions that:

- review panel uses localized human service label and local timezone datetime;
- success panel uses human labels and localized status;
- success panel does not leak raw ids (`doctor_id`, `service_id`, `branch_id`) in normal path.

## Environment/runtime test execution notes

- Targeted test execution completed without environment blockers.

## Explicit non-goals intentionally left for PAT-A1-3B

- broader booking presentation abstraction across all roles/surfaces;
- expanded edge-case matrix beyond the bounded happy-path assertions added here;
- reminder engine/template redesign;
- `/start` redesign or confirm mechanics redesign;
- admin/doctor/owner flow changes;
- migrations.
