# P0-06B3B1 acceptance matrix

Date: 2026-04-27

## /recommendation_open
- usage panel readable: **yes**
- unresolved patient recovery: **yes**
- not found recovery: **yes**
- success detail unchanged: **yes**
- navigation present: **yes**

## /recommendation_action
- usage panel readable: **yes**
- invalid action recovery: **yes**
- invalid state recovery: **yes**
- success detail unchanged: **yes**
- navigation present: **yes**

## /recommendation_products
- usage panel readable: **yes**
- unresolved patient recovery: **yes**
- not found recovery: **yes**
- manual target invalid structured panel: **yes**
- empty products structured panel: **yes**
- success picker unchanged: **yes**
- Back recommendation / Care catalog / Home: **yes**

## Regression
- P0-06B3A: **pass**
- P0-06B2: **pass**
- P0-06B1: **pass**
- P0-06A4: **pass**

- care or recommendation: **passed count=146**

## Evidence (tests run)
- `python -m compileall app tests` — PASS
- `pytest -q tests/test_p0_06b3b1_recommendation_command_fallbacks.py` — PASS (`14 passed`)
- `pytest -q tests/test_p0_06b3a_callback_cleanup.py` — PASS (`5 passed`)
- `pytest -q tests/test_p0_06b2_care_order_readable_surfaces.py` — PASS (`10 passed`)
- `pytest -q tests/test_p0_06b1_care_product_readable_card.py` — PASS (`7 passed`)
- `pytest -q tests/test_p0_06a4_care_recommendations_smoke_gate.py` — PASS (`1 passed`)
- `pytest -q tests -k "care or recommendation"` — PASS (`146 passed, 504 deselected, 2 warnings`)
