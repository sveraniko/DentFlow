# P0-06D2D1 matrix

Дата проверки: 2026-04-28 (UTC).

Bootstrap:
- reusable `run_seed_demo_bootstrap` exists: **yes**
- CLI behavior unchanged: **yes**
- dry-run still works: **yes**
- skip flags consistent: **yes**

Safety:
- safe test DB/harness used: **yes**
- live DB seeding prevented: **yes**

Persisted counts:
- clinics/branches/doctors/services/access codes: **yes**
- patients/contacts/telegram 3001: **yes**
- slots/bookings/waitlist: **yes**
- care products/i18n/availability/settings: **yes**
- recommendations/manual targets/product links: **yes**
- care orders/items/reservations: **yes**

References:
- booking refs valid: **yes**
- care order refs valid: **yes**
- recommendation refs valid: **yes**
- SKU/product refs valid except intentional invalid: **yes**

Relative dates:
- future slots: **yes**
- active bookings future-safe: **yes**
- waitlist shifted: **yes**
- active reservations future-safe: **yes**
- recommendation timestamps coherent: **yes**

Idempotency:
- second run stable counts: **yes**
- no duplicate key objects: **yes**

Regression:
- D2C: **pass**
- D2B2: **pass**
- D2B1: **pass**
- D2A2: **pass**
- D2A1: **pass**
- C4 recommendations smoke: **pass**
- B4 care smoke: **pass**
- P0-05C smoke: **pass**
- care or recommendation: **222** passed
- patient and booking: **105** passed

## Source of truth
- Compiled from:
  - `docs/report/P0_06D2D1_SEED_DEMO_DB_LOAD_SMOKE_REPORT.md`
  - `docs/report/P0_06D2C_MATRIX.md`
  - `tests/test_p0_06d2d1_seed_demo_db_load_smoke.py`
