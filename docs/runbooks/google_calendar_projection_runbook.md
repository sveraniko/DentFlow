# Google Calendar Projection Runbook

## 1) Purpose

Google Calendar integration in DentFlow is an **operational visual mirror** of booking schedule state and is **not booking truth**.

- DentFlow is the booking truth and the place where admin actions happen.
- Google Calendar is a projection for visibility only.
- Operators must use DentFlow for create/update/cancel booking actions, not Google Calendar.

## 2) Projection direction and truth boundary

### Direction (baseline)

one-way only:

- DentFlow booking events -> Google Calendar event upsert/cancel.

### Explicitly forbidden / non-goals in this baseline

- No Calendar-to-DentFlow sync.
- Calendar edits updating DentFlow.
- Calendar as availability source.
- Calendar as reminder engine.
- Deleting bookings from Calendar as a business action.
- Two-way sync.

## 3) Required env/config variables

```env
INTEGRATIONS_GOOGLE_CALENDAR_ENABLED=true
INTEGRATIONS_GOOGLE_CALENDAR_CREDENTIALS_PATH=/path/to/service-account.json
INTEGRATIONS_GOOGLE_CALENDAR_SUBJECT_EMAIL=
INTEGRATIONS_GOOGLE_CALENDAR_APPLICATION_NAME=DentFlow
INTEGRATIONS_GOOGLE_CALENDAR_TIMEOUT_SEC=10

INTEGRATIONS_DENTFLOW_BASE_URL=https://your-dentflow-host
```

Behavior notes:

- `INTEGRATIONS_GOOGLE_CALENDAR_ENABLED=false` means projector skips Google writes by returning a disabled gateway.
- `enabled=true` with missing `INTEGRATIONS_GOOGLE_CALENDAR_CREDENTIALS_PATH` returns a misconfigured gateway (`google_calendar_credentials_path_required`).
- `INTEGRATIONS_GOOGLE_CALENDAR_SUBJECT_EMAIL` is optional and is used only for domain-wide delegation/impersonation.
- `INTEGRATIONS_DENTFLOW_BASE_URL` is used in projected event descriptions/links.

## 4) Google setup checklist

1. Create/select Google Cloud project.
2. Enable Google Calendar API.
3. Create service account.
4. Download service account JSON.
5. Share target calendars with service-account email, or configure domain-wide delegation when using subject impersonation.
6. Create or identify doctor/branch target calendars.
7. Set calendar IDs in DentFlow doctor calendar mapping data.
8. Run projection processing worker/commands.

> DentFlow does not auto-create Google calendars in this baseline.

## 5) Calendar ID mapping model

Current data flow:

- Booking -> Google event mapping is stored in `integration.google_calendar_booking_event_map` (booking id to target calendar id and external event id).
- Doctor target calendar id is read from `integration.google_calendar_doctor_calendars.calendar_external_id` when active mapping exists.
- If doctor mapping is absent, repository falls back to `doctor_{doctor_id}`.

Important fallback caveat:

- `doctor_{doctor_id}` is a local fallback identifier from repository query logic.
- It is useful for tests/demo and for explicit visibility of missing mapping.
- It is **not** guaranteed to be a valid real Google Calendar ID in production.

## 6) Operator/admin commands and surfaces

Worker/script commands:

- `python scripts/process_outbox_events.py --limit 200`
- `python scripts/retry_google_calendar_projection.py --limit 100`
- `python scripts/retry_google_calendar_projection.py --booking-id <booking_id>`

Admin bot surfaces:

- `/admin_calendar`
- `/admin_integrations`

## 7) Operational flow

1. Booking is created/updated/canceled in DentFlow.
2. Booking domain events are written to outbox.
3. Projector/outbox processor consumes booking events.
4. Google Calendar gateway performs upsert/cancel.
5. Event mapping state is upserted in integration mapping table.
6. `/admin_calendar` shows projection awareness/read model.
7. Failed projection can be retried with retry script.

## 8) Troubleshooting checklist

Common failure signatures and checks:

- `google_calendar_integration_disabled`
  - Check `INTEGRATIONS_GOOGLE_CALENDAR_ENABLED`.
- `google_calendar_credentials_path_required`
  - `enabled=true` but credentials path missing/blank.
- `google_calendar_dependencies_missing`
  - Google client libraries unavailable in runtime image.
- Google API `403`
  - Calendar is not shared with service account, or delegation scopes/policies are incorrect.
- Wrong calendar id
  - Verify doctor-to-calendar mapping in DB; do not rely on fallback id in production.
- Event not updating because mapping missing
  - Validate rows in `integration.google_calendar_booking_event_map` and upstream booking projection data.
- Worker not running
  - Start worker/runtime processing outbox events.
- Outbox backlog
  - Run `python scripts/process_outbox_events.py --limit 200` repeatedly until backlog stabilizes.
- Timezone mismatch
  - Check branch/clinic timezone data and rendered local time expectations.
- Service account subject/domain delegation confusion
  - If `INTEGRATIONS_GOOGLE_CALENDAR_SUBJECT_EMAIL` is set, confirm domain-wide delegation is configured; otherwise keep subject empty.

## 9) Safety and data handling notes

- Never commit service-account JSON to git.
- Keep credentials path in environment/runtime secret storage.
- Calendar descriptions must avoid sensitive clinical details.
- Calendar is an operational schedule mirror, not a medical chart.
