# P0-04A Review + Success Visual Polish Report

## Summary
- Polished patient booking review panel rendering with structured copy, localized date/time split fields, explicit missing-value labels, and Confirm/Back/Home actions.
- Polished finalize success panel with structured copy, localized date/time formatting, patient-readable localized statuses, and stable My Booking/Home actions.
- Added finalize failure panels with recovery navigation for slot conflict/unavailable and safe home fallback for invalid state/escalated outcomes.
- Added review-back callback flow (`book:review:back:{session_id}`) to return deterministically to contact prompt with ReplyKeyboardMarkup.
- Ensured contact reply keyboard is dismissed before review panel rendering after contact submission.
- Updated tests and smoke callback namespace contract; refreshed reminder-policy stale date test.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `locales/ru.json`
- `locales/en.json`
- `tests/test_patient_first_booking_review_pat_a1_1.py`
- `tests/test_booking_patient_review_confirm_pat_a1_1a.py`
- `tests/test_patient_booking_copy_pat_a1_3.py`
- `tests/test_p0_03d_patient_booking_smoke_gate.py`
- `tests/test_booking_orchestration.py`
- `docs/report/P0_03D_PATIENT_BOOKING_SMOKE_GATE_REPORT.md`
- `docs/report/P0_04A_REVIEW_SUCCESS_VISUAL_POLISH_REPORT.md`

## P0-03D reminder-test status update
- Previous broad-subset known failure is now resolved.
- `tests/test_booking_orchestration.py::test_reminder_policy_uses_patient_preferences_then_clinic_fallback` now uses dynamic future scheduling (`now + 3 days`) instead of stale fixed date.

## Review panel before/after
- Before: plain text block with technical datetime (`%Y-%m-%d %H:%M %Z`) and raw fallback placeholders.
- After:
  - structured emoji-led sections;
  - separate localized date/time fields;
  - no timezone suffix in patient-facing text;
  - localized missing values (`не выбран` / `not selected`, `не указан` / `not provided`);
  - actions: Confirm, Back, Home.

## Success panel before/after
- Before: compact raw success text path relied on card datetime label and generic status translation.
- After:
  - structured success panel with service/doctor/date/time/branch/status/reminder hint;
  - date/time rendered from booking timestamp in clinic/branch timezone using patient helpers;
  - localized patient-readable status labels (`patient.booking.status.*`);
  - actions: My Booking + Home only.

## New callback map
- Added and registered: `book:review:back:{session_id}`
  - validates active callback session;
  - switches flow mode to `new_booking_contact`;
  - renders contact prompt with reply keyboard (`share contact`, `back`, `home`).

## Date/time formatting notes
- Added helper set near existing patient UI date helpers:
  - `_format_patient_date(dt, locale)`
  - `_format_patient_time(dt, locale)`
  - `_format_patient_datetime_parts(dt, locale)`
- Uses clinic/branch timezone resolution via:
  - `_resolve_booking_timezone_name(clinic_id, branch_id)`
  - `_zone_or_utc(timezone_name)`
- Avoids OS locale and avoids patient-facing `%Z`/timezone suffix on review/success.

## Contact keyboard cleanup behavior
- After contact submission and successful `mark_review_ready`, router now calls reply-keyboard cleanup (`ReplyKeyboardRemove`) before rendering review inline panel.
- Prevents stale contact keyboard from remaining under review actions.

## Finalize outcome behavior
- `OrchestrationSuccess`: polished success panel + My Booking/Home.
- `InvalidStateOutcome`: readable failure panel + Home.
- `SlotUnavailableOutcome` / `ConflictOutcome`: readable failure panel + Choose another time (`book:slots:back:{session_id}`) + Home.
- Other/escalated fallback: escalation message + Home.
- No popup alert on valid confirm callback finalization paths.

## Tests run with exact commands/results
- `python -m compileall app tests` → PASS.
- `pytest -q tests/test_booking_orchestration.py::test_reminder_policy_uses_patient_preferences_then_clinic_fallback` → PASS (1 passed).
- `pytest -q tests/test_p0_03a_nav_callback_contract.py` → PASS (6 passed).
- `pytest -q tests/test_p0_03d_patient_booking_smoke_gate.py` → PASS (6 passed).
- `pytest -q tests/test_patient_first_booking_review_pat_a1_1.py tests/test_patient_home_surface_pat_a1_2.py tests/test_patient_existing_booking_shortcut_pat_a3_2.py` → PASS (84 passed).
- `pytest -q tests/test_patient_reschedule_start_pat_a4_1.py` → PASS (16 passed).
- `pytest -q tests -k "patient and booking"` → PASS (100 passed, 479 deselected; 2 unrelated pytest mark warnings).

## Grep checks
- `rg "Проверьте запись перед подтверждением:|Время: \{datetime\}|Филиал: \{branch\}|Телефон: \{phone\}" app/interfaces/bots/patient locales tests`
  - Legacy key names remain in locale storage for compatibility, but active routing uses `patient.booking.review.panel_v2`.
- `rg "%Y-%m-%d %H:%M %Z|card.datetime_label|pending_confirmation|branch: -|Actions:" app/interfaces/bots/patient tests`
  - No `card.datetime_label` usage in patient finalize success rendering path.
  - `%Y-%m-%d %H:%M %Z` remains in reschedule review path and in tests/stubs outside P0-04A scope.
- `rg "2026, 4, 22" tests/test_booking_orchestration.py`
  - No stale fixed reminder date in `test_reminder_policy_uses_patient_preferences_then_clinic_fallback`.

## Carry-forward for P0-04B
- Edit service from review panel.
- Edit doctor from review panel.
- Edit time from review panel.
- Edit phone from review panel.
