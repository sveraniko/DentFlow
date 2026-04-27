# P0-06B1 — Care product readable card + product path cleanup

## Summary
- Replaced patient-facing care product card body rendering with a dedicated readable text composer based on product/content/category/branch/availability/price/recommendation context.
- Removed runtime reserve unresolved-patient popup-only behavior for product runtime callbacks; now uses inline recovery panel with actionable recovery buttons.
- Removed redundant callback answer in recommendation products success path.
- Added recoverable missing product panel with Care catalog + Home actions.
- Ensured branch picker includes Home and Back.
- Added focused P0-06B1 tests and executed regression/smoke suites.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `locales/ru.json`
- `locales/en.json`
- `tests/test_p0_06b1_care_product_readable_card.py`
- `docs/report/P0_06B1_CARE_PRODUCT_READABLE_CARD_REPORT.md`

## Product card before/after
### Before
- Patient product card body used `CardShellRenderer.to_panel(shell).text` in `_render_product_card(...)`.
- This could surface flattened meta/internal-ish lines.

### After
- Added local helper `_render_patient_care_product_text(...)` and switched `_render_product_card(...)` to compose patient-readable product text directly.
- Text includes title, SKU, category, price, availability, branch, optional description, optional usage hint, optional recommendation reason.
- Card body no longer uses `CardShellRenderer.to_panel(shell).text` for care products.
- Keyboard still uses valid runtime callbacks; Home button appended.

## Product missing behavior
- Missing/inactive product now renders explicit panel text (`patient.care.product.missing.panel`).
- Recovery buttons:
  - Care catalog (`phome:care`)
  - Home (`phome:home`)

## Runtime reserve unresolved behavior
- Runtime encoded product reserve (`decoded.page_or_index == "reserve"`) unresolved patient path now renders inline reserve recovery panel via `_render_care_reserve_patient_resolution_failed_panel(...)`.
- No popup-only valid path.
- Recovery buttons verified:
  - My booking
  - Care catalog
  - Home

## Recommendation product success callback-answer cleanup
- In `recommendation_products_callback(...)`, removed manual `await callback.answer()` directly after `_render_recommendation_picker(...)`.
- Success path now relies on render helper flow to avoid double-answering.

## Branch picker Home behavior
- Branch picker now includes Home (`phome:home`) in addition to Back-to-product runtime callback.

## Tests run (exact commands/results)
- `python -m compileall app tests` → PASS
- `pytest -q tests/test_p0_06b1_care_product_readable_card.py` → PASS (7 passed)
- `pytest -q tests/test_p0_06a4_care_recommendations_smoke_gate.py` → PASS (1 passed)
- `pytest -q tests/test_p0_06a3_care_recommendation_failure_recovery.py` → PASS (4 passed)
- `pytest -q tests/test_p0_06a2_recommendations_entry_empty_states.py` → PASS (4 passed)
- `pytest -q tests/test_p0_06a1_care_entry_empty_states.py` → PASS (3 passed)
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` → PASS (4 passed)
- `pytest -q tests -k "care or recommendation"` → PASS (119 passed, 502 deselected)
- `pytest -q tests -k "patient and booking"` → PASS (105 passed, 516 deselected)

## Grep checks
1. `rg "CardShellRenderer.to_panel\(shell\)\.text" app/interfaces/bots/patient/router.py`
   - Result: one remaining usage in care order card path (carry-forward by design for P0-06B2); product card path no longer uses it.

2. `rg "decoded.page_or_index == \"reserve\"|patient.recommendations.patient_resolution_failed.*show_alert=True" app/interfaces/bots/patient/router.py`
   - Runtime `reserve` branch still exists and now uses inline recovery panel for unresolved patient.
   - Other `show_alert=True` occurrences remain in unrelated flows.

3. `rg "await _render_recommendation_picker\(|await callback.answer\(\)" app/interfaces/bots/patient/router.py`
   - Manually verified there is no unconditional `await callback.answer()` immediately after `_render_recommendation_picker(...)` inside `recommendation_products_callback(...)`.

4. `rg "Actions:|Канал:|Channel:|telegram|care_product_id|branch_id|source_channel|booking_mode" tests/test_p0_06b1_care_product_readable_card.py`
   - Negative assertions present for product-card text leakage guards.

## Defects found/fixed
- Product card text leakage risk from generic shell rendering fixed.
- Runtime product reserve unresolved patient popup-only branch fixed to inline recovery panel.
- Recommendation products success double-answer risk fixed.
- Product missing/inactive dead-end fixed with recoverable panel.
- Branch picker missing Home recovery fixed.

## Carry-forward for P0-06B2
- Care order result/list/order card polish remains for P0-06B2.
- One care order path still uses `CardShellRenderer.to_panel(shell).text` intentionally carried forward.

## Go/No-Go for P0-06B2
- **Go**: P0-06B1 acceptance criteria implemented and focused/regression tests are passing.
