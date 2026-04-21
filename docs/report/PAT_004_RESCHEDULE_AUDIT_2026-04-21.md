# PAT-004 audit — Patient reschedule flow
Date: 2026-04-21
Scope: scenario-truth audit for PAT-004 only

## 1. Executive verdict

**Verdict: Partial**

PAT-004 is **not** a full patient self-service reschedule flow in current runtime. Patient entry points exist from both `/my_booking` and reminder actions, and both can land in the canonical existing-booking panel. The patient can click reschedule, and runtime records a reschedule request by transitioning booking status to `reschedule_requested` and canceling scheduled reminders. But there is no patient-facing slot reselection journey after that click (no slot list, no hold, no slot replacement, no old-slot release through patient flow). Current behavior is therefore “reschedule intent capture/request” plus state transition, not full reschedule completion.

**Final recommendation**

Keep current entry continuity (already good) and close PAT-004 via a narrow, bounded stack: (1) add canonical patient reschedule-reselection route from existing-booking context, (2) wire reselection to existing hold/finalization primitives in orchestration with explicit old-slot handling policy, and (3) add focused callback/state tests for `/my_booking` and reminder paths converging on one reschedule flow. Do not redesign booking engine or reminder architecture.

---

## 2. Current real flow

### Current behavior (runtime truth)

1. **Patient enters existing-booking context**
   - `/my_booking` and `phome:my_booking` both call `_enter_existing_booking_lookup(...)`.
   - Flow first attempts trusted identity shortcut (`_try_resolve_existing_booking_shortcut`) and directly opens existing booking controls if exactly one trusted patient identity resolves.
   - Otherwise it opens existing-booking control session and asks for contact to resolve patient.

2. **Patient sees booking panel actions including reschedule**
   - Existing booking panel keyboard includes “Request reschedule” (`patient.booking.my.reschedule`) as a booking control action.
   - This action is encoded through runtime card callback (`CardAction.RESCHEDULE`, `page_or_index="reschedule"`).

3. **Reminder-driven path also offers reschedule**
   - Reminder rendering for `booking_confirmation` and `booking_no_response_followup` includes `confirm/reschedule/cancel` CTA callbacks as `rem:<action>:<reminder_id>`.
   - On accepted reminder action, router executes canonical handoff to existing-booking panel (`_handoff_reminder_action_to_booking_panel`), including reschedule accepted outcomes.

4. **What reschedule click actually does**
   - `/my_booking` reschedule callback and runtime `c2|... page_or_index="reschedule"` both call `booking_flow.request_reschedule(...)`.
   - `BookingPatientFlowService.request_reschedule(...)` validates existing-booking control session ownership/staleness/booking ownership/status eligibility.
   - Then orchestration `request_booking_reschedule(...)` transitions booking to `reschedule_requested` and cancels scheduled reminder plan.

5. **What patient sees after click**
   - Patient gets re-rendered booking panel in updated status context (`reschedule_requested`), with next-step copy indicating clinic follow-up.
   - There is no automatic transition to slot picker for choosing a new time.

6. **State transitions/events currently recorded**
   - Booking status history records transition to `reschedule_requested`.
   - Outbox event `booking.reschedule_requested` is emitted via booking state service.
   - Reminder plan for the booking is canceled with `booking_reschedule_requested` reason.

7. **Does patient self-select a new slot?**
   - **No** in current patient runtime flow for PAT-004.
   - A lower-level orchestration API `reschedule_booking(...)` exists (admin/system style direct schedule overwrite + reminders replacement), but it is not wired to patient reschedule UI flow.

8. **Canonical booking-panel continuity**
   - Preserved in both relevant entry seams:
     - `/my_booking` path (including trusted shortcut work from PAT-A3-2)
     - accepted reminder actions handoff path (PAT-A3-1)

### Target-state behavior (if following docs narrative)

Docs in booking contracts describe a fuller reschedule sequence: request reschedule -> choose new slot -> secure new slot atomically -> release old slot -> update history/reminders. That sequence is **target-state**, not current patient runtime state.

---

## 3. Evidence map

| Flow segment | Evidence in code | Evidence in tests | Evidence in docs | Status | Notes |
|---|---|---|---|---|---|
| existing-booking reschedule entry | `patient/router.py`: `/my_booking`, `phome:my_booking`, `_enter_existing_booking_lookup`, trusted shortcut helper | `test_patient_existing_booking_shortcut_pat_a3_2.py` (`/my_booking` and home callback parity) | `docs/71_role_scenarios_and_acceptance.md` PAT-004 entry says booking card/reminder | Implemented | Entry exists and is active. |
| `/my_booking` reschedule availability | `_build_patient_booking_controls_keyboard` adds reschedule action for booking panel | Router/flow coverage in `test_booking_patient_flow_stack3c1.py` reschedule path | `booking_docs/50_booking_telegram_ui_contract.md` action-required patterns | Implemented | Reschedule button is present in booking control panel. |
| reminder reschedule availability | `communication/delivery.py` action map includes reschedule for confirmation/followup reminders; callback `rem:reschedule:*` | `test_reminder_actions_stack4b2.py` reminder action matrix includes reschedule; `test_patient_reminder_handoff_pat_a3_1a.py` accepted reschedule handoff | `booking_docs/10_booking_flow_dental.md` action-required reminder includes reschedule | Implemented | Reminder CTA exists and is processed transactionally. |
| reschedule callback handling | `patient/router.py` runtime callback branch (`page_or_index=="reschedule"`) and `request_reschedule` handler call booking flow | `test_booking_patient_flow_stack3c1.py::test_reschedule_cancel_waitlist_and_admin_open_details` | PAT-004 narrative in `docs/71` | Implemented | Callback routes are real and connected. |
| post-click patient feedback | Booking panel re-render after successful request; reminder accepted handoff includes outcome header + booking panel | `test_patient_reminder_handoff_pat_a3_1a.py` verifies post-action panel handoff, including reschedule | PAT-A3 reports define handoff continuity behavior | Implemented | Feedback is panel-based, not just toast, on accepted reminder actions. |
| canonical booking panel continuity | `_handoff_reminder_action_to_booking_panel` starts existing-booking control and renders same booking controls | `test_patient_reminder_handoff_pat_a3_1a.py`, `test_patient_existing_booking_shortcut_pat_a3_2.py` | PAT-A3 report docs | Implemented | Continuity seam is in place. |
| actual slot reselection ability | No patient runtime branch from reschedule action to slot-selection flow for existing booking | No test shows patient selecting a new slot after reschedule request in PAT-004 path | `booking_docs/10_booking_flow_dental.md` section 9 expects reselection | Missing | This is the main closure blocker. |
| booking state transition semantics | `request_booking_reschedule_in_transaction` -> status `reschedule_requested`, reminder cancel; state service emits history+outbox | `test_booking_patient_flow_stack3c1.py` asserts `reschedule_requested`; `test_booking_orchestration.py` checks history transitions | `booking_docs/40_booking_state_machine.md` includes `confirmed -> reschedule_requested` | Implemented | Semantics are request-state oriented, not completed reschedule. |
| stale callback protection | Card callback decode guard + existing-booking action validation against latest session/patient/booking | `test_booking_patient_flow_stack3c1.py` stale/foreign checks; `test_patient_reminder_handoff_pat_a3_1a.py` stale reminder behavior | `booking_docs/50_booking_telegram_ui_contract.md` stale callback rule | Implemented | Guardrails are materially present. |
| human-readable patient-facing reschedule copy | i18n keys for request-reschedule label, outcome header, next-step note (`clinic will contact`) | Reminder handoff tests assert localized outcome headers | `docs/17_localization_and_i18n.md` reminder/localization expectation | Partial | Copy exists and is clear, but reflects request-only model (not self-service reselection). |

---

## 4. Gaps that block PAT-004 closure

1. **No patient self-service slot reselection after reschedule request**
   - **Severity:** blocker
   - **Evidence:** reschedule action routes to `request_reschedule(...)` only; no patient path then opens slot list/hold/finalize for existing booking.
   - **Why it matters:** PAT-004 closure for “reschedule flow” generally implies patient can actually move to a new time, not just register intent.
   - **Type:** mixed (runtime + UX)

2. **No explicit old-slot handling policy in patient reschedule UX**
   - **Severity:** major
   - **Evidence:** current patient path changes status only; slot replacement semantics are not exposed to patient flow.
   - **Why it matters:** without clear reserve/release behavior, reschedule closure is ambiguous and operationally risky.
   - **Type:** mixed

3. **PAT-004 scenario doc currently overstates implementation status**
   - **Severity:** medium
   - **Evidence:** `docs/71` marks PAT-004 Implemented while runtime is request-only.
   - **Why it matters:** acceptance truth drift can cause premature closure and incorrect planning.
   - **Type:** UX/documentation truth gap (not runtime breakage)

---

## 5. Things that are already good enough

- Existing-booking entry seams (`/my_booking`, home callback, trusted shortcut fallback behavior) are sufficient and should be reused.
- Reminder action handling is transactional, stale-safe, and includes canonical booking-panel handoff after accepted actions.
- Existing-booking action integrity validation (session freshness + patient ownership + booking eligibility) is solid and should stay as the security boundary.
- Current status/event/reminder-cancel mechanics for “reschedule requested” are useful and should remain part of the final flow as intermediate semantics.

---

## 6. Minimal implementation stack to close PAT-004

### PAT-A4-1 — Canonical patient reschedule initiation panel
- **Objective:** convert “request reschedule” click into a canonical entry to a dedicated reschedule-selection route (instead of stopping at status-only request).
- **Exact scope:**
  - add explicit patient reschedule mode/state token for existing booking control session;
  - from `/my_booking` and reminder-handoff booking panel, route reschedule to the same canonical reschedule-start branch;
  - preserve stale/session ownership checks.
- **Non-goals:** no redesign of reminder engine, no admin queue redesign, no new booking-route overhaul.
- **Files likely touched:**
  - `app/interfaces/bots/patient/router.py`
  - `app/application/booking/telegram_flow.py`
  - (possibly) `locales/en.json`, `locales/ru.json` for precise copy.
- **Tests likely touched/added:**
  - extend `tests/test_patient_reminder_handoff_pat_a3_1a.py`
  - add focused reschedule-route tests near `tests/test_patient_existing_booking_shortcut_pat_a3_2.py` or a dedicated PAT-A4 file.
- **Migrations needed?** no
- **Acceptance criteria:** clicking reschedule always lands in one canonical patient reschedule-start panel from both entry seams.

### PAT-A4-2 — Patient slot reselection + atomic booking update
- **Objective:** enable patient to choose a new slot and complete reschedule in runtime.
- **Exact scope:**
  - expose slot listing for reschedule mode;
  - secure new slot via hold and finalize update semantics;
  - apply explicit old-slot handling policy during completion;
  - produce clear success/failure/stale feedback.
- **Non-goals:** no platform-wide slot engine rewrite; no admin workdesk changes.
- **Files likely touched:**
  - `app/interfaces/bots/patient/router.py`
  - `app/application/booking/telegram_flow.py`
  - `app/application/booking/orchestration.py` (small adapter/use of existing primitives)
- **Tests likely touched/added:**
  - `tests/test_booking_patient_flow_stack3c1.py` (new reselection scenario)
  - targeted router callback tests for slot reselection branch.
- **Migrations needed?** no
- **Acceptance criteria:** patient can select new slot from reschedule path; booking schedule is changed and visible immediately; failure states are stale-safe.

### PAT-A4-3 — Closure hardening for reminders/state semantics
- **Objective:** lock PAT-004 behavior with focused regression tests and explicit semantics.
- **Exact scope:**
  - verify reminder-driven reschedule and `/my_booking` reschedule converge to same flow;
  - verify state history/outbox/reminder-plan effects for request vs completed reschedule;
  - verify stale callback rejection for obsolete reschedule controls.
- **Non-goals:** no broad reminder policy changes, no analytics expansion.
- **Files likely touched:**
  - `tests/test_reminder_actions_stack4b2.py`
  - `tests/test_patient_reminder_handoff_pat_a3_1a.py`
  - `tests/test_booking_patient_flow_stack3c1.py`
  - `tests/test_booking_orchestration.py`
- **Tests likely touched/added:** targeted PAT-004 regressions only.
- **Migrations needed?** no
- **Acceptance criteria:** PAT-004 test matrix demonstrates real end-to-end patient reselection closure from both entry seams.

---

## 7. Product decisions requiring explicit human confirmation

1. Should PAT-004 closure require **true self-service slot reselection** (recommended) or remain a **request-only intent** scenario?
2. During reschedule reselection, does old slot remain occupied until new slot is secured, or is it released earlier?
3. Must reminder and `/my_booking` reschedule actions converge to one canonical flow (recommended: yes)?
4. Is admin approval/triage part of PAT-004 acceptance, or explicitly separate as admin scenario continuation after patient request?

---

## 8. Final closure checklist

- [ ] Patient with existing booking can enter reschedule from `/my_booking` and reminder path.
- [ ] Both entries converge to one canonical reschedule-selection flow.
- [ ] Patient can select a new slot in bot UI (not only request intent).
- [ ] Old-slot handling policy is explicitly implemented and observable.
- [ ] Booking transitions/history/events are correct for request and completed reschedule.
- [ ] Reminder plan behavior is consistent after reschedule completion.
- [ ] Stale/foreign callbacks are safely rejected.
- [ ] Post-action patient panel clearly shows new booking time/status.
- [ ] PAT-004 status in scenario docs matches runtime truth.

---

## Targeted test execution note for this audit

A focused test subset was executed:
- `tests/test_reminder_actions_stack4b2.py`
- `tests/test_patient_reminder_handoff_pat_a3_1a.py`
- `tests/test_patient_existing_booking_shortcut_pat_a3_2.py`
- `tests/test_booking_patient_flow_stack3c1.py`
- `tests/test_booking_orchestration.py`

Result in this environment: suite mostly passed, with failures in two reminder-planning assertions inside `test_booking_orchestration.py` (`test_reminder_scheduling_on_finalize_and_storage_outside_booking`, `test_reminder_replacement_on_reschedule_and_cancel_on_cancel`). Audit conclusions above rely primarily on direct code-path inspection for PAT-004 seams.
