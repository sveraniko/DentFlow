# PR Stack 3C1 Report — Patient Booking Flow MVP + Admin Escalation Visibility

## 1. Objective

Implement the first real Telegram patient booking MVP slice with:
- active-session start/resume behavior
- service/doctor/slot/contact booking path
- exact-match + no-match + ambiguous contact resolution
- orchestration-driven review/finalize
- minimal admin visibility for escalations and new/pending bookings

## 2. Docs Read

- README.md
- docs/18_development_rules_and_baseline.md
- docs/10_architecture.md
- docs/12_repo_structure_and_code_map.md
- docs/15_ui_ux_and_product_rules.md
- docs/17_localization_and_i18n.md
- docs/25_state_machines.md
- docs/20_domain_model.md
- docs/30_data_model.md
- docs/40_search_model.md
- docs/70_bot_flows.md
- docs/72_admin_doctor_owner_ui_contracts.md
- docs/80_integrations_and_infra.md
- docs/85_security_and_privacy.md
- docs/90_pr_plan.md
- docs/95_testing_and_launch.md
- docs/report/PR_STACK_3A_REPORT.md
- docs/report/PR_STACK_3B1_REPORT.md
- docs/report/PR_STACK_3B2_REPORT.md
- docs/report/PR_STACK_3B2A_REPORT.md
- docs/report/PR_STACK_3B2B_REPORT.md
- booking_docs/10_booking_flow_dental.md
- booking_docs/40_booking_state_machine.md
- booking_docs/50_booking_telegram_ui_contract.md
- booking_docs/booking_api_contracts.md
- booking_docs/booking_test_scenarios.md

## 3. Precedence Decisions

- Lifecycle mutations stay in orchestration/state services; handlers route user inputs only.
- Canonical new-patient creation uses `core_patient` via DB-backed patient registry service.
- Ambiguous exact-contact match escalates to admin; patient receives privacy-safe message with no candidate identity exposure.

## 4. Patient Flow Scope Implemented

- Added `/book` entry in PatientBot.
- Start-or-resume behavior:
  - if user has active non-terminal session in clinic, reuse latest by `updated_at desc`
  - else start new session via orchestration.
- Implemented MVP flow:
  1) choose service
  2) choose doctor preference (`any` or specific doctor)
  3) show nearest open slots
  4) select slot (hold activation through orchestration)
  5) collect phone via Telegram contact or text fallback
  6) resolve patient by exact contact:
     - exact -> attach existing canonical patient
     - no_match -> create canonical minimal patient then attach to session
     - ambiguous -> escalate and stop self-service finalize
  7) mark review-ready
  8) finalize from session
  9) show success panel

## 5. Admin Visibility Scope Implemented

- Added admin command `/booking_escalations`:
  - shows open escalated booking sessions with priority/reason/session summary fields.
- Added admin command `/booking_new`:
  - shows recent bookings in statuses `pending_confirmation` and `confirmed`.

## 6. Slot Display Rule Chosen

- Query only open slots within near-term window (next 30 days), sorted by `start_at ASC, slot_id ASC`.
- Filter by selected specific doctor when requested.
- Branch filter applied if session branch is set.
- Service compatibility rule:
  - include slot if `service_scope` is null
  - include slot if `service_scope.service_ids` includes selected service
  - exclude otherwise

## 7. Patient Resolution Handling Summary

- exact_match: session resolves and proceeds.
- no_match: minimal canonical patient created in `core_patient`, session attached by patient_id.
- ambiguous_match: orchestration escalation created (`ambiguous_exact_contact`), session moved to escalated path, patient sees non-leaking message.

## 8. New-Patient Creation Strategy

- Use canonical DB patient registry (`DbPatientRegistryService`) through `DbCanonicalPatientCreator`.
- Minimal identity:
  - `display_name` from Telegram full name fallback
  - split into first/last (fallback `-` for missing last)
  - phone saved as primary active phone contact.

## 9. Files Added

- app/application/booking/telegram_flow.py
- app/interfaces/bots/patient/router.py
- tests/test_booking_patient_flow_stack3c1.py
- docs/report/PR_STACK_3C1_REPORT.md

## 10. Files Modified

- app/application/booking/orchestration.py
- app/application/booking/__init__.py
- app/application/booking/services.py
- app/infrastructure/db/booking_repository.py
- app/infrastructure/db/patient_repository.py
- app/interfaces/bots/admin/router.py
- app/bootstrap/runtime.py
- locales/en.json
- locales/ru.json

## 11. Commands Run

- `pytest -q tests/test_booking_patient_flow_stack3c1.py tests/test_runtime.py tests/test_runtime_wiring.py tests/test_booking_orchestration.py`

## 12. Test Results

- Pass: `21 passed in 4.10s`

## 13. Known Limitations / Explicit Non-Goals

- No reschedule UI/cancel UI for existing bookings in Telegram.
- No waitlist UI.
- No doctor queue UI.
- No reminder execution changes.
- No smart slot ranking/recommendation engine.
- Booking success panel uses identifiers (doctor/service IDs) rather than enriched display cards for this stack.

## 14. Deviations From Docs (if any)

- None intentional for 3C1 scope.

## 15. Readiness Assessment for PR Stack 3C2

- Ready for 3C2 extension work:
  - richer booking panel edits/navigation
  - stronger stale callback/session mismatch handling
  - deeper admin escalation read/open surface details
  - enhanced booking summary rendering with richer doctor/service projection labels
