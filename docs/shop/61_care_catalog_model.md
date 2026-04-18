# Care Catalog Model

> Canonical product and catalog model for the DentFlow care-commerce block.

## 1. Purpose

This document defines the **canonical product/catalog model** for DentFlow care-commerce.

Its role is to make the commerce layer explicit before further coding continues.

This document answers:

- what a care product is in DentFlow;
- what belongs to the catalog and what does not;
- how products, localized content, recommendation sets, recommendation links, and branch availability relate to one another;
- what is authored in XLSX / Google Sheets;
- what remains canonical in DentFlow DB at runtime;
- what must stay out of scope to avoid turning the subsystem into an ERP mutant.

This document is foundational for the entire `docs/shop/` package.

It should be read before:

- `62_care_catalog_workbook_spec.md`
- `63_recommendation_to_product_engine.md`
- `64_care_patient_catalog_and_flow.md`
- `66_care_stock_and_pickup_semantics.md`
- `67_care_media_and_content_rules.md`

---

## 2. Product thesis

DentFlow care catalog is **not** a generic online store catalog.

It exists for a bounded clinic use case:

- the clinic recommends medically relevant care products;
- the patient can reserve/pick up or purchase them in a bounded, practical flow;
- the clinic can maintain the product master data without a giant Telegram admin panel;
- branch-aware stock baseline and reservation logic remain possible;
- recommendation logic can map to products and product sets cleanly.

Therefore the catalog must be:

- recommendation-friendly;
- operator-friendly;
- localized;
- branch-aware;
- compact enough for Telegram UI;
- separate from runtime order/reservation truth.

---

## 3. Scope of the catalog model

The catalog model covers:

- products;
- product localized content;
- product categories;
- use-case tags;
- recommendation sets / bundles;
- recommendation-to-product links;
- branch availability baseline;
- product media references.

The catalog model does **not** cover:

- orders;
- reservations;
- issue / fulfill state;
- active reserved quantity;
- stock accounting;
- supplier/procurement;
- shipment/delivery operations;
- financial/accounting truth.

Those belong elsewhere.

---

## 4. Source-of-truth model

DentFlow care catalog uses a hybrid truth model.

## 4.1 Catalog authoring truth
Catalog master data is authored through:

- XLSX import
- Google Sheets sync

This includes:
- product rows
- localized labels and descriptions
- branch availability baseline (`on_hand_qty`)
- recommendation links
- recommendation sets / bundles

## 4.2 Runtime operational truth
DentFlow DB remains canonical for:
- care orders
- care reservations
- issue / fulfill truth
- active reserved quantity
- event emission
- derived free quantity

## 4.3 Media truth
Product media is canonical in the DentFlow media/bot layer, even if sheet/XLSX stores a media reference field.

A spreadsheet may carry:
- `media_asset_id`
- `media_ref`
- `cover_image_ref`

But it is not the place where product media binaries “live”.

---

## 5. Canonical product model

A care product is the smallest commercial unit exposed to the patient/admin runtime flow.

## 5.1 Product identity

Each product must have:

- stable internal ID
- stable operator-visible code / SKU
- canonical clinic association
- product status
- product category
- use-case context
- pricing baseline
- pickup capability flags

### Required identity fields
- `care_product_id`
- `clinic_id`
- `sku`
- `product_code` (may equal SKU if no separate distinction is needed)
- `status`
- `category`
- `use_case_tag`
- `price_amount`
- `currency_code`
- `pickup_supported`
- `delivery_supported`
- `sort_order`

### Notes
- `sku` must remain stable across sync/import cycles.
- `product_code` may be omitted if SKU is sufficient, but if both exist their semantics must be explicit.
- `status` must be bounded and not free-text chaos.

---

## 6. Product status model

Recommended bounded status set:

- `active`
- `inactive`
- `archived`

Optional:
- `draft`
- `hidden`

### Recommended baseline usage
For simplicity, DentFlow baseline should use:
- `active`
- `inactive`
- `archived`

where:

### `active`
Product may appear in recommendation/catalog flow.

### `inactive`
Product exists historically but should not appear in new recommendation/catalog flow.

### `archived`
Long-term non-operational state. Rarely needed in patient flow.

Do not invent ten flavors of “temporarily semi-active with maybe seasonal context”.

---

## 7. Product category model

Category is needed for patient-facing narrow catalog UX and operator clarity.

Recommended baseline categories are bounded and human-useful.

Examples:
- `toothbrush`
- `toothpaste`
- `irrigator`
- `floss_interdental`
- `post_op_care`
- `ortho_care`
- `pediatric_care`
- `gum_care`
- `bundle`

These may evolve, but category must stay:
- bounded
- operator-friendly
- patient-friendly
- stable enough for filtering and presentation

This is not a marketplace taxonomy war.

---

## 8. Use-case tag model

`use_case_tag` is not the same as category.

Category answers:
- what kind of product is this?

Use-case tag answers:
- in what recommendation / clinical context is this product useful?

Examples:
- `aftercare_hygiene`
- `orthodontic_support`
- `post_op_soft`
- `periodontal_support`
- `sensitivity_support`
- `child_first_visit`
- `daily_maintenance`

A product may have one primary use-case tag in baseline.
Future expansion may support multiple tags if necessary, but baseline can stay simpler.

Use-case tags are critical for recommendation mapping.

---

## 9. Localized product content model

Products must support localized patient-facing text.

Localized content does not belong in hardcoded code strings.

### Required localized content fields per locale
- `title`
- `description`
- `short_label` (optional but highly useful)
- `justification_text` (optional for recommendation context)
- `usage_hint` (optional later)

At baseline, localized content should support:
- `ru`
- `en`

And be extensible later to:
- `ka`
- `pl`
and beyond.

### Important rule
If a product is patient-facing, its title must not be hidden in code or only in one language.

---

## 10. Product media reference model

A product may have media references such as:
- cover image
- gallery image
- short video
- attachment media

But catalog authoring and media binary handling are separate concerns.

### Catalog may carry:
- `media_asset_id`
- `cover_media_asset_id`
- `video_media_asset_id`
- `media_ref_code`

### Runtime/media truth lives in:
- DentFlow media layer
- bot upload path
- media registry

This allows:
- operator-driven structured catalog
- bot-friendly media attachment
without trying to upload media into Sheets like savages.

---

## 11. Recommendation set / bundle model

This is one of the most important parts of the catalog model.

A recommendation set is a named group of products used to:
- simplify doctor/manager recommendation work;
- support rule-based recommendation mapping;
- avoid typing SKU lists every time;
- keep recommendation logic human-readable.

### Example set codes
- `aftercare_hygiene_basic`
- `ortho_basic`
- `post_op_soft`
- `periodontal_support`
- `child_daily_care`

### Required fields
- `set_code`
- `status`
- `title_key` or localized title fields
- `description_key` or localized description fields
- `product_codes`
- `sort_order`

### Notes
- `product_codes` may be represented in workbook as delimited codes for authoring convenience.
- In DB/runtime this may be normalized via link table if needed.
- Sets must remain explicit, not hidden in doctor memory or message templates.

A set is not an order.
A set is a recommendation/catalog construct.

---

## 12. Recommendation-to-product linkage model

There are two useful linkage levels:

## 12.1 Recommendation type -> product
Example:
- `aftercare` -> certain products
- `orthodontic_support` -> certain products

## 12.2 Recommendation type -> set
Example:
- `aftercare_hygiene` -> `aftercare_hygiene_basic`
- `post_op_soft` -> `post_op_soft`

The second is often more operator-friendly.

### Baseline recommendation linkage should support:
- `recommendation_type`
- `target_kind` (`product` or `set`)
- `target_code`
- `relevance_rank`
- `justification_key` or localized justification text
- `active`

This allows:
- rule-based suggestion
- doctor override
- recommendation-driven patient flow

---

## 13. Branch availability baseline model

This is where catalog meets real clinic operations.

Branch availability baseline must answer:
- is this product offered in this branch?
- what is baseline on-hand quantity?
- what is low-stock threshold?
- is this the preferred pickup branch?

### Required baseline fields
- `branch_id`
- `sku`
- `on_hand_qty`
- `availability_enabled`
- `low_stock_threshold`
- `preferred_pickup`

### Runtime note
This is **not** the full stock truth.

Runtime free quantity is derived from:
`on_hand_qty - active_reserved_qty_in_db`

This separation is intentional and correct.

---

## 14. Baseline availability status model

Patient/admin UI should use compact availability states.

Recommended baseline status values:
- `in_stock`
- `low_stock`
- `out_of_stock`

Derived rule:
- if `availability_enabled = false` -> `out_of_stock`
- if `free_qty <= 0` -> `out_of_stock`
- if `free_qty <= low_stock_threshold` -> `low_stock`
- else -> `in_stock`

This is enough for clinic commerce baseline.
No need to build inventory theology.

---

## 15. Preferred pickup branch model

Preferred pickup branch is a UX helper, not hidden magic.

It may come from:
- product-level default branch
- branch availability row (`preferred_pickup=true`)
- clinic policy (`care.default_pickup_branch_id`)
- previous patient branch context later
- explicit patient override

### Core rule
Preferred pickup branch may preselect a branch.
It must not silently override explicit patient choice.

---

## 16. What belongs in workbook vs DB runtime

## 16.1 Workbook / Sheets authoring layer
Belongs there:
- products
- i18n text
- branch availability baseline
- recommendation links
- recommendation sets
- display/order metadata
- optional preferred pickup hints

## 16.2 DentFlow DB runtime layer
Belongs there:
- care orders
- care reservations
- issue / fulfill
- active reserved quantity
- runtime events
- derived free quantity
- actual pickup branch on order
- reservation consumption/release

This boundary must stay explicit.

---

## 17. Product discoverability model

The care catalog must support:

## Primary path
**Recommendation-first**
- the patient sees products because the clinic recommends them

## Secondary path
**Narrow category catalog**
- the patient may browse “Care” / “Уход”
- but only within a narrow bounded catalog

This avoids both extremes:
- “products exist only if directly pushed”
- “giant online shop inside clinic bot”

---

## 18. Operator usage model

Operators should not be forced into giant Telegram product admin panels.

Preferred operator workflow:
- maintain product master data in XLSX / Google Sheets
- sync/import into DentFlow
- use bot for:
  - media attach
  - compact operational actions
  - stock/order handling where needed

This is the product balance we want to preserve.

---

## 19. Explicit non-goals

This catalog model does **not** include:
- warehouse stock movement ledger
- supplier model
- delivery logistics
- discount engine
- tax engine
- variant matrix hell
- procurement workflows
- accounting truth

If one day those are needed, they should be added intentionally, not smuggled in through product rows.

---

## 20. Summary

The DentFlow care catalog model is built around these ideas:

- products are first-class structured entities;
- localized content is explicit;
- recommendation sets/bundles are first-class operator tools;
- recommendation-to-product links are explicit;
- branch availability baseline is authored externally;
- runtime order/reservation truth stays in DentFlow DB;
- patient discovery is recommendation-first with narrow catalog as secondary path;
- Telegram bot is for operational usage, not giant product authoring panels.

This model must stay compact, operator-friendly, and clinically relevant.

That is the whole point.
