# PAT-001 audit — New visitor first booking (2026-04-21)

## 1) Executive verdict

**Verdict: Partial**

PAT-001 is not missing: a real end-to-end runtime path exists from `/start` -> `/book` -> service -> doctor preference -> slot -> contact -> patient resolve/create -> `review_ready` -> booking finalize -> success message. However, product-quality closure is not yet met because entry remains command-text driven, review/final-confirm is not an explicit user confirmation step in the actual runtime, and success output still formats raw IDs instead of human labels. Reminder scheduling after finalize is implemented in orchestration and backed by reminder services/tests, so backend post-finalization reminder planning appears real and operationally integrated.

**Final recommendation**

Close PAT-001 with a narrow three-PR stack focused only on patient first-booking UX seams: (1) improve `/start` + booking intent capture entry, (2) add explicit review/final-confirm panel before finalize, (3) improve success rendering to human-readable labels and verify reminder chain visibility/readiness. Keep booking orchestration/reminder backbone unchanged (already good). Do not pull in Google Calendar, care flow redesign, admin workdesk, or broad card framework changes.

---

## 2) Current real flow

### Current behavior (code reality)

1. **User sends `/start`**
   - Bot returns a text home panel string (`role.patient.home`) listing command-style entries (`/book`, `/my_booking`, etc.).
   - No inline first-run CTA panel is rendered in this handler.

2. **User initiates booking with `/book`**
   - Router starts or resumes a `service_first` booking session (`start_or_resume_session`) and stores session id in per-user flow state.
   - Router calls resume-panel resolver.

3. **Resume mapping drives next panel**
   - `determine_resume_panel` + `_panel_for_session` map session state to one of: `service_selection`, `doctor_preference_selection`, `slot_selection`, `contact_collection`, `review_finalize`, or terminal.

4. **Service selection**
   - Callback `book:svc:*` updates session service and renders doctor preference panel.

5. **Doctor preference selection**
   - Callback `book:doc:*` supports `any` or specific doctor id.
   - Then renders slot panel.

6. **Slot selection**
   - Callback `book:slot:*` selects slot/hold via orchestration.
   - On success, router requests contact with reply keyboard (`request_contact=True`).

7. **Contact + patient resolution/creation**
   - Contact can come from shared contact or phone-like text.
   - Router stores contact snapshot, resolves patient by contact, and:
     - exact match: attach existing patient;
     - no match: create minimal patient and attach;
     - ambiguous: escalate to admin and stop.

8. **Finalize path in current runtime**
   - Router calls `mark_review_ready`.
   - Immediately after that, router calls `finalize` in the same contact handler (no explicit user “Confirm booking” action step before finalize).

9. **Success output**
   - Success message is text template with placeholders filled from booking fields.
   - It currently uses raw `doctor_id`, `service_id`, `branch_id`, and raw status token.

10. **Reminder scheduling after finalize**
    - Finalization path calls reminder plan replacement in booking orchestration transaction.
    - Reminder planner schedules confirmation/day-before/day-of jobs based on policy and booking timing.

### Target-state behavior (documented but not fully implemented in runtime)

- PAT-001 docs and booking UI contract describe stronger first-run guidance and an explicit **review/final confirm** step before creation.
- i18n docs expect explicit language switching path and first-run language choice “when appropriate”.
- Current runtime supports only command-text `/start` and no explicit first-run language picker in patient `/start` flow.

---

## 3) Evidence map

| Flow segment | Evidence in code | Evidence in tests | Evidence in docs | Status | Notes |
|---|---|---|---|---|---|
| entry/start | `start()` answers `role.patient.home` text only | n/a | PAT-001 notes command-style home | **Partial** | Entry works but not polished CTA panel. |
| intent capture | `/book` command starts/resumes booking session; no intent buttons at `/start` | route/session tests focus booking session, not home CTA | Bot flow docs list canonical patient flows incl. new booking | **Partial** | Intent capture exists but command-oriented. |
| service selection | callback `book:svc:*` -> `update_service` | happy path tests include `update_service` | booking docs expect service/problem first | **Implemented** | Core step present. |
| doctor selection | callback `book:doc:*` supports any/specific doctor | happy path tests include doctor preference | booking docs require doctor preference/code step | **Implemented** | Any + specific choice implemented. |
| slot selection | callback `book:slot:*`, slot unavailable handling, contact prompt next | orchestration tests for hold/conflict/finalize path | booking docs require slot proposals then slot select | **Implemented** | Functional, with stale/slot conflict handling. |
| contact capture | contact share + phone-regex text handlers, request_contact keyboard | happy path sets contact and continues | booking docs require contact confirmation after slot | **Implemented** | JIT contact collection is real (after slot). |
| patient resolution/creation | resolve by contact; no match -> create minimal patient; ambiguous -> escalate | tests verify exact/no-match-create/ambiguous escalation | booking docs define identity resolution | **Implemented** | Behavior strongly evidenced. |
| review/confirm before finalize | `_panel_for_session` can return `review_finalize`, but contact handler immediately marks review + finalizes | tests assert mark_review_ready + finalize sequence, no UI confirm step | UI contract expects explicit review/final confirm | **Partial** | Runtime skips explicit user confirm action before finalize. |
| booking finalize | orchestration requires `review_ready`, active hold, resolved patient, service; creates booking | finalize happy/rollback tests | booking docs define `review_ready -> completed` session transition | **Implemented** | Transactional finalize is robust. |
| success message quality | success template formats doctor/service/branch/status from raw booking fields | no direct patient success-quality test | PAT-001 known gap calls raw ids | **Partial** | User text not fully human-readable. |
| reminder scheduling | finalize calls `_replace_reminder_plan_for_booking_in_transaction` | tests verify reminders scheduled on finalize | README + integration docs: booking triggers reminder intent, comms owns reminder truth | **Implemented** | Backend scheduling is present and tested. |
| reminder user-facing outcome readiness | reminder callback actions wired in patient router; reminder rendering localizes and can use human labels via reference | reminder action/delivery/recovery/runtime tests; one targeted suite assertion is currently stale vs newer humanized rendering | booking docs define reminder CTA expectations | **Partial** | Backend + callback chain strong; one test mismatch indicates evolving copy/context expectations. |

---

## 4) Gaps that block PAT-001 closure

1. **No explicit pre-final user confirm panel/action in runtime**
   - **Severity:** blocker
   - **Evidence:** contact handler marks review-ready then finalizes immediately.
   - **Why it matters:** PAT-001 target UX requires clear review/final confirmation; current flow can finalize immediately after contact submission without explicit final consent step.
   - **Type:** mixed (UX + runtime sequencing)

2. **`/start` remains command-text home, weak first-run intent surface**
   - **Severity:** major
   - **Evidence:** `/start` returns static home text list.
   - **Why it matters:** first-time patient discoverability and guided start are weak; this is exactly where new visitor conversion quality is decided.
   - **Type:** UX-only (handler output)

3. **Booking success copy exposes raw identifiers**
   - **Severity:** major
   - **Evidence:** success template gets `booking.doctor_id`, `booking.service_id`, `booking.branch_id`, raw status.
   - **Why it matters:** product-quality “successful booking” output is not human-friendly and can confuse first-time users.
   - **Type:** UX-only (presentation layer)

4. **Language onboarding path for first-run not evidenced in PAT-001 runtime path**
   - **Severity:** medium
   - **Evidence:** i18n docs require user-selectable language path and first-run option “when appropriate”; `/start` path shows no language entry.
   - **Why it matters:** impacts first-time clarity for multilingual users; may be a closure criterion depending on product decision.
   - **Type:** UX-only

---

## 5) Things that are already good enough

- Booking orchestration constraints for finalize are robust (review-ready state, hold ownership/status, slot conflicts, transactional integrity).
- Just-in-time contact collection is correctly placed after slot selection.
- Patient resolution path (exact/no-match-create/ambiguous-escalate) is implemented and tested.
- Reminder planning is integrated into booking finalization transaction and backed by dedicated planner/service tests.
- Reminder ownership separation is correct: communication layer is canonical reminder truth; booking triggers planning intent.

These should **not** be reworked in the immediate PAT-001 closure wave.

---

## 6) Minimal implementation stack to close PAT-001

### PAT-A1-1 — First-run entry and booking intent surface
- **Objective:** upgrade `/start` from command-text-only home to focused first-booking intent panel.
- **Exact scope:** patient `/start` rendering only (plus i18n keys as needed), keep `/book` orchestration unchanged.
- **Non-goals:** no admin/doctor/owner changes, no care flow redesign, no reminder backend changes.
- **Files likely touched:**
  - `app/interfaces/bots/patient/router.py`
  - `locales/en.json`
  - `locales/ru.json`
- **Tests likely touched/added:** targeted patient router handler tests for `/start` rendering and action wiring.
- **Migrations needed?** no
- **Acceptance criteria:** first-time user sees explicit booking action(s) without memorizing commands; existing `/book` still works.

### PAT-A1-2 — Explicit review/final-confirm step before finalize
- **Objective:** enforce visible review + explicit user confirmation before booking creation.
- **Exact scope:** patient booking UI flow between contact resolution and finalize; add callback/action for final confirm.
- **Non-goals:** no state-machine redesign, no broad card framework refactor.
- **Files likely touched:**
  - `app/interfaces/bots/patient/router.py`
  - possibly booking callback handling helpers in same module
  - locales for review/confirm strings
- **Tests likely touched/added:** patient booking flow tests to assert “review shown first, finalize only after confirm action”.
- **Migrations needed?** no
- **Acceptance criteria:** after contact resolution user sees review summary + confirm action; booking is not created until confirm action is clicked.

### PAT-A1-3 — Human-readable success output + reminder-ready messaging polish
- **Objective:** replace raw-id success rendering with resolved labels and clear next-step copy.
- **Exact scope:** success message composition for PAT-001 creation result; optionally reuse existing label-resolving helpers.
- **Non-goals:** no reminder engine redesign; no Google Calendar surfaces.
- **Files likely touched:**
  - `app/interfaces/bots/patient/router.py`
  - maybe `app/application/booking/telegram_flow.py` (if reusing card label helpers)
  - locales (`en.json`, `ru.json`)
- **Tests likely touched/added:** patient success rendering tests and reminder-context consistency checks.
- **Migrations needed?** no
- **Acceptance criteria:** success output shows human doctor/service/branch labels and clear status/next-step wording; reminder scheduling behavior remains unchanged and verified.

---

## 7) Product decisions requiring explicit human confirmation

1. **Is PAT-001 closure allowed with command-triggered `/book` if `/start` has quick action hints, or must `/start` be fully inline-first?**
2. **Is explicit first-run language choice mandatory for PAT-001 closure now, or acceptable in a later UX increment if language switch exists elsewhere?**
3. **Is explicit review/final confirm a hard closure gate (recommended: yes), or can “contact submission implies consent” remain in MVP?**
4. **Must success output be fully human-readable labels before PAT-001 can be marked closed (recommended: yes)?**

---

## 8) Final closure checklist

- [ ] `/start` gives a clear first-booking entry experience for a new visitor (not command-memory dependent).
- [ ] Booking can be initiated from that entry and follows service -> doctor pref -> slot -> contact.
- [ ] Contact is collected just-in-time (after slot selection), not at initial start.
- [ ] Patient is resolved or minimally created from contact; ambiguous match escalates safely.
- [ ] User sees explicit review panel and performs explicit final confirmation before booking creation.
- [ ] Booking finalization creates booking in canonical state with expected transitions/history.
- [ ] Success output is human-readable (no raw ids for doctor/service/branch/status in user message).
- [ ] Reminder jobs are scheduled after successful finalize according to policy.
- [ ] Reminder callbacks/actions are wired and produce valid acceptance/stale handling.
- [ ] PAT-001 marked Implemented only when all items above are true in runtime, not just in docs.

---

## Execution notes for this audit

- Scope intentionally bounded to PAT-001 plus direct seams (booking session/orchestration/finalize and reminder planning/action chain).
- Targeted tests were runnable; command executed:
  - `pytest -q tests/test_booking_patient_flow_stack3c1.py tests/test_booking_application_foundation.py tests/test_booking_orchestration.py tests/test_reminder_actions_stack4b2.py tests/test_reminder_delivery_stack4b1.py tests/test_reminder_recovery_stack4c1.py tests/test_reminder_rr2.py tests/test_reminder_runtime_integrity_rr1.py tests/test_reminder_worker_wr1.py tests/test_reminder_worker_wr2.py`
- Result: 73 passed, 1 failed (`tests/test_reminder_actions_stack4b2.py::test_rendering_actions_and_context_for_confirmation_and_ack`) due to expectation of raw IDs while reminder rendering now returns humanized labels.
