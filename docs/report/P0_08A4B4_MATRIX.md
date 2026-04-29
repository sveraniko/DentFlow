# P0-08A4B4 — Acceptance Matrix

**Date:** 2026-04-29
**Status:** **GO**

| # | Check | Result |
|---|---|---|
| 1 | DENTFLOW_TEST_DB_DSN used | YES |
| 2 | DB test executed, not skipped | YES |
| 3 | Repository smoke result | **PASS** |
| 4 | Profile details | PASS |
| 5 | Relationships / family | PASS |
| 6 | Preferences | PASS |
| 7 | Questionnaire / answers | PASS |
| 8 | Media assets / links | PASS |
| 9 | Primary media invariant | PASS |
| 10 | No migrations created | YES |
| 11 | B3 media repository | 8/8 PASS |
| 12 | B2 pre-visit questionnaire repository | 8/8 PASS |
| 13 | B1 patient profile family repositories | 5/5 PASS |
| 14 | A4A baseline schema models | 6/6 PASS |
| 15 | A3 baseline schema contract docs | PASS |
| 16 | A2 DB service gap audit docs | PASS |
| 17 | A1 patient profile family media docs | PASS |
| 18 | P0-07c manual pre-live checklist | PASS |
| 19 | Broad: care or recommendation | 231 PASS |
| 20 | Broad: patient and booking | 105 PASS |
| 21 | Unrelated failures | NONE |
| 22 | **GO / NO-GO for P0-08A4C** | **GO** |

## Bugs Fixed

| Bug | File | Category |
|---|---|---|
| Bootstrap DDL FK ordering (pvq → bookings) | `app/infrastructure/db/bootstrap.py` | baseline bootstrap |
| Media upsert NULL created_at/updated_at | `app/infrastructure/db/media_repository.py` | repository SQL |
| asyncpg ambiguous param on nullable filters | `app/infrastructure/db/media_repository.py` | repository SQL |
| B2 test fixture missing address_text | `tests/test_p0_08a4b2_…` | test fixture typo |
| B4 test interface mismatches | `tests/test_p0_08a4b4_…` | test contract alignment |
