# P0-08A4A Matrix

## Schema
- patient_profile_details DDL: **yes**
- patient_relationships DDL: **yes**
- patient_preferences extensions: **yes**
- pre_visit_questionnaires DDL: **yes**
- pre_visit_questionnaire_answers DDL: **yes**
- media_assets reconciled: **yes**
- media_links DDL: **yes**
- no duplicate media_assets table: **yes**

## Domain
- PatientProfileDetails: **yes**
- PatientRelationship: **yes**
- PatientPreference extended: **yes**
- PreVisitQuestionnaire: **yes**
- PreVisitQuestionnaireAnswer: **yes**
- MediaAsset: **yes**
- MediaLink: **yes**

## Truth boundary
- no Alembic: **yes**
- no migrations: **yes**
- no UI/service/media upload claims: **yes**

## Regression
- A4A tests: **pass**
- A3 tests: **pass**
- A2 tests: **pass**
- A1 tests: **pass**
- care/recommendation: **185 passed**
- patient/booking: **297 passed**
