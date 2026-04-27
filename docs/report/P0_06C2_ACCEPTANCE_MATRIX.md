# P0-06C2 matrix

Date: 2026-04-27

Action success:
- ack inline notice + updated detail: **yes**
- accept inline notice + terminal detail: **yes**
- decline inline notice + terminal detail: **yes**
- no popup success: **yes**
- no double answer: **yes**

Invalid state:
- ValueError renders inline warning: **yes**
- current/latest detail shown: **yes**
- no popup-only path: **yes**

Recovery:
- action unresolved patient inline panel: **yes**
- action not found/not owned inline panel: **yes**
- products not found/not owned inline panel: **yes**

Keyboard:
- acknowledged no ack button: **yes**
- accepted/declined no mutation buttons: **yes**
- Back/Home preserved: **yes**

Regression:
- C1: **pass**
- B4: **pass**
- B3B1: **pass**
- A2: **pass**
- care or recommendation: **passed count=186**
- patient and booking: **passed count=105**

Verdict:
- GO to P0-06C3: **yes**

## Evidence (tests/checks)
- `pytest -q tests/test_p0_06c2_recommendation_action_callbacks.py` — PASS (`10 passed`)
- `pytest -q tests/test_p0_06c1_recommendation_detail_card.py` — PASS (`9 passed`)
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` — PASS (`3 passed`)
- `pytest -q tests/test_p0_06b3b1_recommendation_command_fallbacks.py` — PASS (`14 passed`)
- `pytest -q tests/test_p0_06a2_recommendations_entry_empty_states.py` — PASS (`4 passed`)
- `pytest -q tests -k "care or recommendation"` — PASS (`186 passed, 504 deselected, 2 warnings`)
- `pytest -q tests -k "patient and booking"` — PASS (`105 passed, 585 deselected, 2 warnings`)
