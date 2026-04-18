# Care Catalog Workbook Specification

> Canonical XLSX / Google Sheets workbook specification for the DentFlow care catalog.

## 1. Purpose

This document defines the **authoring workbook structure** for the DentFlow care-commerce block.

Its role is to make catalog authoring explicit and operator-friendly.

This workbook is the canonical source for:
- products
- localized product text
- recommendation sets / bundles
- recommendation-to-product links
- branch availability baseline
- selected care settings if needed

This document answers:

- which tabs must exist;
- which fields belong in each tab;
- which fields are required;
- which values are allowed;
- how validation should work;
- what is imported into DentFlow DB;
- what remains runtime truth only inside DentFlow DB.

This document does **not** define:
- runtime reservations
- care orders
- issue / fulfill state
- stock accounting
- media binary upload mechanics

Those belong elsewhere.

---

## 2. Workbook philosophy

The workbook exists to avoid two bad extremes:

### Extreme A
Trying to manage the care catalog entirely through Telegram admin panels.

Result:
- slow operator workflow
- noisy bot UX
- lots of brittle callbacks
- terrible editing experience for structured data

### Extreme B
Trying to keep all runtime truth in Sheets.

Result:
- order/reservation truth leaks out of the system
- stock becomes inconsistent
- debugging becomes archaeology

The correct model is:

### Workbook / Sheets truth
For **catalog master data**

### DentFlow DB truth
For **runtime operational data**

This workbook is therefore a **structured authoring surface**, not the whole care system.

---

## 3. Format and usage rules

## 3.1 Supported formats
The baseline authoring model supports:
- XLSX import
- Google Sheets sync

Both must follow the same logical workbook structure.

## 3.2 Header rules
- first row must be headers
- headers must match the canonical field names exactly
- extra columns may be ignored only if explicitly allowed by importer design
- missing required columns must fail validation

## 3.3 Cell formatting
Operator convenience is important.
The importer must tolerate:
- trimmed whitespace
- mixed case where normalization is safe
- common delimiter variants for list fields (`space`, `comma`, `semicolon`) where explicitly allowed

But:
- free-form chaos must not be accepted where structured values are required

## 3.4 Validation behavior
Import/sync should distinguish:
- fatal workbook errors
- row-level validation errors
- warnings
- skipped rows
- add/update counts

The importer must not silently “best effort” its way through invalid structure.

---

## 4. Workbook tab map

The canonical workbook consists of the following tabs:

1. `products`
2. `product_i18n`
3. `branch_availability`
4. `recommendation_sets`
5. `recommendation_set_items`
6. `recommendation_links`
7. `settings` (optional)

This is the baseline structure.

If future extensions are added, they must not break this baseline.

---

## 5. Tab: `products`

This tab defines the canonical product master rows.

One row = one product.

### Required columns
- `sku`
- `product_code`
- `status`
- `category`
- `use_case_tag`
- `price_amount`
- `currency_code`
- `pickup_supported`
- `delivery_supported`

### Optional columns
- `sort_order`
- `default_pickup_branch_id`
- `media_asset_id`
- `notes`

---

### Field specification

#### `sku`
- type: string
- required: yes
- unique: yes
- semantics: stable operator-facing product key

Rules:
- must be stable across imports
- no spaces recommended
- case normalization should be explicit if importer chooses to normalize

Examples:
- `nm2`
- `brush_soft_01`
- `irrigator_basic`

#### `product_code`
- type: string
- required: yes
- unique: recommended
- semantics: additional canonical product code if needed

Rules:
- may equal `sku`
- if separate from `sku`, must still be stable

#### `status`
- type: enum
- required: yes

Allowed values:
- `active`
- `inactive`
- `archived`

#### `category`
- type: enum/string
- required: yes

Recommended allowed values:
- `toothbrush`
- `toothpaste`
- `irrigator`
- `floss_interdental`
- `post_op_care`
- `ortho_care`
- `pediatric_care`
- `gum_care`
- `bundle`

If project expands categories later, it must do so intentionally.

#### `use_case_tag`
- type: string/enum
- required: yes

Examples:
- `aftercare_hygiene`
- `orthodontic_support`
- `post_op_soft`
- `periodontal_support`
- `daily_maintenance`

#### `price_amount`
- type: decimal
- required: yes

Rules:
- must be non-negative
- normalized to decimal number

Examples:
- `12.50`
- `15`
- `99.99`

#### `currency_code`
- type: enum/string
- required: yes

Examples:
- `EUR`
- `USD`
- `GEL`
- `UAH`

#### `pickup_supported`
- type: boolean
- required: yes

Accepted authoring values:
- `true` / `false`
- `1` / `0`
- `yes` / `no`
- `y` / `n`

Importer should normalize.

#### `delivery_supported`
- type: boolean
- required: yes

Same normalization rules as above.

#### `sort_order`
- type: integer
- required: no
- default: null or system default ordering

#### `default_pickup_branch_id`
- type: string
- required: no

Semantics:
- preferred branch hint for this product
- not a hidden forced branch
- patient may still override if flow allows

#### `media_asset_id`
- type: string
- required: no

Semantics:
- optional reference to media already known to DentFlow
- not binary upload itself

#### `notes`
- type: free text
- required: no
- for operator notes only
- should not be treated as patient-facing content

---

## 6. Tab: `product_i18n`

This tab defines localized patient-facing content for products.

One row = one product for one locale.

### Required columns
- `sku`
- `locale`
- `title`
- `description`

### Optional columns
- `short_label`
- `justification_text`
- `usage_hint`

---

### Field specification

#### `sku`
- type: string
- required: yes
- must reference an existing `products.sku`

#### `locale`
- type: string
- required: yes

Recommended baseline values:
- `ru`
- `en`

Future-expected:
- `ka`
- `pl`

#### `title`
- type: string
- required: yes

This is the main patient-facing product title.

#### `description`
- type: text
- required: yes

Keep it useful and bounded.
Do not turn product descriptions into novels.

#### `short_label`
- type: string
- required: no

Useful for compact product cards and chips.

#### `justification_text`
- type: text
- required: no

Used when product is shown inside recommendation-driven flow.

Example:
- “Подходит для ухода после профгигиены”
- “Suitable after hygiene cleaning”

#### `usage_hint`
- type: text
- required: no

Optional quick usage/support text.

---

## 7. Tab: `branch_availability`

This tab defines baseline stock availability by branch.

One row = one product at one branch.

### Required columns
- `branch_id`
- `sku`
- `on_hand_qty`
- `availability_enabled`

### Optional columns
- `low_stock_threshold`
- `preferred_pickup`

---

### Field specification

#### `branch_id`
- type: string
- required: yes
- must reference an existing branch in the clinic reference layer

#### `sku`
- type: string
- required: yes
- must reference an existing product

#### `on_hand_qty`
- type: integer
- required: yes

Rules:
- must be >= 0
- represents baseline physical quantity available for that branch

Important:
This is **not** `free_qty`.
Runtime free quantity is derived in DentFlow:
`free_qty = on_hand_qty - active_reserved_qty`

#### `availability_enabled`
- type: boolean
- required: yes

Semantics:
- whether this product is operationally available in the branch

#### `low_stock_threshold`
- type: integer
- required: no
- default: branch/global default if absent

Rules:
- must be >= 0

#### `preferred_pickup`
- type: boolean
- required: no
- default: false

Semantics:
- branch may be preferred for this product
- still not hidden forced branch magic

---

## 8. Tab: `recommendation_sets`

This tab defines named recommendation sets/bundles.

One row = one set.

### Required columns
- `set_code`
- `status`

### Optional columns
- `title_ru`
- `title_en`
- `description_ru`
- `description_en`
- `sort_order`

---

### Field specification

#### `set_code`
- type: string
- required: yes
- unique: yes

Examples:
- `aftercare_hygiene_basic`
- `ortho_basic`
- `post_op_soft`

#### `status`
- type: enum
- required: yes

Allowed values:
- `active`
- `inactive`
- `archived`

#### `title_ru`, `title_en`
- type: string
- required: optional but strongly recommended

#### `description_ru`, `description_en`
- type: text
- required: optional

#### `sort_order`
- type: integer
- required: no

---

## 9. Tab: `recommendation_set_items`

This tab links products into sets.

One row = one product in one set.

### Required columns
- `set_code`
- `sku`
- `position`

### Optional columns
- `quantity`
- `notes`

---

### Field specification

#### `set_code`
- type: string
- required: yes
- must reference an existing recommendation set

#### `sku`
- type: string
- required: yes
- must reference an existing product

#### `position`
- type: integer
- required: yes

Semantics:
- order of products in the set

#### `quantity`
- type: integer
- required: no
- default: 1

#### `notes`
- type: text
- required: no

Not a substitute for structured semantics.

---

## 10. Tab: `recommendation_links`

This tab defines rule-level mapping from recommendation logic into products or sets.

One row = one recommendation mapping.

### Required columns
- `recommendation_type`
- `target_kind`
- `target_code`
- `relevance_rank`
- `active`

### Optional columns
- `justification_key`
- `justification_text_ru`
- `justification_text_en`

---

### Field specification

#### `recommendation_type`
- type: string
- required: yes

Examples:
- `aftercare`
- `follow_up`
- `next_step`
- `hygiene_support`
- `monitoring`

#### `target_kind`
- type: enum
- required: yes

Allowed values:
- `product`
- `set`

#### `target_code`
- type: string
- required: yes

Semantics:
- if `target_kind=product`, references `sku`
- if `target_kind=set`, references `set_code`

#### `relevance_rank`
- type: integer
- required: yes

Lower or higher priority interpretation must be documented in importer/runtime and used consistently.
Recommended: lower number = higher priority is acceptable, but be explicit.
If runtime uses higher-is-better, document it and keep it consistent.

#### `active`
- type: boolean
- required: yes

#### `justification_key`
- type: string
- required: no

Preferred for stable localized runtime explanation if a key-based content path is used.

#### `justification_text_ru`, `justification_text_en`
- type: text
- required: no

Acceptable as baseline if key-based text path is not yet in place.
Must still be explicit and localized.

---

## 11. Tab: `settings` (optional)

This tab is optional and should stay small.

One row = one config key/value.

### Required columns
- `key`
- `value`

Examples:
- `care.default_pickup_branch_id`
- `care.low_stock_threshold_default`

This tab must not become a dumping ground for every unresolved product decision.

---

## 12. Validation rules

## 12.1 Workbook-level validation
Import/sync must fail if:
- required tab is missing
- required headers are missing
- duplicate required unique keys exist in the same tab
- enum fields contain unsupported values at workbook level too widely to continue safely

## 12.2 Row-level validation
Row should be marked invalid (not silently imported) if:
- `sku` references are broken
- `branch_id` references are broken
- `target_kind/target_code` mismatch
- `price_amount` invalid
- `on_hand_qty` invalid
- localization row references unknown product
- recommendation set item references unknown set/product

## 12.3 Warning-level issues
Warnings may be raised for:
- missing optional localized text
- missing sort order
- inactive linked entities
- duplicate recommendation links with different rank if not fatal

Warnings must not be mistaken for success invisibly.

---

## 13. Import/sync result model

The importer/sync path should return/report at minimum:

- tabs processed
- rows added
- rows updated
- rows skipped
- validation errors
- warnings
- unchanged rows (optional but useful)

This makes sync/import auditable instead of mystical.

---

## 14. Normalization rules

Importer should normalize where safe:

### Strings
- trim surrounding whitespace
- collapse repeated whitespace where appropriate

### Boolean fields
Accept common values:
- `true/false`
- `1/0`
- `yes/no`
- `y/n`

### Delimited fields
Where multi-value fields are explicitly allowed in future or optional contexts,
the parser may accept:
- comma
- semicolon
- space

But only where the field spec explicitly permits such multi-value input.

Do not normalize free-form chaos into silent truth.

---

## 15. What must not be authored in workbook

The workbook must **not** be used to author runtime operational truth such as:
- care orders
- reservations
- reserved quantity
- issue / fulfill status
- reminder statuses
- patient response statuses

These belong to DentFlow runtime truth in DB.

The workbook is not the live order book.

---

## 16. Media handling rule

The workbook may reference media by ID/ref, but it must not be the binary upload channel.

Actual product media management remains:
- DentFlow bot/media path
- media registry
- media asset references in DB

This is intentional.
Trying to turn Sheets into a media CMS is how humans invite suffering into their own homes.

---

## 17. Authoring workflow recommendation

Recommended operator workflow:

1. maintain products / i18n / sets / links / availability in workbook
2. validate workbook
3. import/sync into DentFlow
4. attach/update media through bot if needed
5. use DentFlow runtime for:
   - reservations
   - issue / fulfill
   - patient flows
   - admin operational actions

This keeps authoring calm and operations real-time.

---

## 18. Summary

The care catalog workbook is the structured authoring surface for care-commerce master data.

It defines:
- products
- localized product content
- branch availability baseline
- recommendation sets
- recommendation-to-product links
- small optional settings

It does **not** define runtime order/reservation truth.

That separation is the whole point.

If this workbook becomes a garbage dump for runtime data, the subsystem will rot quickly.
If it stays a clean master-data authoring surface, the whole commerce layer remains maintainable.
