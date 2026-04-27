# P0-06D2A1 matrix

Date: 2026-04-27

## Harness
- test_patient_db_load_and_seed fixed: **yes**
- no test skip/weakening: **yes**

## Date shift
- relative date mode exists: **yes**
- default static mode unchanged: **yes**
- ISO datetime fields shifted: **yes**
- date-only fields shifted: **yes**
- durations preserved: **yes**
- IDs preserved: **yes**
- original payload not mutated: **yes**

## CLI
- --relative-dates added: **yes**
- --start-offset-days added: **yes**
- no-flag behavior unchanged: **yes**

## Regression
- D1 audit test: **pass**
- booking seed bootstrap: **pass**
- runtime seed behavior: **pass**
- C4 recommendations smoke: **pass**
- B4 care smoke: **pass**
- P0-05C smoke: **pass**
- care or recommendation: **204 passed**
- patient and booking: **105 passed**
