# P0-08A4B1 — Patient Profile / Family / Preferences Repository Foundation Report

## Summary
Implemented repository-layer methods for patient profile details, patient relationships/linked profiles, and patient preference extension fields.

## Files changed
- `app/infrastructure/db/patient_repository.py`
- `tests/test_p0_08a4b1_patient_profile_family_repositories.py`

## Repository methods added
- `get_profile_details`
- `upsert_profile_details`
- `get_profile_completion_state`
- `list_relationships`
- `list_linked_profiles_for_telegram`
- `upsert_relationship`
- `deactivate_relationship`
- `get_patient_preferences`
- `upsert_patient_preferences`
- `update_notification_preferences`
- `update_branch_preferences`

## Profile details behavior
- Added DB read by clinic+patient.
- Added idempotent upsert with `updated_at=NOW()` on conflict.
- Preserves `created_at` via default/unchanged conflict behavior.
- Returns persisted row mapped to `PatientProfileDetails`.

## Relationship / linked profiles behavior
- Added upsert/list/deactivate repository methods.
- Added Telegram-linked profile query that resolves manager from active telegram contact and returns manager + related profiles.
- Includes dedupe and ordering: manager first, then default-booking, then display name.
- Supports `include_inactive` filtering for consent/patient status.

## Preference extension behavior
- Extended persistence SQL for new preference fields:
  - `notification_recipient_strategy`
  - `quiet_hours_start`
  - `quiet_hours_end`
  - `quiet_hours_timezone`
  - `default_branch_id`
  - `allow_any_branch`
- Added get/upsert/update methods with preserve-if-None semantics for notification updates.
- Added creation path for missing preference row with safe dataclass defaults.

## DB-backed tests executed or skipped
- This run executed non-DB tests only.
- DB-backed lane was not executed in this report run.
- A4B4 repository DB smoke remains carry-forward mandatory.

## No Alembic / no migrations confirmation
- No migration files were added.
- No Alembic version directory created.

## Tests run with exact commands/results
- See command log section in execution output.

## Grep checks
- Confirmed new repository method names and preference extension fields present in `app`/`tests`.
- Confirmed no migration-file additions.

## Defects found/fixed
- Preference persistence query previously did not include new A4A extension fields; now included.

## Carry-forward
- P0-08A4B2 questionnaire repository.
- P0-08A4B3 media repository.
- P0-08A4B4 repository DB smoke.

## GO/NO-GO for P0-08A4B2
- **GO** for repository follow-on, with DB-backed validation to be completed in A4B4.
