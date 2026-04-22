# PR ADM-A1C Report — Admin lifecycle integrity, continuity hardening, and regression coverage

## What changed
- Hardened issue lifecycle so `resolve` can no longer short-circuit an `open` issue.
- Enforced canonical lifecycle transitions for supported booking-linked issue types:
  - `take`: `open -> in_progress`
  - `resolve`: `in_progress -> resolved`
- Normalized fresh issue ownership semantics:
  - new/open escalation rows are created without `assigned_to_actor_id`
  - owner is assigned on `take`
  - resolver identity is still persisted on `resolve`
- Strengthened queue/card/reschedule continuity after rescue completion by returning to booking card with preserved `ADMIN_RESCHEDULES` source context and valid back-path token.
- Added focused regression tests for handcrafted callbacks, lifecycle progression, ownership truth, queue continuity, rescue continuity, retry/lifecycle coexistence, and stale handling.

## Exact files changed
- `app/application/booking/telegram_flow.py`
- `app/interfaces/bots/admin/router.py`
- `tests/test_admin_aw4_surfaces.py`
- `tests/test_admin_queues_aw3.py`
- `tests/test_booking_patient_flow_stack3c1.py`
- `locales/en.json`
- `locales/ru.json`
- `docs/report/PR_ADM_A1C_REPORT.md`

## How lifecycle integrity is enforced
- Runtime service guard in `resolve_issue_escalation(...)` now rejects resolve unless escalation is already `in_progress`.
- Admin callback layer now explicitly checks current escalation status before resolve; if not `in_progress`, callback is safely rejected with bounded localized operator feedback.
- Handcrafted/stale/unsupported callbacks remain bounded and non-crashing.

## Ownership truth decision
- **Normalized in this PR**.
- `get_or_create_issue_escalation(...)` no longer assigns `assigned_to_actor_id` at creation while status is `open`.
- Effective ownership now starts at `take`, aligning lifecycle and ownership truth.

## Queue/card/rescue continuity hardening
- On successful admin reschedule confirm, booking card now renders with `ADMIN_RESCHEDULES` source context and queue state token.
- This preserves coherent back-navigation from post-rescue booking card to updated reschedules queue instead of dropping into an unscoped booking context.

## Tests added/updated
- `tests/test_admin_aw4_surfaces.py`
  - handcrafted `resolve` on open issue is rejected safely
  - retry + lifecycle actions coexist for `reminder_failed` without queue breakage
  - existing stale/unsupported lifecycle bounded behavior retained
- `tests/test_admin_queues_aw3.py`
  - reschedule rescue completion keeps booking card back-path to reschedules queue
- `tests/test_booking_patient_flow_stack3c1.py`
  - fresh/open issue escalation has no owner until taken
  - resolve-before-take is blocked and preserves `open` status

## Environment / execution notes
- Focused changed-area tests were executed.
- Full repository suite was not executed in this bounded hardening PR.
- No environment blocker prevented targeted execution.

## ADM-A1 closure statement
- **ADM-A1 is considered closed with this PR (ADM-A1C)**, based on:
  - lifecycle short-circuit prevention,
  - ownership truth normalization,
  - queue/card/rescue continuity hardening,
  - retry/lifecycle coexistence safety,
  - and targeted regression coverage.
