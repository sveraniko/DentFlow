# P0-06E3 Matrix

Generated: 2026-04-28 (UTC)

## Templates
- blank reference CSVs exist: **yes**
- blank patient CSVs exist: **yes**
- demo CSVs exist: **yes**
- README exists: **yes**
- manifest exists: **yes**

## Headers/manifest
- headers match manifest: **yes**
- manifest import_status=template_only: **yes**
- all required tabs listed: **yes**

## Demo data
- doctors from D2A2 present: **yes**
- services from D2A2 present: **yes**
- access codes present: **yes**
- patients present: **yes**
- telegram contacts 3001/3002/3004 present: **yes**
- preferences present: **yes**

## Reference validation
- doctor branch refs valid: **yes**
- access code doctor refs valid: **yes**
- access code service scope refs valid: **yes**
- patient contact refs valid: **yes**
- patient preference refs valid: **yes**

## Docs/truth boundary
- template-only documented: **yes**
- no false active sync claim: **yes**
- future import command marked future: **yes**
- seed_demo current path documented: **yes**

## Regression
- E3 tests: **pass**
- E2 tests: **pass**
- E1 tests: **pass**
- D2C tests: **pass**
- C4/B4 smoke: **pass**
- care or recommendation: **227 passed**
- patient and booking: **105 passed**

## Command log
- `pytest -q tests/test_p0_06e3_reference_patient_sheets_templates.py`
  - result: `8 passed`
- `pytest -q tests/test_p0_06e2_google_calendar_runbook_config.py`
  - result: `11 passed`
- `pytest -q tests/test_p0_06e1_care_catalog_sheets_template.py`
  - result: `5 passed`
- `pytest -q tests/test_p0_06d2c_seed_demo_bootstrap.py`
  - result: `9 passed`
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py`
  - result: `12 passed`
- `pytest -q -k "care or recommendation"`
  - result: `227 passed, 547 deselected, 2 warnings`
- `pytest -q tests -k "patient and booking"`
  - result: `105 passed, 669 deselected, 2 warnings`
