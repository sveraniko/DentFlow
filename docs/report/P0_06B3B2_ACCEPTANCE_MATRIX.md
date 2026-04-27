# P0-06B3B2 acceptance matrix

Date: 2026-04-27

## /care_product_open
- usage readable: **yes**
- clinic unavailable recovery: **yes**
- product missing recovery: **yes**
- success product card unchanged: **yes**

## /care_order_create
- usage readable: **yes**
- unresolved patient recovery: **yes**
- recommendation not found recovery: **yes**
- branch invalid recovery: **yes**
- product not linked recovery: **yes**
- out of stock recovery: **yes**
- success structured order result: **yes**

## /care_orders
- unresolved patient recovery: **yes**
- success orders panel unchanged: **yes**

## /care_order_repeat
- usage readable: **yes**
- unresolved patient recovery: **yes**
- success structured panel: **yes**
- branch selection structured panel: **yes**
- unavailable/not found recovery: **yes**
- no raw view.text output: **yes**

## Regression
- B3B1: **pass**
- B3A: **pass**
- B2: **pass**
- B1: **pass**
- A4: **pass**

- care or recommendation: **passed count=164**
- patient and booking: **passed count=105**

## Evidence (tests run)
- `python -m compileall app tests` — PASS
- `pytest -q tests/test_p0_06b3b2_care_command_fallbacks.py` — PASS (`18 passed`)
- `pytest -q tests/test_p0_06b3b1_recommendation_command_fallbacks.py` — PASS (`14 passed`)
- `pytest -q tests/test_p0_06b3a_callback_cleanup.py` — PASS (`5 passed`)
- `pytest -q tests/test_p0_06b2_care_order_readable_surfaces.py` — PASS (`10 passed`)
- `pytest -q tests/test_p0_06b1_care_product_readable_card.py` — PASS (`7 passed`)
- `pytest -q tests/test_p0_06a4_care_recommendations_smoke_gate.py` — PASS (`1 passed`)
- `pytest -q tests -k "care or recommendation"` — PASS (`164 passed, 504 deselected, 2 warnings`)
- `pytest -q tests -k "patient and booking"` — PASS (`105 passed, 563 deselected, 2 warnings`)
