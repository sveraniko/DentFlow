# P0-05C — My Booking smoke gate report

## Summary
P0-05C adds a dedicated smoke-gate test suite for the full patient **My Booking** contour (readable card, status-aware controls, runtime callbacks, legacy callbacks, waitlist/reschedule edge outcomes, reminder handoff, callback namespace, and callback-answer behavior).

No product behavior was intentionally redesigned in this PR; scope is tests + report.

## Files changed
- `tests/test_p0_05c_my_booking_smoke_gate.py`
- `docs/report/P0_05C_MY_BOOKING_SMOKE_GATE_REPORT.md`

## Smoke matrix

| Area | Covered | Result | Notes |
|---|---|---|---|
| My Booking readable card RU/EN | Yes | Pass | Both locales assert patient-facing readable card and negative internal-field leaks. |
| Status keyboards | Yes | Pass | `pending_confirmation` (4 mutation actions), `confirmed` (3), `reschedule_requested` (2, earlier-slot hidden), terminal statuses (`canceled/completed/no_show`) Home-only. |
| No active booking | Yes | Pass | Empty state includes Book + Home, no `/start` dead-end instruction. |
| Runtime confirm | Yes | Pass | Re-renders clean card with localized status, no raw/debug fields. |
| Runtime cancel prompt/abort/confirm | Yes | Pass | Structured panel + back/home navigation; abort returns unchanged header; confirm returns canceled Home-only card. |
| Runtime waitlist | Yes | Pass | Structured success with current booking context + Home. |
| Runtime reschedule start | Yes | Pass | Structured panel with Select new time, My Booking, Home. |
| Legacy cancel prompt/abort/confirm | Yes | Pass | UX contracts parity with runtime path. |
| Legacy waitlist | Yes | Pass | Structured success panel parity. |
| Legacy reschedule start | Yes | Pass | Structured panel parity. |
| Waitlist failure | Yes | Pass | InvalidState outcome is bounded to callback alert; no crash; no broken/dead-end panel render. |
| Reschedule unavailable | Yes | Pass | Readable unavailable panel with My Booking + Home actions. |
| Reschedule complete | Yes | Pass | Success header + clean My Booking card + controls keyboard; no technical datetime/internal fields. |
| Reminder handoff | Yes | Pass | Reminder accepted handoff renders canonical clean My Booking panel with Home. |
| Callback namespace | Yes | Pass | Collected callback_data limited to approved prefixes + runtime encoded `c2|...`. |
| Double callback answer | Yes | Pass | Valid runtime and legacy tested paths render/update panels without popup alert duplication. |

## Tests run (exact commands/results)
- `python -m compileall app tests` → **pass**
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` → **pass** (4 passed)
- `pytest -q tests/test_p0_05b_my_booking_action_panels.py` → **pass** (6 passed)
- `pytest -q tests/test_p0_05a_my_booking_readable_card.py` → **pass** (5 passed)
- `pytest -q tests/test_p0_04c_review_edit_success_smoke_gate.py` → **pass** (3 passed)
- `pytest -q tests/test_p0_03d_patient_booking_smoke_gate.py` → **pass** (6 passed)
- `pytest -q tests/test_patient_existing_booking_shortcut_pat_a3_2.py` → **pass** (19 passed)
- `pytest -q tests/test_patient_reschedule_start_pat_a4_1.py` → **pass** (16 passed)
- `pytest -q tests/test_patient_reminder_handoff_pat_a3_1a.py` → **pass** (13 passed)
- `pytest -q tests/test_patient_first_booking_review_pat_a1_1.py tests/test_patient_home_surface_pat_a1_2.py` → **pass** (70 passed)
- `pytest -q tests -k "patient and booking"` → **pass** (105 passed, 497 deselected, 2 unrelated pytest mark warnings)

## Grep checks (exact commands/results)

1. `rg "CardShellRenderer.to_panel\(shell\)\.text" app/interfaces/bots/patient/router.py`
   - Result: 2 matches in care/recommendation card paths (not active My Booking render path).

2. `rg "Actions:|Канал:|Channel:|source_channel|booking_mode|branch: -" app/interfaces/bots/patient/router.py tests/test_p0_05c_my_booking_smoke_gate.py`
   - Result: matches in router state/model internals and in P0-05C negative assertion tokens only.

3. `rg "%Y-%m-%d %H:%M %Z|card.datetime_label" app/interfaces/bots/patient/router.py`
   - Result: no matches.

4. `rg "common.yes|common.no" app/interfaces/bots/patient/router.py tests/test_p0_05c_my_booking_smoke_gate.py`
   - Result: matches in reminder-cancel confirmation prompt only.

5. `rg "patient.booking.waitlist.created\"" app/interfaces/bots/patient/router.py`
   - Result: no matches for old flat key pattern query.

6. `rg "mybk:waitlist|mybk:cancel_prompt|mybk:cancel_abort|mybk:cancel_confirm|mybk:reschedule" app/interfaces/bots/patient/router.py tests`
   - Result: legacy handlers remain in router; legacy callbacks covered in tests including P0-05B and new P0-05C smoke.

## Defects found and fixed
- Added a consolidated smoke gate (`tests/test_p0_05c_my_booking_smoke_gate.py`) to prevent regressions across runtime + legacy My Booking flows and edge outcomes.

## Defects carried forward
- Reminder-cancel prompt still uses `common.yes/common.no` (`remc:*`) in reminder-specific confirmation UX.
- This is documented as carry-forward and does not block P0-05C because it is not the active My Booking cancel UX panel.

## Go / no-go recommendation for P0-06
**Go**: proceed to P0-06.

Rationale: P0-05A/P0-05B behavior remains green, P0-03D/P0-04C smoke gates remain green, and new P0-05C smoke gate covers required My Booking contour + runtime/legacy parity + guardrails.
