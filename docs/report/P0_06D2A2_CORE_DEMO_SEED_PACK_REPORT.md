# P0-06D2A2 Core Demo Seed Pack Report

## Summary
- Expanded the core demo seed pack across stack1 (clinic reference), stack2 (patients/contacts/preferences), and stack3 (booking/slot/session/waitlist coverage).
- Kept D2A1 static-anchor + relative-date shifting compatibility intact.
- Added dedicated audit tests for P0-06D2A2 readiness and cross-stack reference integrity.
- Explicitly deferred recommendations/care catalog/care orders seed expansion to D2B1/D2B2.

## Files changed
- `seeds/stack1_seed.json`
- `seeds/stack2_patients.json`
- `seeds/stack3_booking.json`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_p0_06d2a2_core_demo_seed_pack.py`
- `tests/test_booking_seed_bootstrap.py`
- `tests/test_p0_06d2a1_seed_date_shift_foundation.py`
- `docs/92_seed_data_and_demo_fixtures.md`
- `docs/report/P0_06D2A2_CORE_DEMO_SEED_PACK_REPORT.md`

## stack1 before/after

### Before (from D1 audit)
- Doctors: 1
- Services: 1
- Doctor access codes: 1
- Locale service keys missing for treatment/urgent

### After
- Doctors: 3 (`doctor_anna`, `doctor_boris`, `doctor_irina`)
- Public doctors: 2 (`doctor_anna`, `doctor_boris`)
- Services: 4 (`service_consult`, `service_cleaning`, `service_treatment`, `service_urgent`)
- Doctor access codes: 3 (`ANNA-001`, `BORIS-HYG`, `IRINA-TREAT`)
- Locale keys added in both RU/EN:
  - `service.treatment`
  - `service.urgent`

## stack2 before/after

### Before
- Patients: 3
- Contacts: mostly single-contact baseline
- Telegram resolvability for `3001` absent
- Preferences present only for Sergey

### After
- Patients: 4 (added `patient_maria_petrova`)
- Phone contacts: 4
- Telegram contacts: 3 (`3001`, `3002`, `3004`)
- Telegram-resolvable patient ensured for `3001` (`patient_sergey_ivanov`)
- Phone-only patient preserved (`patient_giorgi_beridze`)
- Preferences present for all 4 demo patients with required fields.

## stack3 before/after

### Before
- Availability slots: 6
- Bookings: 1 (single status)
- Waitlist: 1
- Narrow status and doctor/service coverage

### After
- Availability slots: 12 across static anchor dates `2026-04-20`..`2026-04-28`
- Local time windows represented via UTC:
  - morning local (10:00 MSK): `07:00Z`
  - day local (14:00 MSK): `11:00Z`
  - evening local (18:00 MSK): `15:00Z`
- Bookings: 4 with statuses:
  - `pending_confirmation`
  - `confirmed`
  - `reschedule_requested`
  - `canceled`
- Booking status history added for each booking lifecycle.
- Waitlist: 1 active future-window entry.
- Active review-ready booking session and active hold retained for Telegram `3001`.

## Relative-date readiness (D2A1 compatibility)
- Stack3 keeps static fixture anchor dates (intended baseline payload).
- `_shift_stack3_seed_dates(...)` remains the future-safe demo path.
- Validation confirms shifted payload:
  - keeps IDs unchanged,
  - preserves slot/booking durations,
  - moves date windows forward,
  - yields sufficient future slots/bookings for demo runtime.

## Reference integrity checks
- Verified stack3 references point to valid stack1/stack2 entities:
  - booking patient/doctor/service/branch IDs,
  - slot doctor and service scope IDs,
  - booking slot IDs,
  - hold slot/session references,
  - waitlist patient/service/doctor/branch references.

## Grep checks (exact commands/results)
1. `rg "doctor_boris|doctor_irina|service_cleaning|service_treatment|service_urgent|BORIS-HYG|IRINA-TREAT" seeds locales tests`
   - Result: seed/test references found for all required demo reference objects.

2. `rg "\"contact_type\": \"telegram\"|\"contact_value\": \"3001\"|\"contact_value\": \"3002\"|\"contact_value\": \"3004\"" seeds/stack2_patients.json tests`
   - Result: Telegram contacts for `3001`, `3002`, `3004` present in `seeds/stack2_patients.json`.

3. `rg "pending_confirmation|confirmed|reschedule_requested|canceled" seeds/stack3_booking.json tests/test_p0_06d2a2_core_demo_seed_pack.py`
   - Result: all required statuses represented in seed and asserted in tests.

4. `rg "2026-04|2026-05" seeds/stack3_booking.json tests/test_p0_06d2a2_core_demo_seed_pack.py`
   - Result: static anchor dates remain in stack3 seed; D2A2 tests cover relative shift behavior.

## Tests run (exact commands/results)
- `python -m compileall app tests` → pass
- `pytest -q tests/test_p0_06d2a2_core_demo_seed_pack.py` → `7 passed`
- `pytest -q tests/test_p0_06d2a1_seed_date_shift_foundation.py` → `5 passed`
- `pytest -q tests/test_p0_06d1_seed_content_readiness_audit.py` → `3 passed`
- `pytest -q tests/test_booking_seed_bootstrap.py` → `1 passed`
- `pytest -q tests/test_runtime_seed_behavior.py` → `1 passed`
- `pytest -q tests/test_patient_db_load_and_seed.py` → `3 passed`
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py` → `9 passed`
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` → `3 passed`
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` → `4 passed`
- `pytest -q tests -k "care or recommendation"` → `204 passed, 519 deselected, 2 warnings`
- `pytest -q tests -k "patient and booking"` → `105 passed, 618 deselected, 2 warnings`

## Defects found/fixed
- `tests/test_p0_06d2a1_seed_date_shift_foundation.py` had static-time assertions tied to old slot time (`10:00Z`); updated to new baseline (`07:00Z`) while preserving D2A1 intent.

## Carry-forward
- **P0-06D2B1:** care categories/products demo seed remains pending.
- **P0-06D2B2:** recommendations/care orders demo seed remains pending.

## GO / NO-GO recommendation for D2B1
- **GO**.
- Core demo seed prerequisites for D2B1 are now in place:
  - sufficient clinic/doctor/service/access-code baseline,
  - Telegram + phone patient resolution fixtures,
  - future-shiftable stack3 booking density and status coverage,
  - passing seed/audit/smoke regressions in the specified scope.
