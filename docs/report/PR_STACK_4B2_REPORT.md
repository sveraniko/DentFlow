# PR Stack 4B2 Report — Reminder Acknowledgement + Booking Confirmation Actions

## 1. Objective
Implement Stack 4B2 interactive reminder layer on top of 4B1 delivery backbone:
- actionable Telegram reminder rendering,
- canonical reminder acknowledgement handling,
- booking-confirmation reminder callback action bridge,
- callback integrity checks,
- reminder status progression to `acknowledged`,
- worker/test ergonomics carry-forward fix,
- behavioral tests.

## 2. Docs Read
1. `README.md`
2. `docs/18_development_rules_and_baseline.md`
3. `docs/10_architecture.md`
4. `docs/12_repo_structure_and_code_map.md`
5. `docs/15_ui_ux_and_product_rules.md`
6. `docs/17_localization_and_i18n.md`
7. `docs/25_state_machines.md`
8. `docs/30_data_model.md`
9. `docs/35_event_catalog.md`
10. `docs/23_policy_and_configuration_model.md`
11. `docs/70_bot_flows.md`
12. `docs/72_admin_doctor_owner_ui_contracts.md` (targeted callback/panel checks)
13. `docs/80_integrations_and_infra.md`
14. `docs/85_security_and_privacy.md`
15. `docs/90_pr_plan.md`
16. `docs/95_testing_and_launch.md`
17. `docs/report/PR_STACK_4A_REPORT.md`
18. `docs/report/PR_STACK_4A1_REPORT.md`
19. `docs/report/PR_STACK_4B1_REPORT.md`
20. `booking_docs/*` (targeted read of Telegram flow contracts)

## 3. Precedence Decisions
1. Reminder lifecycle truth remains in `communication.reminder_jobs`.
2. Booking truth remains in `booking.bookings` and booking state services/orchestration.
3. Reminder callbacks do not mutate booking directly in handlers; callbacks call application service, which calls booking orchestration.
4. Reminder callback actions are accepted only from `sent` reminders and become `acknowledged` on accepted actions.
5. Stale duplicate callbacks (`acknowledged`/`canceled`/`failed`/`expired`) are rejected safely with typed stale outcomes.

## 4. Reminder Action Model
Implemented canonical Telegram reminder actions:

### `booking_confirmation`
- `confirm`
- `reschedule`
- `cancel`

### `booking_previsit` / `booking_day_of`
- `ack` (acknowledge/got it)

Not implemented in this stack:
- on-my-way variant
- retry engine
- no-response escalation engine

## 5. Callback Integrity Strategy
Callback payload format: `rem:{action}:{reminder_id}`.

Validation chain in `ReminderActionService`:
1. reminder exists (`reminder_id` lookup),
2. reminder is actionable (`status == sent`),
3. stale terminal reminder callbacks are rejected safely,
4. provider message identity check via persisted `communication.message_deliveries` (`delivery_status='sent'` and `provider_message_id` match callback message id),
5. booking-linked actions require linked booking id and existing booking,
6. booking action must be accepted by canonical booking orchestration.

This prevents mismatched reminder/bookings and duplicate mutation on stale callbacks.

## 6. Booking Action Bridge Summary
`ReminderActionService` bridges reminder callbacks to booking orchestration:
- confirm → `BookingOrchestrationService.confirm_booking(...)`
- reschedule → `BookingOrchestrationService.request_booking_reschedule(...)`
- cancel → `BookingOrchestrationService.cancel_booking(...)`
- ack-only → no booking mutation

For accepted actions, reminder is marked `acknowledged` in communication.

## 7. Reminder Content Enrichment Notes
Telegram reminder rendering upgraded to compact contextual format with RU/EN strings and booking context:
- datetime,
- doctor label (fallback: doctor id),
- service label (fallback: service id),
- branch label (fallback: branch id).

Interactive action buttons are attached only for supported reminder types.

## 8. Worker/Test Ergonomics Fix
Applied lazy aiogram import in Telegram sender path:
- removed eager top-level `aiogram` import from reminder sender module,
- import now occurs inside send call,
- added test proving module import path does not require eager aiogram import.

Also normalized `tests/test_worker.py` to run worker bootstrap using `asyncio.run(...)` to avoid dependency on async pytest plugin in dependency-poor environments.

## 9. Files Added
- `app/application/communication/actions.py`
- `tests/test_reminder_actions_stack4b2.py`
- `docs/report/PR_STACK_4B2_REPORT.md`

## 10. Files Modified
- `app/application/communication/delivery.py`
- `app/application/communication/__init__.py`
- `app/application/booking/orchestration.py`
- `app/infrastructure/communication/telegram_delivery.py`
- `app/infrastructure/db/communication_repository.py`
- `app/bootstrap/runtime.py`
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_reminder_delivery_stack4b1.py`
- `tests/test_worker.py`

## 11. Commands Run
- `rg --files | head -n 200`
- `sed -n ...` on implementation/docs files listed above
- `pytest -q tests/test_reminder_delivery_stack4b1.py tests/test_reminder_actions_stack4b2.py tests/test_worker.py`
- `pytest -q tests/test_booking_orchestration.py tests/test_reminder_delivery_stack4b1.py tests/test_reminder_actions_stack4b2.py tests/test_worker.py`

## 12. Test Results
- `tests/test_reminder_delivery_stack4b1.py` ✅
- `tests/test_reminder_actions_stack4b2.py` ✅
- `tests/test_worker.py` ✅
- `tests/test_booking_orchestration.py` ✅

## 13. Known Limitations / Explicit Non-Goals
- No retry engine.
- No no-response escalation execution engine.
- No SMS/email/call reminder providers.
- No owner reminder analytics UI.
- No doctor queue or charting changes.
- No care-commerce/doc generation/AI additions.

## 14. Deviations From Docs (if any)
- None intentional.
- Doctor/service/branch labels in reminder text currently use booking IDs as fallback labels; richer display labels can be introduced later via clinic-reference-backed resolver in delivery path.

## 15. Readiness Assessment for next stack
Stack 4B2 leaves the repo ready for escalation/retry-focused follow-up stacks:
- interactive reminder actions exist,
- callback integrity is explicit,
- reminder acknowledgement is canonical,
- booking actions are bridged through orchestration,
- duplicate/stale callbacks are safely handled,
- worker/test ergonomics are improved for dependency-poor runs.
