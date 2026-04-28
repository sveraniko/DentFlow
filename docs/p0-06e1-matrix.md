# P0-06E1 Matrix

Generated: 2026-04-28 (UTC)

## Templates
- blank CSV tabs exist: **yes**
- demo CSV tabs exist: **yes**
- README exists: **yes**
- headers match parser expectations: **yes**

## Demo CSV
- generated from `care_catalog_demo.json`: **yes**
- counts match JSON: **yes**
- parser accepts CSV workbook: **yes**
- no validation errors: **yes**

## Docs/runbook
- Google Sheet tab names documented: **yes**
- CLI sync command documented: **yes**
- admin sync command documented: **yes**
- access/export model documented: **yes**
- validation/common errors documented: **yes**

## Regression
- E1 tests: **pass**
- D2B1: **pass**
- D2C: **pass**
- C4: **pass**
- B4: **pass**
- care or recommendation: **227 passed**
- patient and booking (E1 acceptance command): **105 passed**

## Command log
- `pytest -q tests/test_p0_06e1_care_catalog_sheets_template.py tests/test_p0_06d2b1_care_catalog_demo_seed.py tests/test_p0_06d2c_seed_demo_bootstrap.py tests/test_p0_06c4_recommendations_smoke_gate.py tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py`
  - result: `33 passed`
- `pytest -q -k "care or recommendation"`
  - result: `227 passed, 528 deselected`
- `pytest -q tests -k "patient and booking"`
  - result: `105 passed, 650 deselected`
- `pytest -q -k "patient or booking"`
  - result: `343 passed, 5 failed, 407 deselected`
  - classification: broader non-E1 acceptance selection; failures were outside the E1 targeted acceptance command
