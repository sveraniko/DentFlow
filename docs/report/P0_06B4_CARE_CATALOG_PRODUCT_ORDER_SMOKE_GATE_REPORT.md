# P0-06B4 — Care catalog/product/order consolidated smoke gate report

## Summary
Implemented a consolidated B4 smoke gate focused on integrated care catalog/product/order behavior, callback namespace checks, callback answer hygiene, and regression grep guards without introducing product features or architecture rewrites.

Result: **GO for P0-06C**.

## Files changed
- `tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py`
- `docs/report/P0_06B4_CARE_CATALOG_PRODUCT_ORDER_SMOKE_GATE_REPORT.md`

## Smoke matrix

| Area | Status | Notes |
|---|---|---|
| care entry | ✅ | care unavailable panel remains care-specific; no generic unavailable token; inline recovery remains. |
| product card | ✅ | readable labels (SKU/category/price/availability/branch), safe text, no raw/debug leaks. |
| product missing | ✅ | covered by existing B1/B3A/B3B2 regressions (re-run in this gate). |
| runtime reserve unresolved | ✅ | inline recovery with My booking/Care/Home; no popup-only path; no double answer. |
| order creation result | ✅ | structured panel, branch display label, no raw `confirmed` leak. |
| orders list | ✅ | readable list surface present; orders entry remains structured and recoverable. |
| order detail | ✅ | readable and safe order detail with ref/branch/status/items and safe navigation. |
| repeat/reorder | ✅ | repeat success path structured and navigable; no double answer in tested path. |
| callback fallback cleanup | ✅ | care:orders and careo:open valid paths render panel and avoid callback double-answer. |
| command fallback cleanup | ✅ | command success/failure surfaces remain panel-based (B3B2 suite re-run). |
| recommendation handoff | ✅ | recommendation product picker opens readable product card; invalid/empty recoveries preserved. |
| callback namespace | ✅ | collected callback_data constrained to allowed prefixes + runtime encoded callbacks. |
| double callback answer | ✅ | smoke-checked callback paths stay at <=1 callback answer payload. |

## Grep checks (exact commands/results)

### 1) CardShellRenderer flat text usage in patient router
```bash
rg "CardShellRenderer.to_panel\(shell\)\.text" app/interfaces/bots/patient/router.py
```
Result: **no matches** ✅

### 2) Raw repeat/order-created output
```bash
rg "await message.answer\(view.text\)|patient.care.order.created" app/interfaces/bots/patient/router.py
```
Result: **no matches** ✅

### 3) Raw care command usage answers
```bash
rg "await message.answer\(i18n.t\(\"patient.care.product.open.usage|await message.answer\(i18n.t\(\"patient.care.order.create.usage|await message.answer\(i18n.t\(\"patient.care.orders.repeat.usage" app/interfaces/bots/patient/router.py
```
Result: **no matches** ✅

### 4) Raw/debug/internal leakage markers
```bash
rg "Actions:|Канал:|Channel:|source_channel|booking_mode|branch: -" app/interfaces/bots/patient/router.py tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py
```
Result:
- test file contains these only in **negative assertions** ✅
- router still contains `booking_mode` in booking state management contexts (not care product/order panel text rendering) ✅
- no active `branch: -` panel text leak found ✅

### 5) Sensitive id marker presence inside B4 smoke file
```bash
rg "care_order_id|care_product_id|patient_id|branch_id" tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py
```
Result: occurrences are in controlled test setup/safe objects; not asserting raw leakage into user text ✅

### 6) show_alert classification inventory
```bash
rg "show_alert=True" app/interfaces/bots/patient/router.py
```
Result: remaining branches are primarily:
- stale/invalid callback guards (`common.card.callback.stale`, booking stale/session missing, reminder invalid/stale)
- valid user action confirmations in reminder cancel flow (`common.yes/common.no` carry-forward)
- booking control guardrails/finalize invalid states
- recommendation not-found/unavailable guardrails
- care order access denied guard (`patient.care.order.open.denied`)

Classification:
- **stale/invalid callback:** majority ✅
- **valid user action:** reminder cancel confirm/abort prompts ✅
- **carry-forward:** reminder yes/no show_alert remains accepted by this scope ✅

No evidence of popup-only replacement for valid care product/order render paths in this smoke.

## Tests run (exact commands/results)

- `python -m compileall app tests` ✅ pass
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` ✅ pass (3 passed)
- `pytest -q tests/test_p0_06b3b2_care_command_fallbacks.py` ✅ pass (18 passed)
- `pytest -q tests/test_p0_06b3b1_recommendation_command_fallbacks.py` ✅ pass (14 passed)
- `pytest -q tests/test_p0_06b3a_callback_cleanup.py` ✅ pass (5 passed)
- `pytest -q tests/test_p0_06b2_care_order_readable_surfaces.py` ✅ pass (10 passed)
- `pytest -q tests/test_p0_06b1_care_product_readable_card.py` ✅ pass (7 passed)
- `pytest -q tests/test_p0_06a4_care_recommendations_smoke_gate.py` ✅ pass (1 passed)
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` ✅ pass (4 passed)
- `pytest -q tests/test_p0_04c_review_edit_success_smoke_gate.py` ✅ pass (3 passed)
- `pytest -q tests/test_p0_03d_patient_booking_smoke_gate.py` ✅ pass (6 passed)
- `pytest -q tests -k "care or recommendation"` ✅ pass (167 passed, 504 deselected, 2 unrelated asyncio-mark warnings)
- `pytest -q tests -k "patient and booking"` ✅ pass (105 passed, 566 deselected, 2 unrelated asyncio-mark warnings)

## Defects found/fixed
- Added integrated B4 smoke coverage for the full care catalog/product/order contour and callback namespace/answer hygiene checks.
- Added B4 router grep guards against regressions to raw text-only fallback patterns.

## Defects carried forward
- Existing global `show_alert=True` usage remains in non-B4 scopes (booking/reminder/recommendation stale/invalid guards and reminder cancel confirm flow).
- No B4-scoped blocker found for care product/order/recommendation handoff surfaces.

## Remaining show_alert classification (B4 perspective)
- `care:orders`, `careo:open`, runtime reserve unresolved, runtime care unresolved, recommendation product picker success: **inline panel paths, no popup-only behavior in smoke tests**.
- popup alerts still used for stale/invalid actions and guard rails in broader router, which is acceptable carry-forward for this PR.

## GO / NO-GO recommendation for P0-06C
**GO**.

Rationale:
- Consolidated B4 smoke gate exists and passes.
- Prior B1/B2/B3A/B3B1/B3B2/A4/P0-05C contracts re-validated.
- No active care product/order raw CardShell flat-text fallback usage.
- No active raw care command usage-answer fallback usage.
- No scoped care product/order popup-only regressions found for valid render paths.
