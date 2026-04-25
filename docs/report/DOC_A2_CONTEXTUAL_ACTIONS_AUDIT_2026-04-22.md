# DOC-A2 audit — In-context clinical note and recommendation issuance continuity (2026-04-22)

## 1. Executive verdict

**Verdict: Partial.**

DOC-A2 is not closed yet. The doctor stack already has real runtime primitives for both requested actions: encounter notes can be added (`/encounter_note`) and recommendations can be issued (`/recommend_issue`) through `DoctorOperationsService`, with recommendation issuance also feeding the already-closed patient aftercare/recommendation channel (including proactive patient delivery attempt). However, both actions remain primarily command-entered and not naturally discoverable from the current callback booking/encounter panel continuity added in DOC-A1. Booking callbacks currently expose open patient/chart/linked recommendation/care-order actions, but not direct in-context “add quick note” or “issue recommendation” actions.

**Final recommendation.**

Proceed with DOC-A2 now, but keep scope narrow: add callback/panel entry points for quick note and recommendation issue directly from active booking/encounter context, reusing existing doctor operations and recommendation services (no domain rewrite). Keep command routes as fallback. Do not bundle broad chart redesign or encounter lifecycle overhaul into this block.

---

## 2. Current real flow

### 2.1 Adding a quick note (actual runtime)

**Current behavior (implemented path):**
1. Doctor reaches encounter context either by command (`/encounter_open`) or by booking callback handoff after `in_service`.
2. Note entry is performed by command:
   - `/encounter_note <encounter_id> <note_type> <note_text>`
3. Router validates command shape and delegates to `DoctorOperationsService.add_encounter_note(...)`, which checks encounter ownership and persists note via clinical service.
4. Doctor receives success text with note id.

**Operational reality:**
- This is usable but command-centric.
- The callback booking keyboard/panel does **not** expose a quick-note action.
- Encounter panel currently serves as context display + back path, not action panel for note capture.

**Target-state implied by docs:**
- Doctor contracts expect quick-note actionability as a natural contextual action with fast capture and note type selection, not raw command syntax as primary interaction.

### 2.2 Issuing a recommendation (actual runtime)

**Current behavior (implemented path):**
1. Doctor issues manually via command:
   - `/recommend_issue <patient_id> <type> <booking_id|-> <title>|<body> [<target_kind>:<target_code>]`
2. Router validates and calls `DoctorOperationsService.issue_recommendation(...)`.
3. Service creates + issues recommendation, optionally stores manual care target override, and attempts proactive patient delivery through `PatientRecommendationDeliveryService`.
4. Booking completion path also auto-creates aftercare recommendation via `_create_completion_aftercare(...)` when completing eligible booking status.

**Operational reality:**
- Issuance is real and end-to-end operational.
- From booking callback context, “Recommendation” currently opens **linked recommendation panel** (read/open latest linked) rather than a direct issue flow.
- Therefore issuance remains command-only from doctor operational surface.

**Target-state implied by docs:**
- Doctor queue/patient summary contracts expect recommendation issue as a primary contextual action.

### 2.3 Booking/encounter contextual reachability summary

- **From booking context:**
  - doctor can open patient, chart, linked recommendation, linked care-order, set in-service/complete.
  - doctor cannot directly trigger quick note or recommendation issue without leaving to command memory.
- **From encounter context:**
  - doctor can view canonical encounter context panel (after DOC-A1), but quick note still requires `/encounter_note` command; recommendation issue still `/recommend_issue`.
- **Conclusion:** context exists; contextual action affordances for DOC-004 and DOC-005 are still missing.

---

## 3. Evidence map

| Flow segment | Evidence in code | Evidence in tests | Evidence in docs | Status | Notes |
|---|---|---|---|---|---|
| booking-context actionability | Doctor booking keyboard has `in_service`, `complete`, `open_patient`, `open_chart`, `open_recommendation`, `open_care_order`; no quick-note/issue actions | `test_booking_linked_opens_12b1.py` validates linked open actions and in-service handoff | `docs/72...` doctor queue/patient summary contracts expect add note + issue recommendation as primary actions | Partial | Booking continuity improved by DOC-A1 but DOC-A2 actions not embedded |
| encounter-context actionability | `_render_doctor_encounter_panel` used for `/encounter_open` and in-service handoff; panel is contextual display with Back only | `test_doctor_in_service_hands_off_into_encounter_context`, `test_encounter_open_command_uses_canonical_encounter_panel` | DOC-A1 reports state canonical encounter context closure | Partial | Encounter context exists but not action-rich for note/recommend issue |
| quick note entry | `/encounter_note` command handler + `DoctorOperationsService.add_encounter_note` | `tests/test_clinical_stack7a.py` validates add note through operations | `docs/72...` quick note contract emphasizes fast structured capture | Partial | Implemented runtime primitive, command-only UX entry |
| recommendation issue entry | `/recommend_issue` command + `DoctorOperationsService.issue_recommendation`; callback `open_recommendation` only renders linked panel | `test_doctor_issue_and_booking_trigger`; care-commerce test for manual target override | `docs/72...` and `docs/70...` frame recommendation issuance as doctor canonical action | Partial | Issuance exists and works but is not callback/panel-first |
| patient-context sufficiency | booking detail includes patient quick-card, service/branch/status/time; encounter panel includes patient display + booking context; patient quick card includes masked phone/flags/upcoming snippet | booking-linked tests assert patient + booking context appears in encounter panel; doctor op tests cover quick-card composition | DOC-A1 reports indicate continuity spine closed | Implemented | Context data is generally sufficient to act safely once action entry exists |
| continuity after note/recommendation action | note path returns id-only success; recommendation issue returns id-only success; no automatic return/edit of booking/encounter panel for these command actions | no doctor callback continuity test for post-note/post-issue return | UI rules favor contextual-over-hierarchical and one active panel | Partial | Functional but not natural in-flow continuity |
| feed into patient aftercare truth | recommendation issue and booking completion aftercare both call recommendation service + issue state; delivery service attempts proactive patient notification callback | recommendation stack tests cover booking-trigger issuance and proactive delivery safe outcomes | PAT-007 reports mark proactive delivery and patient continuity as closed in bounded scope | Implemented | Downstream patient truth exists; doctor entry ergonomics are the remaining gap |
| stale/back safety | card callback decoding + stale handling; linked panels include Back to booking; legacy `doctorbk:*` callback bounded | `test_doctor_legacy_booking_callback_is_bounded`; linked open tests confirm back usage | UI contract requires stale-safe behavior | Implemented | Existing callback safety should be reused for DOC-A2 additions |

---

## 4. Gaps that block DOC-A2 closure

1. **No in-context quick-note action in booking/encounter callback surfaces**
   - **severity:** blocker
   - **evidence:** doctor booking keyboard lacks note action; note exists only as `/encounter_note` command.
   - **why it matters operationally:** clinician must remember and type raw syntax during active encounter, breaking DOC-A2 continuity intent.
   - **type:** mixed (UX + runtime wiring)

2. **No in-context recommendation issue action in booking/encounter callback surfaces**
   - **severity:** blocker
   - **evidence:** booking `open_recommendation` shows linked recommendation panel only; actual issuance via `/recommend_issue` command.
   - **why it matters operationally:** core post-visit action remains command-memory detour rather than natural next step.
   - **type:** mixed (UX + runtime wiring)

3. **Post-action continuity is command-response based, not panel continuity based**
   - **severity:** major
   - **evidence:** note/issue commands return textual acknowledgement (IDs), without contextual re-render tied to active booking/encounter panel.
   - **why it matters operationally:** after action, doctor is not kept in a coherent in-visit surface; increases context drop.
   - **type:** UX-only (with lightweight router wiring)

4. **Encounter panel still context-display-first without bounded action affordances**
   - **severity:** major
   - **evidence:** canonical encounter panel currently gives context + Back; no inline actions for note/recommend issue.
   - **why it matters operationally:** encounter continuity exists structurally but remains non-actionable for DOC-004/005 tasks.
   - **type:** mixed

---

## 5. Things already good enough

- DOC-A1 continuity spine (queue -> booking -> in_service -> canonical encounter panel) is already good baseline and should not be reworked.
- Booking state transitions and booking completion hook are sufficient; no booking state-machine redesign needed for DOC-A2.
- Recommendation domain lifecycle and patient aftercare feed (including proactive delivery attempt + safe fallback) are already operationally valid.
- Existing stale/back callback safety pattern is solid and should be reused for new doctor action entries.
- Doctor patient/chart context payloads are adequate for safe quick-note/recommend actions once entry points are added.

---

## 6. Minimal implementation stack to close DOC-A2

### DOC-A2A — Booking/encounter callback entry for quick note

- **objective:** make quick-note action naturally reachable from active booking/encounter context.
- **exact scope:**
  - add doctor callback action(s) for “Add quick note” from booking panel and/or encounter panel;
  - support compact bounded note-type selection + text capture handoff (minimal two-step command-like capture is acceptable if context-bound);
  - persist via existing `DoctorOperationsService.add_encounter_note`.
- **non-goals:**
  - no full clinical chart redesign;
  - no voice dictation subsystem expansion;
  - no encounter schema changes.
- **files likely touched:**
  - `app/interfaces/bots/doctor/router.py`
  - `locales/en.json`, `locales/ru.json`
- **tests likely touched/added:**
  - `tests/test_booking_linked_opens_12b1.py` (callback path)
  - new/extended doctor router tests for context-bound note capture behavior
- **migrations needed?** no
- **acceptance criteria:**
  - doctor can add a quick note from active booking/encounter context without memorizing `/encounter_note` syntax;
  - stale/back behavior remains bounded;
  - command path remains supported as fallback.

### DOC-A2B — Booking/encounter callback entry for recommendation issuance

- **objective:** make recommendation issuance naturally reachable from booking/encounter context.
- **exact scope:**
  - add callback-driven “Issue recommendation” entry from doctor booking/encounter context;
  - implement bounded compact payload flow (type + title/body minimal capture, optional target link preserved);
  - call existing `DoctorOperationsService.issue_recommendation`.
- **non-goals:**
  - no recommendation lifecycle redesign;
  - no patient recommendation panel redesign (already handled in PAT-A7);
  - no care-commerce redesign.
- **files likely touched:**
  - `app/interfaces/bots/doctor/router.py`
  - optional tiny glue in `app/application/doctor/operations.py` only if helper extraction needed
  - `locales/en.json`, `locales/ru.json`
- **tests likely touched/added:**
  - `tests/test_booking_linked_opens_12b1.py`
  - `tests/test_recommendation_stack10a.py` (doctor callback issue seam)
- **migrations needed?** no
- **acceptance criteria:**
  - doctor can issue recommendation from active context in bounded steps without raw `/recommend_issue` syntax;
  - successful issue still feeds existing patient aftercare truth and proactive delivery behavior;
  - linked recommendation open path remains intact.

### DOC-A2C — Post-action continuity and bounded safety hardening

- **objective:** keep doctor in coherent context after note/recommend actions and preserve stale safety.
- **exact scope:**
  - after quick note or recommendation issue, re-render appropriate encounter/booking panel with concise success hint;
  - ensure stale/invalid callback payload handling mirrors existing bounded behavior;
  - ensure Back returns to originating booking/encounter context deterministically.
- **non-goals:**
  - no broad navigation redesign;
  - no cross-role surface changes;
  - no analytics expansion.
- **files likely touched:**
  - `app/interfaces/bots/doctor/router.py`
  - `tests/test_booking_linked_opens_12b1.py`
  - optional targeted doctor router test module
- **tests likely touched/added:**
  - callback stale payload rejection for new note/issue callbacks
  - continuity assertions for post-action re-render and back semantics
- **migrations needed?** no
- **acceptance criteria:**
  - note/recommend actions no longer end in command dead-ends;
  - stale/back behavior remains deterministic and user-safe;
  - no regressions in DOC-A1 continuity tests.

---

## 7. Final recommendation

Yes — DOC-A2 should be the next implementation target now that DOC-A1 is closed. Build **DOC-A2A first** (quick-note contextual entry), then **DOC-A2B** (recommend issue contextual entry), and finish with **DOC-A2C** safety/continuity hardening. Do **not** start with broad chart UX expansion, encounter lifecycle redesign, or new recommendation domain features; the closure gap is contextual actionability, not domain capability.
