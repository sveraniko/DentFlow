# P0-08B1 Patient Profile Surface Report

## Summary
Implemented patient-home Profile entry and read-only patient profile surface with safe unavailable/not-found states and multi-profile selector.

## Files changed
- app/interfaces/bots/patient/router.py
- locales/ru.json
- locales/en.json
- tests/test_p0_08b1_patient_profile_surface.py

## Home profile entry
Added `phome:profile` button on patient home while preserving existing actions.

## Unavailable/no-profile states
Added readable unavailable and no-profile panels with recovery navigation.

## Single profile card behavior
Displays read-only profile card using profile + preference services; no edit action included.

## Multiple profile selector behavior
Shows linked profile selector and opens `profile:open:{patient_id}`.

## Locale keys added
Added all `patient.profile.*` keys for RU/EN including relationship/completion/channel labels.

## Raw/debug leakage guard
Profile panel avoids exposing raw identifiers and None values.

## Tests run with exact commands/results
See CI/local command output from this task execution.

## Grep checks
Executed requested grep checks for profile callbacks/keys, raw strings, id leakage assertions, and migration mentions.

## No schema/migration confirmation
No schema updates, migration files, or alembic revisions were added.

## Carry-forward
- B2 self profile edit wizard
- B3 contact/minimal identity editor
- C family management UI
- D booking patient selector integration
- E notification settings UI
- F branch preference UI

## GO/NO-GO for P0-08B2
GO (UI surface ready; read-only profile entry/selector/card behavior in place).
