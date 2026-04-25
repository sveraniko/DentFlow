# PR DOC-A2B-2 Report — Recommendation target option, contextual continuity hardening, and regression safety

## What changed after DOC-A2B-1
- Added a bounded optional target step to contextual doctor recommendation issuance after recommendation-type selection and before `Title | Body` capture.
- Added two compact target-mode choices:
  - **Without product target**
  - **Link product/category**
- Added bounded target-code capture with compact text format:
  - `product:<code>`
  - `category:<code>`
- Added minimal validation through existing care-commerce seams:
  - product code validation via `get_product_by_code(...)`
  - category validation via `list_catalog_products_by_category(...)`
- Added safe bounded fallback when target is invalid/unavailable:
  - no crash
  - bounded user-facing feedback
  - retry or switch to no-target
- Preserved DOC-A2B-1 no-target path behavior (still captures `Title | Body` and issues with `target_kind=None`, `target_code=None`).
- Hardened new `drec:*` callback branch handling for malformed/manual payloads and stale pending context.
- Ensured pending recommendation context is cleared on success, cancel, TTL expiry (existing), and safe fatal failure paths.

## Exact files changed
- `app/interfaces/bots/doctor/router.py`
- `app/application/care_commerce/service.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_booking_linked_opens_12b1.py`
- `docs/report/PR_DOC_A2B_2_REPORT.md`

## Optional care target capture flow
1. Doctor selects recommendation type from encounter/booking context.
2. Router shows compact target decision:
   - without target
   - link product/category
3. If **without target**:
   - flow goes directly to `Title | Body`
4. If **link product/category**:
   - router asks for `product:<code>` or `category:<code>`
   - validates using existing care-commerce seams
   - on valid target, stores `target_kind + target_code` in pending context
   - then requests `Title | Body`
   - on invalid target, shows bounded feedback and keeps retry/no-target options

## Patient aftercare compatibility preservation
- Contextual issuance still goes through existing `DoctorOperationsService.issue_recommendation(...)`.
- Manual target persistence continues through existing care-commerce target linkage seam.
- Added bounded `category` target support in care-commerce target resolver so downstream patient recommendation detail CTA resolution remains compatible with PAT-A7 logic.
- No patient-side CTA logic was reimplemented in this PR.

## Tests added/updated
Updated focused doctor router tests in `tests/test_booking_linked_opens_12b1.py` for:
1. no-target path still works after target-step insertion,
2. target path with valid `product:<code>` persists target linkage,
3. target path with valid `category:<code>` is accepted,
4. invalid target is bounded and non-crashing,
5. malformed/stale/manual `drec:*` callback payloads are bounded,
6. cancel clears pending recommendation context,
7. text without pending recommendation context is still ignored,
8. recommendation success still returns doctor to canonical encounter context.

## Environment / execution notes
- Targeted pytest subset for touched doctor-router flow was executed in this environment.
- No migrations were introduced.

## Closure statement
- **DOC-A2B is now considered closed** for bounded contextual recommendation issuance scope (DOC-A2B-1 + DOC-A2B-2).

## Explicit non-goals left for DOC-A2C
- No broad post-action navigation redesign beyond bounded recommendation flow safety.
- No richer in-flow catalog browser/picker for doctor recommendation target selection.
- No recommendation engine redesign.
- No care-commerce subsystem redesign.
- No patient aftercare UX redesign.
- No admin/owner flow changes.
- No migrations.
