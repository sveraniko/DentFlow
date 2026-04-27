# P0-06D1 Seed/Content Readiness Audit Report

## Summary
- Scope audited: static seed files, seed loaders, bootstrap/load commands, and smoke-gate dependency on seed vs test fakes.
- No live DB checks were performed in this PR.
- Current seed pack is coherent structurally, but **not sufficient** for patient beta/live smoke in care/recommendation and booking diversity.
- Recommendation for next step (P0-06D2): **NO-GO until seed expansion is implemented**.

## Files inspected
- `docs/92_seed_data_and_demo_fixtures.md`
- `docs/60_care_commerce.md`
- `docs/70_bot_flows.md`
- `docs/71_role_scenarios_and_acceptance.md`
- `docs/95_testing_and_launch.md`
- `seeds/stack1_seed.json`
- `seeds/stack2_patients.json`
- `seeds/stack3_booking.json`
- `scripts/seed_stack1.py`
- `scripts/seed_stack2.py`
- `scripts/seed_stack3_booking.py`
- `scripts/sync_care_catalog.py`
- `app/infrastructure/db/bootstrap.py`
- `app/infrastructure/db/repositories.py`
- `app/infrastructure/db/patient_repository.py`
- `app/infrastructure/db/booking_repository.py`
- `app/infrastructure/db/recommendation_repository.py`
- `app/infrastructure/db/care_commerce_repository.py`
- `tests/test_patient_db_load_and_seed.py`
- `tests/test_booking_seed_bootstrap.py`
- `tests/test_runtime_seed_behavior.py`
- `tests/test_p0_06c4_recommendations_smoke_gate.py`
- `tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py`
- `tests/test_p0_05c_my_booking_smoke_gate.py`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `docs/report/P0_06C4_RECOMMENDATIONS_SMOKE_GATE_REPORT.md`

## Seed files found
- `seeds/stack1_seed.json` (clinic/reference/access baseline)
- `seeds/stack2_patients.json` (patient registry baseline)
- `seeds/stack3_booking.json` (booking/slot/session baseline)

## Seed scripts found
- `scripts/seed_stack1.py` → loads `seeds/stack1_seed.json` via `seed_stack_data`.
- `scripts/seed_stack2.py` → loads `seeds/stack2_patients.json` via `seed_stack2_patients`.
- `scripts/seed_stack3_booking.py` → loads `seeds/stack3_booking.json` via `seed_stack3_booking`.
- `scripts/sync_care_catalog.py` → imports/syncs care catalog via XLSX/Sheets (not stack seed JSON).

---

## Current seed coverage matrix

| Area | Current state in real seed files | Beta minimum | Status |
|---|---|---|---|
| Clinic/reference | 1 clinic, 1 branch, timezone + locale present | >=1 clinic, >=1 valid branch timezone | ✅ Meets minimal |
| Doctors | 1 doctor only; `public_booking_enabled=true` | >=2 doctors, >=1 public | ❌ Gap |
| Doctor access codes | 1 active code (`ANNA-001`) | >=1 | ✅ Meets minimal |
| Services | 1 service (`consult`) only | >=3 incl consult + hygiene + treatment/urgent | ❌ Gap |
| Patients | 3 patients; 1 phone contact; no explicit patient Telegram binding in seed pack | Telegram-resolvable + phone-resolvable + active-booking patient | ⚠️ Partial |
| Slots | 6 slots total, 5 future / 1 past (as of 2026-04-27); 15-day spread; morning only | future slots, pagination range, multi-window | ⚠️ Partial |
| Bookings | 1 booking only, status `pending_confirmation` | active booking + confirmed + canceled/history | ❌ Gap |
| Recommendations | No recommendation seed objects in stack JSONs | active + history + product-linked + empty/manual-invalid scenario | ❌ Gap |
| Care categories/products | None in stack seeds; catalog can be loaded via sync script | >=2 categories, >=3-5 products, in/out of stock | ❌ Gap |
| Care orders | None in stack seeds | active order + history order + repeatable order | ❌ Gap |
| Linked recommendation products | Not present in stack seeds | >=1 linked product | ❌ Gap |

---

## Detailed audit by required area

### 1) Clinic/reference seed readiness
- Clinics: 1.
- Branches: 1.
- Branch timezone: `Europe/Moscow` present.
- Branch locale: clinic default locale `ru` present.
- Doctors: 1 only.
- Public booking doctors: 1.
- Code-only/protected behavior: one access code exists, but only one doctor profile overall.
- Doctor access codes: 1 active code.
- Services: 1 service only (`service_consult`).
- Service diversity: insufficient (no hygiene, no treatment/urgent category).

**Conclusion:** fails beta minimum due to doctor and service diversity gaps.

### 2) Slot/booking seed readiness
- Availability slots: 6.
- Future slots relative to 2026-04-27 UTC: 5 future, 1 stale/past.
- Slot spread: across dates 2026-04-20..2026-05-05 (15 days).
- Time windows represented: only morning (10:00/11:00 UTC starts).
- Pagination coverage: likely yes for basic list (>=5), but thin.
- Booking sessions: 1.
- Bookings: 1.
- Booking statuses represented: only `pending_confirmation`.
- Stale hardcoded dates: several 2026-04-20 entities now in the past.

**Conclusion:** partial for slots, insufficient for booking lifecycle status coverage.

### 3) Patient seed readiness
- Patients: 3.
- Telegram binding/contact path: seed has phone contact; no explicit patient Telegram mapping in stack seeds.
- Phone-only patient: yes (at least one with phone contact).
- Repeated surname / ambiguous matching: weak (Ivanov/Ivanova are similar but not true repeated surname duplicates).
- Linked to active booking: `patient_sergey_ivanov` linked to booking `bkg_001`.
- Linked to recommendations/care orders: none in seed pack.

**Conclusion:** partial; patient linkage exists for booking but Telegram-resolution seed evidence is weak.

### 4) Recommendation seed readiness
- Recommendations in seed files: none.
- Status coverage: none.
- Patient linkage: none.
- Booking/doctor linkage: none.
- Product-linked recommendation: none.
- Recommendation-without-products scenario in seeds: none.

**Conclusion:** hard blocker for recommendation demo readiness.

### 5) Care catalog seed readiness
- Care categories/products in stack seeds: none.
- SKU/title/price/category/availability/stock/media fields in stack seeds: none.
- Product↔recommendation linkage in stack seeds: none.
- There is a loader path via `scripts/sync_care_catalog.py` (XLSX/Sheets).

**Conclusion:** seed readiness missing in current stack seed pack; operational import path exists.

### 6) Care order seed readiness
- Care orders in stack seeds: none.
- Active/history/repeatable order seed scenarios: none.

**Conclusion:** blocker for live smoke of “Мои резервы / заказы” based on real seed content.

### 7) Scripts and load path readiness
- Stack1 loader: `scripts/seed_stack1.py` → `seed_stack_data`.
- Stack2 loader: `scripts/seed_stack2.py` → `seed_stack2_patients`.
- Stack3 loader: `scripts/seed_stack3_booking.py` → `seed_stack3_booking`.
- Care catalog: separate import/sync via `scripts/sync_care_catalog.py` (xlsx/sheets mode).
- Recommendation/care order dedicated seed loader: not found in `scripts/` for JSON stack profile.
- Makefile one-command bootstrap target for all stacks: absent (`seed-stack1` and `seed-stack2` only).
- Existing tests cover loading of stack2/stack3 and runtime no-auto-seed behavior.

**Conclusion:** reproducible partial path exists, but no single command full demo bootstrap and no recommendation/care-order seed loader.

### 8) Existing smoke test dependency (seed vs fakes)
- P0-03 slot picker / booking behavior: backed by stack3 booking seed and many test doubles.
- P0-05 My Booking smoke gate: uses stubs/fake booking objects in tests.
- P0-06B care smoke gate: mostly in-memory stub services / mocked product/order flows.
- P0-06C recommendations smoke gate: explicitly injects synthetic rows/statuses in test stubs.

**Conclusion:** current green smoke gates prove UX/runtime logic robustness, but they **do not** prove real seed/demo richness for live testing.

---

## Gap matrix

### Blocker
1. No recommendation seed dataset (no statuses, no history, no patient-linked recommendations).
2. No care catalog/product seed dataset in stack JSON seeds.
3. No care order seed dataset.
4. Booking status diversity missing (`confirmed`, `canceled`, etc. absent).
5. Doctor/service diversity below beta minimum.

### Important
1. No one-command full seed bootstrap (stack1+2+3 + care catalog import profile).
2. Hardcoded stale booking/session dates in stack3 may break primary demo expectations over time.
3. Patient Telegram-resolution data path is not explicit in patient seed pack.

### Nice-to-have
1. Add evening slot windows for realistic choice and timezone behavior.
2. Add second branch to validate branch selection/relevance.
3. Add stronger ambiguous-patient matching fixtures (same surname, transliteration variants).

---

## Stale date analysis
- Hardcoded past/stale dates detected in `seeds/stack3_booking.json` for 2026-04-20 session/booking/slot/hold entities.
- As of audit date **2026-04-27**, primary booking object `bkg_001` is already in the past while still `pending_confirmation`.
- Demo risk: a user-facing “active booking” path can render unrealistic/stale schedule context.
- Future slots exist (2026-04-28, 2026-04-29, 2026-04-30, 2026-05-05), so slot browsing can still work.

---

## Test fixtures vs real seed distinction
- Real seed files contain no recommendation objects and no care catalog/order objects.
- Recommendation and care smoke-gate tests rely heavily on test stubs and injected rows, not on `seeds/*.json` richness.
- Therefore “green smoke gates” should be interpreted as runtime contract correctness, not seed completeness for demo/live smoke.

---

## Minimum demo seed proposal for P0-06D2

### Proposed objects to add (targeted)
1. **Reference expansion (stack1)**
   - Add doctors:
     - `doctor_ivan_public` (public booking enabled)
     - `doctor_maria_code_only` (public booking disabled + access code)
   - Add services:
     - `service_hygiene`
     - `service_urgent_pain`
     - optional `service_treatment_followup`
   - Keep existing `doctor_anna` and `service_consult`.

2. **Booking expansion (stack3)**
   - Add >=14 future slots relative to load date profile, across morning/day/evening.
   - Add bookings:
     - `bkg_demo_confirmed` status `confirmed`
     - `bkg_demo_reschedule` status `reschedule_requested`
     - `bkg_demo_canceled` status `canceled`
     - optional `bkg_demo_completed` status `completed`
   - Keep at least one active booking for My Booking.

3. **Recommendation seed profile (new or stack extension)**
   - IDs:
     - `rec_active_issued_001` (`issued`)
     - `rec_active_ack_001` (`acknowledged`)
     - `rec_hist_accepted_001` (`accepted`)
     - `rec_hist_declined_001` (`declined`)
     - optional `rec_hist_expired_001` (`expired`)
   - Link to patient(s), and at least one to `booking_id` + `doctor_id` context.

4. **Care catalog/product seed profile**
   - Categories: `cat_hygiene`, `cat_aftercare`.
   - Products (3-5):
     - `prod_brush_soft` (in stock)
     - `prod_irrigator_basic` (in stock)
     - `prod_postop_gel` (out of stock)
   - Include SKU/title/price/category and branch relevance.

5. **Care orders seed profile**
   - `co_active_001` (`confirmed`/active)
   - `co_ready_pickup_001` (`ready_for_pickup`)
   - `co_hist_fulfilled_001` (`fulfilled`)
   - `co_hist_canceled_001` (`canceled`, if status supported in target flow)
   - one order flagged repeatable scenario.

6. **Recommendation↔product link seed**
   - Link `rec_active_issued_001 -> prod_postop_gel`
   - Link `rec_hist_accepted_001 -> prod_brush_soft`
   - Keep one recommendation without link for empty/manual-invalid flow.

### Recommended relation graph
- `clinic_main`
  - `branch_central`, optional `branch_north`
  - doctors (public + code-only)
  - services (consult/hygiene/urgent)
  - patients (phone + telegram-resolvable)
  - future slots referencing doctor/service/branch
  - bookings referencing slot/patient/doctor/service
  - recommendations referencing patient (+booking/doctor where possible)
  - products linked by recommendation_links/recommendation_product_links
  - care_orders referencing patient/product (+recommendation when appropriate)

---

## One-command seed/load recommendation
Introduce a single command (Makefile target or script wrapper), for example:
- `make seed-demo`
  1. `python scripts/db_bootstrap.py`
  2. `python scripts/seed_stack1.py`
  3. `python scripts/seed_stack2.py`
  4. `python scripts/seed_stack3_booking.py`
  5. `python scripts/sync_care_catalog.py --clinic-id clinic_main xlsx --path docs/shop/dentflow_care_catalog_canonical_workbook_v1.xlsx`
  6. (P0-06D2) recommendation/care-order seed loader invocation

This keeps local/staging bootstrap reproducible and avoids manual DB surgery.

---

## Optional lightweight audit test added
Added `tests/test_p0_06d1_seed_content_readiness_audit.py`.

What it checks:
- JSON validity for stack1/stack2/stack3 files.
- Required top-level arrays exist.
- Core cross-file references stay coherent:
  - slot/booking/session references to branch/doctor/service;
  - booking/session patient references to stack2 patients.
- Computes slot past/future counts without failing on insufficient richness.

Design rule kept: fails on malformed/broken structure, not on business completeness gaps.

---

## Grep checks (exact commands/results)

### 1) Date pinning/stale-risk scan
```bash
rg "2026-04|2026-05|2026-" seeds scripts tests/test_booking_orchestration.py tests/test_p0_06d1_seed_content_readiness_audit.py
```
Result:
- Hits are concentrated in `seeds/stack3_booking.json` hardcoded timestamps/dates.
- Classification:
  - **stale risk:** 2026-04-20 booking/session/hold/slot timestamps.
  - **legitimate static fixture (for now):** a few fixed future slots used as deterministic seed examples.
  - **should become relative in D2:** slot/session/booking dates for active demo profile.

### 2) Care/recommend/product/order support scan
```bash
rg "care|recommend|product|order" seeds scripts docs/92_seed_data_and_demo_fixtures.md
```
Result:
- `docs/92_seed_data_and_demo_fixtures.md` specifies expectations extensively.
- `scripts/sync_care_catalog.py` exists for catalog import/sync.
- `seeds/*.json` do not currently contain care/recommendation/product/order fixture objects.

### 3) Seed/load command scan
```bash
rg "seed_stack|sync_care_catalog|stack3_booking" scripts Makefile README.md docs
```
Result:
- Seed scripts for stack1/2/3 are present.
- Catalog sync script is present.
- Makefile has `seed-stack1`, `seed-stack2`; no full one-command seed-demo target including stack3 + catalog sync.

---

## Tests run (exact commands/results)
- `python -m compileall app tests` → PASS
- `pytest -q tests/test_p0_06d1_seed_content_readiness_audit.py` → PASS (`3 passed`)
- `pytest -q tests/test_booking_seed_bootstrap.py` → PASS (`1 passed`)
- `pytest -q tests/test_patient_db_load_and_seed.py` → **FAIL** (`2 failed, 1 passed`), unrelated harness issue in `_Result` stub missing `.first()` for outbox insert path.
- `pytest -q tests/test_runtime_seed_behavior.py` → PASS (`1 passed`)
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py` → PASS (`9 passed`)
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` → PASS (`3 passed`)
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` → PASS (`4 passed`)
- `pytest -q tests -k "care or recommendation"` → PASS (`204 passed, 507 deselected, 2 warnings`)
- `pytest -q tests -k "patient and booking"` → PASS (`105 passed, 606 deselected, 2 warnings`)

---

## GO/NO-GO recommendation for P0-06D2

## Recommendation: **NO-GO (seed/content readiness incomplete)**

Rationale:
1. Core demo/livesmoke content gaps remain in recommendations, care catalog/products, and care orders.
2. Booking lifecycle coverage in seed is too narrow (single booking, single status).
3. Clinic reference diversity is below minimum beta expectation (1 doctor, 1 service).
4. Existing smoke gates are green but rely significantly on test fakes/stubs, not real seed density.

### Exit criteria to flip to GO in P0-06D2
- Seed pack expanded to cover reference diversity, booking status diversity, recommendations, care catalog/products, and care orders.
- Stale hardcoded active-flow dates replaced with relative/future-safe demo profile.
- One-command reproducible seed/bootstrap path documented and executable.
