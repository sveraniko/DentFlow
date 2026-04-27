# P0-06B2 acceptance matrix

Date: 2026-04-27

## Order creation
- structured success panel: **yes**
- open current / orders / catalog / home: **yes**
- no raw/debug/internal fields: **yes**

## Out of stock
- readable panel: **yes**
- change branch / catalog / home: **yes**

## Orders list
- empty state readable: **yes**
- current/history sections: **yes**
- open/repeat buttons: **yes**
- catalog/home: **yes**

## Order detail
- no CardShellRenderer flat text: **yes**
- readable fields/status/items/branch/amount/ref: **yes**
- back/repeat/home: **yes**
- no Actions/Channel/telegram/raw ids: **yes**

## Repeat/reorder
- success structured: **yes**
- branch selection readable: **yes**
- unavailable/out-of-stock readable: **yes**
- open new / back orders / catalog / home: **yes**
- no double callback answer: **yes**

## Runtime recovery
- CARE_ORDER unresolved inline panel: **yes**
- no popup-only valid path: **yes**

## Regression
- P0-06B1: **pass**
- P0-06A4: **pass**
- P0-05C: **pass**
- care or recommendation: **passed count=129**
- patient and booking: **passed count=105**

## Evidence (tests run)
- `python -m compileall app tests` — PASS
- `pytest -q tests/test_p0_06b2_care_order_readable_surfaces.py` — PASS (`10 passed`)
- `pytest -q tests/test_p0_06b1_care_product_readable_card.py` — PASS (`7 passed`)
- `pytest -q tests/test_p0_06a4_care_recommendations_smoke_gate.py` — PASS (`1 passed`)
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` — PASS (`4 passed`)
- `pytest -q tests -k "care or recommendation"` — PASS (`129 passed, 502 deselected, 2 warnings`)
- `pytest -q tests -k "patient and booking"` — PASS (`105 passed, 526 deselected, 2 warnings`)
