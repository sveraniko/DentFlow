# PR AW-3 Report: Confirmations + Reschedules + Waitlist

## 1. Objective
Implement dedicated admin queue surfaces for confirmations, reschedules, and waitlist on top of AW-1 read models and AW-2 runtime/card behavior, while keeping Today as a separate surface.

## 2. Docs Read
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/10_architecture.md
4. docs/12_repo_structure_and_code_map.md
5. docs/15_ui_ux_and_product_rules.md
6. docs/17_localization_and_i18n.md
7. docs/16_unified_card_system.md
8. docs/16-1_card_profiles.md
9. docs/16-2_card_callback_contract.md
10. docs/16-3_card_media_and_navigation_rules.md
11. docs/16-4_booking_card_profile.md
12. docs/16-5_card_runtime_state_and_redis_rules.md
13. docs/68_admin_reception_workdesk.md
14. docs/69_google_calendar_schedule_projection.md
15. docs/70_bot_flows.md
16. docs/72_admin_doctor_owner_ui_contracts.md
17. docs/80_integrations_and_infra.md
18. docs/85_security_and_privacy.md
19. docs/90_pr_plan.md
20. docs/95_testing_and_launch.md
21. docs/report/PR_AW1_REPORT.md
22. docs/report/PR_AW2_REPORT.md

## 3. Precedence Decisions
- Kept AW-1 admin read service as the queue data source (`AdminWorkdeskReadService.get_confirmation_queue/get_reschedule_queue/get_waitlist_queue`).
- Kept AW-2 Today screen separate (`/admin_today`) and introduced new dedicated queue commands instead of merging them into Today.
- Reused booking card runtime callbacks for booking-linked queue entries; no text-only replacement path for booking open flows.

## 4. Confirmations Queue Strategy
- Added `/admin_confirmations` command with a dedicated queue render.
- Queue rows include time, patient, doctor, service label, branch, confirmation signal, and reminder/no-response hint.
- Added bounded no-response focus toggle.
- Booking open from queue uses card callback contract with `SourceContext.ADMIN_CONFIRMATIONS` and queue-scoped state token.

## 5. Reschedules Queue Strategy
- Added `/admin_reschedules` command with a dedicated queue render.
- Queue rows include time, patient, doctor, service label, branch, and reschedule context hint.
- Booking open from queue uses booking card callbacks with `SourceContext.ADMIN_RESCHEDULES`.
- Back action from booking card returns to reschedules queue.

## 6. Waitlist Queue Strategy
- Added `/admin_waitlist` command with a dedicated queue render.
- Queue rows include patient, preferred doctor/service labels, preferred time window, and status.
- Added bounded waitlist item actions:
  - open entry detail summary
  - close marker action (manual closure marker message)
- No fake connect-to-slot automation introduced.

## 7. Booking Card Integration Notes
- Extended source-context support to include `ADMIN_RESCHEDULES` and existing `ADMIN_CONFIRMATIONS` in runtime callback handling.
- Queue booking opens encode queue source context + queue state token.
- Back navigation now restores:
  - today queue (`ADMIN_TODAY`)
  - confirmations queue (`ADMIN_CONFIRMATIONS`)
  - reschedules queue (`ADMIN_RESCHEDULES`)
- Stale callback checks are enforced using per-queue session state tokens.

## 8. Localization Notes
- Added queue-specific i18n keys for EN/RU for titles, rows, empty states, controls, waitlist detail/close messaging, signals, reminder hints, and queue status labels.
- Service labels use localized rendering path where possible and avoid raw key leakage in primary queue text.

## 9. Files Added
- `tests/test_admin_queues_aw3.py`
- `docs/report/PR_AW3_REPORT.md`

## 10. Files Modified
- `app/interfaces/bots/admin/router.py`
- `app/interfaces/cards/models.py`
- `locales/en.json`
- `locales/ru.json`

## 11. Commands Run
- `pytest -q tests/test_admin_today_aw2.py tests/test_admin_queues_aw3.py`
- `pytest -q tests/test_admin_workdesk_aw1.py tests/test_admin_today_aw2.py tests/test_admin_queues_aw3.py`

## 12. Test Results
- All targeted AW-1/AW-2/AW-3 admin queue tests passed.

## 13. Known Limitations / Explicit Non-Goals
- No Google Calendar integration.
- No patient deep-drilldown expansion.
- No booking engine redesign.
- Waitlist close action is bounded to operational closure marker message in this PR; no scheduling automation.

## 14. Deviations From Docs (if any)
- None intentional.

## 15. Readiness Assessment for AW-4
- AW-3 queue layer is now in place with dedicated surfaces and runtime-safe booking-card navigation.
- AW-4 can build on this with deeper operational workflows (without refactoring queue entry points).
