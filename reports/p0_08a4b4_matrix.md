# P0-08A4B4 matrix (2026-04-29)

DB lane:
- DENTFLOW_TEST_DB_DSN used: **yes**
- DB test executed, not skipped: **yes**
- safe DB guard active: **yes**
- seed-demo run before assertions: **yes**

Profile:
- profile upsert/read/update: **yes**
- completion state read: **yes**

Family:
- relationship upsert/list: **yes**
- linked profiles by Telegram: **yes**
- deactivate/include_inactive: **yes**

Preferences:
- notification prefs update: **yes**
- branch prefs update: **yes**
- existing fields preserved: **yes**

Questionnaire:
- questionnaire upsert/list/complete: **yes**
- answers JSONB round-trip: **yes**
- latest by booking/patient: **yes**

Media:
- asset upsert/read/update: **yes**
- telegram unique id lookup: **yes**
- link attach/list/remove: **yes**
- owner media join: **yes**
- primary media invariant: **yes**
- missing primary link safe: **yes**

Truth boundary:
- no external API calls: **yes**
- no Alembic: **yes**
- no migrations: **yes**

Regression:
- B4 tests: **fail**
- B3/B2/B1 tests: **fail**
- A4A/A3/A2/A1 tests: **pass**
- care/recommendation: **230 passed**
- patient/booking: **105 passed**
