# P0-06D2B1 Care Catalog Demo Seed Report

## Summary
- Added a dedicated care catalog demo seed payload in JSON workbook-tab structure at `seeds/care_catalog_demo.json`.
- Added JSON import support to `CareCatalogSyncService` (`import_workbook(...)`, `import_json(...)`) without changing the existing XLSX/Google Sheets paths.
- Extended CLI sync tool with `json` mode:
  - `python scripts/sync_care_catalog.py --clinic-id clinic_main json --path seeds/care_catalog_demo.json`
- Added audit/loader tests that validate parseability, readiness constraints, recommendation mappings, settings, and service/CLI JSON import path.
- Kept patient recommendations and care orders/reservations out of this scope (deferred to D2B2).

## Files changed
- `seeds/care_catalog_demo.json` (new)
- `app/application/care_catalog_sync/service.py`
- `scripts/sync_care_catalog.py`
- `tests/test_p0_06d2b1_care_catalog_demo_seed.py` (new)
- `docs/92_seed_data_and_demo_fixtures.md`
- `docs/report/P0_06D2B1_CARE_CATALOG_DEMO_SEED_REPORT.md` (new)

## Seed file structure
`seeds/care_catalog_demo.json` contains workbook tabs compatible with `parse_catalog_workbook(...)`:
- `products`
- `product_i18n`
- `branch_availability`
- `recommendation_sets`
- `recommendation_set_items`
- `recommendation_links`
- `settings`

## Product/category coverage
- Total products: 7
- Active products: 6
- Inactive product: 1 (`SKU-OLD-BRUSH`)
- Required categories covered:
  - `toothbrush`
  - `toothpaste`
  - `floss`
  - `rinse`
  - `irrigator`
  - `remineralization`
- Required demo SKUs included:
  - `SKU-BRUSH-SOFT`
  - `SKU-PASTE-SENSITIVE`
  - `SKU-FLOSS-WAXED`
  - `SKU-RINSE-CHX`
  - `SKU-IRRIGATOR-TRAVEL`
  - `SKU-GEL-REMIN`

## RU/EN i18n coverage
- Every active product has both `ru` and `en` i18n rows.
- Active product i18n rows include non-empty `title` and `description`.
- i18n payload also includes `short_label`, `justification_text`, and `usage_hint` for active items.

## Branch availability coverage
For `branch_central`:
- In-stock (>0): 5 products
- Low-stock example: `SKU-RINSE-CHX` (`on_hand_qty=2`, threshold=2)
- Out-of-stock: `SKU-GEL-REMIN` (`on_hand_qty=0`)
- `availability_enabled=true` on all active demo rows
- Preferred pickup row present (`SKU-BRUSH-SOFT`)

## Recommendation set/link coverage
- Recommendation sets: 2
  - `set_daily_hygiene`
  - `set_post_treatment`
- Recommendation set items: 6
- Recommendation links: 4
  - `aftercare_hygiene -> set_daily_hygiene`
  - `sensitivity -> SKU-PASTE-SENSITIVE`
  - `post_treatment -> set_post_treatment`
  - `gum_care -> SKU-IRRIGATOR-TRAVEL`
- Coverage is catalog mapping only (no patient recommendation records).

## Settings coverage
- `care.default_pickup_branch_id = branch_central`
- `care.demo_catalog_version = p0-06d2b1`
- `care.currency = EUR`

## JSON import path
### Service
Added:
- `import_workbook(...)`
- `import_json(...)`

`import_json(...)` loads JSON and routes through `_validate_and_apply(...)` with `source="json"`.

### CLI behavior
`scripts/sync_care_catalog.py` now supports:
- `xlsx` (existing, unchanged)
- `sheets` (existing, unchanged)
- `json` (new)

No router split, no bot UI changes, no schema changes.

## Tests run with exact commands/results
1. `python -m compileall app tests`
   - pass
2. `pytest -q tests/test_p0_06d2b1_care_catalog_demo_seed.py`
   - pass (`7 passed`)
3. `pytest -q tests/test_care_catalog_sync_cc2.py`
   - pass (`6 passed`)
4. `pytest -q tests/test_p0_06d2a2_core_demo_seed_pack.py`
   - pass (`7 passed`)
5. `pytest -q tests/test_p0_06d2a1_seed_date_shift_foundation.py`
   - pass (`5 passed`)
6. `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py`
   - pass (`9 passed`)
7. `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py`
   - pass (`3 passed`)
8. `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py`
   - pass (`4 passed`)
9. `pytest -q tests -k "care or recommendation"`
   - pass (`211 passed, 519 deselected, 2 warnings`)
10. `pytest -q tests -k "patient and booking"`
    - pass (`105 passed, 625 deselected, 2 warnings`)

## Grep checks with exact commands/results
1. `rg "SKU-BRUSH-SOFT|SKU-PASTE-SENSITIVE|SKU-IRRIGATOR-TRAVEL|set_daily_hygiene|aftercare_hygiene|care.default_pickup_branch_id" seeds tests docs scripts app`
   - Result: expected demo catalog objects present in seed/tests/docs/app references.

2. `rg "json.*sync_care_catalog|import_json|import_workbook" scripts app tests`
   - Result: JSON import path present in service, script, and tests.

3. `rg "care_order|care_orders|recommendations\"|recommendation_id" seeds/care_catalog_demo.json`
   - Result: no matches (exit code 1).
   - Interpretation: no patient recommendation records and no care order records in `care_catalog_demo.json`; `recommendation_links` remain catalog mappings.

## Defects found/fixed
- While adding CLI JSON mode smoke test, direct use of `DatabaseConfig()` in `_run(...)` required monkeypatching `DatabaseConfig` to avoid environment DSN dependency in isolated unit test.
- No production defect in import/sync logic observed; existing CC2 parser/service paths remained stable.

## Explicit carry-forward for D2B2
Deferred intentionally to D2B2:
- patient recommendations;
- direct/manual recommendation product targets if extra mapping forms are needed;
- care orders/reservations seed records.

## GO / NO-GO recommendation for D2B2
- **GO**.
- D2B1 acceptance baseline is met:
  - parseable/loadable care catalog demo JSON seed,
  - required product/i18n/availability/recommendation mapping/settings coverage,
  - JSON import path added without breaking XLSX/Sheets sync,
  - requested regressions passing.
