# DentFlow Seed Data and Demo Fixtures

> Seed, fixture, and demo-data specification for DentFlow.

## 1. Purpose

This document defines the minimum seed and fixture strategy for DentFlow.

It exists because complex clinic systems cannot be validated on:
- an empty database;
- three fake rows;
- one doctor named “Test Testovich.”

That is not testing.
That is performance art.

---

## 2. Goals

Seed and fixture data must allow the team and CODEX to validate:

- patient search;
- repeated surnames;
- multilingual names;
- booking history;
- reminder flows;
- owner metrics;
- care-commerce flows;
- chart/export logic;
- access/role surfaces;
- document generation;
- realistic UI density.

---

## 3. Seed families

Recommended seed families:

1. clinic and branch reference
2. doctors
3. services
4. schedules and slots
5. staff and role bindings
6. patients
7. bookings
8. reminders
9. chart/clinical samples
10. recommendations
11. care catalog and orders
12. media and CT-link stubs
13. owner metrics seed/derived validation

---

## 4. Minimum fixture requirements

## 4.1 Clinic reference fixtures
- one clinic minimum
- optional second branch set
- realistic timezone and locale defaults

## 4.2 Doctor fixtures
At least:
- 4–6 doctors
- mixed specialties
- one premium/protected doctor
- one doctor with public booking disabled
- one doctor with urgent-capable routing
- one doctor with code-only behavior if used

## 4.3 Service fixtures
At least:
- hygiene
- consultation
- urgent pain visit
- pediatric visit
- orthodontic/implant-related visit if product scope includes it

## 4.4 Patient fixtures
Need:
- mixed-language names
- repeated surnames
- patients with only phone
- patients with Telegram binding
- patients with photo
- patients with flags
- patients with reminder preference differences
- patients with previous doctor continuity

## 4.5 Booking fixtures
Need:
- upcoming pending_confirmation bookings
- confirmed bookings
- reschedule_requested bookings
- checked_in bookings
- in_service bookings
- completed bookings
- no_show bookings
- canceled bookings
- waitlist entries
- slot holds close to expiry

## 4.6 Reminder fixtures
Need:
- scheduled reminders
- sent reminders
- acknowledged reminders
- failed reminders
- action-required reminders
- “already_on_my_way” acknowledgements
- non-response cases

## 4.7 Clinical fixtures
Need:
- chart anchor
- encounter summaries
- diagnosis examples
- treatment plan examples
- odontogram snapshot payloads
- imaging references
- CT external-link stubs

## 4.8 Recommendation fixtures
Need:
- issued recommendations
- viewed vs unviewed
- accepted vs declined
- post-hygiene recommendation
- braces/aftercare recommendation

## 4.9 Care fixtures
Need:
- care catalog
- reserve-for-pickup order
- ready-for-pickup order
- fulfilled order
- expired reservation

## 4.10 Staff/access fixtures
Need:
- admin actor
- doctor actors
- owner actor
- role bindings
- branch-scoped role examples if branches enabled

---

## 5. Seed formats

Preferred early formats:
- CSV
- XLSX
- JSON fixture packs
- Python-based seed builders

Use reproducible seed pipelines.
Do not rely on “someone manually inserted a few rows in staging.”

---

## 6. Demo realism rules

Fixtures should contain:
- plausible names
- plausible booking density
- overlapping time windows
- repeated patients
- branch/service variety
- care recommendations tied to actual visits
- reminder chains tied to actual bookings

Do not generate sterile perfection.
The point is to test DentFlow against the messiness clinics actually produce.

---

## 7. Seed profiles

Recommended seed profiles:

### `minimal_dev`
Just enough to boot and smoke-test.

### `workflow_demo`
Enough data to demo booking, search, reminders and owner dashboards.

### `pilot_like`
A denser, more realistic profile for staging and pre-pilot validation.

---

## 8. Privacy rule

Use synthetic or deliberately fabricated data.

Do not use uncontrolled production dumps as default dev/demo fixtures.

---

## 9. Relationship to testing

This document supports:
- `docs/40_search_model.md`
- `docs/50_analytics_and_owner_metrics.md`
- `docs/95_testing_and_launch.md`

Without realistic fixtures:
- search looks better than it is;
- analytics looks cleaner than reality;
- role surfaces look less noisy than they will be;
- exports are under-tested.

---

## 10. Summary

DentFlow seed data must be:
- realistic enough to expose real problems;
- structured enough to be reproducible;
- broad enough to cover booking, search, reminders, clinical data, care flows and owner analytics;
- synthetic enough to avoid privacy stupidity.

That is how the team tests a real system instead of a cardboard prop.

---

## 11. Stack3 booking seed date mode

- `scripts/seed_stack3_booking.py` keeps static/default behavior by default.
- Optional relative mode is available for stale-fixture resilience:
  - `python scripts/seed_stack3_booking.py --relative-dates`
  - `python scripts/seed_stack3_booking.py --relative-dates --start-offset-days 2`
  - `python scripts/seed_stack3_booking.py --relative-dates --source-anchor-date 2026-04-20`
- Relative mode shifts booking/session/slot/waitlist date fields while preserving time-of-day, durations, and IDs.

## 12. P0-06D2A2 core demo seed pack baseline

- Stack1 demo reference now includes three doctors (`doctor_anna`, `doctor_boris`, `doctor_irina`), four core services (`consult`, `cleaning`, `treatment`, `urgent`), and three doctor access codes.
- Stack2 patient pack now includes four demo patients with mixed contact resolvability (Telegram + phone and phone-only), including Telegram user `3001`.
- Stack3 booking pack now includes multi-day multi-window availability, at least four booking statuses (`pending_confirmation`, `confirmed`, `reschedule_requested`, `canceled`), and active waitlist coverage.
- Recommendations/care catalog/care orders are intentionally deferred to follow-up tracks:
  - P0-06D2B1: care categories/products demo seed.
  - P0-06D2B2: recommendations/care orders demo seed.

## 13. P0-06D2B1 care catalog demo seed

- File path: `seeds/care_catalog_demo.json`
- Load command:
  - `python scripts/sync_care_catalog.py --clinic-id clinic_main json --path seeds/care_catalog_demo.json`
- Scope note:
  - This seed creates/updates care catalog products and catalog-level recommendation mappings (`recommendation_sets`, `recommendation_set_items`, `recommendation_links`).
  - It does **not** create patient recommendation records.
  - It does **not** create care orders/reservations.

## 14. P0-06D2B2 recommendations + care orders demo seed

- File path: `seeds/demo_recommendations_care_orders.json`
- Loader script:
  - `python scripts/seed_demo_recommendations_care_orders.py --path seeds/demo_recommendations_care_orders.json`
  - `python scripts/seed_demo_recommendations_care_orders.py --path seeds/demo_recommendations_care_orders.json --relative-dates`
  - `python scripts/seed_demo_recommendations_care_orders.py --path seeds/demo_recommendations_care_orders.json --relative-dates --start-offset-days 1`
- Required load order for reproducible demo content:
  1. `python scripts/seed_stack1.py`
  2. `python scripts/seed_stack2.py`
  3. `python scripts/seed_stack3_booking.py --relative-dates`
  4. `python scripts/sync_care_catalog.py --clinic-id clinic_main json --path seeds/care_catalog_demo.json`
  5. `python scripts/seed_demo_recommendations_care_orders.py --path seeds/demo_recommendations_care_orders.json --relative-dates`
- Notes:
  - Care catalog products must be loaded before recommendations/care-orders seed because this loader resolves SKU to `care_product_id`.
  - Patient recommendations in this seed use only domain-valid recommendation types (`aftercare`, `follow_up`, `next_step`, `hygiene_support`, `monitoring`, `general_guidance`).
  - Product mapping is demonstrated through manual targets and direct recommendation-product links.
  - One intentionally invalid manual target is included (`rec_sergey_manual_invalid -> SKU-NOT-EXISTS`) for recovery smoke validation.

## 15. P0-06D2C full demo seed bootstrap

- One-command loader script:
  - `python scripts/seed_demo.py --relative-dates`
  - `python scripts/seed_demo.py --relative-dates --start-offset-days 1`
  - `python scripts/seed_demo.py --relative-dates --clinic-id clinic_main`
- Makefile wrapper:
  - `make seed-demo`

### Required load order

1. stack1 reference seed (`seeds/stack1_seed.json`)
2. stack2 patients (`seeds/stack2_patients.json`)
3. stack3 booking seed (`seeds/stack3_booking.json`) with relative-date mode for demo/live smoke
4. care catalog demo JSON (`seeds/care_catalog_demo.json`)
5. recommendations + care orders demo JSON (`seeds/demo_recommendations_care_orders.json`) with relative-date mode

### Dry-run

- `python scripts/seed_demo.py --relative-dates --dry-run`
- Dry-run does not write to DB.
- Dry-run checks all seed files exist, parses JSON, validates care catalog payload parsing, validates recommendations/care-orders payload, and prints planned step order.

### Notes

- Relative-date mode should be used for stack3 and recommendations/care-orders when running demos or smoke in non-static environments.
- Care catalog JSON import must run before recommendations/care-orders because recommendation/care-order seed resolves SKUs against catalog products.
- Google Sheets catalog sync remains available separately via `scripts/sync_care_catalog.py`.
- Google Sheets templates/import pack are intentionally out of scope for this PR.


## 16. P0-06E1 care catalog Google Sheets template pack

- Template location:
  - `docs/templates/google_sheets/care_catalog/`
- Source relationship:
  - `demo_*.csv` files in this folder are generated from `seeds/care_catalog_demo.json` tab payloads.
- Operational load order:
  - seed/demo bootstrap uses JSON import first:
    - `python scripts/sync_care_catalog.py --clinic-id clinic_main json --path seeds/care_catalog_demo.json`
  - operator mode can use Google Sheets after tab setup:
    - `python scripts/sync_care_catalog.py --clinic-id clinic_main sheets --sheet <url_or_id>`
    - `/admin_catalog_sync sheets <url_or_id>`
- Scope boundary:
  - Google Sheets catalog sync in this pack is for care products/catalog tabs only.
  - patient/doctor/service Sheets sync is not part of P0-06E1.
## 17. Demo seed vs Google Calendar projection

- Demo seed flows create DentFlow reference/patient/booking data in DentFlow storage.
- Google Calendar projection is a separate worker/integration step and is not executed by seed bootstrap itself.
- Seed/demo commands do not call Google Calendar directly.


## 16. P0-06E3 reference/patient Google Sheets templates (template/manual only)

- Template location:
  - `docs/templates/google_sheets/reference_and_patients/`
- Scope includes tabs for:
  - `branches`, `doctors`, `services`, `doctor_access_codes`, `patients`, `patient_contacts`, `patient_preferences`
- Current status:
  - template/manual only;
  - no active Sheets sync for patients/doctors/services in this baseline.
- Truth boundary:
  - demo load path remains `scripts/seed_demo.py` with `seeds/stack1_seed.json` + `seeds/stack2_patients.json`.
- Relation to P0-06D2A2:
  - demo CSV rows mirror the D2A2 reference/patient baseline IDs and relationships.
