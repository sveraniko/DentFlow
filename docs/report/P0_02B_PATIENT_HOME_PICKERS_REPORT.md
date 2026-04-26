# P0-02B — Patient home + service/doctor picker polish report

## Summary
Implemented UX polish for the first patient booking surfaces:
- Product-style `/start` home panel copy and emoji hierarchy.
- Service picker panel copy + emoji labels + Back/Home navigation + empty state.
- Doctor picker panel copy + Any Doctor + Doctor Code CTA + Back/Home navigation.
- Minimal doctor access code flow (prompt, mode routing, validation, retry UX, slot continuation).
- Quick booking suggestion panel now includes Home navigation.

Out of scope items were not changed: slot pagination/localized slot time formatting, CardShellRenderer rewrite, router split, DB schema changes.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `app/application/clinic_reference.py`
- `locales/ru.json`
- `locales/en.json`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `tests/test_patient_existing_booking_shortcut_pat_a3_2.py`

## Home panel before/after
- Before: plain scaffold copy and unstyled buttons.
- After: localized DentFlow intro panel with explanatory body and emoji action hierarchy:
  - 🦷 Book appointment
  - 📅 My booking
  - 💬 Doctor recommendations
  - 🪥 Care & hygiene

## Service picker before/after
- Before: single plain prompt and service rows only.
- After:
  - Readable panel copy with guidance to start from consultation.
  - Emoji-prefixed service buttons while preserving service IDs/callback payloads.
  - Navigation row with Back/Home callbacks.
  - Empty state panel with Home CTA when no services are returned.

## Doctor picker before/after
- Before: plain prompt and any/specific doctor buttons.
- After:
  - Readable panel copy describing specific doctor vs nearest available.
  - `👩‍⚕️ Any available doctor` action.
  - Public doctors list preserved.
  - `🔑 I have a doctor code` action.
  - Back/Home row.

## Doctor code flow implementation notes
- Added reference resolver: `ClinicReferenceService.resolve_doctor_access_code(...)`.
- Validation checks:
  - clinic match
  - active status
  - code match (normalized)
  - expiration
  - optional service scope / branch scope compatibility
  - doctor existence + public booking enabled
- UI flow:
  - `book:doc_code:{session_id}` opens doctor-code prompt and sets `flow.booking_mode = "new_booking_doctor_code"`.
  - Generic text routing handles doctor code submission when in that mode.
  - Valid code updates doctor preference to specific doctor and continues to slot panel.
  - Invalid code shows retry error and keeps Back/Home actions.
- Contact handling preserved:
  - phone regex handler still processes contact modes first (`new_booking_contact`, `existing_lookup_contact`).
  - doctor-code mode is routed safely without changing contact behavior.

## New callback map
- `book:back:services:{session_id}` → validate active session, render service panel.
- `book:back:doctors:{session_id}` → validate active session, render doctor panel.
- `book:doc_code:{session_id}` → validate active session, open doctor-code prompt.

All new callback payloads are backed by registered handlers.

## Tests run with exact commands/results
- `python -m compileall app tests` ✅ pass
- `pytest -q tests/test_patient_home_surface_pat_a1_2.py tests/test_patient_first_booking_review_pat_a1_1.py tests/test_patient_existing_booking_shortcut_pat_a3_2.py` ✅ pass (`65 passed`)

## Grep checks
Command:
- `rg "Добро пожаловать в DentFlow\. Выберите действие:|Выберите услугу для записи\.|Выберите предпочтение по врачу\." app/interfaces/bots/patient locales tests`

Result:
- No matches (exit code 1), confirming old plain RU picker copy is no longer active.

## Carry-forward for P0-03 slot picker recovery
- Slot panel formatting/localization internals were intentionally not modified.
- Doctor-code path now reaches slot panel and can be included in P0-03 slot recovery hardening scenarios.
