# PR Stack 3C2 Report — Existing Booking Control + Session Resume Integrity

## 1. Objective

Implement Stack 3C2 with:
- step-aware booking session resume
- stale callback/session integrity hardening
- patient existing-booking controls (`/my_booking` contact-resolved path)
- patient reschedule-request, cancel, and earlier-slot waitlist intents
- richer booking cards with enriched labels
- minimal admin detail-open surfaces for escalations/bookings

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
- docs/35_event_catalog.md
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
- docs/report/PR_STACK_3C1_REPORT.md
- booking_docs/10_booking_flow_dental.md
- booking_docs/40_booking_state_machine.md
- booking_docs/50_booking_telegram_ui_contract.md
- booking_docs/booking_api_contracts.md
- booking_docs/booking_test_scenarios.md

## 3. Precedence Decisions

- Lifecycle-changing actions remain orchestration/state-service driven (`request_booking_reschedule`, `cancel_booking`, `create_waitlist_entry`, session updates).
- Existing booking identity uses exact contact resolution only; ambiguous contact escalates with privacy-safe response.
- Booking card labels prefer reference data (doctor display name/service code+title key/branch display name) with safe fallback to IDs.

## 4. Session Resume Mapping

Implemented canonical panel mapping in `BookingPatientFlowService._panel_for_session`:
- terminal statuses (`admin_escalated`, `completed`, `canceled`, `expired`) -> `session_terminal`
- missing service -> `service_selection`
- missing/invalid doctor preference -> `doctor_preference_selection`
- no selected slot -> `slot_selection`
- slot exists but contact/patient unresolved -> `contact_collection`
- otherwise -> `review_finalize`

Patient `/book` now uses this mapping and renders the appropriate next-step panel instead of always resetting to service selection.

## 5. Callback/Session Integrity Strategy

- Callback payloads for service/doctor/slot actions now include `session_id`.
- On callback processing, router verifies `callback_session_id` matches the latest active session for that user+clinic via `validate_active_session_callback`.
- On mismatch, action is rejected with localized stale-callback message (`patient.booking.callback.stale`) and no mutation is executed.

## 6. Existing Booking Flow Scope Implemented

- Added patient command `/my_booking`.
- Flow starts/resumes `existing_booking_control` session.
- Requests phone contact, resolves patient via exact-contact resolution.
- Outcomes:
  - exact match + live booking(s): render booking card + control buttons
  - no match: safe no-match message
  - ambiguous: escalate safely, no candidate leakage to patient

## 7. Reschedule / Cancel / Waitlist Scope Implemented

- **Reschedule request**: patient action transitions booking to `reschedule_requested` through orchestration.
- **Cancel flow**: explicit confirmation step (`cancel_prompt` -> `cancel_confirm`) then orchestration transition to `canceled`.
- **Earlier-slot / waitlist intent**: creates canonical waitlist entry through orchestration (`create_waitlist_entry`) linked by booking context and patient/telegram IDs.

No full slot replacement reschedule UI added.

## 8. Admin Detail Scope Implemented

- Existing admin list commands enhanced with enriched booking labels.
- Added detail-open commands:
  - `/booking_escalation_open <escalation_id>`
  - `/booking_open <booking_id>`

These are minimal read/detail surfaces only.

## 9. Enriched Booking Card Strategy

`build_booking_card` now provides display-ready card fields:
- doctor display name
- service `code (title_key)`
- UTC datetime label
- branch display name
- human-readable status key mapping
- compact next-step hint key per status

Used by patient existing-booking controls and admin booking list/detail responses.

## 10. Files Added

- docs/report/PR_STACK_3C2_REPORT.md

## 11. Files Modified

- app/application/booking/telegram_flow.py
- app/interfaces/bots/patient/router.py
- app/interfaces/bots/admin/router.py
- tests/test_booking_patient_flow_stack3c1.py
- locales/en.json
- locales/ru.json

## 12. Commands Run

- `pytest -q tests/test_booking_patient_flow_stack3c1.py tests/test_i18n.py tests/test_runtime_wiring.py`
- `pytest -q tests/test_runtime.py tests/test_runtime_wiring.py tests/test_booking_orchestration.py`

## 13. Test Results

- Pass: `9 passed in 4.21s`
- Pass: `17 passed in 2.99s`

## 14. Known Limitations / Explicit Non-Goals

- No reminder scheduling/execution logic.
- No doctor queue UI.
- No owner analytics UI.
- No full existing-booking slot replacement UX (reschedule remains intent/status-request path).
- No fuzzy patient identity recovery.

## 15. Deviations From Docs (if any)

- None intentional for Stack 3C2 scope.

## 16. Readiness Assessment for next stack

- Booking now supports ongoing patient control surfaces and safer resume/callback behavior.
- Ready for next-stack improvements around deeper admin workflow handling and broader operational flows.
