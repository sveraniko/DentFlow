# P0-06E2 Matrix

Generated: 2026-04-28 (UTC)

## Runbook
- google_calendar_projection_runbook.md exists: **yes**
- one-way mirror documented: **yes**
- no Calendar-as-truth documented: **yes**
- commands documented: **yes**
- troubleshooting documented: **yes**

## Env/config
- env keys in .env.example: **yes**
- settings parse keys: **yes**
- disabled gateway tested: **yes**
- missing credentials tested: **yes**
- real gateway construction without live API tested: **yes**
- in-memory gateway tested: **yes**

## Admin/operator
- /admin_calendar documented/tested: **yes**
- /admin_integrations documented/tested: **yes**
- process_outbox_events documented: **yes**
- retry_google_calendar_projection documented: **yes**

## Safety
- no live Google API in tests: **yes**
- no two-way sync claim: **yes**
- credentials not committed: **yes**

## Regression
- E2 tests: **pass**
- projection tests: **pass**
- admin calendar/integrations: **pass**
- E1 tests: **pass**
- C4/B4 smoke: **pass**
- care or recommendation: **227 passed**
- patient and booking: **105 passed**

## Command log
- `pytest -q tests/test_p0_06e2_google_calendar_runbook_config.py`
  - result: `11 passed`
- `pytest -q tests/test_google_calendar_projection_aw5.py tests/test_google_calendar_projection_aw5a.py`
  - result: `11 passed`
- `pytest -q tests/test_admin_calendar_awareness_s13a.py tests/test_admin_integrations_s13c.py`
  - result: `11 passed`
- `pytest -q tests/test_p0_06e1_care_catalog_sheets_template.py tests/test_p0_06d2b1_care_catalog_demo_seed.py tests/test_p0_06d2c_seed_demo_bootstrap.py tests/test_p0_06c4_recommendations_smoke_gate.py tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py`
  - result: `33 passed`
- `pytest -q -k "care or recommendation"`
  - result: `227 passed, 539 deselected, 2 warnings`
- `pytest -q tests -k "patient and booking"`
  - result: `105 passed, 661 deselected, 2 warnings`
