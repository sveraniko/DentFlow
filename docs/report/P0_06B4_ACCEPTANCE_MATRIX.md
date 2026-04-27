# P0-06B4 matrix

Date: 2026-04-27

Care entry:
- unavailable/empty/category empty covered: **yes**
- recovery navigation: **yes**

Product:
- readable product card: **yes**
- missing product recovery: **yes**
- runtime reserve unresolved inline: **yes**
- no CardShellRenderer flat text: **yes**

Order creation:
- structured result: **yes**
- open current/orders/catalog/home: **yes**
- no raw ids/status: **yes**

Orders:
- empty/list/detail readable: **yes**
- repeat/reorder readable: **yes**
- runtime unresolved inline: **yes**
- no double answer: **yes**

Commands:
- care command fallbacks covered: **yes**
- recommendation command fallbacks still green: **yes**
- no raw message.answer(view.text): **yes**

Regression:
- B3B2: **pass**
- B3B1: **pass**
- B3A: **pass**
- B2: **pass**
- B1: **pass**
- A4: **pass**
- P0-05C: **pass**
- care or recommendation: **passed count=167**
- patient and booking: **passed count=105**

Verdict:

- GO to P0-06C: **yes**

## Evidence (tests/checks)
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` — PASS (`3 passed`)
- `pytest -q tests/test_p0_06b3b2_care_command_fallbacks.py` — PASS (`18 passed`)
- `pytest -q tests/test_p0_06b3b1_recommendation_command_fallbacks.py` — PASS (`14 passed`)
- `pytest -q tests/test_p0_06b3a_callback_cleanup.py` — PASS (`5 passed`)
- `pytest -q tests/test_p0_06b2_care_order_readable_surfaces.py` — PASS (`10 passed`)
- `pytest -q tests/test_p0_06b1_care_product_readable_card.py` — PASS (`7 passed`)
- `pytest -q tests/test_p0_06a4_care_recommendations_smoke_gate.py` — PASS (`1 passed`)
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` — PASS (`4 passed`)
- `pytest -q tests -k "care or recommendation"` — PASS (`167 passed, 504 deselected, 2 warnings`)
- `pytest -q tests -k "patient and booking"` — PASS (`105 passed, 566 deselected, 2 warnings`)
