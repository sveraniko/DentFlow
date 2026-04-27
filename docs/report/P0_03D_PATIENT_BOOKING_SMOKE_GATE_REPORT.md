# P0-03D Patient Booking Smoke Gate Report

## Summary
- Implemented a focused smoke-gate test suite for Phase 0 patient booking safety checks in `tests/test_p0_03d_patient_booking_smoke_gate.py`.
- Covered home/service/doctor surfaces, text routing separation, slot panel/pagination/date/window controls, slot conflict outcomes, contact prompt keyboard behavior, reply-keyboard removal, empty states, reschedule conflict behavior, and callback prefix namespace validation.
- No UX redesign, no router split, no DB schema changes, and no CardShellRenderer rewrite were introduced.

## What was tested
- Home panel smoke content and actions.
- Service picker smoke content and navigation callbacks.
- Doctor picker smoke content, doctor-code path, and nav callbacks.
- Doctor-code vs contact plain-text routing separation.
- Slot RU label smoke (no UTC/Tue/Apr), page-size/pagination affordances, and controls.
- Slot pagination state progression and page-content change.
- Date picker state updates and slot rerender behavior.
- Time-window picker state updates and slot rerender behavior for all windows.
- Slot conflict/unavailable/invalid-state behavior (inline notice, no popup alert, suppression/state safety).
- Contact prompt behavior (ReplyKeyboardMarkup + share/back/home/manual phone text).
- ReplyKeyboardRemove behavior for Home/Back from contact keyboard.
- Empty-state action safety (recommendations, care unavailable, no active booking).
- Reschedule confirm conflict/unavailable behavior.
- Callback namespace contract for produced keyboards in smoke scenarios.

## Files changed
- `tests/test_p0_03d_patient_booking_smoke_gate.py`
- `docs/report/P0_03D_PATIENT_BOOKING_SMOKE_GATE_REPORT.md`

## Smoke matrix
- Home: ✅ covered.
- Service picker: ✅ covered.
- Doctor picker: ✅ covered.
- Doctor code routing: ✅ covered.
- Slot labels: ✅ covered.
- Slot pagination: ✅ covered.
- Date picker: ✅ covered.
- Time-window picker: ✅ covered.
- Slot conflict: ✅ covered.
- InvalidStateOutcome: ✅ covered.
- Contact prompt: ✅ covered.
- ReplyKeyboardRemove: ✅ covered.
- Empty states: ✅ covered.
- Reschedule conflict: ✅ covered.
- Callback namespace: ✅ covered.

## Tests run (exact commands/results)
- `python -m compileall app tests` → PASS.
- `pytest -q tests/test_p0_03a_nav_callback_contract.py` → PASS (6 passed).
- `pytest -q tests/test_patient_home_surface_pat_a1_2.py tests/test_patient_first_booking_review_pat_a1_1.py tests/test_patient_existing_booking_shortcut_pat_a3_2.py` → PASS (84 passed).
- `pytest -q tests/test_patient_reschedule_start_pat_a4_1.py` → PASS (16 passed).
- `pytest -q tests/test_p0_03d_patient_booking_smoke_gate.py` → PASS (6 passed).
- `pytest -q tests -k "patient and booking"` → PASS (100 passed, 479 deselected).

## Grep checks (exact commands/results)
1. `rg "Добро пожаловать в DentFlow\. Выберите действие:|Выберите услугу для записи\.|Выберите предпочтение по врачу\." app/interfaces/bots/patient locales tests`
   - Matches found only in smoke-test negative assertions in `tests/test_p0_03d_patient_booking_smoke_gate.py`.

2. `rg "strftime\("%a %d %b|%H:%M UTC|Tue|Apr" app/interfaces/bots/patient tests`
   - `Tue`/`Apr` constants present in router locale tables (internal mapping constants), not active patient-facing RU slot labels.
   - Remaining matches are tests asserting absence of these fragments.

3. `rg "patient.booking.slot.unavailable.*show_alert=True|reschedule.complete.slot_unavailable.*show_alert=True|reschedule.complete.conflict.*show_alert=True" app/interfaces/bots/patient/router.py`
   - No matches.

4. `rg "Рекомендаций пока нет\.$|Каталог ухода сейчас недоступен\.$|Поделитесь контактом телефона или введите номер в чат" app/interfaces/bots/patient locales tests`
   - No matches.

## Defects found and fixed
- None in production code for this scope.
- Added/strengthened smoke automation only.

## Defects found and carried forward
- None for current smoke scope.
- Previously noted reminder-policy subset failure was resolved by removing the stale hardcoded booking date from `tests/test_booking_orchestration.py::test_reminder_policy_uses_patient_preferences_then_clinic_fallback`.

## Go / No-Go recommendation for P0-04
- **Recommendation: GO for P0-04**.
- Rationale: P0-03D smoke suite passes and validates the critical patient booking safety contracts requested for Phase 0 handoff.
