# P0-06E3 Reference/Patient Sheets Templates Report

## Summary

P0-06E3 delivers a Google Sheets-ready template pack for reference/patient registry data without adding runtime Sheets sync. The pack includes blank CSV contracts, demo CSVs mapped from current seed files, a manifest, documentation, and validation tests.

## Files changed

- `docs/templates/google_sheets/reference_and_patients/README.md`
- `docs/templates/google_sheets/reference_and_patients/reference_patient_sheets_manifest.json`
- `docs/templates/google_sheets/reference_and_patients/branches.csv`
- `docs/templates/google_sheets/reference_and_patients/doctors.csv`
- `docs/templates/google_sheets/reference_and_patients/services.csv`
- `docs/templates/google_sheets/reference_and_patients/doctor_access_codes.csv`
- `docs/templates/google_sheets/reference_and_patients/patients.csv`
- `docs/templates/google_sheets/reference_and_patients/patient_contacts.csv`
- `docs/templates/google_sheets/reference_and_patients/patient_preferences.csv`
- `docs/templates/google_sheets/reference_and_patients/demo_branches.csv`
- `docs/templates/google_sheets/reference_and_patients/demo_doctors.csv`
- `docs/templates/google_sheets/reference_and_patients/demo_services.csv`
- `docs/templates/google_sheets/reference_and_patients/demo_doctor_access_codes.csv`
- `docs/templates/google_sheets/reference_and_patients/demo_patients.csv`
- `docs/templates/google_sheets/reference_and_patients/demo_patient_contacts.csv`
- `docs/templates/google_sheets/reference_and_patients/demo_patient_preferences.csv`
- `scripts/export_reference_patient_demo_to_csv_templates.py`
- `tests/test_p0_06e3_reference_patient_sheets_templates.py`
- `docs/92_seed_data_and_demo_fixtures.md`
- `docs/80_integrations_and_infra.md`

## Template files created

Blank CSV headers only:
- branches
- doctors
- services
- doctor_access_codes
- patients
- patient_contacts
- patient_preferences

## Demo CSV files created

Seed-derived demos include D2A2 baseline IDs:
- branches: `branch_central`
- doctors: `doctor_anna`, `doctor_boris`, `doctor_irina`
- services: `service_consult`, `service_cleaning`, `service_treatment`, `service_urgent`
- doctor access codes: `ANNA-001`, `BORIS-HYG`, `IRINA-TREAT`
- patients: `patient_sergey_ivanov`, `patient_elena_ivanova`, `patient_giorgi_beridze`, `patient_maria_petrova`
- contacts include telegram `3001`, `3002`, `3004`

## Manifest structure

`reference_patient_sheets_manifest.json` defines:
- template name/version
- required tabs
- blank/demo file names per tab
- column contract per tab
- source seed files
- import status (`template_only`)
- future sync command examples (planned placeholders)

## Mapping from stack1/stack2 seed to CSV

- `branches.address <- address_text`
- `branches.locale <- clinics.default_locale`
- `is_active <- status == active`
- `doctors.specialty <- specialty_code`
- `doctors.default_branch_id <- branch_id`
- `services.category <- specialty_required`
- `doctor_access_codes.service_scope/branch_scope <- JSON arrays -> comma-separated`
- `patients.full_name <- display_name (fallback full_name_legal)`
- `patients.preferred_language <- patient_preferences.preferred_language (by patient_id)`
- `patients.sex <- sex_marker`
- `patient_contacts.clinic_id <- derived via patient_id`
- `patient_preferences.contact_time_window <- from-to string`
- `patient_preferences.timezone <- clinic timezone`

## Reference validation

Implemented via `tests/test_p0_06e3_reference_patient_sheets_templates.py`:
- file existence checks
- headers vs manifest exact match
- D2A2 ID presence assertions
- cross-reference checks:
  - doctors->branches
  - access-codes->doctors/services
  - patient_contacts->patients
  - patient_preferences->patients
- row count parity with seed files for direct mappings

## Truth boundary

Documented across template README + infra/seed docs:
- Care catalog Sheets sync exists.
- Reference/patient Sheets sync is **not implemented**.
- This pack is **template only**.
- `seed_demo.py` + seed JSON remains active demo load path.

## Docs updated

- `docs/92_seed_data_and_demo_fixtures.md` now references template location/status and D2A2 relation.
- `docs/80_integrations_and_infra.md` now adds non-active integration note + future command placeholders.

## Tests run (exact commands/results)

- `python -m compileall app tests scripts` ✅ pass
- `pytest -q tests/test_p0_06e3_reference_patient_sheets_templates.py` ✅ `8 passed`
- `pytest -q tests/test_p0_06e2_google_calendar_runbook_config.py` ✅ `11 passed`
- `pytest -q tests/test_p0_06e1_care_catalog_sheets_template.py` ✅ `5 passed`
- `pytest -q tests/test_p0_06d2c_seed_demo_bootstrap.py` ✅ `9 passed`
- `pytest -q tests/test_p0_06d2a2_core_demo_seed_pack.py` ✅ `7 passed`
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py` ✅ `9 passed`
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` ✅ `3 passed`
- `pytest -q tests -k "care or recommendation"` ✅ `227 passed, 547 deselected`
- `pytest -q tests -k "patient and booking"` ✅ `105 passed, 669 deselected`

DB skip note:
- No DB-only acceptance lane was required in this E3 run; no `DENTFLOW_TEST_DB_DSN` skip blocked listed commands.

## Grep checks (exact commands/results)

- `rg "reference_and_patients|demo_doctors.csv|demo_patients.csv|reference_patient_sheets_manifest" docs/templates docs tests`
  - confirms template pack/docs/tests mentions.

- `rg "Reference/patient Sheets sync is not implemented|template only|seed_demo.py" docs/templates/google_sheets/reference_and_patients/README.md docs/92_seed_data_and_demo_fixtures.md docs/80_integrations_and_infra.md`
  - confirms truth-boundary wording exists.

- `rg "sync_reference_patient_sheets.py" docs/templates/google_sheets/reference_and_patients/README.md docs/80_integrations_and_infra.md`
  - command appears as planned placeholder only.

- `rg "doctor_boris|doctor_irina|service_treatment|patient_sergey_ivanov|3001" docs/templates/google_sheets/reference_and_patients tests`
  - confirms D2A2 data appears in demo CSVs and tests.

## Defects found/fixed

- No functional runtime defects introduced.
- Added explicit mapping documentation for seed key differences to avoid schema ambiguity.

## Carry-forward

- P0-06E4 integration readiness smoke/report should validate contract continuity.
- A future PR may implement actual `sync_reference_patient_sheets.py` import path (Sheets/XLSX) using this contract.

## GO/NO-GO recommendation for E4

**GO** for E4 readiness tasks.

Rationale:
- contract pack exists;
- tests enforce manifest/header/data/references boundary;
- docs explicitly avoid false claim of active sync.
