# Reference + Patients Google Sheets Template Pack

## Purpose

These templates define operator-editable data for clinic reference and patient registry.

**Current baseline:** reference/patient Google Sheets sync is **not implemented** in DentFlow in this PR. This pack is **template only** for manual workflows and as a future import contract.

Active demo load path remains:
- `seeds/stack1_seed.json`
- `seeds/stack2_patients.json`
- `scripts/seed_demo.py`

## Included files

### Blank templates (headers only)
- `branches.csv`
- `doctors.csv`
- `services.csv`
- `doctor_access_codes.csv`
- `patients.csv`
- `patient_contacts.csv`
- `patient_preferences.csv`

### Demo templates (generated from current seed baseline)
- `demo_branches.csv`
- `demo_doctors.csv`
- `demo_services.csv`
- `demo_doctor_access_codes.csv`
- `demo_patients.csv`
- `demo_patient_contacts.csv`
- `demo_patient_preferences.csv`

### Contract/meta docs
- `reference_patient_sheets_manifest.json`

## Required Google Sheet tab names

Tab names must match exactly:
- `branches`
- `doctors`
- `services`
- `doctor_access_codes`
- `patients`
- `patient_contacts`
- `patient_preferences`

## How to create the Google Sheet

1. Create a Google Sheet.
2. Create tabs with the exact names above.
3. Paste either blank headers or demo CSV rows into each matching tab.
4. Keep IDs stable (`branch_id`, `doctor_id`, `service_id`, `patient_id`, codes).
5. Export as CSV/XLSX for manual workflows or future import tooling.

## Current import status (truth boundary)

- Care catalog Sheets sync exists.
- Reference/patient Sheets sync is not implemented in this PR.
- This pack is template only and should be used as:
  - manual operator worksheet;
  - future import contract;
  - source for updating JSON seed files manually.

## Seed-to-template mapping notes

These templates use import-friendly column names, with explicit mapping to current seed keys:

- `branches.address` maps from `stack1_seed.json` field `address_text`.
- `branches.locale` maps from clinic `default_locale`.
- `branches.is_active` maps from `status == active`.
- `doctors.specialty` maps from `specialty_code`.
- `doctors.default_branch_id` maps from `branch_id`.
- `services.category` maps from `specialty_required`.
- `doctor_access_codes.service_scope` / `branch_scope` map from array fields to comma-separated IDs.
- `patients.full_name` maps from `display_name` (fallback `full_name_legal`).
- `patients.sex` maps from `sex_marker`.
- `patient_contacts.clinic_id` is derived from the referenced patient.
- `patient_preferences.contact_time_window` maps from `{from,to}` to `HH:MM-HH:MM`.
- `patient_preferences.timezone` is derived from clinic timezone.

## Future import design (planned, not implemented)

```bash
python scripts/sync_reference_patient_sheets.py --clinic-id clinic_main sheets --sheet <url_or_id>
python scripts/sync_reference_patient_sheets.py --clinic-id clinic_main xlsx --path <path>
```

These commands are placeholders for a future PR and do not exist today.

## Validation rules

- IDs must be stable over time.
- `branch_id` must exist before doctors/services reference it.
- `doctor_id` in `doctor_access_codes` must exist.
- `service_scope` IDs in access codes must exist in `services`.
- `patient_contacts.patient_id` and `patient_preferences.patient_id` must exist in `patients`.
- Telegram `contact_value` should be numeric user ID encoded as string.
- Phone values should be E.164-ish or consistently normalized.
- Duplicate primary contacts (same patient + contact_type) are invalid.
- Deleting rows should be handled cautiously (prefer soft deactivation patterns).

## Data governance

- Google Sheets here are operational registry templates, not medical chart records.
- Do not put sensitive clinical notes in general patient sheet columns.
- Keep share access tightly controlled.
- Exported files must not contain secrets.
