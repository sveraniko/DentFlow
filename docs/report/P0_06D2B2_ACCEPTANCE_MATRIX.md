# P0-06D2B2 matrix

Recommendations:
- recommendations >= 7: **yes**
- domain-valid recommendation_type only: **yes**
- statuses cover issued/viewed/ack/accepted/declined/expired: **yes**
- patients valid: **yes**
- booking links valid: **yes**
- title/body non-empty: **yes**

Product targets:
- manual targets >= 4: **yes**
- set target exists: **yes**
- product target exists: **yes**
- direct product link exists: **yes**
- intentional invalid manual target exists: **yes**
- no unsupported catalog mapping types used as recommendation_type: **yes**

Care orders:
- orders >= 4: **yes**
- statuses cover confirmed/ready/fulfilled/canceled-or-expired: **yes**
- items reference real SKUs: **yes**
- totals match prices: **yes**
- reservations match statuses: **yes**
- active order for Sergey/3001: **yes**
- history order exists: **yes**

Loader:
- seed script exists: **yes**
- idempotent upsert behavior: **yes**
- reference validation: **yes**
- relative dates: **yes**
- CLI documented: **yes**

Regression:
- D2B1: **pass**
- D2A2: **pass**
- D2A1: **pass**
- C4 recommendations smoke: **pass**
- B4 care smoke: **pass**
- P0-05C smoke: **pass**
- care or recommendation: **218** passed
- patient and booking: **105** passed

## Source of truth
- Compiled from the post-PR D2B2 readiness report and recorded test runs in:
  - `docs/report/P0_06D2B2_RECOMMENDATIONS_CARE_ORDERS_DEMO_SEED_REPORT.md`
