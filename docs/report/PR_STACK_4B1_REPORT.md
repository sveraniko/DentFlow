# PR Stack 4B1 Report — Telegram Reminder Delivery Pipeline

## 1. Objective
Implement the canonical reminder **delivery** pipeline on top of 4A/4A1 scheduling:
- due reminder claiming,
- Telegram delivery baseline,
- status progression (`scheduled -> queued -> sent/failed/canceled`),
- message delivery persistence,
- canonical Telegram recipient resolution,
- worker integration,
- explicit handling of unsupported channels/missing targets,
- tests for behavior.

No acknowledgement callbacks/buttons were implemented in this stack.

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
- `docs/80_integrations_and_infra.md`
- `docs/85_security_and_privacy.md`
- `docs/90_pr_plan.md`
- `docs/95_testing_and_launch.md`
- `docs/report/PR_STACK_4A_REPORT.md`
- `docs/report/PR_STACK_4A1_REPORT.md`
- `booking_docs/*` (targeted grep scan for reminder ownership and Telegram flow constraints)

## 3. Precedence Decisions
1. Reminder truth remains in `communication` (`reminder_jobs`, `message_deliveries`), not booking.
2. Delivery execution is worker/service driven (not Telegram handler driven).
3. Telegram is the only transport in 4B1; non-Telegram channels are explicitly failed with `unsupported_channel`.
4. Booking terminal states (`canceled`, `completed`, `no_show`) cause cancellation of queued send attempts rather than sending anyway.

## 4. Due-Reminder Claim Strategy
- Added canonical claim API in `DbReminderJobRepository.claim_due_reminders(now, limit)`.
- Uses transactional SQL claim semantics:
  - `SELECT ... FOR UPDATE SKIP LOCKED` on due `status='scheduled'` rows ordered by `scheduled_for, created_at`,
  - immediate `UPDATE ... SET status='queued'` in the same statement scope.
- This provides concurrency-safe claim behavior and prevents duplicate claiming under parallel workers.

## 5. Telegram Recipient Resolution Strategy
- Canonical target source: `core_patient.patient_contacts` with `contact_type='telegram'`.
- Resolver (`DbTelegramReminderRecipientResolver`) reads active primary/verified candidate and returns typed outcomes:
  - `target_found`,
  - `no_target` (`telegram_target_missing`),
  - `invalid_target` (`telegram_target_invalid`).
- Booking PatientBot paths now persist Telegram contact linkage to canonical patient:
  - exact-match resolution path upserts Telegram contact for matched patient,
  - new-patient path upserts Telegram contact for newly created patient.
- This avoids ephemeral chat-state-only resolution and preserves future reminder deliverability.

## 6. Delivery Status Progression
- Implemented runtime progression:
  - `scheduled` → `queued` (claim),
  - `queued` → `sent` on successful Telegram send,
  - `queued` → `failed` on explicit delivery/target/channel failure,
  - `queued` → `canceled` when booking is missing or terminal/non-sendable.
- `acknowledged` remains untouched (reserved for future stack).

## 7. Message Delivery Persistence Notes
- Every send attempt writes `communication.message_deliveries`:
  - `channel`,
  - `attempt_no`,
  - `provider_message_id` (if any),
  - `error_text` for failure/cancel paths.
- Success writes `delivery_status='sent'`.
- Explicit failure paths write `delivery_status='failed'`.
- Booking sanity cancel paths write `delivery_status='canceled'`.

## 8. Worker Integration Notes
- Added reminder delivery worker task entrypoint:
  - `run_reminder_delivery_once(service, batch_limit)`.
- Wired into `app.worker.run_worker_once()` task registry as `reminder_delivery`.
- Delivery pipeline boundary is service-driven:
  - claim + sanity checks + resolve + render + send + persist + status update.
- Configurable batch limit via `REMINDER_DELIVERY_BATCH_LIMIT` env var (default `50`).
- Task failure is logged and contained for bootstrap resiliency.

## 9. Files Added
- `app/application/communication/delivery.py`
- `app/infrastructure/communication/__init__.py`
- `app/infrastructure/communication/telegram_delivery.py`
- `app/infrastructure/workers/reminder_delivery.py`
- `tests/test_reminder_delivery_stack4b1.py`
- `docs/report/PR_STACK_4B1_REPORT.md`

## 10. Files Modified
- `app/application/communication/__init__.py`
- `app/infrastructure/db/communication_repository.py`
- `app/application/booking/telegram_flow.py`
- `app/infrastructure/db/patient_repository.py`
- `app/worker.py`
- `tests/test_booking_patient_flow_stack3c1.py`

## 11. Commands Run
- `rg -n "reminder|communication|message_deliver|telegram|worker" ...`
- `find /workspace -name AGENTS.md -print`
- `pytest -q tests/test_reminder_delivery_stack4b1.py tests/test_booking_patient_flow_stack3c1.py tests/test_worker.py`
- `pytest -q tests/test_reminder_delivery_stack4b1.py tests/test_booking_patient_flow_stack3c1.py`
- `pytest -q tests/test_booking_orchestration.py -q`

## 12. Test Results
- `tests/test_reminder_delivery_stack4b1.py` ✅
- `tests/test_booking_patient_flow_stack3c1.py` ✅
- `tests/test_booking_orchestration.py` ✅
- `tests/test_worker.py` ⚠️ in this environment due missing async pytest plugin registration (`pytest-asyncio` mark/plugin issue at runtime).

## 13. Known Limitations / Explicit Non-Goals
- No acknowledgement actions/buttons/callback handling in this stack.
- No SMS/email/call providers.
- No retry/escalation engine beyond explicit failure/cancel outcomes.
- No stale queued reclaim implemented in this stack.
- Reminder rendering is intentionally minimal, RU/EN only, and non-interactive.

## 14. Deviations From Docs (if any)
- None intentional. Stack stays within delivery-only scope and keeps reminder truth in communication.

## 15. Readiness Assessment for PR Stack 4B2
- Ready for 4B2 acknowledgement layer:
  - delivery backbone exists,
  - status transitions and message persistence are in place,
  - recipient resolution is canonical,
  - worker path is integrated.
- 4B2 can now focus on acknowledgement semantics, callback contracts, and follow-up behavior without reworking transport core.
