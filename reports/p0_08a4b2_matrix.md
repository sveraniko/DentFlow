# P0-08A4B2 matrix (2026-04-29)

Questionnaire repository:
- get_pre_visit_questionnaire: **yes**
- list_pre_visit_questionnaires: **yes**
- upsert_pre_visit_questionnaire: **yes**
- complete_pre_visit_questionnaire: **yes**
- latest by booking: **yes**
- latest by patient: **yes**

Answer repository:
- list answers: **yes**
- upsert answer: **yes**
- bulk upsert answers: **yes**
- delete answer: **yes**
- JSONB answer_value handled: **yes**

DB:
- DB-backed tests run: **yes**
- DB skip documented: **yes**

Truth boundary:
- no Alembic: **yes**
- no migrations: **yes**
- no UI/service claims: **yes**

Regression:
- B2 tests: **pass**
- B1 tests: **pass**
- A4A tests: **pass**
- A3/A2/A1 tests: **pass**
- care/recommendation: **185 passed**
- patient/booking: **297 passed**
