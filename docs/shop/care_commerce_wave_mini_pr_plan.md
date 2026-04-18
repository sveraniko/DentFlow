# Care Commerce Wave — Mini PR Plan

## Goal

Дожать commerce-layer DentFlow до вменяемой, канонической и кодопригодной модели,
где:
- catalog authoring делается через XLSX / Google Sheets,
- recommendation engine мапит контекст в products/sets,
- patient видит recommendation-first narrow catalog,
- stock/pickup semantics четко определены,
- runtime truth orders/reservations не утекает в spreadsheet.

---

## Wave structure

### PR CC-1 — Docs sync + canonical workbook seed
**Deliverables**
- sync `docs/60_care_commerce.md`
- add/update `docs/shop/*`
- add canonical workbook seed (`dentflow_care_catalog_canonical_workbook_v1.xlsx`)

**Why**
- фиксируем модель до нового кодинга
- убираем свободную трактовку Codex

---

### PR CC-2 — Catalog import/sync baseline
**Deliverables**
- XLSX import for care catalog workbook
- Google Sheets sync for same workbook structure
- validation/reporting
- DB replica sync for:
  - products
  - product_i18n
  - recommendation_sets
  - recommendation_set_items
  - recommendation_links
  - branch_availability baseline

**Why**
- убираем Telegram admin hell
- получаем operator-friendly authoring

---

### PR CC-3 — Recommendation-to-product runtime alignment
**Deliverables**
- runtime resolver for recommendation_type -> set/product
- doctor override path
- patient recommendation-linked product rendering
- safe patient recommendation resolution

**Why**
- recommendation layer должен реально кормить commerce flow

---

### PR CC-4 — Patient narrow catalog + branch-aware reserve flow
**Deliverables**
- recommendation-first patient path
- narrow `Care / Уход` catalog path
- compact category/product cards
- preferred branch + explicit override
- reservation/order creation from real catalog data

**Why**
- делаем commerce usable for patient, not just architecturally pretty

---

### PR CC-5 — Stock baseline and pickup operational hardening
**Deliverables**
- branch availability baseline from workbook/sync
- free_qty runtime calculation
- reservation consume/release semantics
- admin ready / issue / fulfill coherence
- compact availability statuses

**Why**
- reserve must mean reserve
- pickup must be operationally honest

---

### PR CC-6 — Media/content operational finish
**Deliverables**
- bot media attach flow preserved
- product media reference wiring
- no hardcoded patient-facing product copy in code
- localized content fallback discipline

**Why**
- media/content chaos must be blocked before scaling

---

## Exit criteria for the wave

Wave is considered complete when:

- commerce docs package is canonical and synced
- workbook structure is accepted and usable
- XLSX import works
- Google Sheets sync works
- product / i18n / set / link / availability data sync into DB coherently
- recommendation-driven commerce flow works
- narrow patient catalog works
- branch-aware reserve/pickup flow works
- reservation/stock baseline is operationally coherent
- no giant product admin panel in Telegram exists

---

## Explicit non-goals for the wave

- no warehouse ERP
- no supplier/procurement layer
- no inventory accounting ledger
- no giant ecommerce storefront
- no care-commerce AI layer
- no delivery logistics platform

---

## Recommended next stack after this wave

After this commerce wave is accepted, move to:

- `12A — Document / 043 Export Baseline`

because then:
- chart truth is structured,
- recommendation/care layers are coherent,
- and export can use stable canonical data instead of half-made commerce logic.
