# PAT-008 audit — Patient care reserve / pickup flow (2026-04-22)

## 1. Executive verdict

**Verdict: Partial.**

PAT-008 is **not missing**, because runtime patient flow already supports real care-order creation with reservation side-effects (not just catalog browsing), plus patient order list/open/repeat paths. A patient can enter from `/care` and from recommendation-linked product entry, open product cards, pick branch, reserve, and create confirmed care orders with reservation records. However, PAT-008 is **not fully closed** because the patient journey is still fragmented and command-dependent for key continuity (notably order list entry and post-reserve continuity), and pickup lifecycle visibility/notifications are only partially surfaced patient-side (status text exists, but there is no canonical “current reserve/pickup” continuity surface or explicit pickup-update message pipeline).

**Final recommendation.**

Treat PAT-008 as a narrow closure task, not a subsystem redesign: keep current care-commerce/runtime primitives, but add one canonical patient continuity surface (current reserve/order + history), unify reserve completion -> order context handoff, and formalize pickup-state patient visibility semantics (including what updates are shown and when). Keep payment out of scope unless product explicitly confirms otherwise.

---

## 2. Current real flow

### A) How patient enters the flow (current runtime)

1. **Direct command entry**: patient runs `/care` -> patient care catalog categories panel.
2. **Home entry**: patient home callback `phome:care` routes to same care catalog entry helper.
3. **Recommendation-linked entry**:
   - from recommendation detail CTA (`prec:products:<recommendation_id>`), or
   - command `/recommendation_products <recommendation_id>`.
   This stores recommendation context in patient flow state and opens recommendation-scoped product picker.
4. **Care-order entry exists but is command-centric**: `/care_orders` opens patient order list; `/care_order_repeat <id>` exists as fallback command path.

### B) What patient sees first

- `/care` and `phome:care` -> paginated **category list**.
- Recommendation-linked entry -> paginated **recommendation product list** with recommendation context badge/rationale.

### C) Product listing/open behavior

- Category/recommendation list rows are rendered as compact unified-card object rows.
- Opening product goes through runtime card callback (`c2|...`) into compact/expanded product card.
- Product detail exposes actions including reserve, branch change, media cover/gallery, and back navigation.

### D) Reserve action/button and actual semantics

When patient presses reserve on product card:

1. branch is resolved (selected in state or preferred in-stock branch);
2. stock is checked (`free_qty >= 1`);
3. **care order is created** (`status=created`);
4. order is immediately transitioned to `confirmed`;
5. reservation row is created (`status=created`) and branch reserved quantity is incremented.

This is **real reserve/order write-path runtime**, not a fake “interest only” click.

### E) What system does next after reserve

- Patient receives localized success panel text including product, branch, order id, order status (`confirmed`), reservation status, and a “next step” line (“clinic will prepare pickup…”).
- But there is no immediate canonical handoff button like “Open my current reserve/order” in the reserve result panel.

### F) Whether patient can view current reserve/order state and pickup context

**Yes, partially:**

- `/care_orders` lists own orders with item summary, branch, status badge, and pickup hint.
- opening order shows compact/expanded order card with status/timeline-oriented detail.
- order list/card supports “reserve again” (repeat) action and branch reselect when required.

**Gaps:**

- order-list entry is still mostly command-driven (no clearly canonical always-visible reserve panel in home/recommendation continuity).
- patient-facing pickup updates are represented as statuses, but not as explicit update-notification flow in patient bot runtime.

### G) Pickup semantics and state transitions currently present

State machine exists in care-commerce service:

- `created -> confirmed -> ready_for_pickup -> issued -> fulfilled` (plus payment/cancel/expired branches).
- admin actions can move pickup lifecycle and consume/release reservations.
- patient side can read resulting status, but does not appear to own pickup transition actions (which is correct for this scenario boundary).

### H) Canonical continuity after actions

- Continuity exists functionally (patient can go to `/care_orders`, open order card, repeat order).
- But continuity is not yet a single obvious patient “current reserve/pickup” journey from reserve success screen and recommendation bridge.

---

### Current vs target-state distinction

- **Current-state reality:** patient can browse + reserve with real order/reservation creation and later view orders.
- **Target-state (docs intent):** smoother end-to-end reserve/pickup continuity with clear current-order panel and pickup update messaging.
- Therefore PAT-008 remains **Partial**; docs describing richer continuity should be treated as target-state where runtime does not yet provide that cohesively.

---

## 3. Evidence map

| Flow segment | Evidence in code | Evidence in tests | Evidence in docs | Status | Notes |
|---|---|---|---|---|---|
| care entry surface | patient router: `/care` -> `_enter_care_catalog`; `phome:care` callback -> same helper | `test_care_command_and_home_callback_share_entry_when_available` | PAT-008 entry says `/care` | Implemented | Command + home callback parity exists. |
| recommendation→care entry continuity | patient router: `/recommendation_products`; `prec:products:*` callback; recommendation-context state and picker rendering | patient home/recommendation callback tests include `prec:products` continuity/fallback | PAT-007/PAT-008 continuity in role scenarios | Implemented | Real bridge exists and is patient-facing. |
| care product listing | `_render_care_categories_panel`, `_render_care_product_list` | CC4C/CC4F UI grammar tests | PAT-008 step 1 | Implemented | Paginated categories/products rendered via card grammar. |
| care product detail | `_render_product_card` with compact/expanded modes, branch/media/reserve/back actions | CC4F asserts reserve/back actions on expanded detail | PAT-008 step 2 | Implemented | Product detail is not command-only. |
| reserve action semantics | `_reserve_product` checks stock, creates order, confirms order, creates reservation, sends result | care-commerce stack tests validate reservation stock behavior and order action path | PAT-008 step 4 | Implemented | Reserve is transactional domain behavior, not browse-only. |
| reserve/order creation truth | care-commerce `create_order`, `transition_order`, `create_reservation` | care-commerce stack tests cover order lifecycle and reserve stock mutations | PAT-008 state transitions | Implemented | Runtime meaning of “reserve” = persisted order + reservation. |
| patient order/reserve state visibility | `/care_orders` -> `_render_care_orders_panel`, open order card, repeat action | CC4F order row/detail text tests | PAT-008 step 5 | Partial | Works, but entry/continuity is still command-first and fragmented. |
| pickup semantics | care-order statuses include ready_for_pickup/issued/fulfilled; admin action path transitions order and reservation | care-commerce stack tests include ready/issue/fulfill semantics | PAT-008 step 6; admin workdesk docs | Partial | Lifecycle exists, but patient pickup update UX is limited to status reads. |
| canonical continuity after reserve action | reserve success message includes order id/next step only; no canonical “open current order” CTA | no dedicated test asserting immediate post-reserve canonical handoff | docs expect coherent reserve/pickup flow | Partial | Functional but not fully canonicalized for patient. |
| stale callback protection | runtime card callbacks decode via codec; malformed -> stale alert; recommendation callbacks validate payload parts | recommendation callback malformed/replay tests | general card safety expectations | Implemented | Safety/hardening present for callback-driven surfaces. |
| human-readable patient-facing copy | localized strings for reserve result, next step, order list/detail/repeat | CC4C/CC4F localization assertions | i18n/product docs | Implemented | Messaging is human-readable and localized, though still operationally terse. |

---

## 4. Gaps that block PAT-008 closure

1. **No canonical post-reserve continuity handoff to current order panel**  
   - **Severity:** blocker  
   - **Evidence:** reserve success panel sends text only; no guaranteed immediate open/current-order CTA path.  
   - **Why it matters:** PAT-008 closure needs coherent patient journey from reserve action to reserve state tracking, not just isolated success text.  
   - **Type:** mixed (UX + runtime wiring).

2. **Patient reserve/order visibility exists but remains command-fragmented**  
   - **Severity:** major  
   - **Evidence:** `/care_orders` and `/care_order_repeat` are command routes; no explicit canonical “current reserve/pickup” surface in patient home continuity.  
   - **Why it matters:** patients can miss order-state follow-through; scenario appears open but operationally brittle.  
   - **Type:** UX-only (with small routing glue).

3. **Pickup-update semantics are not explicitly patient-delivered as updates**  
   - **Severity:** major  
   - **Evidence:** patient sees status when opening order, but runtime evidence centers pickup transitions/admin handling; patient-facing pickup update messaging path is not explicit in patient router.  
   - **Why it matters:** PAT-008 includes reserve/pickup continuity; visibility should be proactive or clearly centralized.  
   - **Type:** mixed.

---

## 5. Things that are already good enough

- **Reserve semantics are real and should not be reworked**: order creation + transition to confirmed + reservation creation is already coherent.
- **Recommendation-to-care bridge is real and useful**: keep `prec:products` / `/recommendation_products` continuity.
- **Card callback safety baseline is strong**: malformed/stale callback handling is already present in recommendation/card flows.
- **Care order repeat baseline is useful**: repeat-as-new with branch reselect and stock revalidation already provides meaningful continuity.
- **Localization baseline for care reserve/order copy exists** and should be iterated, not replaced.

---

## 6. Minimal implementation stack to close PAT-008

### PAT-A8-1 — Canonical patient reserve/order continuity surface

- **Objective:** provide one clear patient-facing “current reserve/order + history” entry and post-reserve handoff.
- **Exact scope:**
  - add canonical care-order entry action from patient home/care panels;
  - reserve-success panel includes direct open-current-order and open-order-list actions;
  - keep existing commands as fallback.
- **Non-goals:** no care-commerce state-machine redesign; no admin queue changes.
- **Files likely touched:**
  - `app/interfaces/bots/patient/router.py`
  - `locales/en.json`, `locales/ru.json`
  - small report/docs update if needed.
- **Tests likely touched/added:**
  - patient home/care continuity tests (`tests/test_patient_home_surface_pat_a1_2.py`)
  - patient care UI flow tests (new focused PAT-A8 continuity test file or existing care UI test files).
- **Migrations needed?** no.
- **Acceptance criteria:**
  - after reserve, patient can open current order in one tap;
  - patient has one obvious entry to current reserve/order list without remembering command syntax.

### PAT-A8-2 — Pickup state visibility contract for patient

- **Objective:** make pickup-state visibility explicit and patient-readable in canonical order surface.
- **Exact scope:**
  - normalize patient order card/panel copy for statuses (`confirmed`, `ready_for_pickup`, `issued`, `fulfilled`, etc.);
  - ensure pickup branch + next-step text are consistently shown in list/detail.
- **Non-goals:** no payment implementation, no staff workflow redesign.
- **Files likely touched:**
  - `app/interfaces/bots/patient/router.py`
  - care-order card rendering helpers if needed
  - `locales/en.json`, `locales/ru.json`.
- **Tests likely touched/added:**
  - patient care UI card/detail assertions (`tests/test_patient_care_ui_cc4f.py`, possibly `cc4c`).
- **Migrations needed?** no.
- **Acceptance criteria:**
  - patient can clearly read pickup context and current status from canonical panel/card;
  - status copy is non-technical and consistent across entry paths.

### PAT-A8-3 — Scenario lock tests for reserve→order continuity and recommendation-linked reserve

- **Objective:** lock PAT-008 regression boundaries with focused tests.
- **Exact scope:**
  - add tests for reserve success -> order continuity action(s);
  - add tests for recommendation-linked reserve preserving recommendation context and creating real order/reservation;
  - add stale/malformed callback safety assertions for care reserve callbacks where missing.
- **Non-goals:** no broad booking or admin regression expansion.
- **Files likely touched:**
  - `tests/test_patient_home_surface_pat_a1_2.py`
  - `tests/test_patient_care_ui_cc4c.py`
  - `tests/test_patient_care_ui_cc4f.py`
  - possibly a new narrow PAT-A8 test file.
- **Migrations needed?** no.
- **Acceptance criteria:**
  - deterministic tests prove coherent patient reserve journey (entry -> reserve -> state visibility);
  - recommendation-linked reserve continuity is covered;
  - stale callback behavior remains bounded.

---

## 7. Product decisions requiring explicit human confirmation

1. **Reserve meaning:** confirm PAT-008 reserve is true reserve-for-pickup (real order+reservation), not “interest/request.”
2. **Recommendation-linked reserve policy:** allow direct reserve from recommendation-linked products vs forcing user through generic `/care` surface.
3. **Canonical patient order surface:** confirm requirement for one “current reserve/order + history” panel as mandatory closure criterion.
4. **Pickup update requirement:** decide whether passive status visibility is enough, or patient must receive explicit pickup-ready/update notifications now.
5. **Payment boundary:** confirm payment remains excluded from PAT-008 closure (reserve/pickup only).
6. **Clinic/branch scoping:** confirm reserve should remain branch-scoped as selected in product flow and recommendation context should not force a different clinic scope.

---

## 8. Final closure checklist

- [ ] Patient can enter PAT-008 from `/care`, home care CTA, and recommendation-linked products.
- [ ] Product browse/detail supports branch choice and reserve action in one coherent surface.
- [ ] Reserve action creates real care order + reservation (not soft request only).
- [ ] Patient has immediate post-reserve path to current order/reserve state.
- [ ] Patient can view current reserve/order status and pickup context without command memorization.
- [ ] Pickup lifecycle status semantics are understandable patient-side.
- [ ] Recommendation-linked reserve continuity is preserved end-to-end.
- [ ] Callback stale/malformed handling remains safe on care reserve paths.
- [ ] PAT-008 acceptance is validated with focused regression tests.

---

## Notes on audit method

- Scope intentionally stayed bounded to PAT-008 and adjacent seams only.
- Runtime truth was prioritized over narrative docs wherever mismatches were found.
- Targeted relevant tests were executable in this environment and passed.
