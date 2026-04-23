# DOC-A2 audit — In-context clinical note and recommendation issuance continuity (2026-04-22)

## 1. Executive verdict

**Verdict: Partial.**

DOC-A2 is **not closed** yet. The doctor runtime already has real note/recommendation primitives (`/encounter_note`, `/recommend_issue`), booking→encounter continuity from DOC-A1 (`in_service` callback handoff), and recommendation issuance that feeds patient aftercare truth (including proactive delivery attempt). But both DOC-A2 actions remain operationally command-centric rather than naturally surfaced as contextual actions inside booking/encounter panels. In current reality, a doctor can complete the jobs, but must still recall syntax and IDs for quick note and recommendation issue in many practical moments.

**Final recommendation.**

Treat DOC-A2 as the next bounded implementation target now, but keep it narrow: first add callback/panel entry points for **quick note** and **issue recommendation** from current booking/encounter context, then keep existing command routes as fallback only. Do **not** redesign clinical domain models, recommendation lifecycle semantics, or care-commerce linkage; the gap is continuity/actionability at surface level, not missing backend truth.

---

## 2. Current real flow

### 2.1 Adding a quick note (actual runtime)

Current doctor note entry is command-driven:

1. Doctor reaches encounter context via either:
   - `/encounter_open <patient_id> [booking_id]`, or
   - booking callback action `in_service` (from booking card) which opens canonical encounter panel.  
2. Doctor adds note via `/encounter_note <encounter_id> <note_type> <note_text>`.  
3. Router calls `DoctorOperationsService.add_encounter_note(...)`, which validates doctor ownership by encounter doctor_id and writes note through clinical service.

Operationally, this works, but the encounter panel itself currently does not expose an inline “Add note” action button or structured quick-note selector. The note path is therefore usable but still command-memory dependent.

### 2.2 Issuing a recommendation (actual runtime)

Current recommendation issue entry is also command-driven:

1. Doctor issues via `/recommend_issue <patient_id> <recommendation_type> <booking_id|-> <title|body> [target_kind:target_code]`.
2. Router calls `DoctorOperationsService.issue_recommendation(...)`.
3. Service checks doctor visibility/booking ownership, creates recommendation, issues it, optionally persists manual care target link, and attempts proactive patient delivery (`prec:open:<id>` callback path).

Additionally, booking completion action (`complete`) auto-creates booking-triggered aftercare recommendation via `_create_completion_aftercare(...)`.

### 2.3 Booking/encounter context reachability

- **Booking context:** yes, doctor can open booking card from queue and mark in-service/complete/patient/chart/linked recommendation/care order.
- **Encounter context:** yes, canonical encounter panel is reachable from in-service handoff and `/encounter_open`.
- **But DOC-A2 actions in-context:** still weak:
  - quick note = command route only,
  - recommendation issue = command route only,
  - booking action `open_recommendation` is linked-read panel, not issuance entry.

### 2.4 Current behavior vs target-state behavior

- **Current behavior:** actionable backend primitives + command entry + limited callback contextual opens.
- **Target-state implied by docs/contracts:** doctor queue/patient/encounter cards should provide natural contextual actions for “add quick note” and “issue recommendation” without raw command detours.

---

## 3. Evidence map

| Flow segment | Evidence in code | Evidence in tests | Evidence in docs | Status | Notes |
|---|---|---|---|---|---|
| booking-context actionability | Doctor booking keyboard has in_service/complete/patient/chart/recommendation/care-order actions; queue and booking callback continuity present. | `test_doctor_router_today_queue_empty_and_patient_open_search_path`, `test_doctor_in_service_hands_off_into_encounter_context`. | DOC-A1 reports and doctor flow maps require queue→booking continuity. | Implemented | Booking surface is operational and bounded.
| encounter-context actionability | `in_service` callback opens canonical encounter panel via `_render_doctor_encounter_panel`; `/encounter_open` reuses same panel. | `test_doctor_in_service_hands_off_into_encounter_context`, `test_encounter_open_command_uses_canonical_encounter_panel`. | DOC-A1B states canonical encounter context closure. | Implemented | Encounter context visibility is materially present.
| quick note entry | Only `/encounter_note` command route; operation exists via `add_encounter_note`. | Clinical service coverage: `test_chart_and_encounter_baseline_flow` (operations-level note). No callback UI note-flow test in doctor router stack. | Doctor UI contract expects fast quick-note capture from care context. | Partial | Runtime support exists, but in-context discoverability is command-heavy.
| recommendation issue entry | Only `/recommend_issue` command for issuance; booking callback `open_recommendation` shows linked recommendation panel (read/open), not issue action. | `test_doctor_issue_and_booking_trigger` validates issue + trigger behavior; linked open tests validate panel open/missing behavior. | DOC-005 and doctor contracts imply operational issue action in doctor flow. | Partial | Issuance exists but panel/context entry is missing.
| patient-context sufficiency | Booking detail and patient quick card include identity/phone flags/booking context; encounter panel includes patient + booking context label. | Queue/booking/context tests in stack6a + 12b1. | DOC-A1 reports explicitly target booking/encounter continuity context. | Partial | Enough for many cases, but no structured note/recommend entry affordance at point-of-care.
| continuity after note/recommendation action | Recommendation: proactive delivery and patient callback path exists; note: simple success ack only (no contextual continuation helper). | Recommendation tests cover proactive delivery safe paths; no doctor contextual re-entry test after note/recommend issue command. | PAT-A7 reports establish patient aftercare continuity bridge. | Partial | Recommendation continuity stronger than quick-note continuity.
| feed into patient aftercare truth | `issue_recommendation` and `_create_completion_aftercare` call recommendation service + delivery bridge. | `test_doctor_issue_and_booking_trigger`, proactive delivery tests in stack10a. | PAT-007/A7 reports document closure path and proactive bridge. | Implemented | Doctor-issued/triggered recommendations feed patient flow.
| stale/back safety | Card callback decode guarded; linked panels and encounter handoff keep Back to booking; legacy `doctorbk:*` bounded stale handler. | `test_doctor_legacy_booking_callback_is_bounded`, linked-open callback coverage. | UI/product rules require stale-safe and deterministic back paths. | Implemented | Existing callback safety should be preserved for DOC-A2 additions.

---

## 4. Gaps that block DOC-A2 closure

1. **No in-context quick note action on booking/encounter surfaces**
   - **Severity:** blocker  
   - **Evidence:** quick note is available through `/encounter_note` command only; booking/encounter callbacks expose no add-note action.  
   - **Why it matters operationally:** doctors in active encounter must switch to command syntax and manually carry encounter_id, which is fragile and slows chairside flow.  
   - **Type:** mixed (UX + runtime wiring)

2. **Recommendation issuance from doctor context is command-only**
   - **Severity:** blocker  
   - **Evidence:** `/recommend_issue` exists; booking callback `open_recommendation` opens linked recommendation read panel instead of issue path.  
   - **Why it matters operationally:** core DOC-005 action is not naturally discoverable from current booking/encounter flow.  
   - **Type:** mixed (UX + runtime wiring)

3. **Encounter context is visible but not yet action-complete for DOC-A2 tasks**
   - **Severity:** major  
   - **Evidence:** canonical encounter panel text exists with back path, but lacks quick-note and recommendation-issue direct controls.  
   - **Why it matters operationally:** DOC-A1 continuity spine is present, but DOC-A2 closure requires that context to be directly actionable.  
   - **Type:** UX-only leading to operational friction

4. **Divergent recommendation pathways (linked-open vs issue command) create mental split**
   - **Severity:** medium  
   - **Evidence:** booking card recommendation action opens latest linked recommendation, while issuance is separate raw command.  
   - **Why it matters operationally:** doctors can read linked recommendation in panel but still need command-memory detour to issue new/revised recommendation.  
   - **Type:** mixed

---

## 5. Things already good enough

- DOC-A1 spine (queue → booking → in_service → canonical encounter panel) is good enough and should not be reworked in DOC-A2.
- `DoctorOperationsService.add_encounter_note(...)` ownership checks and clinical write integration are good enough; no domain rewrite needed.
- `DoctorOperationsService.issue_recommendation(...)` and `_create_completion_aftercare(...)` semantics are good enough for first-wave DOC-A2.
- Recommendation lifecycle and patient continuity bridge (including proactive delivery safe outcomes) are already operationally valuable and should be reused, not redesigned.
- Existing callback stale/back safety patterns in doctor router are good enough baseline for extending contextual actions.

---

## 6. Minimal implementation stack to close DOC-A2

### DOC-A2A — Contextual quick-note entry from active encounter/booking

- **Objective:** make quick note capture naturally reachable from doctor booking/encounter context without raw command syntax.
- **Exact scope:**
  - add bounded callback action(s) on doctor booking/encounter panel for “Add quick note”;
  - provide compact note-type-first flow + short text capture handoff (Telegram-native, minimal steps);
  - bind encounter_id from current context automatically.
- **Non-goals:**
  - no full SOAP editor;
  - no new clinical schema;
  - no chart redesign.
- **Files likely touched:**
  - `app/interfaces/bots/doctor/router.py`
  - (possibly) `locales/en.json`, `locales/ru.json`
- **Tests likely touched/added:**
  - `tests/test_doctor_operational_stack6a.py`
  - `tests/test_booking_linked_opens_12b1.py`
  - (optional) focused doctor encounter-note callback test module
- **Migrations needed?** no
- **Acceptance criteria:**
  - doctor can add a quick note from current booking/encounter context in ≤2 navigation steps;
  - no encounter_id manual typing required in primary path;
  - stale/back behavior remains bounded.

### DOC-A2B — In-context recommendation issuance from booking/encounter

- **Objective:** allow doctor to issue recommendation directly from active booking/encounter context.
- **Exact scope:**
  - add contextual “Issue recommendation” action from doctor booking/encounter surfaces;
  - collect minimal inputs (type + concise title/body) with booking/patient prebound;
  - keep optional care target linking compact and optional.
- **Non-goals:**
  - no recommendation engine lifecycle changes;
  - no patient recommendation UX rewrite;
  - no owner analytics expansion.
- **Files likely touched:**
  - `app/interfaces/bots/doctor/router.py`
  - `app/application/doctor/operations.py` (only if tiny flow helper needed)
  - (possibly) `locales/en.json`, `locales/ru.json`
- **Tests likely touched/added:**
  - `tests/test_doctor_operational_stack6a.py`
  - `tests/test_booking_linked_opens_12b1.py`
  - `tests/test_recommendation_stack10a.py` (regression on issuance semantics)
- **Migrations needed?** no
- **Acceptance criteria:**
  - doctor can issue recommendation from booking/encounter panel without command-memory detour;
  - issued recommendation still feeds existing patient aftercare path unchanged;
  - existing `/recommend_issue` remains valid fallback.

### DOC-A2C — Continuity hardening and path unification for note/recommend actions

- **Objective:** avoid split/dead-end UX after introducing A2A/A2B.
- **Exact scope:**
  - ensure success/failure feedback returns doctor to a deterministic contextual panel;
  - keep linked recommendation open path useful while adding issue path (no confusion between “open linked” and “issue new”);
  - add stale/manual callback guards for any new action payloads.
- **Non-goals:**
  - no broad doctor panel redesign;
  - no completion lifecycle overhaul;
  - no care-commerce workflow changes.
- **Files likely touched:**
  - `app/interfaces/bots/doctor/router.py`
  - tests and locale keys as needed
- **Tests likely touched/added:**
  - `tests/test_booking_linked_opens_12b1.py`
  - `tests/test_doctor_operational_stack6a.py`
- **Migrations needed?** no
- **Acceptance criteria:**
  - no command-only dead-end for DOC-004/DOC-005 primary flows;
  - new callbacks are stale-safe;
  - back navigation remains deterministic and bounded.

---

## 7. Final recommendation

**Yes — DOC-A2 should be the next implementation target now.** Build **DOC-A2A first** (quick-note contextual entry), then **DOC-A2B** (recommendation issuance contextual entry), and finish with **DOC-A2C** continuity hardening. Do **not** start with broad doctor UX redesign, encounter model expansion, or recommendation engine changes; those are outside the bounded closure needed for DOC-A2.
