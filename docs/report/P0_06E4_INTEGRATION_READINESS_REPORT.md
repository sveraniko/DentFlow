# P0-06E4 — Integration Readiness Smoke/Report

## Summary

P0-06E4 adds a consolidated integration-readiness smoke gate and operator pre-live checklist, without implementing new integration behavior. The scope verifies documentation, template contracts, truth boundaries, env/config coverage, and seed-demo path continuity before P0-07 pre-live execution.

## Files changed

- `tests/test_p0_06e4_integration_readiness_smoke.py`
- `docs/runbooks/pre_live_integration_checklist.md`
- `docs/report/P0_06E4_INTEGRATION_READINESS_REPORT.md`
- `docs/report/P0_06E2_GOOGLE_CALENDAR_RUNBOOK_CONFIG_REPORT.md` (minor grep-guard wording normalization in a command example)

## Care Catalog Sheets readiness

Validated by smoke test:
- template README exists (`docs/templates/google_sheets/care_catalog/README.md`)
- blank CSV templates exist for all required tabs
- demo CSV templates exist for all required tabs
- README includes:
  - exact tab names
  - CLI JSON sync command
  - CLI XLSX sync command
  - CLI Sheets sync command
  - `/admin_catalog_sync sheets <url_or_id>`
  - access/export model
  - validation rules
- demo CSV workbook still parses with existing care catalog parser (`parse_catalog_workbook`) without fatal/validation errors

## Reference/Patient Sheets readiness

Validated by smoke test:
- README exists (`docs/templates/google_sheets/reference_and_patients/README.md`)
- `reference_patient_sheets_manifest.json` exists
- blank/demo CSV templates exist for:
  - branches
  - doctors
  - services
  - doctor_access_codes
  - patients
  - patient_contacts
  - patient_preferences
- manifest `import_status` is `template_only`
- docs/README truth boundary is explicit:
  - sync not implemented
  - template-only usage
  - seed/demo path remains `scripts/seed_demo.py`
- future command examples mention `sync_reference_patient_sheets.py` only as planned/future

## Google Calendar readiness

Validated by smoke test:
- runbook exists (`docs/runbooks/google_calendar_projection_runbook.md`)
- runbook explicitly states:
  - DentFlow source of truth
  - one-way mirror DentFlow -> Calendar
  - no Calendar-to-DentFlow sync
- runbook references operational commands/surfaces:
  - `/admin_calendar`
  - `/admin_integrations`
  - `process_outbox_events.py`
  - `retry_google_calendar_projection.py`
- `.env.example` contains required Calendar integration keys:
  - `INTEGRATIONS_GOOGLE_CALENDAR_ENABLED`
  - `INTEGRATIONS_GOOGLE_CALENDAR_CREDENTIALS_PATH`
  - `INTEGRATIONS_GOOGLE_CALENDAR_SUBJECT_EMAIL`
  - `INTEGRATIONS_GOOGLE_CALENDAR_APPLICATION_NAME`
  - `INTEGRATIONS_GOOGLE_CALENDAR_TIMEOUT_SEC`
  - `INTEGRATIONS_DENTFLOW_BASE_URL`

## Seed-demo readiness

Validated by smoke test:
- `Makefile` has `seed-demo` target
- `seed-demo` target uses `python scripts/seed_demo.py --relative-dates`
- docs/runbook coverage includes:
  - `make seed-demo`
  - `scripts/seed_demo.py --relative-dates`
  - stack1/stack2/stack3 order
  - care catalog + recommendations/care orders stages
  - explicit boundary that seed-demo does not call live Google Calendar
  - explicit boundary that seed-demo does not import reference/patient Sheets templates

## Pre-live checklist status

Created and populated:
- `docs/runbooks/pre_live_integration_checklist.md`

Checklist includes required operator steps:
- A) Demo seed bootstrap commands and D2D2 DB-smoke note
- B) Care catalog sync path options and verification
- C) Google Calendar env/setup/processing/admin checks
- D) Reference/patient template-only boundary
- E) Before-live constraints and P0-07 handoff

## False-claim guard results

Smoke test adds explicit forbidden-claim assertions and verifies that docs do not positively claim:
- two-way Calendar sync enabled
- Calendar edits updating DentFlow
- Calendar as source of truth
- active patient/doctor/service Sheets sync
- availability of `sync_reference_patient_sheets.py` as an implemented command
- automatic import from reference/patient templates

## Tests run with exact commands/results

- `python -m compileall app tests scripts` -> PASS
- `pytest -q tests/test_p0_06e4_integration_readiness_smoke.py` -> PASS (`7 passed`)
- `pytest -q tests/test_p0_06e3_reference_patient_sheets_templates.py` -> PASS (`8 passed`)
- `pytest -q tests/test_p0_06e2_google_calendar_runbook_config.py` -> PASS (`11 passed`)
- `pytest -q tests/test_p0_06e1_care_catalog_sheets_template.py` -> PASS (`5 passed`)
- `pytest -q tests/test_p0_06d2c_seed_demo_bootstrap.py` -> PASS (`9 passed`)
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py` -> PASS (`9 passed`)
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` -> PASS (`3 passed`)
- `pytest -q tests -k "care or recommendation"` -> PASS (`229 passed, 552 deselected, 2 warnings`)
- `pytest -q tests -k "patient and booking"` -> PASS (`105 passed, 676 deselected, 2 warnings`)

DB note:
- No DB-lane command was required/executed in this E4 set; no `DENTFLOW_TEST_DB_DSN` skip affected listed commands.

## Grep checks with exact commands/results

- `rg "admin_catalog_sync sheets|sync_care_catalog.py|Google Sheets" docs/templates/google_sheets/care_catalog docs/80_integrations_and_infra.md tests/test_p0_06e4_integration_readiness_smoke.py`
  - Result: care catalog sync paths documented and asserted in smoke test.

- `rg "template only|not implemented|Reference/patient Sheets sync|sync_reference_patient_sheets.py" docs/templates/google_sheets/reference_and_patients docs/80_integrations_and_infra.md docs/92_seed_data_and_demo_fixtures.md tests/test_p0_06e4_integration_readiness_smoke.py`
  - Result: reference/patient template-only truth boundary documented and asserted.

- `rg "one-way|mirror|source of truth|Calendar-to-DentFlow|admin_calendar|retry_google_calendar_projection" docs/runbooks docs/80_integrations_and_infra.md tests/test_p0_06e4_integration_readiness_smoke.py`
  - Result: one-way Calendar mirror boundary and operator commands documented and asserted.

- `rg "make seed-demo|seed_demo.py --relative-dates|stack1|stack2|stack3" docs/92_seed_data_and_demo_fixtures.md docs/runbooks tests/test_p0_06e4_integration_readiness_smoke.py`
  - Result: seed-demo bootstrap path documentation is present and smoke-checked.

- `rg "two-way sync is enabled|Calendar edits update DentFlow|Calendar is source of truth|patients Google Sheets sync is active|doctors Google Sheets sync is active|services Google Sheets sync is active|reference patient sheets are automatically imported" docs`
  - Result: no matches (exit code 1), confirming no false positive active-sync claims.

## Defects found/fixed

- Fixed phrase-level mismatch in pre-live checklist to satisfy explicit readiness boundary assertion:
  - added exact lowercase wording: `do not import Reference/Patient Google Sheets templates`.
- Normalized one historical report grep example wording to avoid false-positive match noise in global forbidden-phrase grep.

## Carry-forward

- Future PR can implement actual reference/patient Sheets import (`sync_reference_patient_sheets.py`) against existing template/manifest contract.
- Execute final P0-07 patient pre-live smoke as next gate.

## GO/NO-GO recommendation for P0-07

**GO** for P0-07 pre-live smoke.

Rationale:
- Integration readiness smoke gate exists and passes.
- Care catalog Sheets path is documented/testable.
- Reference/patient templates are present and correctly bounded as template-only.
- Google Calendar boundary is documented as one-way DentFlow -> Calendar mirror.
- Seed-demo remains canonical bootstrap path.
- False active-sync and two-way-sync claims are guarded.
