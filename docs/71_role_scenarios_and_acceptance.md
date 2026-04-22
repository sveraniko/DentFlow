# 71) Role scenarios and acceptance map

> Operational end-to-end scenario map for DentFlow.
>
> This document answers a different question from the PR plan.
> The PR plan explains **how we are building**.
> This file explains **what the product already does, what each role actually experiences, and what is still incomplete**.

## 1. Purpose

This document defines the real role journeys DentFlow is expected to support and maps them to current implementation reality.

It exists to answer, in one place:

1. what concrete user/role scenarios DentFlow should support;
2. what each actor sees and clicks at a practical Telegram level;
3. which notifications or follow-up messages are sent;
4. which objects and states change underneath;
5. whether the scenario is implemented, partial, or missing;
6. what current docs, code paths, and reports support that conclusion.

This file is deliberately different from nearby documents:

- `docs/70_bot_flows.md` gives the high-level role map.
- `booking_docs/*` define booking logic and UI contracts in depth.
- `docs/72_admin_doctor_owner_ui_contracts.md` defines surface rules for staff/owner UI.
- `docs/73_governance_and_reference_ops.md` covers governance, registries, references, and master-data operating model.
- this file is the **acceptance map** for real user journeys.

---

## 2. How to read scenario status

- **Implemented**
  - The main operational path exists in current runtime, with no known blocking gap for normal usage.

- **Partial**
  - The core path exists, but one or more materially important pieces are still weak, command-centric, not yet first-class in UI, or only partially evidenced.

- **Missing**
  - The scenario is expected by the product model, but current runtime does not provide a credible end-to-end surface.

- **Unknown**
  - Evidence is insufficient. Prefer this over bluffing.

General rule:
- when in doubt, this document should degrade to **Partial** or **Unknown**, not invent closure.

---

## 3. Product guardrails used by all scenarios

The following rules are assumed by every scenario in this file:

1. **DentFlow is source of truth** for bookings, patient links, statuses, reminders, care orders, and generated artifacts.
2. **Google Calendar is a mirror**, not a second scheduling truth.
3. **Google Sheets is allowed for care catalog authoring**, not for live booking truth.
4. **Patient data collection should be just-in-time**. The patient should not be interrogated with a giant intake form before intent is clear.
5. **One actor may carry multiple roles**. “Lead doctor” is not a separate canonical runtime role yet; it is a composite operational persona.
6. **Generated documents are baseline artifacts now**. This is already useful, but it is not the same thing as a fully expanded document/PDF program.

---

## 4. Role/persona model

The product-facing personas used in this map are:

- **New patient**: first contact, no trusted continuity yet.
- **Returning patient**: prior history exists; lower friction is expected.
- **Booked patient**: already has a booking and interacts with reminders, confirmation, change, and follow-up.
- **Admin / reception**: clinic workdesk role for confirmations, schedule rescue, patient access, pickup, and issue handling.
- **Doctor**: queue, patient context, encounter progression, recommendations, booking-linked operational actions.
- **Lead doctor persona**: composite operational persona, typically doctor + wider clinic awareness. This is not a separate canonical role code in current runtime.
- **Owner**: digest, snapshot, alerts, and business/operational oversight consumer.

---

## 5. Scenario format

Each scenario in this document contains:

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

## 6. Patient scenarios

### PAT-001 — New visitor first booking
- **Actor / persona:** New patient.
- **Preconditions:** Patient opens PatientBot without an active booking session.
- **Entry point:** `/start` -> current runtime home -> `/book`.
- **Main flow:**
  1. Patient opens the bot.
  2. Current runtime shows a home text surface (`/start`), not yet a full first-run CTA panel.
  3. Patient enters `/book`.
  4. System starts or resumes a booking session.
  5. Patient chooses service.
  6. Patient chooses doctor preference.
  7. Patient chooses slot.
  8. Only after slot selection does the system request contact/phone.
  9. System resolves or creates the patient linkage from contact.
  10. State machine marks review-ready.
  11. Runtime currently finalizes immediately after contact resolution instead of showing a rich explicit pre-final-confirmation review card.
- **Outbound messages / notifications:** booking success message, then reminder chain according to clinic policy.
- **State / object transitions:** booking session progresses through service/doctor/slot/contact steps -> `review_ready` -> booking created and reminder planning is emitted.
- **Current implementation status:** **Partial**.
- **Evidence:** `app/interfaces/bots/patient/router.py` (`start`, `book_entry`, `select_service`, `select_doctor_preference`, `select_slot`, `_handle_contact_submission`, `_render_resume_panel`); `booking_docs/10_booking_flow_dental.md`; `booking_docs/50_booking_telegram_ui_contract.md`; `docs/17_localization_and_i18n.md`.
- **Known gaps / comments:**
  - `/start` is still a text-command home, not a polished first-run intent panel.
  - explicit first-run language picker is not evidenced in current patient runtime;
  - state machine supports `review_ready`, but runtime currently finalizes immediately after contact resolution;
  - success copy still uses raw identifiers (`doctor_id`, `service_id`, `branch_id`) instead of human display labels.

### PAT-002 — Returning patient quick booking
- **Actor / persona:** Returning patient.
- **Preconditions:** Patient already exists in DentFlow and returns to booking.
- **Entry point:** `/book`.
- **Main flow:**
  1. Patient enters booking again.
  2. Booking session resumes or starts.
  3. Patient proceeds through booking with reduced identity friction because contact-based patient resolution already exists.
  4. Continuity assumptions may influence route selection.
- **Outbound messages / notifications:** booking success and reminder chain.
- **State / object transitions:** new booking created and linked to an existing patient identity when resolution succeeds.
- **Current implementation status:** **Partial**.
- **Evidence:** `app/interfaces/bots/patient/router.py` (`book_entry`, `_handle_contact_submission`); `booking_docs/10_booking_flow_dental.md` (repeat-patient and continuity ideas); `docs/70_bot_flows.md`.
- **Known gaps / comments:**
  - current runtime clearly supports contact-based identity continuity;
  - explicit “quick booking with previous doctor / continuity-first shortcut” is not strongly evidenced as a fully polished patient-visible branch.

### PAT-003 — Existing booked patient confirmation flow
- **Actor / persona:** Booked patient.
- **Preconditions:** Booking exists and is confirmation-eligible.
- **Entry point:** reminder CTA or `/my_booking` booking card action.
- **Main flow:**
  1. Patient opens current booking context.
  2. Patient confirms from booking card or reminder action.
  3. UI updates booking panel accordingly.
- **Outbound messages / notifications:** reminder acknowledgement, optional booking status update.
- **State / object transitions:** confirmation acknowledgement recorded; booking remains in the canonical booking lifecycle.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/patient/router.py` (`my_booking_entry`, booking-card callbacks, `reminder_action_callback`); `booking_docs/10_booking_flow_dental.md`; `booking_docs/booking_test_scenarios.md`.
- **Known gaps / comments:** reminder truth remains in communication/reminder layer by design, not as a fake parallel booking truth.

### PAT-004 — Reschedule flow
- **Actor / persona:** Booked patient.
- **Preconditions:** Active booking exists.
- **Entry point:** booking card action or reminder CTA.
- **Main flow:**
  1. Patient requests reschedule.
  2. Runtime updates booking state into reschedule-requested path.
  3. Booking card is re-rendered.
  4. Admin/rescue path can continue later if needed.
- **Outbound messages / notifications:** reschedule-related messaging and later updated booking/reminder messages.
- **State / object transitions:** booking enters `reschedule_requested`; reminder and operational follow-up are updated downstream.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/patient/router.py` (`request_reschedule`, booking-card callback branch for reschedule); `booking_docs/10_booking_flow_dental.md`; `booking_docs/booking_test_scenarios.md`.
- **Known gaps / comments:** advanced rescue and operator intervention live on admin side, not patient side.

### PAT-005 — Cancel flow
- **Actor / persona:** Booked patient.
- **Preconditions:** Active booking exists.
- **Entry point:** booking card cancel action.
- **Main flow:**
  1. Patient opens cancel prompt.
  2. Patient confirms or aborts.
  3. Booking card updates after cancellation.
- **Outbound messages / notifications:** cancellation confirmation and downstream reminder adjustments.
- **State / object transitions:** booking moves to canceled state.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/patient/router.py` (`cancel_prompt_by_runtime`, `cancel_prompt`, `cancel_confirm`); `booking_docs/10_booking_flow_dental.md`; `booking_docs/booking_test_scenarios.md`.
- **Known gaps / comments:** no major acceptance blocker surfaced in the convergence pack.

### PAT-006 — Reminder acknowledgement flow
- **Actor / persona:** Booked patient.
- **Preconditions:** Reminder has been sent.
- **Entry point:** reminder callback.
- **Main flow:** patient taps reminder CTA according to reminder policy. `ack` means “received/understood” reminder acknowledgement and is intentionally distinct from attendance confirmation (`confirm`).
- **Outbound messages / notifications:** reminder-action acceptance/stale/invalid feedback.
- **State / object transitions:** `ack` updates reminder acknowledgement record only (non-destructive) and does **not** mutate booking status; accepted `ack` hands off to canonical booking continuity. `ack` currently adds no special future-reminder suppression policy beyond normal reminder planning.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/patient/router.py` (`reminder_action_callback`); `booking_docs/10_booking_flow_dental.md`; `booking_docs/50_booking_telegram_ui_contract.md`.
- **Known gaps / comments:** detailed reminder debugging stays with admin/issues and owner analytics, not patient UX.

### PAT-007 — Post-visit recommendation / aftercare flow
- **Actor / persona:** Recently treated patient.
- **Preconditions:** Recommendation or aftercare content exists for this patient.
- **Entry point:** `/recommendations`, recommendation open/action routes, or linked follow-up path.
- **Main flow:**
  1. Patient resolves to own patient identity.
  2. Patient lists recommendations.
  3. Patient opens recommendation detail.
  4. Patient can acknowledge / accept / decline.
  5. Patient may continue into recommendation-linked product flow.
- **Outbound messages / notifications:** recommendation text, action acknowledgement, potential follow-up guidance.
- **State / object transitions:** recommendation status may change from issued -> viewed/acknowledged/accepted/declined.
- **Current implementation status:** **Partial**.
- **Evidence:** `app/interfaces/bots/patient/router.py` (`recommendations_list`, `recommendations_open`, `recommendations_action`, `recommendation_products`); `docs/60_care_commerce.md`; `docs/70_bot_flows.md`.
- **Known gaps / comments:**
  - patient-facing recommendations exist as commands and flows;
  - broader post-visit document delivery and richer linked aftercare packaging are still incomplete.

### PAT-008 — Care reserve / pickup flow
- **Actor / persona:** Patient.
- **Preconditions:** Care catalog and care-order surfaces are enabled.
- **Entry point:** `/care`, recommendation-linked product flow, or care-order list.
- **Main flow:**
  1. Patient browses care categories or recommendation-linked products.
  2. Patient opens product card.
  3. Patient selects branch if needed.
  4. Patient reserves/creates care order.
  5. Patient can list own care orders and repeat eligible orders.
  6. Pickup is completed with admin-side operational handling.
- **Outbound messages / notifications:** order creation, reserve/pickup update messages.
- **State / object transitions:** care order created, confirmed, and later processed through pickup lifecycle.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/patient/router.py` (`care_catalog`, `recommendation_products`, `care_product_open`, `care_order_create`, `care_orders`, `care_order_repeat`, callback handlers for product/branch/reserve/order open); `docs/60_care_commerce.md`; `docs/68_admin_reception_workdesk.md`.
- **Known gaps / comments:** PAT-008 closure scope is reserve/pickup continuity and patient-safe pickup-ready proactive open; broader commerce polish/governance remains outside PAT-008.

### PAT-DOC-001 — Patient receives a post-visit document artifact
- **Actor / persona:** Patient.
- **Preconditions:** Clinic wants to deliver generated aftercare/recommendation/export artifact directly to patient.
- **Entry point:** patient post-visit follow-up or document delivery action.
- **Main flow:** expected future path for patient-visible document delivery.
- **Outbound messages / notifications:** generated artifact delivery or secure link.
- **State / object transitions:** generated artifact becomes patient-visible.
- **Current implementation status:** **Missing**.
- **Evidence:** `docs/65_document_templates_and_043_mapping.md` defines the family concept; convergence and 12B reports explicitly focused current delivery on admin/doctor surfaces.
- **Known gaps / comments:** current generated document baseline is useful for staff but is not yet a patient-facing document delivery program.

---

## 7. Admin / reception scenarios

### ADM-001 — Open today workdesk
- **Actor / persona:** Admin / reception.
- **Preconditions:** Admin role binding exists.
- **Entry point:** `/admin_today`.
- **Main flow:** open today workdesk, inspect queues and operational slices, drill into booking objects.
- **Outbound messages / notifications:** compact workdesk panel render.
- **State / object transitions:** read/projection only until an action is selected.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/admin/router.py` (`admin_today`, `admin_today_callback` and related AW2/AW4 callback paths); `docs/68_admin_reception_workdesk.md`; convergence/admin reports from AW wave.
- **Known gaps / comments:** queue-source context/back-behavior still has some polish room, but the workdesk surface itself is present.

### ADM-002 — Search/open patient
- **Actor / persona:** Admin / reception.
- **Preconditions:** Patient registry/read model exists.
- **Entry point:** `/admin_patients` or `/search_patient`.
- **Main flow:**
  1. Admin searches patients.
  2. Admin opens patient row/card.
  3. Admin navigates to booking or linked operational context.
- **Outbound messages / notifications:** search results and patient card render.
- **State / object transitions:** mostly read/navigation transitions.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/admin/router.py` (`admin_patients`, `search_patient`, patient-card related callbacks); `docs/68_admin_reception_workdesk.md`.
- **Known gaps / comments:** this is an operational registry view, not yet a full governance console.

### ADM-003 — Search/open booking
- **Actor / persona:** Admin / reception.
- **Preconditions:** Booking exists.
- **Entry point:** `/booking_open`, today/workdesk rows, or search result.
- **Main flow:** admin opens booking card and acts from compact/expanded operational panel.
- **Outbound messages / notifications:** booking card render and any downstream patient updates caused by actions.
- **State / object transitions:** booking state may change through confirmation, check-in, reschedule, cancel, etc.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/admin/router.py` (`booking_open`, booking callbacks); `docs/16-4_booking_card_profile.md`; `docs/68_admin_reception_workdesk.md`.
- **Known gaps / comments:** none blocking at base acceptance level.

### ADM-004 — Confirm / check-in booking
- **Actor / persona:** Admin / reception.
- **Preconditions:** Booking is in a confirmation/check-in eligible state.
- **Entry point:** booking card or queue action.
- **Main flow:** admin confirms booking and/or marks arrival/check-in.
- **Outbound messages / notifications:** patient-facing status update and reminder adjustments where appropriate.
- **State / object transitions:** `pending_confirmation` -> `confirmed`; later `checked_in`.
- **Current implementation status:** **Implemented**.
- **Evidence:** admin booking actions in `app/interfaces/bots/admin/router.py`; `docs/16-4_booking_card_profile.md`; `docs/68_admin_reception_workdesk.md`.
- **Known gaps / comments:** exact policy split between admin and doctor still depends on clinic practice, but operational path exists.

### ADM-005 — Reschedule handling
- **Actor / persona:** Admin / reception.
- **Preconditions:** Reschedule request exists or a booking needs manual rescue.
- **Entry point:** `/admin_reschedules` or booking context.
- **Main flow:** admin opens the request, reviews the booking, and progresses the booking into a corrected slot/state path.
- **Outbound messages / notifications:** patient reschedule updates and downstream reminder updates.
- **State / object transitions:** `reschedule_requested` -> updated booking path.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/admin/router.py` (`admin_reschedules` and related queue callbacks); `docs/68_admin_reception_workdesk.md`; booking docs.
- **Known gaps / comments:** the path exists; complex rescue cases may still remain operator-heavy by design.

### ADM-006 — Reminder exception / no-response handling
- **Actor / persona:** Admin / reception.
- **Preconditions:** Reminder failure, stale action, or no-response issue exists.
- **Entry point:** `/admin_confirmations`, `/admin_issues`, or issue-linked booking context.
- **Main flow:** admin opens issue queue, inspects affected booking, and applies rescue action.
- **Outbound messages / notifications:** patient contact or internal issue resolution messaging.
- **State / object transitions:** reminder/issue state updates and possible booking state changes.
- **Current implementation status:** **Partial**.
- **Evidence:** `app/interfaces/bots/admin/router.py` (`admin_confirmations`, `admin_issues`, issue callbacks); `docs/68_admin_reception_workdesk.md`; owner/issue analytics docs.
- **Known gaps / comments:** the queue surfaces exist, but not every rescue path is evidenced as fully polished end-to-end.

### ADM-007 — Linked recommendation handling from booking
- **Actor / persona:** Admin / reception.
- **Preconditions:** Booking has a linked recommendation.
- **Entry point:** booking card linked object action.
- **Main flow:** admin opens bounded recommendation panel from booking and navigates back without falling into raw placeholder text.
- **Outbound messages / notifications:** localized bounded recommendation panel.
- **State / object transitions:** mainly read/navigation.
- **Current implementation status:** **Implemented**.
- **Evidence:** `docs/report/PR_12B1_REPORT.md`; `app/interfaces/bots/admin/router.py` (linked recommendation branch after convergence).
- **Known gaps / comments:** broader recommendation management outside booking-linked open is a separate concern.

### ADM-008 — Linked care-order / pickup handling from booking
- **Actor / persona:** Admin / reception.
- **Preconditions:** Booking/patient has linked care order.
- **Entry point:** booking card linked object action or care pickup queue.
- **Main flow:** admin opens bounded care-order panel and continues pickup-oriented workdesk handling.
- **Outbound messages / notifications:** localized care-order panel and pickup updates.
- **State / object transitions:** care-order lifecycle and pickup transitions continue in operational layer.
- **Current implementation status:** **Implemented**.
- **Evidence:** `docs/report/PR_12B1_REPORT.md`; `app/interfaces/bots/admin/router.py` (linked care-order open); `app/interfaces/bots/admin/router.py` (`admin_care_pickups`);
- **Known gaps / comments:** governance and authoring of care catalog are out of scope for this scenario and covered separately in `docs/73_governance_and_reference_ops.md`.

### ADM-009 — Calendar mirror awareness flow
- **Actor / persona:** Admin / reception.
- **Preconditions:** Calendar projection backend is enabled for the clinic.
- **Entry point:** external Google Calendar visual layer + DentFlow as action surface.
- **Main flow:**
  1. Admin uses Calendar for visual awareness of day/week load.
  2. Admin returns to DentFlow for actual mutations and operational truth.
- **Outbound messages / notifications:** calendar event projection updates happen from DentFlow changes.
- **State / object transitions:** DentFlow booking changes project outward to calendar.
- **Current implementation status:** **Partial**.
- **Evidence:** `docs/69_google_calendar_schedule_projection.md`; `app/application/integration/google_calendar_projection.py`; projector worker/runtime docs and reports.
- **Known gaps / comments:** backend projection exists, but a first-class admin mirror surface inside Telegram is not yet the main operational UX.

### ADM-DOC-001 — Generate 043/export artifact from staff context
- **Actor / persona:** Admin / reception.
- **Preconditions:** Export services and template resolution are configured.
- **Entry point:** `/admin_doc_generate` and related patient/booking context.
- **Main flow:** admin triggers document generation for patient/booking-linked context.
- **Outbound messages / notifications:** generation result/status messages.
- **State / object transitions:** generated document artifact is created and registered.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/admin/router.py` (`admin_doc_generate`); `app/application/export/*`; `docs/65_document_templates_and_043_mapping.md`; PR 12A/12B reports.
- **Known gaps / comments:** current baseline is artifact generation, not a final broad PDF/document family rollout.

### ADM-DOC-002 — Open and download generated document
- **Actor / persona:** Admin / reception.
- **Preconditions:** Generated document already exists.
- **Entry point:** `/admin_doc_open`, `/admin_doc_download`, registry/open flows.
- **Main flow:** admin opens metadata/status view and downloads the actual artifact when supported.
- **Outbound messages / notifications:** metadata card and Telegram document delivery.
- **State / object transitions:** read/download only.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/admin/router.py` (`admin_doc_open`, `admin_doc_download`); `docs/report/PR_12B2_REPORT.md`.
- **Known gaps / comments:** provider support is intentionally bounded; not every storage provider is a direct delivery surface.

---

## 8. Doctor scenarios

### DOC-001 — Open upcoming queue
- **Actor / persona:** Doctor.
- **Preconditions:** Doctor role binding exists.
- **Entry point:** `/today_queue` or `/next_patient`.
- **Main flow:** doctor opens queue, inspects current and upcoming patients, and jumps into booking context.
- **Outbound messages / notifications:** queue panel render.
- **State / object transitions:** read/navigation until explicit action is taken.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/doctor/router.py` (`today_queue`, `next_patient`); doctor operational reports.
- **Known gaps / comments:** queue is intentionally operational and narrow, not a giant chart dashboard.

### DOC-002 — Open current booking
- **Actor / persona:** Doctor.
- **Preconditions:** Booking is visible to this doctor.
- **Entry point:** queue row or `/booking_open`.
- **Main flow:** doctor opens booking card and enters treatment-related operational context.
- **Outbound messages / notifications:** booking card render.
- **State / object transitions:** read/navigation until doctor acts.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/doctor/router.py` (`booking_open`, booking callbacks); `docs/72_admin_doctor_owner_ui_contracts.md`.
- **Known gaps / comments:** none blocking at base acceptance level.

### DOC-003 — Mark in service / start encounter
- **Actor / persona:** Doctor.
- **Preconditions:** Booking is visible and in a valid state.
- **Entry point:** booking action from doctor booking card.
- **Main flow:** doctor marks booking progression to `checked_in`, `in_service`, or similar operational state.
- **Outbound messages / notifications:** updated card/state messaging.
- **State / object transitions:** booking state transitions through doctor-allowed actions.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/application/doctor/operations.py` (`DOCTOR_ALLOWED_ACTIONS`); `app/interfaces/bots/doctor/router.py` (`booking_action`).
- **Known gaps / comments:** encounter lifecycle is intentionally bounded and does not try to mimic a giant EMR from day one.

### DOC-004 — Add quick note / see relevant patient context
- **Actor / persona:** Doctor.
- **Preconditions:** Doctor can access the patient/booking.
- **Entry point:** `/patient_open`, `/chart_open`, `/encounter_open`, `/encounter_note`.
- **Main flow:** doctor opens current patient/chart context and adds or reviews concise encounter information.
- **Outbound messages / notifications:** chart/encounter note response.
- **State / object transitions:** encounter or chart note content updates.
- **Current implementation status:** **Partial**.
- **Evidence:** `app/interfaces/bots/doctor/router.py` (`patient_open`, `chart_open`, `encounter_open`, `encounter_note`); clinical/chart docs and reports.
- **Known gaps / comments:** baseline context exists, but this is still intentionally narrower than a full deep-chart workplace.

### DOC-005 — Issue recommendation
- **Actor / persona:** Doctor.
- **Preconditions:** Doctor has valid patient/booking context.
- **Entry point:** `/recommend_issue`.
- **Main flow:** doctor issues recommendation linked to patient/booking context.
- **Outbound messages / notifications:** recommendation creation feedback and later patient/admin visibility.
- **State / object transitions:** recommendation created/issued.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/doctor/router.py` (`recommend_issue`); recommendation service; related product docs.
- **Known gaps / comments:** recommendation analytics and broader uptake reporting belong to owner/business layer.

### DOC-006 — Open linked care-order from booking
- **Actor / persona:** Doctor.
- **Preconditions:** Booking has linked care-order context.
- **Entry point:** booking linked object action.
- **Main flow:** doctor opens bounded care-order panel from booking and returns safely.
- **Outbound messages / notifications:** localized care-order panel.
- **State / object transitions:** mainly read/navigation.
- **Current implementation status:** **Implemented**.
- **Evidence:** `docs/report/PR_12B1_REPORT.md`; `app/interfaces/bots/doctor/router.py` linked care-order branch after convergence.
- **Known gaps / comments:** doctor is not the warehouse operator; this is a clinical/operational awareness surface, not a fulfillment console.

### DOC-007 — Complete encounter / visit
- **Actor / persona:** Doctor.
- **Preconditions:** Booking is in a progressable state.
- **Entry point:** doctor booking action.
- **Main flow:** doctor marks booking as completed and finishes visit-side operational progression.
- **Outbound messages / notifications:** updated booking card/state messaging.
- **State / object transitions:** booking progresses to `completed` when valid.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/application/doctor/operations.py`; `app/interfaces/bots/doctor/router.py` (`booking_action`).
- **Known gaps / comments:** deeper post-visit document delivery and broader patient follow-up are separate layers.

### DOC-DOC-001 — Doctor document registry / open / download
- **Actor / persona:** Doctor.
- **Preconditions:** Generated document exists or can be generated for booking context.
- **Entry point:** `/doc_generate`, `/doc_registry_booking`, `/doc_open`, `/doc_download`, `/doc_regenerate`.
- **Main flow:** doctor generates or opens a booking-linked document and downloads the artifact when supported.
- **Outbound messages / notifications:** registry, metadata card, Telegram document delivery.
- **State / object transitions:** generated artifact created or retrieved.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/doctor/router.py`; `docs/report/PR_12B2_REPORT.md`; `docs/65_document_templates_and_043_mapping.md`.
- **Known gaps / comments:** this is a staff-side document baseline, not patient delivery.

---

## 9. Owner scenarios

### OWN-001 — Open daily digest
- **Actor / persona:** Owner.
- **Preconditions:** Owner role binding exists.
- **Entry point:** `/owner_digest`.
- **Main flow:** owner opens latest digest with booking and alert counts.
- **Outbound messages / notifications:** digest message.
- **State / object transitions:** read-only projection consumption.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/owner/router.py` (`owner_digest`); owner analytics service.
- **Known gaps / comments:** digest is intentionally compact, not a BI warehouse.

### OWN-002 — Open live clinic snapshot
- **Actor / persona:** Owner.
- **Preconditions:** Owner role binding exists.
- **Entry point:** `/owner_today`.
- **Main flow:** owner opens current clinic snapshot for today.
- **Outbound messages / notifications:** snapshot message.
- **State / object transitions:** read-only projection consumption.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/owner/router.py` (`owner_today`); owner analytics service.
- **Known gaps / comments:** current snapshot is compact; deeper drilldowns remain limited.

### OWN-003 — Open anomaly / exception view
- **Actor / persona:** Owner.
- **Preconditions:** Owner alerts exist.
- **Entry point:** `/owner_alerts`, `/owner_alert_open`.
- **Main flow:** owner lists alerts and opens a specific anomaly/exception item.
- **Outbound messages / notifications:** alert list and alert detail.
- **State / object transitions:** read-only analytics/alert consumption.
- **Current implementation status:** **Implemented**.
- **Evidence:** `app/interfaces/bots/owner/router.py` (`owner_alerts`, `owner_alert_open`).
- **Known gaps / comments:** alert model exists, but owner still lacks many planned business drilldowns.

### OWN-004 — Open care-performance view
- **Actor / persona:** Owner.
- **Preconditions:** Care-commerce metrics are expected at owner level.
- **Entry point:** dedicated owner care-performance surface.
- **Main flow:** planned owner view for attach-rate / care-performance visibility.
- **Outbound messages / notifications:** care-performance summary.
- **State / object transitions:** read-only analytics consumption.
- **Current implementation status:** **Missing**.
- **Evidence:** `docs/50_analytics_and_owner_metrics.md` and `docs/70_bot_flows.md` describe the need; current owner router does not expose a dedicated care-performance command.
- **Known gaps / comments:** owner surface today is digest/snapshot/alerts baseline, not the full planned analytics set.

---

## 10. Cross-role notification map

The key outbound message classes currently intended by the product are:

| Notification class | Primary recipient(s) | Current role meaning | Current status |
|---|---|---|---|
| Booking creation / success | Patient | Confirms created booking and starts reminder lifecycle | Implemented |
| Reminder chain | Patient | Confirms / nudges / routes reschedule-cancel decisions | Implemented |
| Reminder issue / no-response visibility | Admin, Owner | Makes operational failures visible for rescue or oversight | Partial |
| Reschedule / cancel updates | Patient, Admin | Keeps booking state aligned across patient and workdesk | Implemented |
| Recommendation / aftercare | Patient, Doctor, Admin | Clinical follow-up and product-bridge layer | Partial |
| Care reserve / pickup updates | Patient, Admin | Connects patient care order with reception fulfillment | Implemented |
| Generated document artifact status | Admin, Doctor | Staff-side export/open/download baseline | Implemented |
| Patient-facing document delivery | Patient | Post-visit export/aftercare artifact delivery | Missing |
| Owner digest / alerts | Owner | Aggregated clinic visibility | Implemented |

---

## 11. Current coverage snapshot

| Scenario ID | Role | Status | Primary evidence | Next action if partial/missing |
|---|---|---|---|---|
| PAT-001 | Patient | Partial | patient router + booking docs | polish `/start`, add true home CTA panel, explicit review-before-finalize, human labels in success copy |
| PAT-002 | Patient | Partial | patient router + booking docs | add stronger continuity-first UX for returning patients |
| PAT-003 | Patient | Implemented | patient router + reminder flows | keep regression coverage |
| PAT-004 | Patient | Implemented | patient router reschedule callbacks | keep regression coverage |
| PAT-005 | Patient | Implemented | patient router cancel callbacks | keep regression coverage |
| PAT-006 | Patient | Implemented | reminder callback flow | keep regression coverage |
| PAT-007 | Patient | Partial | recommendation routes + care docs | deepen aftercare/document bridge |
| PAT-008 | Patient | Implemented | care router flows + admin pickup docs | keep regression coverage |
| PAT-DOC-001 | Patient | Missing | document docs + convergence reports | design patient-facing artifact delivery |
| ADM-001 | Admin | Implemented | admin workdesk routes | continue workdesk polish only as needed |
| ADM-002 | Admin | Implemented | admin patient search/list routes | add governance/reporting companion surfaces separately |
| ADM-003 | Admin | Implemented | booking open/card routes | keep regression coverage |
| ADM-004 | Admin | Implemented | admin booking actions | keep regression coverage |
| ADM-005 | Admin | Implemented | admin reschedules | keep regression coverage |
| ADM-006 | Admin | Partial | confirmations/issues queues | strengthen rescue/issue-control acceptance where needed |
| ADM-007 | Admin | Implemented | PR 12B-1 + admin router | keep regression coverage |
| ADM-008 | Admin | Implemented | PR 12B-1 + pickup routes | separate governance/catalog concerns into 73 |
| ADM-009 | Admin | Partial | calendar projection docs + integration code | build visible admin mirror surface if product still wants it |
| ADM-DOC-001 | Admin | Implemented | export services + admin doc commands | embed deeper into contextual workdesk only if needed |
| ADM-DOC-002 | Admin | Implemented | PR 12B-2 + admin doc routes | keep provider support bounded |
| DOC-001 | Doctor | Implemented | doctor queue routes | keep regression coverage |
| DOC-002 | Doctor | Implemented | doctor booking open | keep regression coverage |
| DOC-003 | Doctor | Implemented | doctor booking actions | keep regression coverage |
| DOC-004 | Doctor | Partial | doctor chart/patient/note routes | deepen only if operationally needed |
| DOC-005 | Doctor | Implemented | recommendation issue route | keep regression coverage |
| DOC-006 | Doctor | Implemented | PR 12B-1 + doctor router | keep regression coverage |
| DOC-007 | Doctor | Implemented | doctor booking actions | keep regression coverage |
| DOC-DOC-001 | Doctor | Implemented | doctor doc routes + PR 12B-2 | keep provider support bounded |
| OWN-001 | Owner | Implemented | owner digest route | extend only if business needs real drilldowns |
| OWN-002 | Owner | Implemented | owner today route | extend only if business needs real drilldowns |
| OWN-003 | Owner | Implemented | owner alerts routes | extend only if business needs real drilldowns |
| OWN-004 | Owner | Missing | owner metrics docs only | define and implement care-performance owner surface |

---

## 12. Relationship to governance and next-step control

This document answers:
- what real users and staff should be able to do;
- how far each role journey has progressed.

It does **not** answer, in full:
- who governs patient base as a clinic asset;
- how doctor/staff registry changes are managed;
- how chief-doctor authority should be represented;
- what belongs in Google Sheets vs DentFlow vs Google Calendar;
- how generated document families should be governed beyond current staff baseline.

Those questions are covered in:
- `docs/73_governance_and_reference_ops.md`

The practical reading order should now be:
1. `docs/70_bot_flows.md` — role map
2. `docs/71_role_scenarios_and_acceptance.md` — scenario acceptance reality
3. `docs/73_governance_and_reference_ops.md` — governance/master-data operating model
4. `booking_docs/*` and UI contract docs — lower-level detail
