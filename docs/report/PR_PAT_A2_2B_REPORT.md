# PR PAT-A2-2B Report — Quick-book suggestion parity, truthful semantics, and fallback hardening

## What changed after PAT-A2-2A

This PR hardens PAT-A2-2A without redesigning booking orchestration.

- Made **"same doctor"** a real, distinct quick-book action (`qbook:same_doctor:<session_id>`), no longer wired to repeat callback behavior.
- Preserved **"repeat previous service"** semantics and slot-jump behavior.
- Kept **"choose something else"** on normal service selection.
- Hardened quick-book fallback outcomes so incomplete/invalid prefill no longer creates dead-end behavior.
- Kept stale callback behavior bounded and non-technical.
- Added explicit parity assertions for `/book` and `phome:book` quick-book surface callbacks.
- Improved suggestion service label resolution to prefer localizable service title key where available.

## Exact files changed

- `app/interfaces/bots/patient/router.py`
- `app/application/booking/telegram_flow.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_patient_existing_booking_shortcut_pat_a3_2.py`
- `tests/test_booking_patient_flow_stack3c1.py`
- `docs/report/PR_PAT_A2_2B_REPORT.md`

## How "same doctor" now differs from "repeat previous service"

### Repeat previous service (`qbook:repeat:<session_id>`)

- Requires complete pattern (`service_id`, `doctor_id`, `branch_id`).
- Applies full prefill:
  - `service_id`
  - `doctor_id`
  - `branch_id`
  - `doctor_preference_type="specific"`
- Routes directly to slot selection.

### Same doctor (`qbook:same_doctor:<session_id>`)

- Requires doctor continuity inputs (`doctor_id`, `branch_id`).
- Applies bounded prefill:
  - `doctor_id`
  - `branch_id`
  - `doctor_preference_type="specific"`
- Does **not** apply prior `service_id`.
- Routes to service selection panel, preserving meaning: same doctor preference, service still explicit user choice.

## How suggestion labels are resolved

Quick-book suggestion panel now resolves service display using narrow fallback order:

1. localized title from `service_title_key` (user locale, then EN fallback)
2. `service_code`
3. bounded missing fallback text

This keeps labels truthful and humanized without introducing broad presentation refactors.

## Parity and fallback cases now covered

- `/book` trusted returning flow shows quick-book panel with callback set:
  - `qbook:repeat:<session_id>`
  - `qbook:same_doctor:<session_id>`
  - `qbook:other:<session_id>`
- `phome:book` shows the same callback set and same quick-book panel semantics.
- Missing/incomplete same-doctor prefill falls back to service selection (safe bounded fallback).
- Repeat path apply failure now falls back to service selection instead of a dead-end.
- Stale/manual quick-book callback remains bounded via stale alert, with no raw technical detail leakage.

## Tests added/updated

- `tests/test_patient_existing_booking_shortcut_pat_a3_2.py`
  - updated quick-book surface assertions for callback truth/parity (`/book`, `phome:book`)
  - added same-doctor distinct routing test
  - added same-doctor incomplete prefill safe fallback test
  - added stale/manual same-doctor callback bounded behavior test
  - added localized service-title preference test
- `tests/test_booking_patient_flow_stack3c1.py`
  - added assertions for recent prefill metadata (`service_title_key`, `service_code`)
  - added service-level test for same-doctor prefill helper behavior

## Environment / full-suite notes

- Focused PAT-A2/PAT-A1/PAT-A3 patient-flow tests were run successfully in this environment.
- Full repository suite was not run in this PR pass (bounded hardening scope).

## PAT-A2-2 closure statement

- **PAT-A2-2 is considered closed** with this PR (`PAT-A2-2A + PAT-A2-2B`):
  - suggestion surface semantics are now truthful (no deceptive duplicate action),
  - `/book` and `phome:book` quick-book behavior is parity-covered,
  - fallback/stale behaviors are bounded,
  - quick path remains explicit and review/confirm-preserving.

## Explicit non-goals left for PAT-A2-3

- One-tap finalization or silent auto-booking.
- Broader PAT-002 closure-proof instrumentation beyond focused quick-book regressions.
- Broader docs truth-status sweep outside this PR report.
- Reminders redesign, admin/doctor/owner flow changes, or migrations.
