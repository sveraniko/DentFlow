# PAT-003 audit — Existing booked patient confirmation flow (2026-04-21)

## 1. Executive verdict

**Verdict: Partial**

PAT-003 is materially implemented at the runtime/core level, but not fully closed as a clean patient-confirmation journey. Existing-booking access works through `/my_booking` (contact-based lookup + booking card controls), and reminder callbacks are real and transactional (`confirm`/`reschedule`/`cancel`/`ack`), including stale/invalid handling. However, the reminder path is still action-toast centric (no canonical post-action booking panel update), and there is no clearly unified patient-facing confirmation surface that behaves consistently between `/my_booking` and reminder entry. Also, scenario docs currently overstate closure by labeling PAT-003 “Implemented”; code/test evidence supports **Partial**.

**Final recommendation**

Treat PAT-003 as a bounded closure task, not a platform refactor: keep current orchestration/reminder backbone and stale guards, then add a thin integration layer that turns reminder acceptance into a clear patient-facing “you are confirmed / requested changes / canceled” panel with optional canonical booking card handoff. Do this through a narrow three-PR stack (PAT-A3-1..3) focused on entry unification, confirmation feedback consistency, and regression coverage for reminder+`/my_booking` seams.

---

## 2. Current real flow

### 2.1 Current behavior (runtime reality)

#### Entry A: `/my_booking`
1. Patient enters `/my_booking` (or `phome:my_booking`).
2. Router starts/resumes **existing booking control** session (`route_type="existing_booking_control"`) and sets `booking_mode="existing_lookup_contact"`.
3. Bot asks for contact/phone (`patient.booking.my.contact_prompt`).
4. Contact submission resolves patient by exact contact:
   - exact match -> fetch bookings by patient;
   - no match -> `patient.booking.my.no_match`;
   - ambiguous -> escalates to admin and shows escalated response.
5. If exact+live booking exists, router renders booking card text (`BookingCardAdapter` expanded panel) and action buttons.
6. Actions currently exposed from `/my_booking` panel:
   - **Confirm** (only when booking is `pending_confirmation`)
   - **Reschedule request**
   - **Earlier slot waitlist**
   - **Cancel** (with confirm/abort prompt)
7. Confirm from `/my_booking` calls `confirm_existing_booking` -> orchestration `confirm_booking` -> status moves `pending_confirmation -> confirmed` on success; panel is re-rendered.

#### Entry B: reminder callback path (`rem:*`)
1. Reminder worker sends reminder message from `communication.reminder_job` queue.
2. Message rendering uses localized text + booking date/time + context labels and action buttons by reminder type:
   - `booking_confirmation` / `booking_no_response_followup`: `confirm`, `reschedule`, `cancel`
   - `booking_previsit`, `booking_day_of`, `booking_next_visit_recall`: `ack`
3. Patient taps callback `rem:<action>:<reminder_id>`.
4. Router calls `ReminderActionService.handle_action(...)` with provider message id check.
5. Service enforces reminder actionability (`sent` only), stale checks (`acknowledged/canceled/failed/expired`), message-id integrity check, then:
   - `ack`: reminder -> `acknowledged`
   - `confirm`: orchestration confirm booking + reminder acknowledge
   - `reschedule`: orchestration reschedule-request + reminder acknowledge
   - `cancel`: orchestration cancel booking + reminder acknowledge
6. Router clears reminder keyboard on accepted action (best effort) and returns toast/alert (`accepted`, `stale`, `invalid`).

### 2.2 What is target-state (document narrative beyond runtime)

- PAT-003 in `docs/71_role_scenarios_and_acceptance.md` is marked “Implemented”, but current user journey is still split: `/my_booking` has a booking-card surface while reminder callback path returns toast-only feedback.
- Booking docs/UI contracts imply a clearer action-required confirmation journey with compact but explicit patient flow continuity; runtime currently does not provide a canonical post-reminder booking panel handoff.
- Unified booking-card profile docs imply stronger cross-entry consistency than current reminder-action UX actually provides.

---

## 3. Evidence map

| Flow segment | Evidence in code | Evidence in tests | Evidence in docs | Status | Notes |
|---|---|---|---|---|---|
| existing-booking entry | `patient/router.py`: `_enter_existing_booking_lookup`, `/my_booking`, `phome:my_booking`; `telegram_flow.py`: `start_or_resume_existing_booking_session` | `test_patient_home_surface_pat_a1_2.py` parity for `/my_booking` and `phome:my_booking`; `test_booking_patient_flow_stack3c1.py` route isolation | `docs/71` PAT-003 entry mentions `/my_booking`/reminder | Implemented | Entry exists and is isolated from new-booking route family. |
| `/my_booking` behavior | `patient/router.py`: existing lookup prompt, contact mode switch, `_show_existing_booking_result` with booking actions | `test_booking_patient_flow_stack3c1.py` exact/no-match/ambiguous control flow | `booking_docs/10`, `docs/71` | Implemented | Requires contact submission first; not direct booking list from command alone. |
| current/upcoming booking lookup | `telegram_flow.py`: `resolve_existing_booking_by_contact` -> list bookings by patient -> live statuses filter + sort | `test_booking_patient_flow_stack3c1.py::test_existing_booking_controls_exact_match_no_match_and_ambiguous` | `docs/71`, `booking_docs/10` | Implemented | “Live” statuses include pending/confirmed/reschedule_requested/checked_in/in_service. |
| reminder scheduling linkage | `booking/orchestration.py`: finalize/reschedule replace plan; cancel/terminal cancel plan | `test_booking_orchestration.py` reminder scheduling/replacement/cancel coverage | `README`, `booking_docs/60` | Implemented | Booking emits reminder planning, communication owns reminder truth. |
| reminder delivery content | `communication/delivery.py`: `render_booking_reminder_message`, localized summary/context/timezone | `test_reminder_delivery_stack4b1.py`, `test_reminder_rr2.py` | `booking_docs/50`, `booking_docs/10` | Implemented | Humanized labels supported when reference service provided; safe fallback labels otherwise. |
| reminder action buttons | `delivery.py::_build_actions` map by reminder_type | `test_reminder_actions_stack4b2.py` action expectations; `test_reminder_delivery_stack4b1.py` send payload actions | `booking_docs/50` action-required pattern | Implemented | Confirmation reminders expose `confirm/reschedule/cancel`; previsit/day-of expose `ack` only. |
| confirm/ack callback handling | `patient/router.py`: `reminder_action_callback`; `communication/actions.py`: transactional handling + booking bridge | `test_reminder_actions_stack4b2.py` accept/stale/invalid/atomicity | `docs/71` PAT-006, booking docs | Implemented | Real mutation path exists; booking transition and reminder acknowledge are atomic in tx scope. |
| stale callback protection | `actions.py` terminal reminder stale; message-id mismatch invalid; `telegram_flow.py` existing-control stale/mismatch; runtime callback token guards in router | `test_reminder_actions_stack4b2.py` duplicate/stale/mismatch; `test_booking_patient_flow_stack3c1.py` stale session rejection; `test_reminder_runtime_integrity_rr1.py` transition rules | `booking_docs/40` stale callback rule | Implemented | Strong for reminder state + existing-booking action session ownership. |
| patient-facing feedback after confirm | `/my_booking` path re-renders booking panel; reminder path returns toast and clears keyboard only | No dedicated router test for reminder callback UI feedback rendering | `docs/15`, unified-card docs expect coherent panel UX | Partial | Backend mutation is complete, but reminder UX feedback is minimal and not canonical-card based. |
| state/event recording | `booking_state_service` via orchestration writes booking status history/events; finalize writes `booking.created`, status history | `test_booking_orchestration.py` checks history/outbox mutation | `booking_docs/40`, `booking_docs/10` | Implemented | Status mutation persistence is present. |
| human-readable booking presentation | `/my_booking` uses booking card snapshot/adapter; reminder message renders readable copy; fallback can still be generic | `test_reminder_rr2.py` human labels, locale fallback; booking card tests in stack3c1 | `docs/16`, `docs/16-4`, `docs/17` | Partial | Human-readable exists, but two entry surfaces are not unified and reminder post-action continuity is weak. |

---

## 4. Gaps that block PAT-003 closure

1. **No canonical post-reminder confirmation panel continuity**
   - **Severity:** blocker
   - **Evidence:** `reminder_action_callback` currently returns toast (`accepted/stale/invalid`) and removes markup; it does not transition user into updated booking card/panel.
   - **Why it matters:** PAT-003 is about a clean confirmation journey for an already-booked patient; status change without clear contextual confirmation panel is functionally correct but UX-incomplete.
   - **Type:** mixed

2. **`/my_booking` entry requires contact re-submission each time (no lightweight direct continuity route evidenced)**
   - **Severity:** major
   - **Evidence:** `_enter_existing_booking_lookup` always prompts contact and sets `existing_lookup_contact` mode.
   - **Why it matters:** returning booked patients may experience unnecessary friction before they can confirm attendance.
   - **Type:** mixed (runtime flow + UX)

3. **No explicit test coverage for patient-router reminder callback UI feedback contract**
   - **Severity:** medium
   - **Evidence:** reminder tests heavily cover service-level action and delivery; no direct test of `patient/router.py::reminder_action_callback` rendering/edit behavior.
   - **Why it matters:** PAT-003 closure depends on patient-visible confirmation behavior, not only backend correctness.
   - **Type:** mixed

4. **Scenario acceptance doc overstates closure vs current UX state**
   - **Severity:** medium
   - **Evidence:** `docs/71` marks PAT-003 Implemented; runtime still split across uneven UX surfaces.
   - **Why it matters:** can cause premature sign-off without closing real patient-experience seams.
   - **Type:** UX/documentation alignment

---

## 5. Things that are already good enough

- Reminder backbone and scheduling ownership boundaries are correct and should be retained (booking triggers intent; communication owns reminder truth).
- Reminder action transaction semantics are solid (booking transition + reminder ack together; stale/invalid/message mismatch handling exists).
- Existing-booking control validation strongly guards stale or foreign booking actions (session ownership + patient ownership checks).
- `/my_booking` booking controls (confirm/reschedule/waitlist/cancel prompt) are operational and tied to canonical booking transitions.
- Reminder delivery relevance checks (already confirmed, booking missing, window passed, reschedule_requested) prevent incorrect sends.

---

## 6. Minimal implementation stack to close PAT-003

### PAT-A3-1 — Canonical booked-patient panel handoff after reminder actions
- **Objective:** Ensure reminder `confirm/reschedule/cancel/ack` returns a clear, human-readable patient panel (or direct `/my_booking` card render) rather than toast-only completion.
- **Exact scope:** `patient/router.py` reminder callback flow + minimal helper reuse from existing booking card renderer.
- **Non-goals:** No reminder engine redesign; no admin/doctor/owner changes; no booking state machine changes.
- **Files likely touched:**
  - `app/interfaces/bots/patient/router.py`
  - locale keys (`locales/en.json`, `locales/ru.json`) for concise post-action feedback copy
- **Tests likely touched/added:**
  - new focused patient-router reminder callback tests (accepted/stale/invalid + panel continuity)
- **Migrations needed?** no
- **Acceptance criteria:** After reminder action, patient sees explicit outcome panel with updated booking context (or safe fallback panel) and no stale action keyboard remains.

### PAT-A3-2 — Reduce friction in existing-booking entry while preserving safety
- **Objective:** Allow booked patient to reach current booking context with less repeated friction (while preserving identity safety).
- **Exact scope:** existing booking entry logic in patient router/flow service; bounded continuity shortcut when safe (e.g., already linked telegram contact/session context), fallback to contact prompt when not safe.
- **Non-goals:** No identity model redesign; no broad patient profile UX changes.
- **Files likely touched:**
  - `app/interfaces/bots/patient/router.py`
  - `app/application/booking/telegram_flow.py`
- **Tests likely touched/added:**
  - existing-booking entry tests for shortcut-vs-prompt paths
  - stale/foreign booking guard regressions
- **Migrations needed?** no
- **Acceptance criteria:** Returning patient can open existing booking with fewer steps in safe cases; unsafe/unknown cases still require contact resolution.

### PAT-A3-3 — PAT-003 acceptance hardening tests and scenario-truth update
- **Objective:** Lock closure with narrow regression coverage and align scenario acceptance docs to runtime truth.
- **Exact scope:** tests around `/my_booking` + reminder callback UX contract; update scenario status text after code closure.
- **Non-goals:** No platform-wide audit refresh; no unrelated role-surface updates.
- **Files likely touched:**
  - `tests/test_booking_patient_flow_stack3c1.py`
  - new patient router reminder callback test file (targeted)
  - `docs/71_role_scenarios_and_acceptance.md` (PAT-003 status note only, after runtime closure)
- **Tests likely touched/added:** targeted PAT-003 test slice only
- **Migrations needed?** no
- **Acceptance criteria:** deterministic tests prove end-to-end booked-patient confirmation journey across `/my_booking` and reminder entry; docs no longer overstate/understate runtime reality.

---

## 7. Product decisions requiring explicit human confirmation

1. **Primary PAT-003 entry weighting:** Is PAT-003 considered closed only when both `/my_booking` and reminder-entry provide equivalent confirmation clarity, or is one canonical and the other secondary?
2. **Meaning of “Confirm attendance”:** Should patient confirmation transition booking status (`pending_confirmation -> confirmed`) as today, or be modeled as reminder acknowledgment only in some cases?
3. **Canonical patient surface:** Should reminder confirmation outcomes always hand off to the same booking card used by `/my_booking`?
4. **Scope boundary with PAT-004/PAT-005:** Are reminder buttons for `reschedule`/`cancel` required for PAT-003 closure, or is PAT-003 closure satisfied by confirmation/ack only with those actions treated as adjacent but non-blocking?

---

## 8. Final closure checklist

- [ ] Existing booked patient can enter via `/my_booking` and reach current booking context reliably.
- [ ] Reminder message for confirmation-eligible booking includes actionable confirm/reschedule/cancel controls.
- [ ] Reminder callback validates staleness/message integrity and is safe against duplicate taps.
- [ ] Confirmation action updates canonical booking state where eligible.
- [ ] Patient receives clear post-action feedback in-panel (not only transient toast) with human-readable booking context.
- [ ] `/my_booking` and reminder-driven confirmation outcomes are behaviorally consistent enough for patient understanding.
- [ ] Stale callbacks (session mismatch, foreign booking, terminal reminder) are safely rejected with bounded user guidance.
- [ ] Booking status/history mutation is recorded and reminders are acknowledged/canceled/replanned correctly.
- [ ] PAT-003 is marked Implemented only when the above are true in runtime + tests.

---

## Execution notes (this audit run)

Targeted test slice was executed in this environment:

- `pytest -q tests/test_reminder_actions_stack4b2.py tests/test_reminder_delivery_stack4b1.py tests/test_reminder_recovery_stack4c1.py tests/test_reminder_rr2.py tests/test_reminder_runtime_integrity_rr1.py tests/test_reminder_worker_wr1.py tests/test_reminder_worker_wr2.py tests/test_booking_patient_flow_stack3c1.py tests/test_booking_orchestration.py tests/test_patient_home_surface_pat_a1_2.py`

Result:
- 78 passed, 1 failed.
- Failing test: `tests/test_reminder_actions_stack4b2.py::test_rendering_actions_and_context_for_confirmation_and_ack` (asserts raw ids in reminder text; runtime currently renders safe generic/humanized context labels in this path).
