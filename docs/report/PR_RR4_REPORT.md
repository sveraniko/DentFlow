# PR RR-4 Report — Human-Readable Reminder Context + Policy Cleanup

## 1. Objective
Close reminder-line UX/policy gaps by removing raw internal identifiers from user-facing reminder context, adding bounded localized fallback resolution for doctor/service/branch labels, and replacing hardcoded manual retry enable behavior with explicit policy control.

## 2. Docs Read
1. `README.md`
2. `docs/10_architecture.md`
3. `docs/17_localization_and_i18n.md`
4. `docs/18_development_rules_and_baseline.md`
5. `docs/25_state_machines.md`
6. `docs/70_bot_flows.md`
7. `docs/80_integrations_and_infra.md`
8. `docs/85_security_and_privacy.md`
9. `docs/90_pr_plan.md`
10. `docs/95_testing_and_launch.md`
11. `docs/report/PR_RR1_REPORT.md`
12. `docs/report/PR_RR2_REPORT.md`
13. `docs/report/PR_RR3_REPORT.md`

## 3. Scope Implemented
- Reminder rendering now resolves human labels from clinic reference data (doctor display name, localized service title, branch display name).
- Reminder rendering no longer uses raw `doctor_id`, `service_id`, `branch_id` in normal user-facing message body path.
- Added bounded fallback behavior for unresolved labels: preferred locale -> clinic default locale -> safe generic human text.
- Manual retry path no longer uses hardcoded `enabled = True`; it is now controlled via explicit policy key (`communication.manual_retry_enabled`).
- Added RR-4 behavioral tests for human-readable context, no-id leak behavior, fallback strategy, and manual retry policy toggle.

## 4. Human-Readable Context Strategy
- During reminder rendering, booking context is mapped through clinic reference entities:
  - doctor: `Doctor.display_name`
  - service: localized translation via `Service.title_key`
  - branch: `Branch.display_name`
- Rendering receives `ClinicReferenceService` in worker runtime, preserving existing reminder delivery/runtime boundaries while improving text quality.

## 5. Fallback Strategy
Implemented bounded fallback chain for service labels and overall reminder context:
1. Preferred locale label (`reminder.locale_at_send_time`) where available.
2. Clinic default locale label (`clinic.default_locale`) when preferred locale is unavailable.
3. Safe generic localized fallback text:
   - doctor unknown
   - service unknown
   - branch unknown

Raw IDs and raw title keys are not used as normal user-visible fallback in reminder body.

## 6. Retry Policy Cleanup Notes
- Replaced hardcoded `enabled = True` in manual retry service path with policy-controlled toggle:
  - `communication.manual_retry_enabled` (default true).
- Policy behavior remains bounded and inspectable through the existing policy resolver/repository model.
- Added test proving disabled policy returns `manual_retry_disabled` and does not schedule retry reminder jobs.

## 7. Files Added
- `docs/report/PR_RR4_REPORT.md`

## 8. Files Modified
- `app/application/communication/delivery.py`
- `app/application/communication/recovery.py`
- `app/application/clinic_reference.py`
- `app/domain/policy_config/models.py`
- `app/worker.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_reminder_rr2.py`
- `tests/test_reminder_recovery_stack4c1.py`

## 9. Commands Run
- `rg --files -g 'AGENTS.md'`
- `find .. -name AGENTS.md -print`
- `sed -n ...` over required architecture/localization/runtime docs and RR reports
- `rg -n "doctor_id|service_id|branch_id|enabled = True|manual_retry|retry" app tests locales`
- `pytest -q tests/test_reminder_rr2.py tests/test_reminder_delivery_stack4b1.py tests/test_reminder_recovery_stack4c1.py tests/test_reminder_runtime_integrity_rr1.py tests/test_admin_aw4_surfaces.py`

## 10. Test Results
- Reminder RR-1/RR-2/RR-3/RR-4 targeted regression suite passed:
  - `31 passed in 9.26s`

## 11. Remaining Known Limitations
- Doctor and branch labels currently rely on reference display names and are not separately locale-variant fields in the domain model.
- If clinic reference data is absent, message falls back to safe generic human text (not rich labels), which is safe but less personalized.
- This PR intentionally does not introduce a broad message-template platform or reminder subsystem redesign.

## 12. Final Readiness Assessment for the reminder line
Reminder line is now substantially more human-facing and policy-clean:
- user-facing reminders render readable doctor/service/branch context,
- raw internal identifiers are removed from normal message body path,
- fallback behavior is bounded and localized,
- manual retry enable behavior is explicit and policy-driven.

Within RR-4 scope, the reminder line is ready to be considered polish-complete for this wave.
