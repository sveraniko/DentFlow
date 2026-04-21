# PAT-007 audit — Post-visit recommendation / aftercare flow (2026-04-22)

## 1. Executive verdict

**Verdict: Partial.**

PAT-007 is **partially implemented** in current runtime. The patient can access recommendations through `/recommendations`, open detail with `/recommendation_open <id>`, perform status actions (`ack|accept|decline`), and optionally open recommendation-linked care products via `/recommendation_products <id>`. This is real patient-facing behavior, not only staff/internal tooling. However, the flow is still command-centric and identifier-heavy (ID-based open/actions), has no proactive patient push delivery path evidenced in patient bot code, no canonical “latest aftercare card” surface, and no patient-facing document/export delivery path. The richer “aftercare package” narrative in docs remains target-state, not current state.

**Final recommendation.**

Close PAT-007 with a narrow stack that keeps current recommendation and care-commerce backbones but adds a canonical patient-facing post-visit continuity surface: (a) one human-readable recommendation panel with latest+history semantics, (b) bounded proactive delivery trigger from issuance/completion path, and (c) explicit scenario contract/tests for recommendation-vs-aftercare-vs-care-link boundaries. Do **not** redesign the recommendation engine, care-commerce subsystem, or staff linked-open flows.

---

## 2. Current real flow

### 2.1 Current runtime behavior (evidenced)

1. **Recommendation creation after visit exists on doctor-side paths.**
   - Doctor can issue recommendation manually (`/recommend_issue`).
   - Doctor booking completion action auto-creates and issues a booking-triggered `aftercare` recommendation (localized title/body keys).

2. **Patient identity must resolve first.**
   - Patient recommendation entry resolves patient via recommendation repository mapping from Telegram user.
   - If mapping is missing/ambiguous, patient gets failure message and cannot proceed.

3. **Patient access is pull-based commands/callback entry.**
   - `/recommendations` (also patient home callback) lists up to 8 recommendations with raw status/type and a follow-up command per row (`/recommendation_open <id>`).
   - `/recommendation_open <id>` opens detail, auto-marks issued->viewed, and renders title/type/status/body.
   - `/recommendation_action <ack|accept|decline> <id>` updates lifecycle state.

4. **Optional linked care action exists but is separate and command-driven.**
   - `/recommendation_products <id>` resolves recommendation targets in care-commerce and opens recommendation-context product picker/card flow.
   - If mapping invalid or no products, patient sees bounded fallback text.

5. **Continuity exists, but only as loose command/care continuation.**
   - After opening/action, continuity is mainly “run next command” (action command, products command, `/care`, care order flows).
   - No canonical post-read/ack dedicated “next steps” panel for aftercare continuity is evidenced.

6. **Patient-facing document/export is not in runtime path.**
   - Document generate/open/download routes are staff-side (admin/doctor).
   - No patient router command/callback for generated document delivery is evidenced.

### 2.2 Target-state behavior described in docs (not fully runtime)

- Bot-flow and scenario docs describe post-visit guidance/aftercare continuity and broader recommendation journey as product intent.
- Document strategy includes future aftercare/recommendation PDFs, but this is explicitly future-family planning, not current patient delivery runtime.

---

## 3. Evidence map

| Flow segment | Evidence in code | Evidence in tests | Evidence in docs | Status | Notes |
|---|---|---|---|---|---|
| recommendation creation source | `DoctorOperationsService.issue_recommendation` + `_create_completion_aftercare`; doctor bot `/recommend_issue` handler | `test_doctor_issue_and_booking_trigger` | PAT-007 + DOC-005 scenario notes | Implemented | Creation/issuance exists and includes booking-triggered aftercare. |
| patient entry to recommendations | patient router `/recommendations` + `phome:recommendations` callback | `test_recommendations_command_and_home_callback_share_entry_when_available` | PAT-007 entry point mentions `/recommendations` | Implemented | Patient-facing entry exists through command and home CTA when service enabled. |
| `/recommendations` behavior | `_enter_recommendations_list` renders list and `/recommendation_open <id>` hints | indirect via patient home tests | PAT-007 step 2 | Partial | Works, but list is command/ID centric and capped to first 8 rows. |
| human-readable recommendation rendering | `/recommendation_open` renders localized detail template with title/body/type/status | recommendation lifecycle tests cover state logic, not patient rendering richness | UX docs call for care-like messaging | Partial | Text is readable but still technical status/type and command-based actions. |
| latest vs history semantics | list returns repo order, prints rows[:8], no explicit “latest/current” marker | no explicit patient test for latest/history semantics | PAT-007 continuity expectation | Partial | History exists as list, but no canonical active/latest framing for patient. |
| aftercare instruction semantics | booking completion auto-creates `aftercare` recommendation, detail shows plain body text | lifecycle/doctor tests verify creation and transitions | docs call out post-visit guidance/aftercare continuity | Partial | Aftercare currently equals recommendation text lifecycle, not richer structured instructions. |
| linked care action availability | `/recommendation_products` + recommendation-context product/care order flow | care-commerce tests cover target resolution; patient care UI tests cover card grammar | care-commerce docs define recommendation-first discovery | Implemented | Optional bridge exists; still separate from recommendation continuity UX. |
| patient-facing document/export participation | no patient router document commands; export routes in admin/doctor routers | document registry tests are admin/doctor only | PAT-DOC-001 marked Missing; doc family says “eventually” | Missing | Staff-only delivery baseline; no patient artifact delivery path. |
| canonical continuity after recommendation view | open/action commands exist; care continuation via separate commands/cards | no dedicated PAT-007 continuity test | docs describe broader continuity intent | Partial | Continuity is functional but not canonicalized as one patient aftercare journey. |
| stale callback protection | card callback decode handles stale/invalid for card paths; recommendations flow mostly command-based | home stale callback test (optional action unavailable safe) | general callback safety expectations | Partial | Care card callbacks guarded; recommendation command flows do not use callback tokens. |
| distinction between recommendation and care-commerce action | recommendation lifecycle in `RecommendationService`; care ordering in `CareCommerceService` | separate recommendation and care-commerce test stacks | architecture/care-commerce docs keep bounded contexts separate | Implemented | Boundaries are clear in code; patient UX coupling still lightweight. |

---

## 4. Gaps that block PAT-007 closure

1. **No canonical patient-facing aftercare surface (latest + actionable continuity).**
   - **Severity:** blocker
   - **Evidence:** `/recommendations` outputs command list with IDs; no dedicated latest/active aftercare card/workflow.
   - **Why it matters:** PAT-007 is post-visit patient journey; current path is technically available but not coherent as canonical aftercare flow.
   - **Type:** mixed (UX + runtime)

2. **No proactive recommendation delivery path evidenced.**
   - **Severity:** major
   - **Evidence:** patient-side access is command/pull; no push send to patient from issuance/booking-completion code path.
   - **Why it matters:** recently treated patients may never see aftercare unless they manually pull.
   - **Type:** runtime-only

3. **Patient-facing document delivery absent for aftercare/recommendation artifacts.**
   - **Severity:** major
   - **Evidence:** admin/doctor document open/download routes exist; patient router has none.
   - **Why it matters:** if PAT-007 expects patient-visible artifact continuity, this seam is currently missing.
   - **Type:** runtime-only

4. **Recommendation readability is acceptable but operationally technical.**
   - **Severity:** medium
   - **Evidence:** command syntax and raw statuses/types exposed to patient in detail/list copy.
   - **Why it matters:** undermines “human-readable canonical aftercare” requirement.
   - **Type:** UX-only

---

## 5. Things that are already good enough

- Recommendation lifecycle model (`issued/viewed/acknowledged/accepted/declined`) is solid and transition-guarded.
- Doctor-side issuance and booking-completion auto-aftercare trigger already exist.
- Patient ownership checks on open/action routes prevent cross-patient recommendation access.
- Recommendation -> care-product resolution bridge is present and bounded (including invalid-target fallback).
- Care and recommendation bounded contexts are kept distinct in application services.
- Callback stale handling for card-based care flows is present and should be reused, not reworked.

---

## 6. Minimal implementation stack to close PAT-007

### PAT-A7-1 — Canonical patient recommendation/aftercare surface

- **Objective:** provide one canonical patient-facing aftercare panel with latest+history semantics.
- **Exact scope:** replace command-heavy listing/open wording with panelized output (latest highlighted + history list + bounded actions), while preserving existing lifecycle operations.
- **Non-goals:** no recommendation engine redesign; no staff UI refactor; no care-commerce redesign.
- **Files likely touched:**
  - `app/interfaces/bots/patient/router.py`
  - `locales/en.json`, `locales/ru.json`
  - PAT-007-focused patient router tests (new/updated)
- **Tests likely touched/added:** patient router tests for latest-vs-history rendering, readable action labels, and continuity controls.
- **Migrations needed?:** no
- **Acceptance criteria:** patient can open one canonical recommendations/aftercare surface, understand latest recommendation without IDs, and still access history and lifecycle actions.

### PAT-A7-2 — Proactive post-visit recommendation delivery bridge

- **Objective:** ensure new issued post-visit recommendation can be proactively delivered to patient (not pull-only).
- **Exact scope:** bounded delivery trigger from issuance/completion seam to patient bot message path (with safe fallback to pull command).
- **Non-goals:** no broad messaging scheduler redesign; no owner/admin analytics work.
- **Files likely touched:**
  - doctor operations/recommendation issue integration seam
  - patient communication adapter seam (minimal)
  - targeted tests for trigger and fallback behavior
- **Tests likely touched/added:** focused unit/integration tests asserting proactive send attempt and non-fatal fallback.
- **Migrations needed?:** no
- **Acceptance criteria:** when recommendation is issued for linked Telegram patient, patient receives proactive message with direct canonical open path.

### PAT-A7-3 — PAT-007 continuity contract and stale-safe actions

- **Objective:** lock scenario behavior in tests/docs: recommendation vs aftercare vs care-link semantics and continuity.
- **Exact scope:** add PAT-007 targeted scenario tests and tighten stale/invalid handling for any new callbacks in A7-1/2.
- **Non-goals:** no platform-wide callback refactor; no full PAT-008 scope expansion.
- **Files likely touched:**
  - PAT-007 test module(s) under `tests/`
  - `docs/71_role_scenarios_and_acceptance.md` (status/details only if needed)
- **Tests likely touched/added:** end-to-end-ish patient scenario tests covering open/action/continuity/product-link path and stale safety.
- **Migrations needed?:** no
- **Acceptance criteria:** PAT-007 has deterministic regression coverage and explicit boundary assertions with PAT-008/PAT-DOC seams.

---

## 7. Product decisions requiring explicit human confirmation

1. **Delivery mode:** Should PAT-007 be pull-only (`/recommendations`) or require proactive push on issue/completion?
2. **Canonical surface model:** Should patient see one “latest aftercare” card first, with optional history, or equal-weight list?
3. **Document scope:** Is patient-facing document/export delivery part of PAT-007 closure now, or intentionally deferred to PAT-DOC?
4. **Care link requirement:** Is recommendation->care-product entry mandatory for PAT-007 closure or optional adjunct (PAT-008 adjacency)?
5. **Read/ack semantics:** Is explicit read/acknowledgement state required for PAT-007 acceptance, or informational open is sufficient?

---

## 8. Final closure checklist

- [ ] Patient has a canonical, human-readable post-visit recommendation/aftercare entry surface.
- [ ] Latest active recommendation is clearly distinguishable from history.
- [ ] Patient can open recommendation detail without raw ID-driven UX.
- [ ] Recommendation lifecycle actions (ack/accept/decline) are patient-safe and explicit.
- [ ] At least one proactive delivery path exists (or pull-only is explicitly accepted as product decision).
- [ ] Recommendation-to-care link behavior is clearly defined (required vs optional) and tested.
- [ ] No cross-patient access is possible for recommendation open/action.
- [ ] Stale/invalid interaction handling is bounded and user-safe.
- [ ] PAT-007 acceptance is separated from PAT-008 full commerce flow.
- [ ] PAT-007 acceptance is separated from PAT-DOC patient document delivery unless explicitly included.

---

## Test execution note for this audit

Targeted tests were runnable in this environment and executed for relevant recommendation/patient-entry/staff-linked evidence:

- `tests/test_recommendation_stack10a.py`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `tests/test_booking_linked_opens_12b1.py`

Result: 16 passed.
