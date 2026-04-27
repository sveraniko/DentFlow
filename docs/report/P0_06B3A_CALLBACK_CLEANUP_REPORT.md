# P0-06B3A Callback Cleanup Report

## Summary
- Removed duplicate callback acknowledgements on `care:orders` and `careo:open:{order_id}` success paths; these now rely on `_send_or_edit_panel(...)` callback handling only.
- Switched unresolved patient handling in `prec:products:{recommendation_id}` from popup alert to inline recovery panel with **My Booking** and **Home** navigation.
- Normalized missing/inactive care product recovery in callback paths to readable inline panel (`patient.care.product.missing.panel`) with **Care catalog** and **Home** actions.
- Added focused regression tests for callback no-double-answer and popup-to-panel recovery behavior.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `tests/test_p0_06b3a_callback_cleanup.py`
- `docs/report/P0_06B3A_CALLBACK_CLEANUP_REPORT.md`

## Double-answer cleanup
### `care:orders`
- Removed trailing `await callback.answer()` after `_render_care_orders_panel(...)` success render.
- Invalid/stale handling remains unchanged in dedicated alert branches.

### `careo:open:{order_id}`
- Removed trailing `await callback.answer()` after successful `_open_patient_care_order_from_callback(...)`.
- Invalid callback shape branch (`len(parts) != 3`) still uses alert deny popup.

## Recommendation products unresolved patient behavior
- `recommendation_products_callback(...)` now renders inline recovery panel when patient resolution fails:
  - Text: `patient.recommendations.patient_resolution_failed.panel`
  - Buttons: `phome:my_booking`, `phome:home`
- No popup-only path on this valid user action.

## Product missing callback recovery behavior
- Added reusable `_render_care_product_missing_panel(...)` and reused it in:
  - `_render_product_card(...)` missing/inactive product path.
  - `_reserve_product(...)` missing/inactive product path.
  - runtime media callback (`cover` / `gallery:*`) missing/inactive product path.
- Panel text/key: `patient.care.product.missing.panel`
- Buttons: `phome:care`, `phome:home`

## Remaining `show_alert=True` classification (care/recommendation)
- **Stale/invalid callback parsing or unavailable entities**:
  - `patient.recommendations.callback.unavailable`
  - `patient.recommendations.not_found`
  - `patient.care.order.open.denied`
  - `common.card.callback.stale`
- **Carry-forward outside B3A scope (booking/reminder domains)**:
  - `patient.booking.*` stale/unavailable/invalid state alerts
  - `patient.reminder.*` stale/invalid/confirm alerts
- **Valid user-action popup-only paths addressed in this PR**:
  - recommendation products unresolved patient: converted to inline panel
  - care product missing callback recovery: converted to inline panel

## Grep checks
- `rg "await _render_care_orders_panel\(|await _open_patient_care_order_from_callback\(" app/interfaces/bots/patient/router.py`
  - Result: occurrences remain, but no unconditional `await callback.answer()` immediately after success render/open.
- `rg "patient.recommendations.patient_resolution_failed.*show_alert=True" app/interfaces/bots/patient/router.py`
  - Result: **no match**.
- `rg "patient.care.product.missing.*show_alert=True|care.product.missing.*show_alert=True" app/interfaces/bots/patient/router.py`
  - Result: **no match**.
- `rg "show_alert=True" app/interfaces/bots/patient/router.py`
  - Result: remaining alerts are stale/invalid/unavailable and carry-forward booking/reminder branches.

## Tests run (exact commands/results)
- `python -m compileall app tests` ✅ pass
- `pytest -q tests/test_p0_06b3a_callback_cleanup.py` ✅ pass
- `pytest -q tests/test_p0_06b2_care_order_readable_surfaces.py` ✅ pass
- `pytest -q tests/test_p0_06b1_care_product_readable_card.py` ✅ pass
- `pytest -q tests/test_p0_06a4_care_recommendations_smoke_gate.py` ✅ pass
- `pytest -q tests/test_p0_06a3_care_recommendation_failure_recovery.py` ✅ pass
- `pytest -q tests/test_p0_06a2_recommendations_entry_empty_states.py` ✅ pass
- `pytest -q tests/test_p0_06a1_care_entry_empty_states.py` ✅ pass
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` ✅ pass
- `pytest -q tests -k "care or recommendation"` ✅ pass (`132 passed, 504 deselected`)

## Defects found/fixed
1. Duplicate callback ack risk after care orders panel render.
2. Duplicate callback ack risk after care order open render.
3. Popup-only unresolved patient handling in recommendation products callback.
4. Popup/text-only product-missing recovery in callback media/reserve paths.

## Carry-forward for P0-06B3B
- Command fallback panels (`/recommendation_products`, `/recommendation_open`, `/recommendation_action`, `/care_product_open`, `/care_order_create`, `/care_orders`, `/care_order_repeat`).
- Command success panel harmonization and callback/command parity checks.
- Command-level repeat/order UX adjustments.

## Go / No-Go recommendation for P0-06B3B
- **Go**: callback-layer cleanup is stable, regression checks are green, and remaining work is command-path scoped.
