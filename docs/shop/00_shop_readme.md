# Shop Documentation Package

> Detailed documentation package for the DentFlow care-commerce block.

## Purpose

This directory holds the detailed product, catalog, recommendation, and stock/pickup design for DentFlow commerce.

The root-level document `docs/60_care_commerce.md` remains the high-level overview.
This package holds the operational and product-level detail that should **not** be dumped into one giant file.

This keeps the wiki structured instead of turning it into a markdown landfill.

---

## Document map

### `61_care_catalog_model.md`
Defines the canonical product model:
- products
- localized product content
- recommendation sets / bundles
- recommendation-to-product links
- category and use-case structure
- product media references

### `62_care_catalog_workbook_spec.md`
Defines the operator workbook model for:
- XLSX import
- Google Sheets sync
- sheet tabs
- columns
- validation rules
- enum/value expectations
- source-of-truth rules for catalog authoring

### `63_recommendation_to_product_engine.md`
Defines how recommendations map to products:
- rule-based baseline
- doctor override
- trigger matrix
- recommendation sets
- product linkage strategy
- recommendation-driven care suggestions

### `64_care_patient_catalog_and_flow.md`
Defines patient-facing commerce behavior:
- recommendation-first discovery
- narrow catalog model
- category navigation
- product cards
- reserve/pickup flow
- repeat purchase baseline

### `66_care_stock_and_pickup_semantics.md`
Defines stock and pickup semantics:
- branch availability baseline
- free quantity semantics
- reservation rules
- preferred pickup branch + override
- issue / fulfill logic
- what lives in sheet vs DB

### `67_care_media_and_content_rules.md`
Defines:
- product media strategy
- media attach through bot
- content boundaries
- localization/content rules
- what should not be authored in code

---

## Source-of-truth reminder

### Authored in XLSX / Google Sheets
- products
- i18n labels and descriptions
- branch availability baseline
- recommendation links
- recommendation sets/bundles

### Canonical in DentFlow DB
- care orders
- care reservations
- issue / fulfill runtime truth
- active reserved quantity
- event emission

### Canonical in media layer
- product photos / video / attached media assets

---

## Product direction

DentFlow care-commerce is:

- recommendation-first
- narrow-catalog second
- clinically relevant
- branch-aware
- reservation-aware
- operator-friendly in authoring
- compact in Telegram UI

It is not:
- SIS store clone
- giant Telegram admin commerce panel
- warehouse/accounting subsystem

---

## Recommended authoring order

1. `61_care_catalog_model.md`
2. `62_care_catalog_workbook_spec.md`
3. `63_recommendation_to_product_engine.md`
4. `64_care_patient_catalog_and_flow.md`
5. `66_care_stock_and_pickup_semantics.md`
6. `67_care_media_and_content_rules.md`

That order defines the model first, then the authoring surface, then the engine, then the UX and stock semantics.

---

## Current status

This package is intentionally introduced before further commerce coding to prevent Codex from improvising product logic inside the codebase.

The next recommended detailed document is:

- `docs/shop/61_care_catalog_model.md`
