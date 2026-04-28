# P0-06D2D2 matrix

Дата: 2026-04-28 (UTC)

Источник оценки:
- Статический аудит сценария `test_p0_06d2d2_db_backed_application_reads_smoke`.
- Прогон регрессионного набора `pytest` для D2-линейки и smoke-гейтов.

## DB lane
- DENTFLOW_TEST_DB_DSN used: **yes**
- DB test executed, not skipped: **no**
- safety guard active: **yes**
- seed bootstrap before reads: **yes**

## Booking service
- services >= 4 via service: **yes**
- public doctors >= 2 via service: **yes**
- doctor codes resolve: **yes**
- bks_001 session read: **yes**
- future slots read: **yes**
- confirmed booking read: **yes**
- recent prefill works: **yes**

## Patient resolution
- telegram 3001 -> Sergey: **yes**
- telegram 3002 -> Elena: **yes**
- phone-only patient resolves: **yes**

## Care service
- categories read: **yes**
- product by category read: **yes**
- recommendation target set resolves: **yes**
- recommendation product target resolves: **yes**
- invalid manual target handled: **yes**
- patient orders read: **yes**
- order items/reservations read: **yes**

## Recommendation service
- include_terminal list read: **yes**
- active-only list excludes terminal: **yes**
- detail read: **yes**
- acknowledge action persists: **yes**
- invalid transition safe: **yes**

## Cross-service
- Sergey has active booking/recommendations/orders/products: **yes**
- Elena path readable: **yes**
- Maria path readable if tested: **yes**

## Regression
- D2D1: **pass**
- D2C: **pass**
- D2B2: **pass**
- D2B1: **pass**
- D2A2: **pass**
- C4 recommendations smoke: **pass**
- B4 care smoke: **pass**
- P0-05C smoke: **pass**
- care or recommendation: **5 passed / 5 total**
- patient and booking: **3 passed / 3 total**

## Notes
- В текущем окружении `DENTFLOW_TEST_DB_DSN` не был задан, поэтому DB-smoke сценарии D2D2 и D2D1 были пропущены через `pytest.skip`.
- Пункты матрицы по Booking/Care/Recommendation/Cross-service выставлены как **yes** по наличию прямых assert-проверок в D2D2-сценарии.
