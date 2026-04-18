# Care Commerce

> High-level overview of the DentFlow care-commerce block.

## Purpose

This document is the **entry point** for the care-commerce subsystem.

Its role is not to fully describe every product, rule, stock behavior, or patient flow in one giant file.
Its role is to define:

- why care-commerce exists in DentFlow;
- what business problem it solves;
- how it relates to recommendations, booking, charting, and owner analytics;
- where the detailed commerce documentation lives.

This document is intentionally concise.
Detailed design for catalog, workbook, recommendation mapping, patient catalog UX, and stock/pickup semantics is moved into the dedicated `docs/shop/` package.

---

## Care-commerce thesis

DentFlow care-commerce is **not** a generic store and **not** a copy of SIS inside a clinic bot.

It exists to solve a specific problem:

- the clinic recommends clinically relevant care products;
- the patient can conveniently reserve or purchase them;
- the clinic can operationally manage pickup and issuance;
- the owner can measure uptake and attach-rate;
- all of this happens without turning DentFlow into a bloated retail ERP.

Care-commerce is therefore:

- recommendation-first;
- medically relevant;
- branch-aware;
- reservation-aware;
- compact in UI;
- maintainable by operators through structured catalog authoring, not giant Telegram admin panels.

---

## Scope of the care-commerce block

Care-commerce in DentFlow covers:

- product catalog baseline;
- recommendation-to-product linkage;
- recommendation sets / product bundles;
- patient-facing narrow catalog and recommendation-driven entry;
- care order lifecycle;
- reservation lifecycle;
- pickup and issuance flow;
- baseline branch availability;
- catalog authoring via XLSX / Google Sheets;
- product media attached through bot/media layer.

It does **not** attempt to cover:

- full inventory accounting;
- procurement/suppliers;
- warehouse transfers;
- logistics/shipping platform;
- large ecommerce storefront behavior;
- financial ERP.

---

## Architectural position

Care-commerce is a separate bounded context.

### It depends on:
- `core_patient` for canonical patient truth;
- `booking` for booking context and patient journey hooks;
- `clinical` for recommendation context;
- `recommendation` for patient-specific recommendation truth;
- `access_identity` and role rules for admin/doctor actions;
- `policy_config` for baseline behavior;
- `media_docs` for media asset references;
- `owner_views` and analytics projections for later reporting.

### It must remain distinct from:
- recommendation truth;
- booking truth;
- stock/accounting systems.

---

## Source-of-truth model

The care-commerce block uses a **hybrid source-of-truth model**.

### Catalog master data authoring truth
Catalog master data is authored through:

- XLSX import
- Google Sheets sync

This includes:
- products
- localized text
- branch availability baseline (`on_hand_qty`)
- recommendation links
- recommendation sets / product bundles

### Runtime operational truth
DentFlow DB remains canonical for:
- care orders
- care reservations
- reservation release/consume
- issue / fulfill state
- event emission
- derived stock-free quantity

### Media truth
Product media remains canonical through the DentFlow bot/media path, not through spreadsheet files as binary truth.

---

## Patient product discovery model

Patient product discovery in DentFlow is:

### Primary:
**recommendation-first**
- doctor recommendation
- rule-based recommendation
- encounter/booking trigger

### Secondary:
**narrow catalog**
- categories like brushes, irrigators, aftercare, ortho care, pediatric care
- not a giant open-ended storefront
- still available so the patient can return later and buy without waiting for a fresh recommendation

This keeps the experience both practical and bounded.

---

## Stock and pickup model

The stock baseline is intentionally minimal.

### In XLSX / Sheets
Authoring layer holds:
- `on_hand_qty`
- availability enabled/disabled
- low stock threshold
- preferred pickup hints

### In DentFlow DB
Runtime layer holds:
- reservations
- reserved quantity
- issue / fulfill state

### Effective free quantity
`free_qty = on_hand_qty_from_catalog - active_reserved_qty_in_db`

This gives the clinic a usable stock baseline without turning the project into a warehouse system.

---

## Documentation package

All detailed care-commerce docs live in:

- `docs/shop/00_shop_readme.md`

That package is the authoritative design space for:
- catalog model
- workbook specification
- recommendation mapping
- patient-facing catalog behavior
- stock and pickup semantics
- media/content rules

This file should stay high-level.
Detailed decisions belong in `docs/shop/`.

---

## Implementation note

Care-commerce must not be implemented as a giant Telegram admin wizard.

Operator-friendly catalog authoring belongs in:
- XLSX
- Google Sheets

Telegram remains the right place for:
- patient reserve/pickup flow
- admin operational actions
- media attach
- compact stock/order handling where frequent operational action is useful

That is the intentional product balance.

---

## Current status

This file is now the overview document for the care-commerce block.

Detailed next-step docs are tracked in `docs/shop/`.
