# P0-06B3A acceptance matrix

Date: 2026-04-27

## Double-answer
- care:orders success no double answer: **yes**
- careo:open success no double answer: **yes**

## Recommendation products
- unresolved patient inline panel: **yes**
- My Booking/Home: **yes**
- no popup-only valid path: **yes**

## Product missing
- media callback missing product inline panel: **yes**
- reserve callback missing product inline panel: **yes**
- Care catalog/Home: **yes**
- no popup-only valid path: **yes**

## Show alerts
- remaining care/recommendation show_alert classified: **yes**
- no valid user action popup-only left in scoped paths: **yes**

## Regression
- P0-06B2: **pass**
- P0-06B1: **pass**
- P0-06A4: **pass**

- care or recommendation: **passed count=132**

## Evidence (tests run)
- `python -m compileall app tests` — PASS
- `pytest -q tests/test_p0_06b3a_callback_cleanup.py` — PASS (`5 passed`)
- `pytest -q tests/test_p0_06b2_care_order_readable_surfaces.py` — PASS (`10 passed`)
- `pytest -q tests/test_p0_06b1_care_product_readable_card.py` — PASS (`7 passed`)
- `pytest -q tests/test_p0_06a4_care_recommendations_smoke_gate.py` — PASS (`1 passed`)
- `pytest -q tests -k "care or recommendation"` — PASS (`132 passed, 504 deselected, 2 warnings`)
