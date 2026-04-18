# PR CC-2 Report — Care Catalog Import / Sync Baseline

## 1. Objective
Build the first operator-friendly care catalog authoring/sync baseline for DentFlow commerce:
- canonical workbook parser/validator,
- XLSX import path,
- Google Sheets sync baseline,
- DB replica upsert path,
- structured result reporting,
- minimal operator trigger surface,
- compatibility with existing care order/reservation runtime flows.

## 2. Docs Read
Read and applied this precedence stack (in order):
1. `README.md`
2. `docs/18_development_rules_and_baseline.md`
3. `docs/10_architecture.md`
4. `docs/12_repo_structure_and_code_map.md`
5. `docs/60_care_commerce.md`
6. `docs/shop/00_shop_readme.md`
7. `docs/shop/61_care_catalog_model.md`
8. `docs/shop/62_care_catalog_workbook_spec.md`
9. `docs/shop/63_recommendation_to_product_engine.md`
10. `docs/shop/64_care_patient_catalog_and_flow.md`
11. `docs/shop/66_care_stock_and_pickup_semantics.md`
12. `docs/shop/67_care_media_and_content_rules.md`
13. `docs/30_data_model.md`
14. `docs/35_event_catalog.md`
15. `docs/80_integrations_and_infra.md`
16. `docs/85_security_and_privacy.md`
17. `docs/90_pr_plan.md`
18. `docs/95_testing_and_launch.md`
19. `docs/report/PR_STACK_11A_REPORT.md`
20. `docs/report/PR_STACK_11A1_REPORT.md`
21. `docs/report/PR_STACK_11A2_REPORT.md`

## 3. Precedence Decisions
- Kept workbook/Sheets as catalog master-data authoring truth.
- Kept runtime order/reservation/issue truth DB-canonical.
- Preserved media as reference-only (`media_asset_id`), no binary upload in workbook path.
- Implemented validation-fail behavior for broken workbook structure (no silent best-effort).

## 4. Workbook Parsing Strategy
Implemented explicit canonical parser with:
- required tab enforcement,
- exact required header validation,
- row normalization for strings/booleans/integers/decimals,
- row-level validation errors,
- workbook-level fatal errors,
- reference checks across tabs (`sku`, `set_code`, `branch_id`, target link references).

## 5. XLSX Import Strategy
Implemented XLSX baseline as:
1. read `.xlsx` (OOXML zip/xml reader),
2. map sheet rows into canonical tab dictionaries,
3. validate/normalize through shared parser,
4. abort apply on fatal or validation errors,
5. apply upserts by stable keys,
6. return structured import result summary.

## 6. Google Sheets Sync Strategy
Implemented controlled Sheets baseline using explicit sheet URL/ID:
- download via Google export endpoint (`format=xlsx`),
- feed to same XLSX reader + parser + apply path,
- return structured failure on download/sync errors (`sheets_download_failed`).

Note: This is an export-based baseline, not full OAuth Sheets API writeback.

## 7. DB Replica / Upsert Strategy
Extended DB baseline schema and repository methods for catalog replica:
- `care_commerce.product_i18n`
- `care_commerce.recommendation_sets`
- `care_commerce.recommendation_set_items`
- `care_commerce.recommendation_links`
- `care_commerce.catalog_settings`

Upsert keys:
- products: `(clinic_id, sku)`
- i18n: `(care_product_id, locale)`
- availability: `(branch_id, care_product_id)`
- sets: `(clinic_id, set_code)`
- set_items: `(care_recommendation_set_id, care_product_id)`
- links: `(clinic_id, recommendation_type, target_kind, target_code)`
- settings: `(clinic_id, key)`

## 8. Source-of-Truth Integrity Notes
- Import updates baseline on-hand availability (`available_qty` from workbook `on_hand_qty`).
- Import does **not** overwrite runtime `reserved_qty` on availability upsert conflict.
- Free quantity remains runtime-derived in existing care service (`available_qty - reserved_qty`).
- Orders/reservations/issue/fulfill tables are not imported from workbook.

## 9. Media Compatibility Notes
- Parser/import supports `media_asset_id` as reference field in products tab.
- No media binary transport via workbook/sheets introduced.
- Existing bot/media ownership model remains unchanged.

## 10. Files Added
- `app/application/care_catalog_sync/__init__.py`
- `app/application/care_catalog_sync/models.py`
- `app/application/care_catalog_sync/parser.py`
- `app/application/care_catalog_sync/sheets.py`
- `app/application/care_catalog_sync/service.py`
- `app/application/care_catalog_sync/xlsx_reader.py`
- `scripts/sync_care_catalog.py`
- `tests/test_care_catalog_sync_cc2.py`
- `docs/report/PR_CC2_REPORT.md`

## 11. Files Modified
- `app/infrastructure/db/bootstrap.py`
- `app/infrastructure/db/care_commerce_repository.py`
- `app/application/care_commerce/service.py`
- `app/interfaces/bots/patient/router.py`
- `tests/test_care_commerce_stack11a.py`

## 12. Commands Run
- `find .. -name AGENTS.md -print`
- `rg --files | head -n 200`
- `sed -n ...` (docs and source inspection)
- `pytest -q tests/test_care_catalog_sync_cc2.py tests/test_care_commerce_stack11a.py`
- `pytest -q tests/test_recommendation_stack10a.py`

## 13. Test Results
- `tests/test_care_catalog_sync_cc2.py` passed.
- `tests/test_care_commerce_stack11a.py` passed.
- `tests/test_recommendation_stack10a.py` passed.

## 14. Known Limitations / Explicit Non-Goals
- No giant Telegram catalog editor built.
- No stock ledger/accounting/procurement/ERP subsystem.
- Google Sheets sync baseline is export-download based (not full API orchestration).
- No spreadsheet media binary management.
- No runtime order/reservation truth migration into workbook.

## 15. Readiness Assessment for Next Commerce PR
This PR establishes the catalog foundation needed for next commerce work:
- canonical authoring input path is now explicit,
- parser + validation + sync outcomes are auditable,
- catalog replica model exists in DB,
- patient/admin runtime flows remain compatible and can now consume catalog-type recommendation links as fallback.

Recommended next steps:
1. introduce richer operator visibility/history for sync runs,
2. add authenticated Google API mode for private sheets,
3. expand patient-facing narrow catalog UX on top of synced catalog content,
4. add localized content rendering from DB `product_i18n` in bot surfaces.
