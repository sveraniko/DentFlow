# P0-06C3 matrix

Date: 2026-04-27

List:
- readable title/summary/rows: **yes**
- active/history/all filters: **yes**
- default filter selects active/history correctly: **yes**
- no raw/debug/internal fields: **yes**
- no technical datetime: **yes**

History:
- terminal rows visible in history: **yes**
- include_terminal=True or equivalent: **yes**
- history empty state readable: **yes**

Pagination:
- page size enforced: **yes**
- next/prev work: **yes**
- page clamp works: **yes**

Callbacks:
- prec:list handler: **yes**
- open row -> detail works: **yes**
- no double-answer: **yes**
- malformed callback safe: **yes**

Regression:
- C2: **pass**
- C1: **pass**
- B4: **pass**
- A2: **pass**
- care or recommendation: **passed count=195**
- patient and booking: **passed count=105**

## Evidence (tests/checks)
- `pytest -q tests/test_p0_06c3_recommendation_list_history.py` — PASS (`9 passed`)
- `pytest -q tests/test_p0_06c2_recommendation_action_callbacks.py tests/test_p0_06c1_recommendation_detail_card.py tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py tests/test_p0_06a2_recommendations_entry_empty_states.py` — PASS (`26 passed`)
- `pytest -q tests -k "care or recommendation"` — PASS (`195 passed, 504 deselected, 2 warnings`)
- `pytest -q tests -k "patient and booking"` — PASS (`105 passed, 594 deselected, 2 warnings`)
