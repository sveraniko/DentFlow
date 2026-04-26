# DentFlow — Docs vs Code Audit

> Comparison of documented functionality, interfaces, and user flows against actual codebase state.
> Created: 2026-04-26

---

## 1. Executive Summary

The DentFlow documentation is **extensive and architecturally mature** (70+ pages across 16-series card docs, booking docs, and role flow docs). The codebase has a **solid foundation** with booking, care-commerce, recommendations, reminders, admin workdesk, doctor operations, and owner analytics all present.

However, the audit reveals a critical pattern: **several major subsystems exist as documented, designed, and partially coded — but are disconnected or only superficially wired into the actual Telegram surfaces.**

The most significant finding: the **Unified Card System** (`interfaces/cards/`) is fully built as an infrastructure layer (8 files, ~1100 lines, with Redis-backed runtime state, callback codec, stale protection, panel family management, 6 card profiles) — and it **IS imported and used** by patient, admin, and doctor routers. But the **actual rendering path** (`CardShellRenderer.to_panel()`) produces a **flat text-only Panel** with no InlineKeyboardMarkup, no real Telegram formatting, and no media handling. The sophisticated card contract documented in 3000+ lines of specs is **structurally present but visually inert**.

---

## 2. Card System (docs/16_* series) — Status: STRUCTURALLY BUILT, RENDERING GAP

### What docs define (6 documents, ~4000 lines):
- Unified card shell with 6 profiles (product, patient, doctor, booking, recommendation, care_order)
- Compact/expanded modes with explicit transition rules
- Source-context-aware navigation (Back returns to source panel, not generic home)
- Redis-backed callback token registry with TTL and stale protection
- One-active-panel discipline per panel family
- Role-safe action filtering
- Media on-demand (cover, gallery)
- Callback namespace: `card:<profile>:<action>:<entity_id>:<context...>`

### What code has:
- `app/interfaces/cards/models.py` — All enums and dataclasses: `CardProfile`, `EntityType`, `CardMode`, `SourceContext`, `CardAction`, `CardShell`, `SourceRef` — **fully built, matches docs**
- `app/interfaces/cards/adapters.py` (749 lines) — Seeds + RuntimeSnapshots + ViewBuilders for all 6 profiles — **fully built**
- `app/interfaces/cards/callbacks.py` — `CardCallbackCodec` with Redis token encode/decode, legacy fallback, stale validation — **fully built**
- `app/interfaces/cards/runtime_state.py` — `CardRuntimeCoordinator`, `CardRuntimeStateStore`, `PanelFamily` enum, TTL config, `InMemoryRedis` fallback — **fully built**
- `app/interfaces/cards/panel_runtime.py` — `ActivePanelRegistry`, `render_or_replace` logic — **fully built**
- `app/interfaces/cards/navigation.py` — `resolve_back_target`, `transition_mode` — **fully built**
- `app/interfaces/cards/rendering.py` (24 lines) — **THE GAP**: `CardShellRenderer.to_panel()` produces a flat text `Panel` object. No `InlineKeyboardMarkup`, no Telegram `parse_mode`, no badge emoji, no compact/expanded visual difference, no action buttons rendered as inline keyboard.

### Imports from routers:
- **Patient router**: imports `BookingCardAdapter`, `BookingRuntimeViewBuilder`, `CareOrderCardAdapter`, `ProductCardAdapter`, `CardCallbackCodec`, `CardRuntimeCoordinator`, etc. — **actively uses card system**
- **Admin router**: imports `BookingCardAdapter`, `CareOrderCardAdapter`, `PatientCardAdapter`, `CardCallbackCodec` — **actively uses card system**
- **Doctor router**: imports `BookingCardAdapter`, `CareOrderCardAdapter`, `CardCallbackCodec` — **actively uses card system**
- **Owner router**: **does NOT import card system at all** — renders everything via raw text/commands

### Verdict:
The card system infrastructure is real and wired. The gap is in the **rendering layer** — the bridge from `CardShell` → actual Telegram message with inline keyboard, formatted text, and media. This is the single most impactful thing to fix.

---

## 3. Patient Bot (docs/70, 71 PAT-001 to PAT-008)

### Documented scenarios vs code:

| Scenario | Doc Status | Code Reality | Gap |
|---|---|---|---|
| PAT-001 New patient booking | Implemented | **Functional** — service→doctor→slot→contact→review→confirm works end-to-end (after recent hotfixes) | `/start` is still text-command, not a polished first-run CTA panel |
| PAT-002 Returning patient quick booking | Implemented | **Partial** — `_try_render_quick_book_suggestions` exists but heuristic-based | No preference model, no "rebook same doctor" shortcut |
| PAT-003 Confirmation flow | Implemented | `my_booking_entry`, reminder callbacks exist | Booking card uses card system but rendering is basic |
| PAT-004 Reschedule | Implemented | `request_reschedule` handler exists | Works but rescue path is admin-side only |
| PAT-005 Cancel | Implemented | `cancel_prompt`, `cancel_confirm` exist | Functional |
| PAT-006 Reminder ack | Implemented | `reminder_action_callback` exists | `ack` vs `confirm` distinction coded |
| PAT-007 Recommendations | Implemented | `recommendations_list`, `recommendations_open`, `recommendations_action` exist | Functional |
| PAT-008 Care reserve/pickup | Implemented | `care_catalog`, `care_product_open`, `care_order_create` exist | Functional |
| PAT-DOC-001 Patient document delivery | Missing | **No code** | Not started |

### Patient Home Panel:
- **Docs say**: role home with CTA panel, language picker, navigation
- **Code reality**: `/start` sends a text message with inline buttons for booking, my_booking, recommendations, care, language. **No card system used for home.** Home panel is ad-hoc inline keyboard, not a card shell.
- Post-booking success shows "Моя запись" + "← Главная" buttons (recently fixed) — but these are one-off constructions, not card system panels.

---

## 4. Admin Bot (docs/68, 70, 71, 72 — ADM-001 to ADM-DOC-002)

### Documented scenarios vs code:

| Scenario | Doc Status | Code Reality | Gap |
|---|---|---|---|
| ADM-001 Today workdesk | Implemented | `admin_today` handler, AW2/AW4 callbacks — **functional** | Queue source context/back still rough |
| ADM-002 Search patient | Implemented | `admin_patients`, `search_patient` — **functional** | Operational, not governance console |
| ADM-003 Open booking | Implemented | `booking_open`, callbacks — **functional** | Uses card adapters |
| ADM-004 Confirm/check-in | Implemented | Booking action callbacks — **functional** | |
| ADM-005 Reschedule handling | Implemented | `admin_reschedules` — **functional** | Complex rescue is manual |
| ADM-006 Reminder issues | Partial | `admin_confirmations`, `admin_issues` — **queues exist** | Not every rescue path polished |
| ADM-007 Linked recommendation | Implemented | Bounded recommendation panel from booking | |
| ADM-008 Care pickup | Implemented | `admin_care_pickups` — **functional** | |
| ADM-009 Calendar mirror | Implemented | `/admin_calendar` — bounded read surface | |
| ADM-DOC-001 Generate doc | Implemented | `admin_doc_generate` — **functional** | |
| ADM-DOC-002 Open/download doc | Implemented | `admin_doc_open`, `admin_doc_download` — **functional** | |

### Admin Card System Usage:
Admin router imports `PatientCardAdapter`, `BookingCardAdapter`, `CareOrderCardAdapter`. These adapters build seeds and snapshots. But the admin router is 3262 lines in ONE closure function — making it very hard to trace whether card shells are actually rendered through the card renderer or through ad-hoc text construction.

---

## 5. Doctor Bot (docs/70, 71, 72 — DOC-001 to DOC-DOC-001)

| Scenario | Doc Status | Code Reality | Gap |
|---|---|---|---|
| DOC-001 Queue | Implemented | `today_queue`, `next_patient` — **functional** | |
| DOC-002 Open booking | Implemented | `booking_open` — **functional** | Uses card adapters |
| DOC-003 Mark in service | Implemented | `booking_action` — **functional** | |
| DOC-004 Quick note | Partial | `patient_open`, `chart_open`, `encounter_note` — **exist** | Still narrower than docs envision |
| DOC-005 Issue recommendation | Implemented | `recommend_issue` — **functional** | |
| DOC-006 Linked care order | Implemented | Care order branch after convergence | |
| DOC-007 Complete encounter | Implemented | `booking_action` — **functional** | |
| DOC-DOC-001 Doc registry | Implemented | `/doc_generate`, `/doc_open`, `/doc_download` — **functional** | |

---

## 6. Owner Bot (docs/50, 70, 71, 73 — OWN-001 to OWN-004)

| Scenario | Doc Status | Code Reality | Gap |
|---|---|---|---|
| OWN-001 Daily digest | Implemented | `owner_digest` — **functional** | Compact, not BI |
| OWN-002 Live snapshot | Implemented | `owner_today` — **functional** | |
| OWN-003 Anomaly view | Implemented | `owner_alerts`, `owner_alert_open` — **functional** | Many planned drilldowns missing |
| OWN-004 Care performance | Implemented (bounded) | `owner_care` — **functional** | Read-only counts, no revenue analytics |

### Owner Card System Usage:
**Owner router does NOT use the card system at all.** It's 539 lines of raw text message sends via `/commands`. No card adapters, no callbacks, no inline keyboards beyond basic buttons. This is the most visually primitive of all 4 bots.

---

## 7. Governance (docs/73 — GOV-001 to GOV-010)

| Scenario | Status | Code |
|---|---|---|
| GOV-001 Clinic references read | Implemented | `/clinic`, `/branches`, `/doctors`, `/services` |
| GOV-002 Patient registry | Partial | Admin search/patient card works, owner `/owner_patients` is read-only |
| GOV-003 Staff roster read | Partial | `/doctors` + `/owner_staff` — read-only |
| GOV-004 Staff lifecycle mutation | **Missing** | No add/deactivate/offboard workflow |
| GOV-005 Role binding policy | Partial | Role codes exist, composite policy not frozen |
| GOV-006 Care catalog sync | Implemented | `/admin_catalog_sync` + sync services |
| GOV-007 Calendar mirror | Implemented | Bounded mirror |
| GOV-008 Doc governance | Implemented | Export baseline |
| GOV-009 Patient doc delivery | **Missing** | No patient-facing artifact delivery |
| GOV-010 Owner governance console | Partial | Read-only snapshots only |

---

## 8. "Floating" Functionality — Built But Not Connected

These are subsystems that exist in code but are disconnected, underutilized, or not surfaced to the user:

### 8.1 Card Rendering Layer
**File**: `app/interfaces/cards/rendering.py` (24 lines)
**Problem**: `CardShellRenderer.to_panel()` converts a rich `CardShell` (with badges, meta lines, actions, navigation) into a **flat text string**. Actions are rendered as text labels, not as `InlineKeyboardButton`. No `parse_mode=HTML`. No visual hierarchy.
**Impact**: The entire card infrastructure (models, adapters, callbacks, runtime state, navigation) exists but produces visually impoverished output.

### 8.2 Card Navigation System
**File**: `app/interfaces/cards/navigation.py` (23 lines)
**Problem**: `resolve_back_target()` correctly determines Back target, but the rendering layer doesn't produce actual Back buttons. Navigation remains implicit in handler logic, not driven by the card system.

### 8.3 Owner Bot — No Card System Integration
**File**: `app/interfaces/bots/owner/router.py` (539 lines)
**Problem**: Completely bypasses the card system. No inline keyboards. No drill-down actions. No callbacks. Raw text output only.

### 8.4 Patient Home — Ad-hoc, Not Card-Based
**Problem**: Patient home panel (`/start`, `phome:home`) is built with hand-coded `InlineKeyboardMarkup`, not through the card system. Each panel is a one-off construction.

### 8.5 Waitlist Flow
**Documented in**: booking_docs/10 (section 11), booking_test_scenarios (BKG-013)
**Code**: No evidence of a patient-facing waitlist join flow or admin waitlist management queue. `admin_waitlist_panel` is documented in 72 but no handler found.

### 8.6 Voice Search
**Documented in**: docs/15 (section 7.3 — "voice input is first-class")
**Code**: `SpeechToTextService` and `VoiceSearchModeStore` exist. Admin/doctor routers import them. But voice search is only wired to search handlers, not to booking or other flows.

### 8.7 Stale Panel Invalidation
**Documented in**: docs/16-5 (section 15 — explicit invalidation required)
**Code**: `invalidate_panel()`, `supersede_active_panel()` exist in `CardRuntimeStateStore`. But actual routers don't call invalidation when workflow transitions happen (e.g., booking completion should invalidate the booking detail panel).

---

## 9. UI/UX Assessment — What Needs Fixing

### 9.1 CRITICAL: Card Renderer Must Produce Real Telegram UI

The #1 issue. `CardShellRenderer.to_panel()` must:
- Generate HTML-formatted text with `<b>`, `<i>` tags
- Produce `InlineKeyboardMarkup` from `CardShell.actions`
- Add Back/Home navigation buttons from `CardShell.navigation`
- Support compact/expanded visual differentiation
- Handle badge chips as emoji or Unicode markers

**Proposal**: Rewrite `rendering.py` to produce `(text: str, keyboard: InlineKeyboardMarkup)` tuples with proper Telegram formatting. This alone will activate the entire card system visually.

### 9.2 HIGH: Patient Home Must Be a Proper Card Panel

Current `/start` is a text message with inline buttons. It should be:
- A home card with role-appropriate sections
- Language picker integrated
- Quick actions: Book, My Bookings, Recommendations, Care Orders
- Notification settings (future)
- Profile/contact management (future)

**Proposal**: Create a `patient_home` card profile or a dedicated home panel builder that uses the card rendering system.

### 9.3 HIGH: Owner Bot Needs Card System Integration

Owner bot is the most visually primitive surface. It should:
- Use inline keyboards for drill-down (digest → today → alerts → detail)
- Support callback-based navigation instead of command-only
- Use the card system for alert cards and metric cards

**Proposal**: Wire owner router to use `CardCallbackCodec` and add `owner_digest_panel`, `owner_alert_card` profiles.

### 9.4 MEDIUM: Booking Card Visual Polish

Booking card adapters and seeds exist. The card is wired. But visual output is basic.

**Proposal**:
- Booking compact card: `📅 28.04 10:00 | 👤 Иванов И. | 🦷 Гигиена | ✅ Подтверждён`
- Actions as inline buttons: `[Подробнее] [Перенести] [Отменить]`
- Expanded: add reminder status, linked objects, patient contact hint

### 9.5 MEDIUM: Navigation Consistency

Back behavior is documented extensively but implemented inconsistently:
- Some handlers use `phome:home` (patient home)
- Some use ad-hoc callback patterns
- Card system's `resolve_back_target()` is not called from handlers

**Proposal**: Standardize all card-based panels to use the card navigation system. Every rendered panel should include a Back button generated from `SourceRef`.

### 9.6 MEDIUM: One-Active-Panel Discipline

Documented as non-negotiable. Code has `ActivePanelRegistry` and `render_or_replace()`.
But handlers often send new messages instead of editing existing ones.

**Proposal**: Audit all `send_message` calls in routers. Replace with `_send_or_edit_panel` pattern that uses `ActivePanelRegistry`.

### 9.7 LOW: Waitlist Surface

Documented but absent. Not blocking for pilot, but important for operational completeness.

### 9.8 LOW: Patient-Facing Document Delivery

Marked as Missing in docs. Not blocking for pilot.

---

## 10. Architecture Quality Assessment

### What's Good:
1. **Domain model is clean** — separate bounded contexts for booking, patient, communication, care-commerce, clinical, export
2. **Service layer is real** — `BookingOrchestrationService`, `AdminWorkdeskReadService`, `DoctorOperationsService`, `OwnerAnalyticsService` are proper application services
3. **Card system infrastructure is professional** — Redis-backed runtime state, token-based callbacks, stale protection, TTL management
4. **i18n is consistent** — `I18nService` used everywhere, locale resolution per user
5. **Access control is role-based** — `AccessResolver`, `guard_roles`, `RoleCode` enum

### What's Problematic:
1. **Giant closure pattern** — patient router (4460 lines), admin (3262), doctor (2217) all in single `make_router()` functions
2. **Card rendering gap** — the most important visual layer is a 24-line stub
3. **Owner bot is disconnected** from the card system entirely
4. **Navigation is implicit** — handlers implement Back manually instead of using the card navigation system
5. **Panel lifecycle is partially implemented** — `ActivePanelRegistry` exists but is not consistently used

---

## 11. Recommended Implementation Priority

### Phase 1: Activate Card Rendering (1-2 days)
1. Rewrite `CardShellRenderer` to produce `(text, InlineKeyboardMarkup)` with HTML formatting
2. Add a `_render_card_panel()` helper to each router that sends/edits messages using card renderer output
3. Test with booking card in patient bot

### Phase 2: Patient Home Redesign (1 day)
1. Build a proper patient home panel using card rendering
2. Include: greeting, quick actions, language switch
3. Use `ActivePanelRegistry` for home panel

### Phase 3: Owner Bot Card Integration (1-2 days)
1. Add inline keyboards and callbacks to owner digest/today/alerts
2. Use card rendering for alert cards
3. Add drill-down navigation

### Phase 4: Navigation Standardization (1-2 days)
1. Implement consistent Back behavior using `resolve_back_target()`
2. Ensure all card panels include source-aware Back buttons
3. Wire `ActivePanelRegistry` into all card panel renders

### Phase 5: Visual Polish (ongoing)
1. Booking card formatting
2. Patient card formatting
3. Status chips and badge emoji
4. Compact/expanded visual differentiation

---

## 12. Files Audited

| File | Lines | Used By | Status |
|---|---|---|---|
| `interfaces/cards/models.py` | 149 | All card files | Complete, matches docs |
| `interfaces/cards/adapters.py` | 749 | Patient, Admin, Doctor routers | Complete, 6 profiles built |
| `interfaces/cards/callbacks.py` | 127 | Patient, Admin, Doctor routers | Complete, Redis-backed |
| `interfaces/cards/runtime_state.py` | 214 | callbacks.py, panel_runtime.py | Complete, production-ready |
| `interfaces/cards/panel_runtime.py` | 40 | Routers (partially) | Complete but underused |
| `interfaces/cards/navigation.py` | 23 | Not called from routers | **Disconnected** |
| `interfaces/cards/rendering.py` | 24 | Potentially by routers | **Stub — critical gap** |
| `interfaces/bots/patient/router.py` | 4460 | Runtime | Functional, uses cards partially |
| `interfaces/bots/admin/router.py` | 3262 | Runtime | Functional, uses cards partially |
| `interfaces/bots/doctor/router.py` | 2217 | Runtime | Functional, uses cards partially |
| `interfaces/bots/owner/router.py` | 539 | Runtime | **No card system usage** |

---

## 13. Conclusion

DentFlow has a **professionally designed architecture** and a **thorough documentation set**. The booking flow works end-to-end. All 4 role surfaces exist and are functional.

The main problem is not missing features — it's the **gap between designed infrastructure and visible UI output**. The card system is the most striking example: 1100+ lines of well-structured code that produces 24 lines of flat text output.

Closing this rendering gap is the single highest-ROI improvement. It will immediately:
- Make all 4 bot surfaces look professional
- Activate source-aware navigation
- Enable one-active-panel discipline
- Provide stale callback protection for free
- Make the product feel like one coherent system instead of a collection of `/commands`

The documentation is not fiction — it's a blueprint that's 80% implemented structurally. The remaining 20% is the **last mile**: visual rendering, consistent navigation, and owner bot integration.
