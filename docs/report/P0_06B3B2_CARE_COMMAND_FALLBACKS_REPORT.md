# P0-06B3B2 — Care command fallback cleanup report

## Summary
Implemented fallback cleanup for care command handlers only:
- `/care_product_open`
- `/care_order_create`
- `/care_orders`
- `/care_order_repeat`

All touched command paths now use structured panels (`_send_or_edit_panel`) with navigation keyboards instead of raw `message.answer(...)` text-only fallbacks.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_p0_06b3b2_care_command_fallbacks.py`
- `tests/test_patient_home_surface_pat_a1_2.py`

## /care_product_open before/after
### Before
- Usage fallback used raw `message.answer(i18n.t("patient.care.product.open.usage", ...))`.
- Clinic-unavailable fallback used generic booking unavailable text.

### After
- Usage renders `patient.care.command.product_open.usage.panel` via `_send_or_edit_panel(...)`.
- Clinic unavailable renders `patient.care.command.clinic_unavailable.panel` with Home-only recovery.
- Missing/unavailable product reuses `_render_care_product_missing_panel(...)`.
- Success path remains product card rendering via `_render_product_card(...)`.

## /care_order_create before/after
### Before
- Usage/unresolved/not-found/branch-invalid/product-not-linked/out-of-stock used raw text answers.
- Success used raw string output with raw status/ids.

### After
- Usage renders command usage panel with Recommendations/Catalog/Orders/Home nav.
- Unresolved patient uses `_render_care_reserve_patient_resolution_failed_panel(...)`.
- Recommendation not found/not-owned uses existing `patient.recommendations.command.not_found.panel` with Recommendations/My booking/Home.
- Branch invalid uses `patient.care.command.order_create.branch_invalid.panel`.
- Product-not-linked uses `patient.care.command.order_create.product_not_linked.panel` and `prec:products:{recommendation_id}`.
- Out-of-stock uses structured `patient.care.order.out_of_stock.panel` with branch display label.
- Success reuses structured order-result panel via new shared helper `_render_care_order_created_panel(...)`.

## /care_orders before/after
### Before
- Unresolved patient fallback used raw recommendations patient resolution failed text.

### After
- Unresolved patient now uses `_render_care_orders_patient_resolution_failed_panel(...)`.
- Success path unchanged: `_render_care_orders_panel(...)`.

## /care_order_repeat before/after
### Before
- Usage/unresolved used raw text fallback.
- Result path used `await message.answer(view.text)` (text only, no keyboard).

### After
- Usage renders `patient.care.command.order_repeat.usage.panel` with Orders/Catalog/Home.
- Unresolved patient uses `_render_care_orders_patient_resolution_failed_panel(...)`.
- Result always rendered via `_send_or_edit_panel(...)` + `_repeat_action_keyboard(...)`.
- Success/branch-selection/unavailable/not-found are now navigable (open new/back orders/catalog/home).

## Command recovery keyboards
- Added `_care_command_recovery_keyboard(...)` helper for care command fallback nav.
- Allowed callbacks used:
  - `phome:care`
  - `care:orders`
  - `phome:my_booking`
  - `phome:home`

## Reused helpers/panels
- Reused `_render_care_product_missing_panel(...)`.
- Reused `_render_care_reserve_patient_resolution_failed_panel(...)`.
- Reused `_render_care_orders_patient_resolution_failed_panel(...)`.
- Reused `patient.care.order.out_of_stock.panel`.
- Reused `_repeat_action_keyboard(...)` + `_reserve_again_from_order(...)`.
- Added `_render_care_order_created_panel(...)` and reused it from `_reserve_product(...)` and command success path.

## Tests run (exact commands/results)
- `python -m compileall app tests` ✅ pass
- `pytest -q tests/test_p0_06b3b2_care_command_fallbacks.py` ✅ pass (18 passed)
- `pytest -q tests/test_p0_06b3b1_recommendation_command_fallbacks.py` ✅ pass (14 passed)
- `pytest -q tests/test_p0_06b3a_callback_cleanup.py` ✅ pass (5 passed)
- `pytest -q tests/test_p0_06b2_care_order_readable_surfaces.py` ✅ pass (10 passed)
- `pytest -q tests/test_p0_06b1_care_product_readable_card.py` ✅ pass (7 passed)
- `pytest -q tests/test_p0_06a4_care_recommendations_smoke_gate.py` ✅ pass (1 passed)
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` ✅ pass (4 passed)
- `pytest -q tests -k "care or recommendation"` ✅ pass (164 passed, 504 deselected)

## Grep checks (exact commands/results)
- `rg "await message.answer\\(i18n.t\\(\\\"patient.care.product.open.usage|await message.answer\\(i18n.t\\(\\\"patient.care.order.create.usage|await message.answer\\(i18n.t\\(\\\"patient.care.orders.repeat.usage" app/interfaces/bots/patient/router.py` → no matches ✅
- `rg "await message.answer\\(i18n.t\\(\\\"patient.recommendations.patient_resolution_failed|await message.answer\\(i18n.t\\(\\\"patient.recommendations.not_found|await message.answer\\(i18n.t\\(\\\"patient.care.order.branch_invalid|await message.answer\\(i18n.t\\(\\\"patient.care.order.product_not_linked" app/interfaces/bots/patient/router.py` → no matches ✅
- `rg "await message.answer\\(view.text\\)|patient.care.order.created" app/interfaces/bots/patient/router.py` → no matches ✅
- `rg "patient.care.command" app/interfaces/bots/patient/router.py locales tests` → keys/usage found ✅

## Defects found/fixed
- Care command fallback surfaces had raw text-only exits with no inline recovery navigation.
- `/care_order_repeat` command emitted text-only result with no action keyboard.
- `/care_order_create` assumed `linked_resolution.products[].product` always populated; added fallback to repository product lookup for robustness.

## Carry-forward for P0-06B4 smoke gate
- Keep command fallback checks in smoke gate assertions for panelized failures.
- Keep grep guard to prevent reintroduction of raw `message.answer(view.text)` for command repeat paths.

## Go / No-go recommendation for P0-06B4
**Go** — P0-06B3B2 scope is complete and targeted; required regressions in B3B1/B3A/B2/B1/A4/P0-05C pass in this branch.
