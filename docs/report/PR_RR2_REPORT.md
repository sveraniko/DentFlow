# PR RR-2 Report — Reminder UX, Cadence & Follow-up Logic

## 1. Objective
Move reminders from delivery-only reliability into patient-guidance UX: clear reminder types, bounded cadence, localized copy, bounded no-response follow-up, and a modest next-visit/prophylaxis baseline.

## 2. Docs Read
1. `README.md`
2. `docs/10_architecture.md`
3. `docs/18_development_rules_and_baseline.md`
4. `docs/17_localization_and_i18n.md`
5. `docs/25_state_machines.md`
6. `docs/68_admin_reception_workdesk.md`
7. `docs/70_bot_flows.md`
8. `docs/80_integrations_and_infra.md`
9. `docs/85_security_and_privacy.md`
10. `docs/90_pr_plan.md`
11. `docs/95_testing_and_launch.md`
12. `docs/81_worker_topology_and_runtime.md`
13. `docs/report/PR_RR1_REPORT.md`
14. `docs/report/FULL_PROJECT_STATE_AUDIT.md`

## 3. Scope Implemented
- Reworked reminder rendering into explicit type UX profiles with localized RU/EN summaries and action sets.
- Moved reminder copy to i18n catalogs and removed ad-hoc hardcoded patient text from worker logic.
- Made appointment time presentation local-time aware (branch timezone, then clinic timezone, then app default fallback).
- Updated cadence planner to explicit confirmation / day-before / same-day logic.
- Added bounded no-response follow-up reminder generation before escalation.
- Added bounded next-visit/prophylaxis baseline reminder scheduling on completed visits (policy-gated).
- Added RR-2-focused behavioral tests.

## 4. Reminder Type UX Notes
Implemented explicit patient-facing distinction for:
- `booking_confirmation`: confirmation decision expected (`confirm/reschedule/cancel`).
- `booking_previsit`: upcoming guidance (`ack`).
- `booking_day_of`: same-day guidance (`ack`).
- `booking_no_response_followup`: second confirmation request (`confirm/reschedule/cancel`), bounded by policy and idempotent follow-up ID.
- `booking_next_visit_recall`: modest prophylaxis recall baseline (`ack`).

## 5. Cadence Strategy
Implemented bounded cadence:
- confirmation reminder at `booking.confirmation_offset_hours` (default 24h),
- upcoming day-before reminder at `booking.upcoming_day_before_offset_hours` (default 24h),
- same-day reminder at `booking.same_day_reminder_offset_hours` (default 2h).

Intentionally not implemented:
- multi-step campaign trees,
- frequency optimization/ML,
- broad marketing sequencing.

## 6. No-Response Follow-Up Strategy
- Existing no-response detection remains policy-gated (`booking.non_response_escalation_enabled`).
- RR-2 now schedules one deterministic follow-up reminder (`booking_no_response_followup`) before escalation, if enabled.
- Escalation waits for follow-up to be sent and pass a bounded grace window (`booking.non_response_escalation_after_followup_minutes`).
- No infinite loops: single deterministic follow-up ID per confirmation reminder.

## 7. Next-Visit / Prophylaxis Baseline Notes
- Added policy-gated baseline scheduling on completed booking:
  - `booking.next_visit_recall_enabled` (default true),
  - `booking.next_visit_recall_after_days` (default 180).
- Implemented as one bounded reminder, not a campaign engine.
- If reminder time is already in the past, no reminder is created.

## 8. Localization Notes
- Added RU/EN keys for reminder layout, reminder-type summaries, and reminder action labels.
- Reminder rendering now pulls from i18n catalogs in worker runtime.
- Default local-time formatting now includes timezone abbreviation in message body.

## 9. Files Added
- `tests/test_reminder_rr2.py`
- `docs/report/PR_RR2_REPORT.md`

## 10. Files Modified
- `app/application/communication/delivery.py`
- `app/application/communication/reminders.py`
- `app/application/communication/recovery.py`
- `app/application/communication/runtime_integrity.py`
- `app/application/booking/orchestration.py`
- `app/domain/policy_config/models.py`
- `app/worker.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_booking_orchestration.py`
- `tests/test_reminder_recovery_stack4c1.py`

## 11. Commands Run
- `sed -n ...` for required docs and reminder/runtime files.
- `pytest -q tests/test_reminder_rr2.py tests/test_reminder_actions_stack4b2.py tests/test_reminder_delivery_stack4b1.py tests/test_reminder_recovery_stack4c1.py tests/test_booking_orchestration.py tests/test_reminder_runtime_integrity_rr1.py`

## 12. Test Results
- Targeted RR-2 reminder behavior tests passed locally.

## 13. Remaining Known Limitations
- Reminder copy currently uses doctor/service/branch identifiers from booking entity; richer human labels need projection enrichment.
- Next-visit baseline is completion-triggered single reminder only; no recurrence ladder.
- Follow-up/no-response logic is booking-confirmation scoped, not generalized for other reminder families.

## 14. Readiness Assessment for RR-3
RR-2 is ready for downstream refinement:
- reminder UX and cadence are explicit and bounded,
- no-response flow is now explainable and non-spammy,
- local-time and localization are integrated into reminder rendering,
- scope remains focused on appointment guidance (not CRM expansion).
