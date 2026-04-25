# PR DOC-A2B-1 Report — Contextual doctor recommendation issue flow from booking/encounter context

## What changed
- Added contextual **Issue recommendation** CTA to the canonical doctor encounter panel keyboard, alongside existing **Add quick note** and **Back to booking** actions.
- Added **Issue recommendation** CTA to doctor booking panel only for safe `in_service` booking context.
- Implemented callback-driven contextual recommendation flow:
  - `drec:start:<encounter_id>:<booking_id|->`
  - `drec:type:<encounter_id>:<recommendation_type>:<booking_id|->`
  - `drec:cancel:<encounter_id>:<booking_id|->`
- Implemented context-bound pending recommendation capture and free-text processing using `Title | Body` format.
- Persisted recommendations through existing `DoctorOperationsService.issue_recommendation(...)` path (including patient aftercare delivery behavior already wired behind that service).
- Preserved existing `/recommend_issue ...` command fallback unchanged.

## Exact files changed
- `app/interfaces/bots/doctor/router.py`
- `tests/test_booking_linked_opens_12b1.py`
- `locales/en.json`
- `locales/ru.json`
- `docs/report/PR_DOC_A2B_1_REPORT.md`

## Pending recommendation context model
A tiny in-router pending context (`_PendingEncounterRecommendation`) is stored by Telegram user id and includes:
- `doctor_id`
- `clinic_id`
- `patient_id`
- `encounter_id`
- `booking_id`
- `recommendation_type` (mapped to existing domain-supported recommendation types)
- `created_at`

Lifecycle/cleanup behavior:
- TTL: 10 minutes
- cleared on success
- cleared on failure/unavailable
- cleared on explicit cancel
- expired context auto-cleared on next read

## How aftercare delivery path is preserved
- Contextual flow calls `DoctorOperationsService.issue_recommendation(...)` directly.
- No parallel/manual recommendation persistence path was introduced.
- This preserves the existing downstream delivery semantics already present in operations service (including patient proactive recommendation delivery attempt where configured).

## Encounter continuity after recommendation issue
- On successful contextual recommendation save:
  - doctor receives compact success hint,
  - canonical encounter panel is re-rendered,
  - encounter actions remain available (`Issue recommendation`, `Add quick note`, `Back to booking`).
- If encounter cannot be reloaded safely, flow still returns bounded success text without crashing.

## Tests added/updated
- Updated doctor encounter continuity assertions to include contextual recommendation CTA.
- Updated booking panel CTA assertions to enforce recommendation CTA shown only in safe (`in_service`) context.
- Added recommendation-flow tests for:
  - type selection and pending context path,
  - capture message invoking existing recommendation issuance path,
  - post-save return to canonical encounter context,
  - no hijack when no pending context exists,
  - malformed `Title | Body` handling,
  - `/recommend_issue` command fallback remains operational.

## Environment and execution notes
- Targeted doctor-router tests were run in this environment.
- No migrations were introduced.

## Explicit non-goals left for DOC-A2B-2 and DOC-A2C
### Left for DOC-A2B-2
- Optional care target selection (`target_kind:target_code`) in contextual callback flow.
- Any richer recommendation editor UX beyond bounded `Title | Body` input.

### Left for DOC-A2C
- Additional cross-action continuity polish beyond bounded recommendation issue path.
- Any broader stale/back hardening expansions outside this focused bounded flow.
