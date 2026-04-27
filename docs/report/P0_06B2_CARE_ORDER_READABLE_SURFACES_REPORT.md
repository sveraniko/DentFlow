# P0_06B2 Care Order Readable Surfaces Report

## Summary
Implemented readability and navigation polish for care order result/list/detail/repeat surfaces, added inline unresolved-patient recovery in CARE_ORDER runtime callbacks, removed flat `CardShellRenderer` order detail rendering, and added focused regression tests.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_p0_06b2_care_order_readable_surfaces.py`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `docs/report/P0_06B2_CARE_ORDER_READABLE_SURFACES_REPORT.md`

## Order creation result before/after
- Before: flat success copy with limited nav.
- After: structured readable panel with product/branch/status/next-step, and keyboard including open current, orders, care catalog, home.

## Orders empty/list before/after
- Before: generic/legacy empty/list wording and weaker navigation.
- After: localized readable empty panel and list sections (`Current order` / `History`) with safe short refs, item summary, localized status, branch display name, amount, hints, and catalog/home navigation.

## Order detail card before/after
- Before: detail text from `CardShellRenderer.to_panel(shell).text`.
- After: dedicated patient-facing text renderer with localized fields, safe short reference, no raw IDs/debug channels/internal fields, and keyboard with repeat (when actionable), back to orders, and home.

## Runtime CARE_ORDER unresolved patient behavior
- Before: popup-only alert in CARE_ORDER runtime callback path.
- After: inline recovery panel via existing orders patient-resolution-failed helper, with My Booking + Home actions.

## Repeat/reorder result behavior
- Added readable repeat success/branch-selection/unavailable texts.
- Added repeat keyboard navigation consistency: open new (when created), back to orders, care catalog, home.
- Branch choice labels now prefer branch display names.

## Repeat branch selection behavior
- Runtime branch-selection now renders readable instructional panel and uses display labels instead of raw branch IDs when available.

## Double callback-answer cleanup
- Removed explicit extra `callback.answer()` calls after `_send_or_edit_panel(...)` in repeat/repeat_branch CARE_ORDER runtime paths.
- Removed extra answer in direct `care:repeat:*` success path.

## Grep results
- `rg "CardShellRenderer.to_panel\(shell\)\.text" app/interfaces/bots/patient/router.py`
  - No matches.
- `rg "reservation_hint=reservation_hint" app/interfaces/bots/patient/router.py`
  - Single usage only (no duplicate argument in snapshot construction).
- `rg "decoded.source_context == SourceContext.CARE_ORDER_LIST|patient.recommendations.patient_resolution_failed.*show_alert=True" app/interfaces/bots/patient/router.py`
  - CARE_ORDER runtime branch present; unresolved-patient path now routes to inline panel helper.
- `rg "await _send_or_edit_panel\(|await callback.answer\(\)" app/interfaces/bots/patient/router.py`
  - Manually verified repeat/repeat_branch branches do not call `callback.answer()` after panel render.
- `rg "Actions:|Канал:|Channel:|telegram|care_order_id|care_product_id|patient_id|source_channel|booking_mode|branch: -" tests/test_p0_06b2_care_order_readable_surfaces.py`
  - Used for explicit negative assertions only.

## Tests run
- `python -m compileall app tests` ✅
- `pytest -q tests/test_p0_06b2_care_order_readable_surfaces.py` ✅
- `pytest -q tests/test_p0_06b1_care_product_readable_card.py` ✅
- `pytest -q tests/test_p0_06a4_care_recommendations_smoke_gate.py` ✅
- `pytest -q tests/test_p0_06a3_care_recommendation_failure_recovery.py` ✅
- `pytest -q tests/test_p0_06a2_recommendations_entry_empty_states.py` ✅
- `pytest -q tests/test_p0_06a1_care_entry_empty_states.py` ✅
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` ✅
- `pytest -q tests/test_patient_care_order_delivery_pat_a8_2a.py` ✅
- `pytest -q tests/test_patient_care_pickup_flow_pat_a8_2b.py` ✅
- `pytest -q tests -k "care or recommendation"` ✅

## Defects found/fixed
- Care order detail still leaking flat shell text.
- Care order panels leaking raw-ish fallback/internals.
- Missing home recovery in multiple care order paths.
- CARE_ORDER runtime unresolved patient as popup-only path.
- Repeat/repeat_branch callback double-answer risk.
- Repeat branch labels showing raw IDs.
- Care order snapshot duplicate `reservation_hint=reservation_hint` removed in affected area.

## Carry-forward for P0-06B3
- Remaining command-path fallback polish outside scoped care order runtime surfaces.
- Additional runtime callback cleanup in non-care profiles.
- Edge-case UX coverage for unusual multi-item/multi-branch recommendation flows.

## Go/No-Go for P0-06B3
- **Go**: Acceptance criteria for P0-06B2 are met in code and tests.
