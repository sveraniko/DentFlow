# P0-06B3B1 Recommendation Command Fallbacks Report

## Summary
- Cleaned up fallback/usage/error paths for `/recommendation_open`, `/recommendation_action`, and `/recommendation_products` so they render readable inline panels with recovery navigation instead of raw text-only `message.answer(...)` outputs.
- Added a shared recommendation command recovery keyboard helper and reused existing patient-resolution and recommendation-products recovery panels.
- Added focused regression test coverage for command fallback states and success paths.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_p0_06b3b1_recommendation_command_fallbacks.py`

## `/recommendation_open` before/after
### Before
- Usage fallback: raw `patient.recommendations.open.usage` text.
- Unresolved patient + not-found merged into raw `patient.recommendations.not_found` text.

### After
- Usage fallback renders `patient.recommendations.command.open.usage.panel` via `_send_or_edit_panel(...)` + shared recovery keyboard (`Recommendations / My booking / Main menu`).
- Unresolved patient uses existing `_render_recommendations_patient_resolution_failed_panel(...)`.
- Missing/not-owned recommendation uses `patient.recommendations.command.not_found.panel` + shared recovery keyboard.
- Success remains unchanged (recommendation detail panel).

## `/recommendation_action` before/after
### Before
- Usage fallback: raw `patient.recommendations.action.usage` text.
- Not-found/unresolved: raw `patient.recommendations.not_found` text.
- Invalid state: raw `patient.recommendations.action.invalid_state` text.

### After
- Usage fallback renders `patient.recommendations.command.action.usage.panel` + shared recovery keyboard.
- Unresolved patient uses `_render_recommendations_patient_resolution_failed_panel(...)`.
- Missing/not-owned uses `patient.recommendations.command.not_found.panel` + shared recovery keyboard.
- Invalid state renders `patient.recommendations.command.action.invalid_state.panel` + shared recovery keyboard.
- Success remains unchanged (re-render detail panel).

## `/recommendation_products` before/after
### Before
- Usage fallback used raw care usage key `patient.care.products.open.usage`.
- Unresolved patient / not-found used raw recommendation text keys.
- `manual_target_invalid` and empty outputs were raw text keys.

### After
- Usage fallback renders `patient.recommendations.command.products.usage.panel` + command keyboard with `Recommendations / Care catalog / Main menu`.
- Unresolved patient reuses `_render_recommendations_patient_resolution_failed_panel(...)`.
- Missing/not-owned uses `patient.recommendations.command.not_found.panel` + shared recovery keyboard.
- `manual_target_invalid` and empty now both reuse `_render_recommendation_products_recovery_panel(...)` with:
  - `patient.care.products.manual_target_invalid.panel`
  - `patient.care.products.empty.panel`
- Success remains unchanged (recommendation picker render).

## Command recovery keyboards
- Added `_recommendation_command_recovery_keyboard(locale, include_care_catalog=False)`.
- Default rows:
  - `💬 Recommendations` → `phome:recommendations`
  - `📅 My booking` → `phome:my_booking`
  - `🏠 Main menu` → `phome:home`
- Products usage mode (`include_care_catalog=True`):
  - `💬 Recommendations` → `phome:recommendations`
  - `🪥 Care catalog` → `phome:care`
  - `🏠 Main menu` → `phome:home`

## Tests run (exact commands/results)
- `python -m compileall app tests` — **PASS**
- `pytest -q tests/test_p0_06b3b1_recommendation_command_fallbacks.py` — **PASS** (14 passed)
- `pytest -q tests/test_p0_06b3a_callback_cleanup.py` — **PASS** (5 passed)
- `pytest -q tests/test_p0_06b2_care_order_readable_surfaces.py` — **PASS** (10 passed)
- `pytest -q tests/test_p0_06b1_care_product_readable_card.py` — **PASS** (7 passed)
- `pytest -q tests/test_p0_06a4_care_recommendations_smoke_gate.py` — **PASS** (1 passed)
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` — **PASS** (4 passed)
- `pytest -q tests -k "care or recommendation"` — **PASS** (146 passed, 504 deselected, 2 warnings)

## Grep checks (exact commands/results)
- `rg "patient.recommendations.open.usage|patient.recommendations.action.usage|patient.care.products.open.usage" app/interfaces/bots/patient/router.py`
  - Result: no matches in active command handlers.
- `rg "await message.answer\(i18n.t\(\"patient.recommendations.not_found|await message.answer\(i18n.t\(\"patient.recommendations.patient_resolution_failed|await message.answer\(i18n.t\(\"patient.care.products.empty|await message.answer\(.*manual_target_invalid" app/interfaces/bots/patient/router.py`
  - Result: legacy raw `message.answer(...)` remains only in non-target carry-forward care command paths, not in the three recommendation command handlers addressed in P0-06B3B1.
- `rg "patient.recommendations.command" app/interfaces/bots/patient/router.py locales tests`
  - Result: new command keys exist in locales and are used in router + focused tests.

## Defects found/fixed
- Fixed: text-only dead-end usage/failure paths in recommendation command handlers.
- Fixed: unresolved/not-found handling in `/recommendation_open` and `/recommendation_action` now separated and navigable.
- Fixed: `/recommendation_products` manual target invalid / empty now use structured recovery panel with navigation.

## Carry-forward for P0-06B3B2
Out-of-scope care command fallback cleanup still pending (as requested):
- `/care_product_open`
- `/care_order_create`
- `/care_orders`
- `/care_order_repeat`

## Go / no-go recommendation for P0-06B3B2
- **Go** for P0-06B3B2.
- Recommendation command fallback cleanup is complete and regression checks passed for adjacent recommendation/care/my-booking surfaces.
