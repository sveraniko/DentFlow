# P0-06C1 matrix

Date: 2026-04-27

Detail card:
- readable title/status/type/body: **yes**
- no raw/debug/internal fields: **yes**
- RU/EN localized: **yes**

Keyboard:
- issued/viewed actions: ack/accept/decline/products/back/home: **yes**
- acknowledged actions: accept/decline/products/back/home, no ack: **yes**
- terminal statuses: no mutation actions: **yes**
- draft/prepared: no mutation actions: **yes**

Open callback:
- unresolved patient inline panel: **yes**
- not found/not owned inline panel: **yes**
- no popup-only valid path: **yes**
- no double answer: **yes**

Regression:
- products handoff works: **yes**
- mark_viewed still works: **yes**
- P0-06B4: **pass**
- care or recommendation: **passed count=176**
- patient and booking: **passed count=105**

Verdict:
- GO: **yes**

## Evidence (tests/checks)
- `pytest -q tests/test_p0_06c1_recommendation_detail_card.py` — PASS (`9 passed`)
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` — PASS (`3 passed`)
- `pytest -q tests -k "care or recommendation"` — PASS (`176 passed, 504 deselected, 2 warnings`)
- `pytest -q tests -k "patient and booking"` — PASS (`105 passed, 575 deselected, 2 warnings`)
