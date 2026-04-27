# P0-06C4 matrix

Date: 2026-04-27

Entry:
- unavailable/unresolved/empty covered: **yes**
- recovery navigation: **yes**

List:
- active/history/all covered: **yes**
- pagination covered: **yes**
- terminal history visible: **yes**
- no raw/debug fields: **yes**

Detail:
- readable card covered: **yes**
- status-aware keyboard covered: **yes**
- open unresolved/not-found recovery: **yes**

Actions:
- ack/accept/decline inline notices: **yes**
- invalid-state inline warning: **yes**
- unresolved/not-found recovery: **yes**
- no popup-only valid path: **yes**
- no double answer: **yes**

Products:
- success picker: **yes**
- manual-invalid/empty recovery: **yes**
- not-found/unresolved recovery: **yes**
- product card from recommendation context: **yes**

Commands:
- recommendation command fallbacks covered: **yes**

Regression:
- C3: **pass**
- C2: **pass**
- C1: **pass**
- B4: **pass**
- A2: **pass**
- care or recommendation: **passed count=204**
- patient and booking: **passed count=105**

Verdict:
- GO to next step: **yes**

## Evidence (tests/checks)
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py` — PASS (`9 passed`)
- `pytest -q tests/test_p0_06c3_recommendation_list_history.py` — PASS (`10 passed`)
- `pytest -q tests/test_p0_06c2_recommendation_action_callbacks.py` — PASS (`10 passed`)
- `pytest -q tests/test_p0_06c1_recommendation_detail_card.py` — PASS (`9 passed`)
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` — PASS (`3 passed`)
- `pytest -q tests/test_p0_06b3b1_recommendation_command_fallbacks.py` — PASS (`14 passed`)
- `pytest -q tests/test_p0_06a2_recommendations_entry_empty_states.py` — PASS (`4 passed`)
- `pytest -q tests -k "care or recommendation"` — PASS (`204 passed, 504 deselected, 2 warnings`)
- `pytest -q tests -k "patient and booking"` — PASS (`105 passed, 603 deselected, 2 warnings`)
