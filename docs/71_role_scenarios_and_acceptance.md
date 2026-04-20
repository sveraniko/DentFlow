# 71) Role scenarios and acceptance map

## 1. Purpose

This document defines **real operational end-to-end scenarios** for DentFlow and maps each scenario to current implementation visibility.

It exists to answer, in one place:
1. what role journeys DentFlow is expected to support,
2. what each actor sees/clicks at a practical level,
3. what outbound notifications are sent,
4. what state/object transitions happen,
5. whether the scenario is implemented, partial, or missing,
6. what existing docs/reports/tests currently evidence the scenario.

How this differs from nearby documents:
- `docs/70_bot_flows.md` gives role flow maps; this file adds **acceptance status + evidence + known gaps** per concrete scenario.
- `booking_docs/booking_test_scenarios.md` is a booking test pack; this file is **product-operational role journey mapping**, not a test-case catalog.
- `docs/72_admin_doctor_owner_ui_contracts.md` defines UI contracts; this file gives **cross-role scenario coverage visibility** and implementation maturity.

---

## 2. How to read scenario status

- **Implemented**
  - Scenario is operationally present end-to-end for the role path,
  - with grounded evidence in current docs/reports/tests,
  - and no known blocking gap called out in the latest convergence reports.

- **Partial**
  - Core path exists, but one or more required parts are incomplete, constrained, or not yet exposed in role UI.
  - Use this status when there is real progress but not full acceptance closure.

- **Missing**
  - Scenario is expected by product docs but no credible implementation surface is evidenced.

- **Unknown**
  - Evidence is insufficient or ambiguous. Prefer this over bluffing.

---

## 3. Scenario format

Every scenario in this document uses these fields:
- **Scenario ID**
- **Actor / persona**
- **Preconditions**
- **Entry point**
- **Main flow**
- **Outbound messages / notifications**
- **State / object transitions**
- **Current implementation status**
- **Evidence**
- **Known gaps / comments**

---

## 4. Role/persona model

Product-facing personas used in this map:
- **New patient**: first contact, no trusted prior continuity context.
- **Returning patient**: prior history exists, continuity and speed are expected.
- **Booked patient**: has an existing booking and receives confirmations/reminders/change actions.
- **Admin / reception**: operational workdesk owner for confirmations, reschedules, check-in, communication exceptions, and pickup operations.
- **Doctor**: queue and encounter progression persona.
- **Lead doctor persona (composite/operational)**: not a separate canonical system role by default; used where one doctor functionally combines treatment and local operational coordination.
- **Owner**: digest/snapshot/anomaly/care performance consumer.

---

## 5. Patient scenarios

### PAT-001 — New visitor first booking
- **Actor / persona:** New patient.
- **Preconditions:** Patient opens PatientBot without established booking session.
- **Entry point:** `/start` in PatientBot.
- **Main flow:**
  1. Patient sees initial start panel for booking entry (compact Telegram-first flow).
  2. Greeting/intro is expected as short UX copy, not long narrative.
  3. Language selection path is available (first-run or settings-driven), with RU/EN model.
  4. System captures intent/problem/service direction first (booking-first, not form-first).
  5. System proposes doctor/slot route (including preference/code path where applicable).
  6. **Only then** asks minimal identity/contact confirmation needed to finalize booking.
  7. Review panel shows service/time/doctor/contact snapshot.
  8. Final confirmation creates booking and starts reminder chain.
- **Outbound messages / notifications:** booking confirmation-needed/confirmed message, then reminder chain according to policy.
- **State / object transitions:** booking draft/session progression -> `booking.bookings` created in `pending_confirmation` or `confirmed`; reminder scheduling intent emitted to Communication context.
- **Current implementation status:** **Implemented (core flow) / Partial (full UX evidence granularity)**.
- **Evidence:** `booking_docs/10_booking_flow_dental.md` (booking-first principle, flow order, contact confirmation late); `booking_docs/50_booking_telegram_ui_contract.md` (step contract, contact confirmation, review panel, reminder action UI); `docs/17_localization_and_i18n.md` (language selection/switching rules); `docs/70_bot_flows.md` (canonical patient flows).
- **Known gaps / comments:** Current evidence is documentation + booking test coverage model; this file does not certify every literal first-message copy variant in runtime.

### PAT-002 — Returning patient quick booking
- **Actor / persona:** Returning patient.
- **Preconditions:** Existing patient history/continuity context can be resolved.
- **Entry point:** Patient booking entry from bot menu or `/start`.
- **Main flow:**
  1. System recognizes likely returning patient context.
  2. Offers continuity with previous doctor where policy permits.
  3. Patient selects slot quickly with reduced friction compared to new patient path.
  4. Minimal contact confirmation if needed.
  5. Booking confirmation path continues.
- **Outbound messages / notifications:** booking confirmation/reminders.
- **State / object transitions:** new booking in canonical status set; continuity-routing analytics hooks.
- **Current implementation status:** **Implemented**.
- **Evidence:** `booking_docs/10_booking_flow_dental.md` (Route B continuity, repeat patient faster); `booking_docs/booking_test_scenarios.md` BKG-002; `docs/70_bot_flows.md` returning-patient quick booking.
- **Known gaps / comments:** Continuity policy edge-cases (doctor availability/branch constraints) may still require admin fallback.

### PAT-003 — Existing booked patient confirmation flow
- **Actor / persona:** Booked patient.
- **Preconditions:** Booking exists in `pending_confirmation` or active reminder window.
- **Entry point:** reminder/action-required message CTA.
- **Main flow:** patient acknowledges confirmation intent (or action alternative).
- **Outbound messages / notifications:** confirmation reminder + acknowledgement result messaging.
- **State / object transitions:** reminder acknowledgement stored; booking remains confirmed/continues per policy without introducing hidden statuses.
- **Current implementation status:** **Implemented**.
- **Evidence:** `booking_docs/10_booking_flow_dental.md` reminder/confirmation logic; `booking_docs/50_booking_telegram_ui_contract.md` action-required reminder UI; `booking_docs/booking_test_scenarios.md` BKG-006/BKG-007.
- **Known gaps / comments:** No separate “reminder engine truth” inside booking by design.

### PAT-004 — Reschedule flow
- **Actor / persona:** Booked patient.
- **Preconditions:** Active booking exists.
- **Entry point:** booking card action or reminder CTA.
- **Main flow:** patient requests reschedule, receives alternative slot path or admin-assisted fallback.
- **Outbound messages / notifications:** reschedule acknowledgement + updated booking/reminder messages.
- **State / object transitions:** booking enters `reschedule_requested`, then updated to new slot/status path with history and reminder updates.
- **Current implementation status:** **Implemented**.
- **Evidence:** `booking_docs/10_booking_flow_dental.md` section 9; `booking_docs/booking_test_scenarios.md` BKG-008; `docs/16-4_booking_card_profile.md` patient actions include reschedule.
- **Known gaps / comments:** Operational rescue dependency exists when automated proposals are insufficient.

### PAT-005 — Cancel flow
- **Actor / persona:** Booked patient.
- **Preconditions:** Active booking exists.
- **Entry point:** booking card or reminder-action path.
- **Main flow:** patient cancels booking and receives bounded confirmation.
- **Outbound messages / notifications:** cancellation confirmation; reminder chain update.
- **State / object transitions:** booking status -> `canceled`; reminder plan updated.
- **Current implementation status:** **Implemented**.
- **Evidence:** `booking_docs/10_booking_flow_dental.md` section 10; `booking_docs/booking_test_scenarios.md` BKG-009; `docs/16-4_booking_card_profile.md` patient actions include cancel.
- **Known gaps / comments:** None critical surfaced in convergence pack.

### PAT-006 — Reminder acknowledgement flow
- **Actor / persona:** Booked patient.
- **Preconditions:** Reminder issued (24h/same-day/action-required).
- **Entry point:** reminder notification CTA.
- **Main flow:** patient taps acknowledgement action (confirm/on my way/reschedule/cancel path per policy).
- **Outbound messages / notifications:** acknowledgement feedback + downstream update notifications where needed.
- **State / object transitions:** communication acknowledgement record updated; booking follow-up logic applied.
- **Current implementation status:** **Implemented**.
- **Evidence:** `booking_docs/10_booking_flow_dental.md` action-required reminder pattern; `booking_docs/50_booking_telegram_ui_contract.md` reminder CTA contract; `booking_docs/booking_test_scenarios.md` BKG-006/BKG-007.
- **Known gaps / comments:** Detailed reminder debugging remains admin/issue view, not patient booking card.

### PAT-007 — Post-visit recommendation / aftercare flow
- **Actor / persona:** Returning or recently treated patient.
- **Preconditions:** Recommendation/aftercare output linked to encounter/booking context.
- **Entry point:** patient recommendation/aftercare message or linked panel.
- **Main flow:** patient receives recommendation/aftercare guidance and can proceed toward care actions where supported.
- **Outbound messages / notifications:** recommendation and aftercare localized messaging.
- **State / object transitions:** recommendation lifecycle updates; possible link to care reserve flow.
- **Current implementation status:** **Partial**.
- **Evidence:** `docs/70_bot_flows.md` includes recommendation response; `docs/60_care_commerce.md` recommendation-first model; `docs/17_localization_and_i18n.md` localized recommendation/aftercare expectations; `docs/report/CONVERGENCE_PACK_DELTA_AUDIT_2026-04-20.md` indicates some cross-role linked-object convergence focused on admin/doctor and identifies patient-facing document/cross-surface gaps.
- **Known gaps / comments:** Patient-facing breadth of post-visit linked surfaces is not fully evidenced as complete end-to-end in convergence reports.

### PAT-008 — Care reserve/pickup flow
- **Actor / persona:** Patient (post-recommendation or direct care intent).
- **Preconditions:** Care catalog/order pathways enabled for clinic.
- **Entry point:** recommendation-linked care action or patient care surface.
- **Main flow:** patient reserves care item(s), receives pickup guidance, completes pickup with admin involvement.
- **Outbound messages / notifications:** reserve confirmation, pickup readiness/update messages.
- **State / object transitions:** care reservation/order state updates; pickup status transitions.
- **Current implementation status:** **Partial**.
- **Evidence:** `docs/60_care_commerce.md` scope includes care order lifecycle + pickup; `docs/68_admin_reception_workdesk.md` care pickup queue; `docs/70_bot_flows.md` care reserve/pickup canonical patient flow.
- **Known gaps / comments:** Convergence/delta report notes operator UI expansion areas in 13A (integration surfaces), so full operational closure should be treated as partial.

---

## 6. Admin scenarios

### ADM-001 — Open today workdesk
- **Actor / persona:** Admin / reception.
- **Preconditions:** Admin role binding active.
- **Entry point:** ClinicAdminBot main workdesk entry.
- **Main flow:** open Today section with pending confirmations, upcoming bookings, reschedules, pickups, and issue indicators.
- **Outbound messages / notifications:** compact workdesk panel updates.
- **State / object transitions:** read/projection refresh only unless action invoked.
- **Current implementation status:** **Partial**.
- **Evidence:** `docs/68_admin_reception_workdesk.md` (Today model is canonical); `docs/70_bot_flows.md` canonical admin flow includes today/workdesk.
- **Known gaps / comments:** Documented model is clear; full panel-by-panel implementation evidence is not asserted here.

### ADM-002 — Search/open patient
- **Actor / persona:** Admin / reception.
- **Preconditions:** Search index/read models available.
- **Entry point:** admin search action.
- **Main flow:** search patient, open patient quick card, jump to related booking/care context.
- **Outbound messages / notifications:** search results + card render.
- **State / object transitions:** mostly read transitions; optional linked open actions.
- **Current implementation status:** **Partial**.
- **Evidence:** `docs/68_admin_reception_workdesk.md` sections on Patients and search-as-workdesk tool; `docs/10_architecture.md` clinic operations contour.
- **Known gaps / comments:** End-to-end runtime proof in this convergence set is limited.

### ADM-003 — Search/open booking
- **Actor / persona:** Admin / reception.
- **Preconditions:** booking exists.
- **Entry point:** booking list/search row -> booking card open.
- **Main flow:** open booking card with admin compact/expanded operational actions.
- **Outbound messages / notifications:** card render and optional bounded updates.
- **State / object transitions:** read -> optional booking action transition.
- **Current implementation status:** **Implemented**.
- **Evidence:** `docs/16-4_booking_card_profile.md` admin booking card variant/actions; `docs/68_admin_reception_workdesk.md` booking list/card as core; convergence 12B reports focus on improving linked opens from booking cards (implying base booking open path present).
- **Known gaps / comments:** None blocking at base “open booking” path level.

### ADM-004 — Confirm/check-in booking
- **Actor / persona:** Admin / reception.
- **Preconditions:** booking in confirmation/check-in eligible state.
- **Entry point:** booking card or confirmation queue.
- **Main flow:** confirm booking and/or mark patient arrival/check-in.
- **Outbound messages / notifications:** patient-facing booking status update/reminder adjustments as needed.
- **State / object transitions:** `pending_confirmation` -> `confirmed`; then `checked_in` when arrival marked.
- **Current implementation status:** **Implemented**.
- **Evidence:** canonical status model in README + booking docs; admin actions in `docs/68_admin_reception_workdesk.md`; booking card admin actions in `docs/16-4_booking_card_profile.md`.
- **Known gaps / comments:** Exact role split for check-in vs doctor-side check-in is policy-sensitive; admin ownership is strongly emphasized.

### ADM-005 — Reschedule handling
- **Actor / persona:** Admin / reception.
- **Preconditions:** reschedule request exists or patient contact issue requires reschedule.
- **Entry point:** Reschedules queue or booking card action.
- **Main flow:** open requested booking, inspect context, offer/assign new slot, close request.
- **Outbound messages / notifications:** patient reschedule updates.
- **State / object transitions:** `reschedule_requested` -> updated booking slot/status; reminder chain recalculated.
- **Current implementation status:** **Implemented**.
- **Evidence:** `docs/68_admin_reception_workdesk.md` reschedule queue and actions; `booking_docs/10_booking_flow_dental.md` reschedule behavior.
- **Known gaps / comments:** Heavy edge-cases may still require manual rescue path.

### ADM-006 — Reminder exception / no-response handling
- **Actor / persona:** Admin / reception.
- **Preconditions:** reminder failure or no-response signal exists.
- **Entry point:** Confirmations queue / Issues queue.
- **Main flow:** admin opens issue-linked booking context and applies rescue action (confirm, reschedule, cancel, manual follow-up path).
- **Outbound messages / notifications:** patient contact attempts and internal issue resolution updates.
- **State / object transitions:** reminder issue state updates; booking state changes as needed.
- **Current implementation status:** **Partial**.
- **Evidence:** `docs/68_admin_reception_workdesk.md` confirmations/issues queue semantics; `docs/16-4_booking_card_profile.md` reminder issue hints on admin/owner variants.
- **Known gaps / comments:** Detailed issue-control surfaces are described as bounded/non-overloaded; not all low-level operations are proven as complete in latest reports.

### ADM-007 — Linked recommendation handling
- **Actor / persona:** Admin / reception.
- **Preconditions:** booking has linked recommendation.
- **Entry point:** booking card linked object action.
- **Main flow:** open bounded recommendation panel from booking and navigate back safely.
- **Outbound messages / notifications:** localized panel messaging.
- **State / object transitions:** mostly read/navigation unless explicit recommendation action triggered.
- **Current implementation status:** **Implemented**.
- **Evidence:** `docs/report/PR_12B1_REPORT.md` states admin linked recommendation placeholder replaced with bounded localized panel + tests.
- **Known gaps / comments:** Focus is linked-open convergence; broader recommendation management outside this path may still vary.

### ADM-008 — Linked care-order / pickup handling
- **Actor / persona:** Admin / reception.
- **Preconditions:** booking/patient has linked care order.
- **Entry point:** booking card linked care-order action or care pickup queue.
- **Main flow:** open bounded care-order panel from booking; continue to pickup operations in workdesk context.
- **Outbound messages / notifications:** localized panel + pickup updates.
- **State / object transitions:** care order/pickup status progression.
- **Current implementation status:** **Implemented (linked open) / Partial (full pickup operations closure)**.
- **Evidence:** `docs/report/PR_12B1_REPORT.md` linked open convergence for admin care order; `docs/68_admin_reception_workdesk.md` care pickups queue model.
- **Known gaps / comments:** End-to-end pickup operation breadth remains partly operational-model driven.

### ADM-009 — Calendar mirror awareness flow
- **Actor / persona:** Admin / reception.
- **Preconditions:** Google Calendar projection configured.
- **Entry point:** admin calendar mirror open action.
- **Main flow:** view visual schedule mirror for awareness, then return to DentFlow for actions.
- **Outbound messages / notifications:** projection status awareness surfaces.
- **State / object transitions:** no truth transitions in Calendar; DentFlow remains action truth.
- **Current implementation status:** **Missing (admin mirror UI surface)**.
- **Evidence:** `docs/69_google_calendar_schedule_projection.md` defines mirror model; `docs/report/CONVERGENCE_PACK_DELTA_AUDIT_2026-04-20.md` explicitly marks admin calendar mirror UI as absent (13A).
- **Known gaps / comments:** Do not treat Calendar as system of record.

---

## 7. Doctor scenarios

### DOC-001 — Open upcoming queue
- **Actor / persona:** Doctor.
- **Preconditions:** doctor role binding and schedule data available.
- **Entry point:** doctor surface queue command.
- **Main flow:** open upcoming list, select booking, move into focused booking context.
- **Outbound messages / notifications:** queue panel/card updates.
- **State / object transitions:** read transitions until action.
- **Current implementation status:** **Partial**.
- **Evidence:** `docs/70_bot_flows.md` canonical doctor flow includes upcoming queue; `docs/16-4_booking_card_profile.md` doctor variant and source-context behavior.
- **Known gaps / comments:** Current doc/report set emphasizes linked-open convergence rather than explicit queue completeness proof.

### DOC-002 — Open current booking
- **Actor / persona:** Doctor.
- **Preconditions:** active booking exists.
- **Entry point:** queue row/booking open action.
- **Main flow:** open doctor booking card with compact operational context.
- **Outbound messages / notifications:** card render and bounded updates.
- **State / object transitions:** read -> optional state action.
- **Current implementation status:** **Implemented**.
- **Evidence:** `docs/16-4_booking_card_profile.md` doctor booking card profile; `docs/70_bot_flows.md` open current booking listed as canonical.
- **Known gaps / comments:** None blocking for base open path.

### DOC-003 — Mark in service / start encounter
- **Actor / persona:** Doctor.
- **Preconditions:** booking arrived/eligible for encounter start.
- **Entry point:** doctor booking card action.
- **Main flow:** doctor marks encounter start.
- **Outbound messages / notifications:** internal operational update; optional downstream signals.
- **State / object transitions:** `checked_in` -> `in_service`.
- **Current implementation status:** **Implemented**.
- **Evidence:** canonical statuses in README and booking docs; doctor operational actions in booking card profile.
- **Known gaps / comments:** Check-in ownership should remain policy-consistent with admin flow.

### DOC-004 — Add quick note / see relevant patient context
- **Actor / persona:** Doctor.
- **Preconditions:** current booking selected.
- **Entry point:** booking context during encounter.
- **Main flow:** doctor reviews compact patient/booking context and records quick note.
- **Outbound messages / notifications:** minimal operational confirmations.
- **State / object transitions:** chart/note projection update (without redefining booking truth).
- **Current implementation status:** **Partial**.
- **Evidence:** `docs/10_architecture.md` doctor contour includes quick notes/context; `docs/16-4_booking_card_profile.md` chart boundary and compact contextual hints.
- **Known gaps / comments:** Full encounter note UX path is not fully evidenced in provided convergence docs.

### DOC-005 — Issue recommendation
- **Actor / persona:** Doctor (or lead doctor operationally).
- **Preconditions:** encounter context exists.
- **Entry point:** doctor booking/encounter action.
- **Main flow:** issue recommendation and link to patient/care path.
- **Outbound messages / notifications:** patient recommendation message, localized copy.
- **State / object transitions:** recommendation object created/linked to booking/patient.
- **Current implementation status:** **Implemented (core) / Partial (full downstream breadth)**.
- **Evidence:** `docs/70_bot_flows.md` doctor canonical flow includes issue recommendation; `docs/60_care_commerce.md` recommendation-first care model; `docs/report/PR_12B1_REPORT.md` doctor linked recommendation open convergence.
- **Known gaps / comments:** Full downstream patient/document/care expansion remains staged across packs.

### DOC-006 — Open linked care-order
- **Actor / persona:** Doctor.
- **Preconditions:** linked care order exists for booking/patient.
- **Entry point:** booking linked object action.
- **Main flow:** open bounded care-order panel and return to booking flow.
- **Outbound messages / notifications:** localized panel text.
- **State / object transitions:** primarily navigation/read.
- **Current implementation status:** **Implemented**.
- **Evidence:** `docs/report/PR_12B1_REPORT.md` doctor linked care-order placeholder replaced with bounded panel and tests.
- **Known gaps / comments:** Does not imply complete doctor-side care fulfillment console.

### DOC-007 — Complete encounter
- **Actor / persona:** Doctor.
- **Preconditions:** booking in service.
- **Entry point:** booking/encounter completion action.
- **Main flow:** doctor marks completion and triggers post-visit continuity outputs.
- **Outbound messages / notifications:** completion-linked follow-up/recommendation/aftercare where configured.
- **State / object transitions:** `in_service` -> `completed`.
- **Current implementation status:** **Implemented (status path) / Partial (post-visit bundle consistency)**.
- **Evidence:** canonical status model in README + booking docs; doctor flow completion intent in `docs/70_bot_flows.md`.
- **Known gaps / comments:** Post-visit unified messaging and linked patient document surfaces are not universally closed.

---

## 8. Owner scenarios

### OWN-001 — Open daily digest
- **Actor / persona:** Owner.
- **Preconditions:** owner role binding and digest projections available.
- **Entry point:** OwnerBot digest command.
- **Main flow:** owner opens compact daily digest and scans key clinic signals.
- **Outbound messages / notifications:** daily digest message/panel.
- **State / object transitions:** projection read only.
- **Current implementation status:** **Partial**.
- **Evidence:** `docs/70_bot_flows.md` owner daily digest canonical flow; `docs/10_architecture.md` owner contour responsibilities.
- **Known gaps / comments:** This map does not assert full runtime parity across all digest slices.

### OWN-002 — Open live clinic snapshot
- **Actor / persona:** Owner.
- **Preconditions:** real-time/projection snapshot available.
- **Entry point:** owner snapshot action.
- **Main flow:** owner opens live state snapshot for current operational pulse.
- **Outbound messages / notifications:** snapshot panel.
- **State / object transitions:** projection read only.
- **Current implementation status:** **Partial**.
- **Evidence:** `docs/70_bot_flows.md` live snapshot canonical flow; `docs/10_architecture.md` owner contour.
- **Known gaps / comments:** Implementation depth per metric dimension may vary.

### OWN-003 — Open anomaly / exception view
- **Actor / persona:** Owner.
- **Preconditions:** exception/anomaly projections produced.
- **Entry point:** owner anomaly command or digest drill-down.
- **Main flow:** owner reviews anomalies (e.g., reminder/no-show/backlog patterns) and may drill into bounded context.
- **Outbound messages / notifications:** anomaly panel/alerts.
- **State / object transitions:** projection read, optional drill-down navigation.
- **Current implementation status:** **Partial**.
- **Evidence:** `docs/70_bot_flows.md` anomaly and exception flows; owner visibility principles in architecture.
- **Known gaps / comments:** Calendar mirror UI absence for admin does not block owner anomaly read models but reduces some operational transparency chains.

### OWN-004 — Open care-performance view
- **Actor / persona:** Owner.
- **Preconditions:** care-commerce and recommendation projections available.
- **Entry point:** owner care-performance view.
- **Main flow:** owner inspects care uptake/attach-rate style performance indicators.
- **Outbound messages / notifications:** care-performance summary/drill-down panels.
- **State / object transitions:** analytics projection read.
- **Current implementation status:** **Partial**.
- **Evidence:** `docs/70_bot_flows.md` owner care-performance canonical flow; `docs/60_care_commerce.md` owner measurement objective.
- **Known gaps / comments:** Detailed operator-facing integration UI remains staged (13A-oriented in delta audit).

---

## 9. Cross-role notification map

Key outbound notifications/messages across roles:

- **Booking confirmation**
  - Patient receives booking created/confirmation-needed or confirmed output.
  - Admin/doctor see booking status chips/queues reflecting confirmation state.

- **Reminder**
  - Patient receives 24h/same-day/action-required reminder CTAs.
  - Admin receives exception/no-response visibility in workdesk queues.
  - Owner sees aggregate impacts/anomalies in digest/snapshot layers.

- **Reschedule/cancel updates**
  - Patient receives update acknowledgement and next-step panel.
  - Admin queue/workdesk reflects changed operational load.
  - Calendar mirror (when present) reflects DentFlow-side changes as projection only.

- **Recommendation / aftercare**
  - Doctor/admin initiate recommendation-linked continuity actions.
  - Patient receives localized recommendation/aftercare guidance.
  - Owner receives uptake/performance projection signals.

- **Care reserve/pickup related notifications**
  - Patient receives reserve/pickup readiness updates.
  - Admin sees pickup queue and linked booking/patient context.
  - Owner observes care attach/performance patterns.

---

## 10. Current coverage snapshot

| Scenario ID | Role | Status | Primary evidence | Next action if partial/missing |
|---|---|---|---|---|
| PAT-001 | Patient | Implemented / Partial | booking flow + booking UI contract + i18n + bot flow docs | Add explicit runtime UX evidence trace for `/start` panel variants and language-first-entry rendering. |
| PAT-002 | Patient | Implemented | booking Route B + BKG-002 | Monitor continuity edge-cases under branch/availability constraints. |
| PAT-003 | Patient | Implemented | booking reminder logic + BKG-006/007 | Keep reminder acknowledgements visible in admin/owner projections. |
| PAT-004 | Patient | Implemented | booking reschedule flow + BKG-008 | Continue validating admin rescue branch under high-load clinics. |
| PAT-005 | Patient | Implemented | booking cancel flow + BKG-009 | Keep reminder recalculation consistency checks. |
| PAT-006 | Patient | Implemented | reminder action contract + BKG-006/007 | No immediate gap; maintain localization parity. |
| PAT-007 | Patient | Partial | bot flow + care-commerce + delta audit | Consolidate end-to-end post-visit continuity visibility (patient-facing linked surfaces). |
| PAT-008 | Patient | Partial | care-commerce + admin workdesk care queue + bot flow | Complete operator/patient care flow surfaces targeted in follow-up integration stack. |
| ADM-001 | Admin | Partial | admin workdesk canonical model | Validate/close concrete runtime panel coverage against model. |
| ADM-002 | Admin | Partial | admin search/workdesk model + architecture | Add/confirm explicit acceptance evidence for search-to-patient open path. |
| ADM-003 | Admin | Implemented | booking card profile + workdesk booking list/card + 12B linked-open context | None critical. |
| ADM-004 | Admin | Implemented | canonical statuses + admin actions in workdesk/card docs | Keep role-boundary discipline for check-in ownership. |
| ADM-005 | Admin | Implemented | admin reschedule queue model + booking reschedule behavior | None critical. |
| ADM-006 | Admin | Partial | admin confirmations/issues queues + reminder hints | Harden exception-handling acceptance checks as dedicated scenario pack. |
| ADM-007 | Admin | Implemented | PR_12B1 linked recommendation convergence | Maintain localized bounded panel quality. |
| ADM-008 | Admin | Implemented / Partial | PR_12B1 linked care-order convergence + care pickup model | Expand full pickup-operation acceptance map beyond linked open path. |
| ADM-009 | Admin | Missing | calendar projection doc + delta audit missing UI statement | Implement admin calendar mirror UI as read-only projection (13A path). |
| DOC-001 | Doctor | Partial | bot flow canonical queue + booking card source behavior | Add explicit doctor queue runtime acceptance evidence. |
| DOC-002 | Doctor | Implemented | doctor booking card + bot flow | None critical. |
| DOC-003 | Doctor | Implemented | canonical statuses + doctor action model | Keep state transition guardrails aligned with admin check-in ownership. |
| DOC-004 | Doctor | Partial | architecture doctor contour + booking/chart boundary | Add end-to-end note/context evidence in doctor runtime docs/tests. |
| DOC-005 | Doctor | Implemented / Partial | doctor recommendation flow + care-commerce + PR_12B1 | Complete broader downstream continuity surfaces. |
| DOC-006 | Doctor | Implemented | PR_12B1 linked care-order convergence | None critical for linked-open acceptance. |
| DOC-007 | Doctor | Implemented / Partial | canonical completion status + bot flow | Tighten unified post-completion continuity acceptance trace. |
| OWN-001 | Owner | Partial | owner digest flow map + architecture owner contour | Add implementation-facing evidence map for digest widgets. |
| OWN-002 | Owner | Partial | owner live snapshot flow map | Add runtime acceptance evidence for snapshot consistency. |
| OWN-003 | Owner | Partial | owner anomaly/exception flow map | Expand anomaly scenario evidence and drill-down linkage map. |
| OWN-004 | Owner | Partial | owner care-performance flow + care-commerce objectives | Add measurable acceptance hooks for care KPIs and projections. |

---

### Notes for audit use

- This scenario map intentionally separates **role journeys** from **UI callback contracts** and **test-case scripts**.
- Calendar remains projection/mirror only; DentFlow remains operational truth.
- Where evidence is not closure-grade, status is marked Partial/Missing instead of inferred complete.
