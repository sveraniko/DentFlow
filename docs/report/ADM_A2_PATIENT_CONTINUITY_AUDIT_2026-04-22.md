# ADM-A2 audit — Admin patient search/open to active-booking continuity

Date: 2026-04-22  
Scope: bounded operational audit (analysis only, no runtime code changes)

## 1) Executive verdict

**Verdict: Partial**

Admin can search and open patients through `/admin_patients` with callback-safe patient-card open, and booking cards/actions are strong once a booking card is already open. However, the patient-card leg is still mostly summary/back from the admin patient queue and does not provide a first-class patient→active-booking handoff. In current runtime, continuity from patient context into booking action is primarily available in the reverse direction (booking→patient), or by falling back to command/queue entry points.

**Final recommendation**

Treat ADM-A2 as the next bounded implementation target now that ADM-A1 is closed. Keep it narrow: add explicit active-booking discovery/open from admin patient card, preserve deterministic back/stale behavior across patient→booking transitions, and add targeted regression tests. Do not broaden into CRM redesign, chart expansion, or unrelated admin architecture work.

## 2) Current real flow

### Current behavior (runtime truth)

1. **Admin patient search entry**
   - `/search_patient` exists, guarded to admin role, and returns text-only search results via `run_patient_search(...)`.
   - This route does **not** provide inline open actions; it is a textual lookup output.

2. **Admin patient list/open path**
   - `/admin_patients <query>` renders patient rows and callback buttons.
   - Each row callback is encoded as patient card `OPEN` with `SourceContext.ADMIN_PATIENTS` and a queue state token.

3. **Patient card actual next actions in admin runtime**
   - When admin opens from `/admin_patients`, runtime renders a patient panel text and currently attaches only a **Back** button in callback handling.
   - `CardAction.BOOKINGS` exists in card model/adapter contracts, but admin runtime callback branch for patient profile does not implement patient-card booking open/action continuation.

4. **Active booking visibility from patient context**
   - Patient snapshot includes `upcoming_booking_label` string when found from today schedule projection, but no booking ID is carried in patient runtime snapshot/seed.
   - Therefore, patient panel can show a booking snippet, but has no direct callback path to open that booking.

5. **Booking actions reachability**
   - Booking card actions are operationally meaningful and wired (confirm/check-in/reschedule/cancel/open linked entities), with source-context aware back behavior for today/confirmations/reschedules/issues.
   - But from admin patient-card context, there is no first-class patient→booking open path; continuity usually requires detouring to other queues or commands (`/booking_open`).

6. **Back/stale safety across current chain**
   - `/admin_patients` queue token is validated in runtime callbacks; stale callbacks fail safely.
   - Back from patient card returns to patient queue.
   - There is no equivalent back chain from patient-origin booking path because that path is not implemented.

### Target-state behavior implied by docs

Docs and prior audit narrative expect admin search continuity to support: patient lookup → patient card → active booking open → booking actions, without command fallback. Current runtime does not close this chain yet; it remains partial and queue/command-biased at the patient-card transition point.

## 3) Evidence map

| Flow segment | Evidence in code | Evidence in tests | Evidence in docs | Status | Notes |
|---|---|---|---|---|---|
| patient search entry | `search_patient` command handler in admin router; text output via `run_patient_search(...)` | `tests/test_search_ui_stack5a1a.py` guards `/search_patient` role path | ADM-002 scenario and admin audit mention `/search_patient` | Implemented | Works as lookup, not operational continuation surface. |
| patient results/list | `/admin_patients` + `_render_admin_patients` builds list and row callbacks | `test_admin_patients_search_and_open_card` | ADM-002 narrative says search/open patient | Implemented | List with open callbacks and state token exists. |
| patient card open | `admin_runtime_card_callback` patient-profile branch renders panel | `test_admin_patients_search_and_open_card` confirms card opens | Docs report patient card exists | Implemented | Open is real and callback-safe. |
| active booking visibility from patient context | `_build_patient_snapshot` sets `upcoming_booking_label` from workdesk schedule row | No focused test asserts booking snippet-driven operational action | UI/product docs expect patient card to expose current booking context | Partial | Visibility is text snippet only; no operational binding. |
| patient -> booking transition | No patient callback branch handling `CardAction.BOOKINGS`; patient panel markup in admin callback is back-only | No admin test covering patient-card `BOOKINGS` action | Prior audit ADM-A2 target explicitly calls this out | Missing | Core ADM-A2 gap. |
| booking actions from patient-origin path | Booking actions exist in `_admin_booking_keyboard` and booking callback branches | AW2/AW3 tests cover booking card open/back/actions from queues | ADM-003/004 marked implemented | Partial | Implemented generally, but not reachable naturally from patient-card origin. |
| back navigation / continuity | Back from patient card to `/admin_patients` queue implemented; booking back for several source contexts implemented | AW2/AW3 tests cover queue↔booking back paths; AW4 covers patient-card open only | ADM-A1C continuity hardening for other queues documented | Partial | Good for existing contexts, absent for patient-origin booking context. |
| stale callback safety | Source-context state token checks include `ADMIN_PATIENTS` | AW2/AW3/AW4 include stale callback assertions (mostly other queues + patient open path) | Governance/testing docs emphasize bounded safety | Implemented | Strong callback stale handling where paths exist. |
| human-readable admin continuity | Patient card rendering is readable summary; booking panels are operational | Tests assert key text appears but not full continuity chain | UI rules call for patient card first actions incl. open active booking | Partial | Human-readable exists; action continuity does not fully match intended operational path. |

## 4) Gaps that block ADM-A2 closure

1. **No first-class patient-card → active booking action path**
   - **Severity:** blocker
   - **Evidence:** admin patient callback branch renders panel with back-only keyboard; no handler for patient `BOOKINGS` action.
   - **Why operationally:** admin cannot continue naturally from patient context into booking actions; must detour to queue/command.
   - **Type:** mixed (runtime + UX)

2. **Patient snapshot lacks active-booking identity binding (only label snippet)**
   - **Severity:** major
   - **Evidence:** `PatientRuntimeSnapshot`/seed carry `upcoming_booking_label` text but not booking ID.
   - **Why operationally:** without booking identity, the UI cannot provide deterministic “open active booking” from patient card.
   - **Type:** runtime-only

3. **`/search_patient` is text-only and disconnected from card continuity**
   - **Severity:** medium
   - **Evidence:** command uses `run_patient_search(...)` returning formatted text, no callbacks.
   - **Why operationally:** one of the documented entry points does not bridge into patient card/booking continuity.
   - **Type:** mixed (UX + runtime)

4. **No dedicated regression test for full patient-search → patient-card → booking-action chain**
   - **Severity:** medium
   - **Evidence:** current tests cover patient card open and queue/booking flows separately, not end-to-end patient-origin booking continuity.
   - **Why operationally:** continuity regressions can slip while individual surfaces still pass.
   - **Type:** runtime-only (test coverage)

## 5) Things already good enough

- Admin patient queue search/list/open mechanics in `/admin_patients` with callback encoding and source context.
- Booking card action stack for admin (confirm/check-in/reschedule/cancel + linked opens) once booking is opened.
- Queue-scoped stale callback protections and deterministic back behavior for existing booking source contexts.
- Existing AW2/AW3/AW4 test coverage for today/queue integrity and callback safety should be preserved rather than reworked.

## 6) Minimal implementation stack to close ADM-A2

### ADM-A2A — Patient card active-booking bridge

- **Objective:** make patient card operationally continue into active booking.
- **Exact scope:**
  - add deterministic active-booking resolution for patient context (prefer live statuses and nearest upcoming);
  - wire patient-card `BOOKINGS` callback action in admin runtime;
  - open booking panel with preserved source context for patient-origin continuity.
- **Non-goals:**
  - no booking state-machine changes;
  - no CRM/history redesign;
  - no chart/recommendation workflow expansion.
- **Files likely touched:**
  - `app/interfaces/bots/admin/router.py`
  - `app/interfaces/cards/adapters.py` (only if seed/action exposure tweaks are strictly required)
  - optionally lightweight helper in `app/application/booking/telegram_flow.py` (read-side only)
- **Tests likely touched/added:**
  - `tests/test_admin_aw4_surfaces.py` or new focused ADM-A2 continuity test module
- **Migrations needed?** no
- **Acceptance criteria:**
  - from `/admin_patients` open patient card, admin can open active booking in <=1 tap;
  - if no active booking exists, bounded explicit message is shown;
  - callback remains stale-safe.

### ADM-A2B — Patient-origin booking back-chain integrity

- **Objective:** preserve intuitive back navigation when booking is opened from patient context.
- **Exact scope:**
  - define patient-origin source_ref/page token conventions;
  - ensure booking card back returns to the same patient panel (or patient queue per explicit design), not generic booking list.
- **Non-goals:**
  - no redesign of other queue contexts;
  - no global navigation framework rewrite.
- **Files likely touched:**
  - `app/interfaces/bots/admin/router.py`
  - possibly `app/interfaces/cards/navigation.py` only if absolutely needed
- **Tests likely touched/added:**
  - targeted callback round-trip tests in admin suite for patient-origin back
- **Migrations needed?** no
- **Acceptance criteria:**
  - patient-origin booking open/back is deterministic and context-preserving;
  - stale tokens reject handcrafted/outdated callbacks safely.

### ADM-A2C — Command/list entry harmonization and regression net

- **Objective:** reduce command fallback bias and lock continuity by tests.
- **Exact scope:**
  - choose one bounded harmonization: either `/search_patient` offers openable result callbacks, or it explicitly routes users toward `/admin_patients` continuity path;
  - add end-to-end regression covering patient-search/list → patient-card → booking open → booking action.
- **Non-goals:**
  - no multi-surface redesign;
  - no localization sweep unrelated to added copy.
- **Files likely touched:**
  - `app/interfaces/bots/admin/router.py`
  - `app/interfaces/bots/search_handlers.py` (only if callback-capable output strategy is adopted)
  - tests under `tests/test_admin_*` (focused)
- **Tests likely touched/added:**
  - new ADM-A2 continuity test(s) + small updates to existing admin patient/search tests
- **Migrations needed?** no
- **Acceptance criteria:**
  - documented ADM-A2 path is reproducible in tests;
  - no command-only detour required for common patient→booking continuation.

## 7) Final recommendation

Yes—ADM-A2 should be the next implementation target now. Build **ADM-A2A** first (patient-card active-booking bridge), then **ADM-A2B** (back/stale integrity for patient-origin booking navigation), and only then **ADM-A2C** (entry harmonization + regression net). Do **not** start with broader CRM/history expansion, recommendation/care redesign, or calendar/owner features.
