# PR Stack 4C1 Report — Reminder Recovery + No-Response Escalation + Admin Recovery Loop

## 1. Objective
Implement the final booking reminder hardening loop for `booking-base-v1`: stale queued recovery, retry-safe delivery baseline, booking-linked no-response escalation, and minimal admin recovery actions.

## 2. Docs Read
- `README.md`
- `docs/18_development_rules_and_baseline.md`
- `docs/10_architecture.md`
- `docs/12_repo_structure_and_code_map.md`
- `docs/15_ui_ux_and_product_rules.md`
- `docs/17_localization_and_i18n.md`
- `docs/25_state_machines.md`
- `docs/30_data_model.md`
- `docs/35_event_catalog.md`
- `docs/23_policy_and_configuration_model.md`
- `docs/70_bot_flows.md`
- `docs/72_admin_doctor_owner_ui_contracts.md`
- `docs/80_integrations_and_infra.md`
- `docs/85_security_and_privacy.md`
- `docs/90_pr_plan.md`
- `docs/95_testing_and_launch.md`
- prior reports: `4A`, `4A1`, `4B1`, `4B2`, `4B2A`
- targeted `booking_docs/*` references for escalation/reminder ownership

## 3. Precedence Decisions
1. Kept reminder lifecycle truth in `communication.reminder_jobs` and delivery attempts in `communication.message_deliveries`.
2. Kept booking truth in `booking.bookings`; no shadow booking state introduced.
3. Reused canonical `booking.admin_escalations` queue for reminder recovery/no-response escalation.
4. Did not add handler-level recovery logic; recovery runs in application services + worker tasks.

## 4. Recovery Strategy Summary
- **Stale queued**: scan `queued` reminders with `queued_at <= now - stale_timeout`; requeue to `scheduled` for retry, or mark failed+escalate when retry attempts are exhausted.
- **Retry baseline**: classify failures as retryable (transient send exception) vs non-retryable (unsupported channel / missing target); retryable failures schedule bounded retry, non-retryable failures become `failed`.
- **No-response**: scan sent `booking_confirmation` reminders older than policy threshold, not acknowledged, while booking remains response-requiring.
- **Escalation idempotency**: deterministic escalation IDs per reason+reminder prevent duplicate open escalations across repeated scans.

## 5. Stale Queued Handling
- Added reminder runtime metadata (`queued_at`, attempt/error fields).
- Added stale queued repository scan and reclaim operation.
- Added recovery service path `recover_stale_queued_reminders` with threshold + max-attempt policy.

## 6. Retry / Non-Retryable Failure Handling
- Delivery service now supports bounded retry scheduling for retryable transport failures.
- Retry policy keys:
  - `communication.reminder_retry_enabled`
  - `communication.reminder_retry_max_attempts`
  - `communication.reminder_retry_delay_minutes`
- Non-retryable failures remain explicit `failed` with error metadata.

## 7. No-Response Escalation Strategy
- Added `detect_confirmation_no_response` worker path.
- Uses policy keys:
  - `booking.non_response_escalation_enabled`
  - `booking.non_response_escalation_after_minutes`
- Guardrails:
  - skips acknowledged reminders,
  - skips terminal bookings (`confirmed`, `canceled`, `completed`, `no_show`),
  - duplicate-safe via deterministic escalation key.

## 8. Admin Recovery Loop Scope
Minimal admin recovery actions added:
- open escalation detail (existing)
- take escalation (`in_progress`)
- resolve escalation (`resolved`)

AdminBot commands:
- `/booking_escalation_open <id>`
- `/booking_escalation_take <id>`
- `/booking_escalation_resolve <id>`

## 9. Files Added
- `app/application/communication/recovery.py`
- `app/infrastructure/workers/reminder_recovery.py`
- `tests/test_reminder_recovery_stack4c1.py`
- `docs/report/PR_STACK_4C1_REPORT.md`

## 10. Files Modified
- communication/domain/repository/bootstrap/policy files for recovery fields and policies
- worker bootstrap wiring and exports
- booking flow + admin router + locale keys for recovery actions
- delivery tests updated for retry scheduling baseline

## 11. Commands Run
- `pytest -q tests/test_reminder_delivery_stack4b1.py tests/test_reminder_recovery_stack4c1.py tests/test_reminder_actions_stack4b2.py tests/test_worker.py`
- `pytest -q tests/test_booking_patient_flow_stack3c1.py`

## 12. Test Results
- reminder delivery/recovery/actions/worker set: **pass**
- booking patient flow regression: **pass**

## 13. Known Limitations / Explicit Non-Goals
- No provider-specific exponential backoff framework.
- No SMS/email channels added.
- No owner analytics or operations dashboard added.
- No schema expansion to add a separate recovery queue.
- Escalation linkage uses patient->latest session lookup (booking model currently does not carry direct `booking_session_id`).

## 14. Deviations From Docs (if any)
- No intentional strategic deviation.
- Minor pragmatic implementation detail: recovery escalation derives session linkage from latest patient session to fit existing canonical escalation schema.

## 15. Booking-Base-v1 Readiness Assessment
For this stack scope, the reminder recovery loop is now coherent:
- stale queued reminders are no longer silently stranded,
- retry-safe baseline exists,
- non-response escalation exists with duplicate safety,
- admin has minimal take/resolve loop,
- behavior is covered by focused tests.

This stack moves Booking to the intended `booking-base-v1` hardening target for reminder recovery and minimal human rescue path.
