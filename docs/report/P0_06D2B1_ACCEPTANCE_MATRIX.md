# P0-06D2B1 matrix

Date: 2026-04-28

## Seed file
- care_catalog_demo.json exists: **yes**
- required tabs exist: **yes**
- parser accepts it: **yes**

## Products
- products >= 6: **yes**
- active products >= 5/6: **yes**
- categories covered: **yes**
- unique SKU/product_code: **yes**
- price/currency present: **yes**

## I18n
- RU rows for active products: **yes**
- EN rows for active products: **yes**
- title/description non-empty: **yes**
- usage_hint present: **yes**

## Availability
- branch_central rows: **yes**
- in-stock products >= 4: **yes**
- low-stock case exists: **yes**
- out-of-stock case exists: **yes**
- preferred pickup exists: **yes**

## Recommendation catalog mappings
- sets >= 2: **yes**
- set items valid: **yes**
- links >= 4: **yes**
- required recommendation types covered: **yes**

## Loader
- JSON import path exists: **yes**
- XLSX/sheets behavior unchanged: **yes**
- sync service upserts products/i18n/availability/sets/links/settings: **yes**

## Regression
- D2A2: **pass**
- D2A1: **pass**
- C4 recommendations smoke: **pass**
- B4 care smoke: **pass**
- P0-05C smoke: **pass**
- care or recommendation: **211 passed**
- patient and booking: **105 passed**
