# P0-06E1 — Care Catalog Google Sheets Template + Sync Runbook Report

## Summary

Implemented a local Google Sheets-ready care catalog template pack, demo CSV pack derived from `seeds/care_catalog_demo.json`, operator runbook documentation, compatibility tests, and regression verification for existing care/recommendation seed and smoke lanes.

## Files changed

- Added template pack directory and files:
  - `docs/templates/google_sheets/care_catalog/README.md`
  - `docs/templates/google_sheets/care_catalog/products.csv`
  - `docs/templates/google_sheets/care_catalog/product_i18n.csv`
  - `docs/templates/google_sheets/care_catalog/branch_availability.csv`
  - `docs/templates/google_sheets/care_catalog/recommendation_sets.csv`
  - `docs/templates/google_sheets/care_catalog/recommendation_set_items.csv`
  - `docs/templates/google_sheets/care_catalog/recommendation_links.csv`
  - `docs/templates/google_sheets/care_catalog/settings.csv`
  - `docs/templates/google_sheets/care_catalog/demo_products.csv`
  - `docs/templates/google_sheets/care_catalog/demo_product_i18n.csv`
  - `docs/templates/google_sheets/care_catalog/demo_branch_availability.csv`
  - `docs/templates/google_sheets/care_catalog/demo_recommendation_sets.csv`
  - `docs/templates/google_sheets/care_catalog/demo_recommendation_set_items.csv`
  - `docs/templates/google_sheets/care_catalog/demo_recommendation_links.csv`
  - `docs/templates/google_sheets/care_catalog/demo_settings.csv`
- Updated docs:
  - `docs/92_seed_data_and_demo_fixtures.md`
  - `docs/80_integrations_and_infra.md`
- Added tests:
  - `tests/test_p0_06e1_care_catalog_sheets_template.py`

## Template files created

Blank tab CSVs were created with header-only rows and exact parser-compatible column names for:

- products
- product_i18n
- branch_availability
- recommendation_sets
- recommendation_set_items
- recommendation_links
- settings

## Demo CSV files created

Demo tab CSVs were created from `seeds/care_catalog_demo.json` for all seven tabs:

- demo_products
- demo_product_i18n
- demo_branch_availability
- demo_recommendation_sets
- demo_recommendation_set_items
- demo_recommendation_links
- demo_settings

## Tab/column compatibility

- Parser header contract source: `app/application/care_catalog_sync/parser.py` (`_HEADERS`).
- Template headers are validated in `tests/test_p0_06e1_care_catalog_sheets_template.py` against parser headers and seed row keys.
- Required tab set is enforced in tests for all seven tabs.

## Demo CSV round-trip parse result

`tests/test_p0_06e1_care_catalog_sheets_template.py` verifies that demo CSV workbook rows parse with:

- `parse_catalog_workbook(workbook=..., known_branch_ids={"branch_central"}, source="csv_template")`
- no fatal errors
- no validation errors
- products count >= 6
- branch availability exists
- recommendation links exist

Result: PASS.

## Google Sheets setup runbook

Runbook added at:

- `docs/templates/google_sheets/care_catalog/README.md`

Includes:

- tab purpose and required tab names;
- Sheet creation/paste workflow;
- access/export expectations for current mode;
- validation notes and operator update workflow.

## CLI/admin sync commands

Documented commands:

- `python scripts/sync_care_catalog.py --clinic-id clinic_main json --path seeds/care_catalog_demo.json`
- `python scripts/sync_care_catalog.py --clinic-id clinic_main xlsx --path <path>`
- `python scripts/sync_care_catalog.py --clinic-id clinic_main sheets --sheet <url_or_id>`
- `/admin_catalog_sync sheets <url_or_id>`
- `/admin_catalog_sync xlsx <server_local_path>`

## Access model

Documented explicitly:

- Current simple mode expects sheet exportability/shareability for downloader path.
- Private OAuth/service-account-only mode remains a future hardening task unless deployment already supports it.

## Tests run with exact commands/results

- `python -m compileall app tests scripts` → PASS
- `pytest -q tests/test_p0_06e1_care_catalog_sheets_template.py` → PASS (5 passed)
- `pytest -q tests/test_p0_06d2d2_db_backed_application_reads.py` → SKIP (1 skipped; DB lane env dependent)
- `pytest -q tests/test_p0_06d2d1_seed_demo_db_load_smoke.py` → PASS/SKIP (2 passed, 1 skipped; DB lane env dependent)
- `pytest -q tests/test_p0_06d2c_seed_demo_bootstrap.py` → PASS (9 passed)
- `pytest -q tests/test_p0_06d2b1_care_catalog_demo_seed.py` → PASS (7 passed)
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py` → PASS (9 passed)
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` → PASS (3 passed)
- `pytest -q tests -k "care or recommendation"` → PASS (227 passed, 528 deselected)
- `pytest -q tests -k "patient and booking"` → PASS (105 passed, 650 deselected)

## Grep checks with exact commands/results

- `rg "care_catalog_google|admin_catalog_sync sheets|sync_care_catalog.py" docs/templates docs scripts tests`
  - Result: template docs/tests and integration docs include sync command references.
- `rg "products.csv|product_i18n.csv|branch_availability.csv|recommendation_links.csv" docs/templates/google_sheets/care_catalog tests`
  - Result: README lists required CSV filenames; template coverage is present in docs/tests.
- `rg "Google Sheets" docs/92_seed_data_and_demo_fixtures.md docs/80_integrations_and_infra.md docs/templates/google_sheets/care_catalog/README.md`
  - Result: all target docs mention Google Sheets template/sync context.

## Defects found/fixed

- Added missing operator-facing template pack for care catalog Sheets workflow.
- Added explicit runbook coverage for tab names, sync command paths, and access model.
- Added parser-contract regression tests to prevent drift between template headers and importer expectations.

## Carry-forward

- P0-06E2: Calendar integration runbook/config verification.
- P0-06E3: Patients/doctors/services Sheets templates + manual import docs.

## GO / NO-GO for E2

- Recommendation: **GO**.
- Rationale:
  - P0-06E1 acceptance scope is implemented (templates + demo pack + runbook + tests + docs + report).
  - Existing care/recommendation smoke/regression lanes pass.
  - DB-dependent lanes were explicitly skipped where environment dependent and documented.
