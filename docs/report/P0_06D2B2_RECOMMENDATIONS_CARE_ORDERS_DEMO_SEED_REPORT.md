# P0-06D2B2 Recommendations + Care Orders Demo Seed Report

## Summary
- Added a new demo seed payload for patient recommendations, manual recommendation targets, direct recommendation-product links, care orders, care order items, and care reservations.
- Added a dedicated seed loader script with optional relative-date shifting, payload validation, SKU resolution against care catalog products, and idempotent SQL upserts for order/order-item/reservation rows.
- Added readiness tests for structure, domain constraints, references, totals, status timestamp coverage, reservation semantics, and date-shifting behavior.
- Kept D2B1 scope constraints intact: no schema migrations, no workbook spec changes, no new care catalog products, and no bot/UI/router changes.

## Files changed
- `seeds/demo_recommendations_care_orders.json` (new)
- `scripts/seed_demo_recommendations_care_orders.py` (new)
- `tests/test_p0_06d2b2_recommendations_care_orders_seed.py` (new)
- `docs/92_seed_data_and_demo_fixtures.md`
- `docs/report/P0_06D2B2_RECOMMENDATIONS_CARE_ORDERS_DEMO_SEED_REPORT.md` (new)

## Seed file structure
`seeds/demo_recommendations_care_orders.json` top-level arrays:
- `recommendations`
- `manual_recommendation_targets`
- `recommendation_product_links`
- `care_orders`
- `care_order_items`
- `care_reservations`

Also includes `source_anchor_date` for relative-date anchoring.

## Recommendation coverage
- Patients covered:
  - `patient_sergey_ivanov`
  - `patient_elena_ivanova`
  - `patient_maria_petrova`
  - `patient_giorgi_beridze`
- Statuses covered:
  - `issued`, `viewed`, `acknowledged`, `accepted`, `declined`, `expired`, `withdrawn`
- Domain-valid recommendation types only:
  - `hygiene_support`, `general_guidance`, `monitoring`, `aftercare`, `next_step`, `follow_up`
- Booking links included where applicable:
  - `bkg_sergey_confirmed`, `bkg_elena_reschedule`, `bkg_giorgi_canceled`, `bkg_sergey_pending`
- Product target linking:
  - Manual target to set (`set_daily_hygiene`)
  - Manual target to product (`SKU-PASTE-SENSITIVE`)
  - Manual target to category (`floss`)
  - Intentional invalid manual product target (`SKU-NOT-EXISTS`)

## Manual target coverage
- `rec_sergey_hygiene_issued -> set_daily_hygiene`
- `rec_sergey_sensitive_ack -> SKU-PASTE-SENSITIVE`
- `rec_elena_post_treatment_viewed -> set_post_treatment`
- `rec_sergey_monitoring_accepted -> category: floss`
- `rec_sergey_manual_invalid -> SKU-NOT-EXISTS` (intentional edge case)

## Direct product link coverage
- Direct recommendation-product link seeded:
  - `rec_sergey_monitoring_accepted -> SKU-FLOSS-WAXED`
- Loader resolves `sku -> care_product_id` after care catalog import.

## Care order coverage
- Orders seeded:
  - `co_sergey_confirmed_brush` (`confirmed`)
  - `co_sergey_ready_paste` (`ready_for_pickup`)
  - `co_elena_fulfilled_rinse` (`fulfilled`)
  - `co_maria_canceled_floss` (`canceled`)
  - `co_giorgi_expired_irrigator` (`expired`)
- Items:
  - SKUs mapped to catalog products only.
- Reservations:
  - `active` for confirmed/ready orders
  - `consumed` for fulfilled
  - `released` for canceled
  - `expired` for expired order
- Totals:
  - each `care_orders.total_amount` equals sum of item `line_total`
  - each item `line_total = quantity * unit_price`
  - unit prices aligned to catalog demo prices converted to cents.

## Relative-date behavior
- Added `shift_demo_recommendations_care_orders_dates(...)` in loader script.
- Shifts all `*_at` fields and `expires_at` while preserving IDs and interval spacing.
- Supports explicit `source_anchor_date` from payload and CLI override.
- Static mode unchanged when `--relative-dates` is omitted.

## Loader behavior
- Script path: `scripts/seed_demo_recommendations_care_orders.py`
- CLI examples:
  - `python scripts/seed_demo_recommendations_care_orders.py --path seeds/demo_recommendations_care_orders.json`
  - `python scripts/seed_demo_recommendations_care_orders.py --path seeds/demo_recommendations_care_orders.json --relative-dates`
  - `python scripts/seed_demo_recommendations_care_orders.py --path seeds/demo_recommendations_care_orders.json --relative-dates --start-offset-days 1`
- Validates payload references against stack1/2/3/catalog seed payloads before DB writes.
- Validates DB references (patients/bookings/branches/SKUs) before SQL seeding.
- Idempotent writes:
  - recommendations via repository `save(...)` upsert path,
  - manual targets via `upsert_manual_recommendation_target(...)`,
  - recommendation-product links via repository upsert,
  - care orders/items/reservations via SQL `ON CONFLICT` upsert.

## Tests run with exact commands/results
1. `python -m compileall app tests`
   - pass
2. `pytest -q tests/test_p0_06d2b2_recommendations_care_orders_seed.py`
   - pass (`7 passed`)
3. `pytest -q tests/test_p0_06d2b1_care_catalog_demo_seed.py`
   - pass (`7 passed`)
4. `pytest -q tests/test_p0_06d2a2_core_demo_seed_pack.py`
   - pass (`7 passed`)
5. `pytest -q tests/test_p0_06d2a1_seed_date_shift_foundation.py`
   - pass (`5 passed`)
6. `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py`
   - pass (`9 passed`)
7. `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py`
   - pass (`3 passed`)
8. `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py`
   - pass (`4 passed`)
9. `pytest -q tests -k "care or recommendation"`
   - pass (`218 passed, 519 deselected, 2 warnings`)
10. `pytest -q tests -k "patient and booking"`
   - pass (`105 passed, 632 deselected, 2 warnings`)

## Grep checks with exact commands/results
1. `rg "rec_sergey_hygiene_issued|rec_elena_post_treatment_viewed|rec_sergey_manual_invalid|co_sergey_confirmed_brush|co_sergey_ready_paste" seeds scripts tests docs`
   - Result: expected demo recommendation/order IDs present in seed + tests + loader.

2. `rg "aftercare_hygiene|sensitivity|post_treatment|gum_care" seeds/demo_recommendations_care_orders.json tests/test_p0_06d2b2_recommendations_care_orders_seed.py`
   - Result: no unsupported mapping types used as patient `recommendation_type`; only lexical occurrences in IDs/codes (e.g., `set_post_treatment`).

3. `rg "SKU-NOT-EXISTS" seeds tests docs`
   - Result: intentional invalid manual target present and tested.

4. `rg "relative_dates|start_offset_days|source_anchor_date" scripts tests app`
   - Result: new loader supports relative dates and existing stack3 date-shift coverage remains present.

## Defects found/fixed
- Added explicit validation warning path for intentional invalid manual target (`SKU-NOT-EXISTS`) so the seed remains valid while retaining the edge-case fixture.
- Added deterministic total/unit-price checks in tests and validator to prevent impossible order totals.

## Carry-forward for P0-06D2C
- Bundle stack1/stack2/stack3/care-catalog/recommendations-care-orders into one command bootstrap script with clear order and optional relative-date mode flags.

## Carry-forward for P0-06D2D
- Run end-to-end seed smoke against actual DB harness/staging-like environment and capture real insert/update counts + round-trip read checks.

## GO / NO-GO recommendation for D2C
- **GO**.
- Seed artifacts and validation coverage are in place; regressions requested in this scope are passing.
