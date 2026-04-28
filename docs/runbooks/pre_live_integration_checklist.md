# Pre-live Integration Checklist

Use this checklist as the operator gate before live validation and P0-07 patient pre-live smoke.

## A) Demo seed bootstrap

Choose one:

```bash
make seed-demo
```

or

```bash
python scripts/seed_demo.py --relative-dates --start-offset-days 1
```

Checks:
- Confirm expected 5-step order runs: stack1 -> stack2 -> stack3 -> care catalog -> recommendations/care orders.
- If available in environment, run DB-backed smoke from D2D2 (`tests/test_p0_06d2d2_db_backed_application_reads.py`).
- Do not call Google Calendar from `seed_demo`; it is not part of seed bootstrap.
- do not import Reference/Patient Google Sheets templates during seed bootstrap.

## B) Care catalog integration path

Choose one source:
- JSON demo bootstrap path (`seeds/care_catalog_demo.json` via seed demo).
- Google Sheets template path (`docs/templates/google_sheets/care_catalog/`).
- XLSX upload path.

Run one sync command:

```text
/admin_catalog_sync sheets <url_or_id>
```

or CLI:

```bash
python scripts/sync_care_catalog.py --clinic-id clinic_main sheets --sheet <url_or_id>
python scripts/sync_care_catalog.py --clinic-id clinic_main xlsx --path <path>
```

Checks:
- No fatal/validation sync errors.
- Products appear in patient care catalog surfaces.

## C) Google Calendar projection (one-way mirror)

Set env and configuration:
- `INTEGRATIONS_GOOGLE_CALENDAR_ENABLED=true`
- `INTEGRATIONS_GOOGLE_CALENDAR_CREDENTIALS_PATH` points to existing service-account JSON.
- Optional: `INTEGRATIONS_GOOGLE_CALENDAR_SUBJECT_EMAIL` for delegation.
- `INTEGRATIONS_DENTFLOW_BASE_URL` is set correctly.

Google-side checks:
- Share destination calendar with service-account identity.
- Confirm calendar IDs mapped for doctors/branches.

Projection commands:

```bash
python scripts/process_outbox_events.py --limit 200
python scripts/retry_google_calendar_projection.py --limit 100
```

Checks:
- Open `/admin_calendar` and `/admin_integrations`.
- Booking event appears in Google Calendar mirror.
- Keep truth boundary explicit: DentFlow is source of truth; no Calendar-to-DentFlow updates.

## D) Reference/patient templates (current boundary)

- Use `docs/templates/google_sheets/reference_and_patients/` as template/manual contract only.
- Keep demo bootstrap path on `seed_demo.py` and stack JSON files.
- Reference/patient Sheets templates are not automatic sync in this baseline.

## E) Before live

- Run final P0-07 patient pre-live smoke.
- Do not promise reference/patient Sheets sync as active integration until implemented in a dedicated future PR.
