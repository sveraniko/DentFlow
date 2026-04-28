# Care Catalog Google Sheets Template Pack

This folder contains an operator-facing template pack for care catalog sync.

## Included files

### Blank templates (headers only)
- `products.csv`
- `product_i18n.csv`
- `branch_availability.csv`
- `recommendation_sets.csv`
- `recommendation_set_items.csv`
- `recommendation_links.csv`
- `settings.csv`

### Filled demo templates (from `seeds/care_catalog_demo.json`)
- `demo_products.csv`
- `demo_product_i18n.csv`
- `demo_branch_availability.csv`
- `demo_recommendation_sets.csv`
- `demo_recommendation_set_items.csv`
- `demo_recommendation_links.csv`
- `demo_settings.csv`

## Required Google Sheets tab names

When preparing a Google Sheet for sync, tab names must match exactly:

- `products`
- `product_i18n`
- `branch_availability`
- `recommendation_sets`
- `recommendation_set_items`
- `recommendation_links`
- `settings`

## What each tab means

- `products`: base care product catalog rows (SKU, status, category, pricing, channel support flags).
- `product_i18n`: localized title/description and optional recommendation text per SKU+locale.
- `branch_availability`: per-branch availability baseline and inventory hints per SKU.
- `recommendation_sets`: reusable recommendation bundles (set metadata and sort order).
- `recommendation_set_items`: SKU composition of recommendation sets.
- `recommendation_links`: mappings from recommendation_type to product/set targets.
- `settings`: optional key/value catalog settings.

## Google Sheets setup workflow

1. Create a new Google Sheet.
2. Create tabs with the exact names listed above.
3. Open each CSV in this folder and paste/import into the matching tab.
4. Ensure the sheet is shareable/exportable for the current sync mode (see access model below).
5. Run sync through CLI or admin command.

## Sync commands

### CLI

```bash
python scripts/sync_care_catalog.py --clinic-id clinic_main json --path seeds/care_catalog_demo.json
python scripts/sync_care_catalog.py --clinic-id clinic_main xlsx --path <path>
python scripts/sync_care_catalog.py --clinic-id clinic_main sheets --sheet <url_or_id>
```

### Admin bot

```text
/admin_catalog_sync sheets <url_or_id>
/admin_catalog_sync xlsx <server_local_path>
```

## Access model (current)

- If the Sheets downloader uses the public/export URL path, the Google Sheet must be accessible for export by the sync runner.
- Private OAuth/service-account-only mode is a future hardening task unless explicitly configured in runtime.

## Validation rules to expect

Typical validation behavior in sync/import:

- unknown `branch_id` fails validation;
- duplicate product SKU/code rows fail validation;
- missing `product_i18n` title/required localized fields fail validation;
- `branch_availability.branch_id` must map to an existing known branch;
- invalid booleans/integers/ranks fail row validation.

## Update workflow (operator runbook)

1. Edit catalog data in Google Sheets tabs.
2. Run catalog sync (`sheets`, or `xlsx/json` for local workflows).
3. Check sync result summary in admin output/logs for fatal/validation errors.
4. After successful sync, patient-facing catalog/recommendation surfaces read updated data from DB.

## Notes

- This template pack targets care catalog/product authoring only.
- Patient/doctor/service sync templates are intentionally out of scope in this pack.
