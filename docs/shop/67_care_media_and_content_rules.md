# Care Media and Content Rules

> Canonical media, content, and localization rules for the DentFlow care-commerce block.

## 1. Purpose

This document defines how product media and patient-facing content must be handled in the DentFlow care-commerce block.

Its role is to make explicit:

- what kind of media may be attached to care products;
- where media truth lives;
- where product text/content truth lives;
- which content belongs in workbook/Google Sheets and which belongs in DentFlow runtime;
- how localization applies to product and recommendation-facing content;
- what should never be hardcoded in code;
- what must remain operationally simple in Telegram.

This document closes an important gap:
without explicit media/content rules, care-commerce quickly degrades into a mix of:
- hardcoded strings,
- spreadsheet hacks,
- random asset references,
- and bot-level improvisation.

That is not acceptable.

---

## 2. Core principle

# Media and content must be structured, localized, and source-of-truth aware.

This means:

- user-facing product text does not live as hardcoded code strings;
- product media binaries do not live in spreadsheets;
- spreadsheet/workbook may carry content keys and media references, but not replace runtime media truth;
- Telegram bot may be used as the practical media attachment path;
- DentFlow DB/media layer remains canonical for media asset references;
- patient-facing content must be localized and bounded.

---

## 3. Content truth model

DentFlow care-commerce uses a split truth model for content.

## 3.1 Workbook / Google Sheets content truth
Workbook/Sheets is the canonical authoring surface for:
- product titles
- product descriptions
- short labels
- optional justification text
- recommendation set labels
- optional product-facing usage hints
- optional media references by ID/key

This is where operators should edit structured catalog content.

## 3.2 DentFlow DB/media truth
DentFlow DB + media layer are canonical for:
- media assets
- bot-uploaded media
- final media asset references attached to products
- generated runtime links to assets

This is where media truth must live.

## 3.3 Code truth
Code must **not** become a content store.

Code may contain:
- localization keys
- fallback-safe internal constants
- formatting rules

Code must **not** contain:
- hardcoded patient-facing product titles
- hardcoded recommendation explanation text
- hardcoded aftercare product copy
- hardcoded multilingual product descriptions

The project already has localization discipline.
Care-commerce must obey it.

---

## 4. Media model

Care product media should support a practical, bounded set of asset types.

Recommended asset types:
- cover image
- gallery image
- short product video
- optional recommendation illustration
- optional branch pickup illustration if ever needed later

This stack does not require:
- 3D viewer
- giant gallery editor
- media CDN product site ambitions

---

## 5. Canonical media references

A product may reference media by:

- `media_asset_id`
- `cover_media_asset_id`
- `gallery_media_asset_ids` (if supported later)
- `video_media_asset_id`
- `media_ref_code` (optional operator-friendly alias only if justified)

### Important
A spreadsheet/workbook may store a media reference field,
but the binary/media truth must remain in the DentFlow media layer.

The spreadsheet must not become:
- a file storage system
- a binary distribution layer
- a chaotic URL graveyard

---

## 6. Bot-managed media attachment

Telegram bot remains the practical way to attach product media.

### Why
Because:
- operators can quickly upload or replace visual assets;
- this avoids trying to manage media binaries inside spreadsheets;
- DentFlow already has media/asset concepts;
- Telegram is practical for this type of admin action.

### Recommended baseline behavior
Operator/admin may:
- open product media attach flow
- upload image/video
- bind uploaded media asset to product
- optionally replace cover image
- optionally remove or supersede previous media binding

This does not require a giant media admin panel.
It only needs a compact operational path.

---

## 7. Spreadsheet media fields

Workbook/Sheets may still carry media-related columns, but only as references/metadata.

Recommended optional fields:
- `media_asset_id`
- `cover_media_asset_id`
- `video_media_asset_id`
- `media_note`
- `external_media_ref` (only if intentionally supported and safe)

### Rules
- importer may accept these as references
- importer must not try to ingest raw binary media from the workbook
- external URLs must not be trusted blindly
- media references must be validated where possible

---

## 8. Product localized content model

Every patient-facing product must have localized content.

At minimum for each locale:
- `title`
- `description`

Highly recommended:
- `short_label`
- `justification_text`
- `usage_hint`

This should be maintained through:
- `product_i18n` workbook tab
- synced into catalog content truth
- resolved through locale-aware runtime services

### Required baseline locales
- `ru`
- `en`

Future-ready:
- `ka`
- `pl`

---

## 9. Recommendation-facing product content

Products shown through recommendations are a special content case.

When a product appears in a recommendation-driven flow, patient-facing content may include:
- normal product title
- compact explanation why it is relevant
- optional recommendation-specific justification
- optional usage hint

### Important rule
This content must still come from structured content sources:
- workbook i18n
- justification keys
- localized template/content path

It must not be hardcoded in doctor flow code.

That mistake was already painful once. Do not repeat it.

---

## 10. Recommendation set / bundle content

Recommendation sets must also have patient-facing labels.

Recommended content fields:
- set title per locale
- set description per locale
- optional concise “why this set” text

These should live in:
- workbook/Sheets authoring layer
- or dedicated content rows synced from it

A set must not be represented only by a code in patient-facing UX.

---

## 11. Localized runtime resolution

Runtime content resolution should follow a coherent fallback model.

Preferred resolution order:
1. patient preferred locale
2. clinic default locale
3. system fallback locale

For care products and recommendation-facing content:
- if locale-specific content exists, use it
- if missing, use documented fallback
- do not silently drop to random English hardcodes

Missing localized content should be visible as a content quality issue, not hidden forever.

---

## 12. Content formatting rules

Patient-facing content must be:
- compact
- clear
- clinically relevant
- non-hype
- readable in Telegram

Avoid:
- giant paragraphs
- fake ecommerce persuasion copy
- excessive uppercase
- bizarre emoji spam
- technical operator jargon

This is clinic commerce, not a dropshipping fever dream.

---

## 13. What belongs in workbook vs what belongs in code

## Workbook / Google Sheets
Belongs there:
- product labels
- descriptions
- recommendation justifications
- usage hints
- set titles/descriptions
- category-facing text
- compact product content metadata

## Code
Belongs there:
- content keys
- fallback logic
- formatting/rendering
- UI composition rules
- safe internal constants

### Forbidden in code
Do not hardcode:
- patient-facing product names
- recommendation explanatory copy
- multilingual aftercare texts
- category descriptions
- set descriptions

If text is shown to the patient, it should almost certainly not live in Python code.

---

## 14. What belongs in bot vs what belongs in workbook

## Bot
Belongs there:
- media attach/update path
- compact operational preview
- recommendation send/open actions
- patient/admin reserve/pickup/order flow

## Workbook
Belongs there:
- product catalog text
- localized content
- set/bundle content
- justification text
- content-oriented catalog metadata

This split must remain intentional.

---

## 15. Media safety and moderation baseline

This document does not create a full moderation subsystem.
But some baseline rules must exist.

### Product media should:
- be relevant to the product
- not contain private patient information
- not expose clinical records accidentally
- not contain unsafe/random unrelated content
- be safe for patient-facing display

### Recommendation/content media should:
- be generic/product-facing
- not expose private patient-specific media unless an explicit separate feature is designed

Do not mix:
- product media
with
- patient clinical photos

Those are different worlds and must remain so.

---

## 16. External URLs and content references

External URLs may exist as metadata references, but they are dangerous if left loose.

Rules:
- external URLs should be optional and exceptional
- they should be validated or constrained where possible
- they must not become the main media truth path if avoidable
- patient-facing use of untrusted external URLs should be handled carefully

Baseline recommendation:
prefer bot-uploaded/internal media asset references over arbitrary URLs.

---

## 17. Product card content baseline

A patient-facing product card should resolve from structured localized content:
- title
- description
- short label
- category
- price
- compact availability status
- recommendation justification if in recommendation flow
- media if available

This must be deterministic.
The product card should not depend on random ad hoc string concatenation from handlers.

---

## 18. Category and narrow catalog content baseline

The patient-facing “Care / Уход” catalog may need:
- category labels
- compact category descriptions
- section headings

These must also be localized and structured.
Do not hardcode category names in random handlers if a content/key path already exists.

---

## 19. Missing content behavior

If localized content is missing, runtime should behave coherently.

Recommended behavior:
- use locale fallback
- if fallback still missing, use a safe operator-visible placeholder or log/warning path
- avoid crashing
- avoid silent empty cards if possible

This is content quality handling, not magic.

---

## 20. Future extensibility without CMS bloat

This document does not require a giant CMS.
But it should leave room for future improvements such as:
- richer justification text
- better bundle descriptions
- richer media galleries
- localized recommendation templates

The correct path is:
- structured content model
- workbook-driven authoring
- bot/media operational updates
not
- hardcoded strings scattered across code

---

## 21. Explicit non-goals

This media/content ruleset does **not** include:
- a full content management system
- WYSIWYG editor
- giant media DAM platform
- patient UGC/media upload for products
- AI content generation
- marketing copy engine

The goal is operational correctness and maintainable content, not content empire-building.

---

## 22. Summary

The care-commerce media/content model in DentFlow follows these rules:

- workbook/Sheets author product text and localized content;
- DentFlow media layer owns product media truth;
- bot is the practical media attachment path;
- code must not become a content dumping ground;
- recommendation-facing content must be structured and localized;
- product media and patient clinical media must remain separate;
- external URLs are exceptional, not the default media truth.

This is how the commerce layer stays maintainable.

Anything else turns into chaos very quickly.
