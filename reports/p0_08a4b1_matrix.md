# P0-08A4B1 matrix (2026-04-29)

Profile repository:
- get_profile_details: **yes**
- upsert_profile_details: **yes**
- get_profile_completion_state: **yes**
- idempotent update: **yes**

Family repository:
- list_relationships: **yes**
- list_linked_profiles_for_telegram: **yes**
- upsert_relationship: **yes**
- deactivate_relationship: **yes**
- self + related profiles returned: **yes**

Preferences:
- get_patient_preferences: **yes**
- upsert_patient_preferences: **yes**
- update_notification_preferences: **yes**
- update_branch_preferences: **yes**
- new fields mapped: **yes**

DB:
- DB-backed tests run: **skipped**
- DB skip documented: **yes**

Truth boundary:
- no Alembic: **yes**
- no migrations: **yes**
- no UI/service claims: **yes**

Regression:
- B1 tests: **pass**
- A4A tests: **pass**
- A3/A2/A1 tests: **pass**
- care/recommendation: **185 passed**
- patient/booking: **297 passed**
