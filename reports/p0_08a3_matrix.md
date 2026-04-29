# P0-08A3 matrix (2026-04-29)

Contract:
- baseline contract doc exists: **yes**
- profile schema contract: **yes**
- family schema contract: **yes**
- preference extension contract: **yes**
- questionnaire contract: **yes**
- media contract: **yes**

Services:
- PatientProfileService contract: **yes**
- PatientFamilyService contract: **yes**
- PatientPreferenceService contract: **yes**
- BookingPatientSelectorService contract: **yes**
- PreVisitQuestionnaireService contract: **yes**
- PatientMediaService contract: **yes**

Integration:
- booking selector contract: **yes**
- document bridge contract: **yes**
- media phase plan: **yes**

Truth boundary:
- no Alembic/migrations: **yes**
- no implementation claims: **yes**
- A1/A2 docs linked: **yes**

Regression:
- A3 test: **pass**
- A2 test: **pass**
- A1 test: **pass**
- care/recommendation: **3 passed**
- patient/booking: **6 passed**

Links:
- A1: `reports/p0_07c_matrix.md`
- A2: `reports/p0_08a2_matrix.md`
