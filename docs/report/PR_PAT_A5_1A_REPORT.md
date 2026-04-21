# PR PAT-A5-1A Report

## What changed
- Reminder-driven patient cancel is now a two-step flow: the first `rem:cancel:<reminder_id>` tap opens a bounded yes/no confirmation prompt instead of executing cancellation.
- Added dedicated reminder-cancel confirmation callbacks under a local prefix:
  - `remc:confirm:<reminder_id>`
  - `remc:abort:<reminder_id>`
- Confirm path now executes real cancellation through existing reminder action service (`ReminderActionService.handle_action(..., action="cancel")`) and preserves canonical accepted-action handoff into the patient booking panel.
- Abort path is bounded and non-mutating: no cancellation service call is made; patient receives localized cancellation-aborted feedback; inline keyboard is best-effort cleared.
- Kept all non-cancel reminder actions (`ack`, `confirm`, `reschedule`) unchanged.

## Exact files changed
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_patient_reminder_handoff_pat_a3_1a.py`
- `docs/report/PR_PAT_A5_1A_REPORT.md`

## How reminder cancel confirm flow works
1. Patient taps `rem:cancel:<reminder_id>` in reminder message.
2. Router does **not** call reminder action service yet.
3. Router sends a compact localized prompt with Yes/No callbacks:
   - Yes -> `remc:confirm:<reminder_id>`
   - No -> `remc:abort:<reminder_id>`
4. On `remc:confirm:<reminder_id>`:
   - resolve provider message id from callback message when present;
   - call `reminder_actions.handle_action(reminder_id=..., action="cancel", provider_message_id=...)`;
   - if accepted: best-effort clear keyboard and hand off to canonical booking panel continuity;
   - if stale: show localized stale alert;
   - if invalid: show localized invalid alert.
5. On `remc:abort:<reminder_id>`:
   - no booking mutation;
   - no reminder cancel action call;
   - bounded localized aborted feedback;
   - best-effort clear keyboard.

## How canonical post-cancel handoff is preserved
- Accepted `remc:confirm:*` outcomes still call the existing `_handoff_reminder_action_to_booking_panel(...)` reminder handoff path.
- That path still starts a fresh existing-booking control context and renders canonical canceled booking panel continuity for the patient.
- No changes were made to the non-cancel accepted reminder handoff behavior.

## Tests added/updated
Updated `tests/test_patient_reminder_handoff_pat_a3_1a.py` with focused PAT-A5-1A coverage:
1. `rem:cancel:*` now shows confirmation and does not cancel immediately.
2. `remc:confirm:*` performs real cancel action call and hands off to canonical canceled booking panel.
3. `remc:abort:*` does not call cancel action and does not mutate booking flow state.
4. Existing accepted reminder handoff matrix for non-cancel actions remains validated.

## Environment and execution
- Targeted test file executed in this environment.
- No environment blocker prevented running the bounded PAT-A5-1A test scope.

## Explicit non-goals intentionally left for PAT-A5-1B and PAT-A5-2
- No `/my_booking` cancel flow redesign.
- No reminder scheduling engine redesign.
- No booking engine/state-machine redesign.
- No slot-release runtime subsystem changes.
- No admin/doctor/owner flow changes.
- No migrations.
