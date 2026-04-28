# P0-07B3 Matrix (2026-04-28)

## DB lane
- DENTFLOW_TEST_DB_DSN used: **yes**
- DB test executed, not skipped: **yes**
- safe DB guard active: **yes**
- seed-demo run before assertions: **yes**

## Booking mutation
- protected doctor code still works: **yes**
- new booking mutation green: **yes**
- edit time / hold release green: **yes**
- existing booking action green: **yes**

## Recommendation mutation
- ack persists: **yes**
- accept persists: **yes**
- decline persists: **yes**
- invalid-state safe: **yes**
- post-mutation list/detail green: **yes**

## Care mutation
- in-stock reserve green: **yes**
- order/items/reservation green: **yes**
- repeat/reorder green or safe constraint: **yes**

## Out-of-stock invariant
- failure detected: **yes**
- no reservation created: **yes**
- no active user-visible invalid order: **yes**
- technical leftover documented if present: **yes** (no leftover detected in assertions)

## Post-mutation read
- booking surface clean: **yes**
- recommendation surface clean: **yes**
- care order surface clean: **yes**
- no raw/debug leakage: **yes**

## Safety
- no live Google call: **yes**
- callback namespace sane: **yes**

## Regression
- P0-07B2: **pass**
- P0-07B1: **pass**
- P0-07A: **pass**
- D2D2: **pass**
- E4: **pass**
- C4: **pass**
- B4: **pass**
- P0-05C: **pass**
- care or recommendation: **3 passed**
- patient and booking: **6 passed**
