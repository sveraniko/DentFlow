# PR RR-1 Report — Reminder Runtime & Delivery Integrity

## 1. Objective
Harden reminder runtime behavior so due selection, claim discipline, send/fail/ack/retry/recovery and relevance revalidation are explicit, bounded, and testable for production reminder guidance reliability.

## 2. Docs Read
1. `README.md`
2. `docs/10_architecture.md`
3. `docs/18_development_rules_and_baseline.md`
4. `docs/25_state_machines.md`
5. `docs/35_event_catalog.md`
6. `docs/68_admin_reception_workdesk.md`
7. `docs/70_bot_flows.md`
8. `docs/80_integrations_and_infra.md`
9. `docs/85_security_and_privacy.md`
10. `docs/90_pr_plan.md`
11. `docs/95_testing_and_launch.md`
12. `docs/81_worker_topology_and_runtime.md`
13. `docs/report/PR_WR1_REPORT.md`
14. `docs/report/PR_WR2_REPORT.md`
15. `docs/report/FULL_PROJECT_STATE_AUDIT.md`

## 3. Scope Implemented
- Added explicit reminder runtime integrity module for state transitions and booking-truth relevance decisions.
- Hardened reminder delivery to revalidate booking truth before send and terminate no-longer-relevant reminders explicitly (`canceled` or `expired`) instead of attempting delivery.
- Added explicit expired write path in repository/runtime integration.
- Added `reminder.queued` event emission at due-claim step to make queued/claimed transition explicit and auditable.
- Extended tests for relevance suppression, expiration behavior, and explicit transition model checks.

## 4. Reminder State Machine Notes
Implemented explicit transition table in runtime code:
- `scheduled -> queued|canceled|expired`
- `queued -> scheduled|sent|failed|canceled|expired`
- `sent -> acknowledged|expired`
- terminal: `acknowledged`, `canceled`, `expired`

Runtime decisions now explicitly classify non-send terminal outcomes (canceled vs expired) based on booking truth and timing.

## 5. Due Selection / Claim Strategy
- Due selection remains bounded (`LIMIT`) and safe (`FOR UPDATE SKIP LOCKED`) in one SQL claim step.
- Claim writes `status='queued'` + `queued_at` immediately to establish ownership before send.
- Queued transition now emits `reminder.queued` outbox event for auditability and state traceability.
- Duplicate-send risk remains bounded by claim discipline + queued-state gating for terminal updates.

## 6. Retry / Recovery Strategy
- Transient send failures still move through bounded retry scheduling (`scheduled` with incremented `delivery_attempts_count`) and eventually `failed`.
- Stale queued reminders continue to be recovered by recovery service using stale window policy and max-attempt policy.
- Exhausted stale queued reminders explicitly fail and escalate.

## 7. Relevance Revalidation Notes
Before send, booking-linked reminders are revalidated against booking truth:
- missing booking -> `canceled`
- terminal booking (`canceled`, `completed`, `no_show`) -> `canceled`
- `reschedule_requested` -> `canceled`
- confirmation reminder for already confirmed booking -> `canceled`
- booking start window already passed -> `expired`

This suppresses stale/no-longer-relevant reminders and keeps booking truth canonical.

## 8. Files Added
- `app/application/communication/runtime_integrity.py`
- `tests/test_reminder_runtime_integrity_rr1.py`
- `docs/report/PR_RR1_REPORT.md`

## 9. Files Modified
- `app/application/communication/__init__.py`
- `app/application/communication/delivery.py`
- `app/infrastructure/db/communication_repository.py`
- `tests/test_reminder_delivery_stack4b1.py`

## 10. Commands Run
- `sed -n ...` for required docs and reminder/runtime files
- `pytest -q tests/test_reminder_delivery_stack4b1.py tests/test_reminder_runtime_integrity_rr1.py tests/test_reminder_recovery_stack4c1.py`

## 11. Test Results
- Targeted RR-1 reminder integrity tests passed locally.

## 12. Remaining Known Limitations
- This PR does not introduce distributed exactly-once semantics; bounded duplicate prevention remains claim+lease best effort as documented in WR-2.
- Expiration policy is currently runtime-rule based (`booking_window_passed`) and can be expanded with per-reminder-type policy keys later.
- No new reminder admin UI/recovery console wave is included (out of RR-1 scope).

## 13. Readiness Assessment for RR-2
RR-1 is ready to hand off to RR-2 copy/UX/admin-surface expansions because runtime integrity paths (due/claim/send/fail/retry/recover/relevance suppression) are now explicit, bounded, and test-covered.
