# DentFlow UI/UX and Product Rules

> Product interaction rules, Telegram UX constraints, and implementation-facing UI discipline for DentFlow.

## 1. Purpose of this document

This document defines the non-negotiable product and UI/UX rules for DentFlow.

Its purpose is to ensure that implementation stays aligned with the intended product behavior and does not drift into:

- chat clutter;
- duplicated panels and duplicated actions;
- desktop-style flows forced into Telegram;
- random handler-specific micro-UX inventions;
- delayed voice/search support;
- hardcoded one-language strings;
- interface regressions caused by isolated feature work.

This document must be treated as a **product constraint document**, not as optional design commentary.

It exists so that CODEX and any future implementer understand that UX discipline in DentFlow is part of the architecture, not decoration added later.

This document complements, but does not replace:

- `README.md`
- `docs/10_architecture.md`
- `docs/20_domain_model.md`
- `booking_docs/50_booking_telegram_ui_contract.md`

If this document and an implementation disagree, the implementation is wrong.

---

## 2. Product stance

DentFlow is a **Telegram-first, phone-first operating system for private dental clinics**.

The user experience must reflect real working conditions:

- doctors often use phones, not desktops;
- administrators operate in interrupt-heavy chat conditions;
- owners consume operational signals quickly and asynchronously;
- patients want short guided flows, not software labyrinths.

Therefore DentFlow UX must be:

- compact;
- directive;
- fast;
- resumable;
- consistent across modules;
- resistant to chat noise;
- optimized for short mobile interactions.

The system may be internally complex.
The visible behavior must stay clear and low-friction.

---

## 3. Global product principles

### 3.1 Telegram-first

DentFlow v1 must feel native to Telegram.

This means:

- inline keyboards for constrained decisions;
- message editing and controlled panel replacement instead of flooding the chat;
- native Telegram affordances where useful;
- no dependency on Mini App / Web App for core workflows;
- no fake desktop UI forced into chat.

### 3.2 Phone-first

All critical workflows must be comfortable on a phone.

The system must assume:

- one-hand usage is common;
- the user may be moving, busy, or between tasks;
- typing long text is expensive;
- fast repeat actions matter more than decorative visual richness.

### 3.3 One active panel

At any point in an active flow, the user should have one primary active panel in chat.

The system must avoid:

- parallel competing panels;
- stale duplicated action surfaces;
- sending a new message for every tiny update if the current panel can be edited safely;
- multiple places to do the same operational action.

This is one of the most important product rules in the entire system.

### 3.4 Clean chat over verbose chat

DentFlow must not behave like a noisy helper bot.

The system should prefer:

- concise prompts;
- panel replacement;
- stateful editing;
- short confirmations;
- compact summaries.

The system should avoid:

- repeated boilerplate;
- giant explanatory paragraphs during operational flows;
- duplicate notifications for the same state change;
- turning the chat into an audit log for routine actions.

### 3.5 Simplicity outside, sophistication inside

The user should never feel the full internal complexity of the system.

A doctor should feel that DentFlow is a fast operational tool.
An administrator should feel that it is a guided control surface.
A patient should feel that it is an attentive booking and follow-up assistant.
An owner should feel that it is a concise signal dashboard.

---

## 4. UX goals by role

## 4.1 Patient

The patient flow must optimize for:

- fast clinic entry;
- low-friction booking;
- clear reminders;
- easy cancellation / rescheduling;
- clear next steps;
- aftercare continuity;
- trust and clarity.

The patient should not be forced into:

- complex menu exploration;
- full schedule browsing;
- unnecessary free-text typing;
- unclear dead ends.

## 4.2 Administrator / reception

The admin flow must optimize for:

- patient lookup speed;
- queue handling speed;
- compact case review;
- quick status changes;
- controlled exception handling;
- low message noise;
- one-screen operational context.

The admin should not need to navigate a maze of menus to do routine actions.

## 4.3 Doctor

The doctor flow must optimize for:

- short interactions;
- fast patient retrieval;
- quick review of current context;
- one-tap recommendation actions where possible;
- minimum typing;
- fast note/status updates;
- use during interrupted clinical work.

The doctor interface must not assume long desk sessions.

## 4.4 Owner

The owner flow must optimize for:

- daily digest readability;
- quick understanding of clinic state;
- anomaly visibility;
- drill-down only when needed;
- signal density without clutter.

The owner interface must not feel like an admin panel transplanted into chat.

---

## 5. Navigation model

### 5.1 Navigation must be shallow

DentFlow should avoid deep menu trees.

Recommended stance:

- shallow top-level entry points;
- direct contextual actions;
- back navigation that is predictable;
- no hidden branches that require memory gymnastics.

### 5.2 Contextual over hierarchical

Whenever possible, the next action should come from current context, not from forcing the user to climb back through a global menu.

Examples:

- from a patient card -> booking, note, recommendation, contact;
- from a booking panel -> reschedule, change doctor, change date;
- from a care recommendation -> reserve, dismiss, send explanation;
- from an owner digest -> open the related slice directly.

### 5.3 Back means “back in the current flow”

The back action must be deterministic.

It must not randomly dump the user into unrelated menus.

If a flow is linear, back should return to the previous meaningful step.
If a panel is contextual, back should return to the panel that opened it.

### 5.4 No duplicate entry points for the same action

The same operational action should not appear in three different inconsistent places.

A user should have one obvious way to:

- edit booking parameters;
- reserve a care product;
- reopen a patient card;
- change language;
- run a patient search.

---

## 6. Panel lifecycle rules

### 6.1 Primary rule

If a panel can be edited in place safely, prefer editing over sending a new message.

### 6.2 New message is justified when

A new message may be sent when:

- a final confirmation must remain visible;
- a notification is a durable event the user may need later;
- editing the old message would cause confusion;
- Telegram limitations make editing unsafe;
- the flow intentionally transitions from one context into another.

### 6.3 Replaced panels must not leave confusing ghosts

When a panel is superseded, stale buttons must not remain dangerous.

Required strategies:

- edit old message;
- mark old panel as expired;
- reject stale callbacks gracefully;
- show a concise recovery action.

### 6.4 Long-running flows must be resumable

If the user leaves mid-flow and returns later, the system should:

- recover the active state when possible;
- explain briefly what is pending;
- offer resume / restart where appropriate.

---

## 7. Input model rules

DentFlow uses a **hybrid input model**.

The system must deliberately choose between:

- buttons;
- free text;
- voice input;
- native Telegram contact/location/media;
- structured quick actions.

### 7.1 Buttons are preferred when

Buttons should be used for:

- bounded choices;
- status changes;
- confirms/cancels;
- short routing decisions;
- slot selection;
- language switching;
- “show more” / “change X” actions.

### 7.2 Free text is allowed when it reduces friction

Free text is appropriate for:

- date input;
- surname input;
- doctor code input;
- quick note;
- clarification for “other”;
- recovery from ambiguous search.

Free text is not appropriate for:

- service taxonomy selection;
- routine binary decisions;
- navigation;
- states that need precise controlled values.

### 7.3 Voice input is first-class, not an afterthought

Voice-assisted retrieval and voice-friendly entry points must exist early.

Priority use cases:

- find patient;
- open patient quickly;
- search by spoken name/phone fragment;
- short operational notes if supported later.

Voice should not initially try to replace the whole interface.
It should solve narrow high-value actions.

### 7.4 Native Telegram inputs

Use native Telegram features where they reduce friction:

- contact share for phone confirmation;
- location share when needed;
- photo/file upload for medical context or documents.

---

## 8. Search UX rules

Search is a first-class product surface, not a secondary utility.

### 8.1 Search must be globally reachable

Patient search must be easy to access from admin and doctor flows.
It should not be buried in menus.

### 8.2 Search must be fast to start

There should be no long setup before searching.
The flow should allow:

- type and search;
- tap voice and search;
- tap recent patient if applicable.

### 8.3 Search must tolerate real-world mess

The user experience must support:

- partial names;
- transliteration differences;
- fuzzy matches;
- multilingual names;
- phone-based lookup;
- voice-to-text errors.

### 8.4 Search results must be actionable

A result should not be a dead label.
A search result card must offer direct actions such as:

- open patient;
- book;
- view last appointment;
- add note;
- message / contact path where relevant.

### 8.5 Search failure must degrade gracefully

If exact retrieval fails, the system should:

- show close candidates;
- propose manual refinement;
- allow voice retry;
- allow creating a new patient only through controlled flow.

---

## 9. Booking UX rules

Booking is a first-class subsystem.
Detailed booking interaction rules live in:

- `booking_docs/10_booking_flow_dental.md`
- `booking_docs/40_booking_state_machine.md`
- `booking_docs/50_booking_telegram_ui_contract.md`

This document sets only project-level booking UX rules.

### 9.1 Booking must be wizard-first

Do not expose full calendars or raw schedules as the primary experience.

### 9.2 Booking must reduce choice overload

Show:

- constrained service choices;
- short urgency/date choices;
- short time window choices;
- 3 to 5 best slot proposals.

Do not show:

- giant doctor catalogs by default;
- entire daily schedules;
- entire month grids;
- all possible slots at once.

### 9.3 Booking must stay editable within the flow

The user must be able to change:

- date preference;
- time window;
- doctor preference;
- slot choice.

These edits should feel like surgical adjustments, not full restarts unless necessary.

### 9.4 Booking must protect premium capacity

Public booking UX must respect policy constraints for premium doctors.
The interface must not accidentally reveal or overflow protected resources.

---

## 10. Patient card rules

Patient cards are central operational UI objects.

A patient card should present:

- essential identity;
- preferred contact path;
- current booking state if relevant;
- concise recent activity;
- contextual actions.

A patient card should avoid:

- massive biography dumps;
- dense historical noise by default;
- too many buttons at once;
- exposing projection-only values as if they were canonical truth.

Recommended first actions from a patient card:

- book / rebook;
- open active booking;
- add note;
- send recommendation;
- open care order context;
- view recent visits or booking history summary.

---

## 11. Care-commerce UX rules

Care-commerce must feel like medically contextual continuation, not random retail intrusion.

### 11.1 Recommendation-first, catalog-second

The primary UX is not “browse products”.
The primary UX is:

- the system explains why a product is relevant;
- the system offers a small curated choice;
- the user can reserve, buy, or dismiss.

### 11.2 Keep product choice small

Do not dump large catalog grids into Telegram chat.

The preferred pattern is:

- recommendation reason;
- 1 to 3 suggested options;
- direct next action.

### 11.3 Fulfillment options must be explicit

When relevant, the interface should clearly state available options:

- reserve for clinic pickup;
- buy now;
- pay at pickup if supported;
- add to next visit handling.

### 11.4 Recommendation messaging must feel like care

Copy should emphasize:

- treatment support;
- aftercare;
- prevention;
- context relevance.

It must not feel like aggressive upsell spam.

---

## 12. Owner UX rules

Owner UX must prioritize signals over detail.

### 12.1 Digest-first

The owner should receive concise digests first, with drill-down available on demand.

### 12.2 No operator clutter

Owner panels must not mirror admin operational detail unless explicitly requested.

### 12.3 Anomalies over vanity dashboards

The most useful owner surface is often:

- what changed;
- what is broken;
- where conversion dropped;
- where no-show increased;
- where care-commerce underperforms.

### 12.4 Drill-down must stay bounded

The owner should be able to go deeper, but not descend into an unstructured swamp of raw records.

---

## 13. Multifunction control patterns

DentFlow may use compact multifunction controls where the pattern is clear, reusable, and learnable.

The reference stance comes from proven patterns in prior systems such as:

- one-tap value change;
- typed adjustment after activation;
- compact stepper-like controls;
- one-panel edit behavior.

### 13.1 Rule for multifunction controls

A multifunction control is allowed only when:

- its behavior is stable across the system;
- it reduces friction materially;
- it does not hide dangerous or surprising actions;
- it can be explained once and then reused consistently.

### 13.2 No one-off cleverness

Do not invent unique “smart” controls for only one screen.
If a compact pattern exists, it should become a pattern, not a trick.

### 13.3 Priority pattern example

An edit control may support:

- quick default action on tap;
- structured text adjustment after activation;
- one-panel confirmation.

But if the same logic cannot be understood or reused elsewhere, do not introduce it.

---

## 14. Message copy and microcopy rules

### 14.1 Concise and operational

DentFlow copy must be short, direct, and unambiguous.

### 14.2 One question per step

Operational flows should ask one question at a time.

### 14.3 Labels must match user intent

User-facing labels should reflect how people think, not how the database is named.

Examples:

- “Болит зуб” is good;
- raw internal taxonomy slugs are not.

### 14.4 Confirmations must be explicit

After important actions, the user must know what happened.

Good examples:

- booking confirmed;
- reservation created;
- reminder scheduled;
- language changed.

### 14.5 Error copy must recover, not just complain

Error states should explain:

- what failed;
- whether the state is safe;
- what the user can do next.

---

## 15. Localization and i18n rules

Localization is not an afterthought.

DentFlow must start with:

- Russian as primary/default language;
- English as a supported language from the first implementation wave.

The system must also be easy to extend later to languages such as:

- Georgian;
- Polish;
- others.

### 15.1 No hardcoded UI strings in handlers

Handlers must not become the final home of message text.
All user-facing strings should be resolved through localization keys.

### 15.2 Language selection must be available in bot options

Changing interface language must be a normal user action, not an admin hack.

### 15.3 Localization must apply across flows

The selected language should affect:

- prompts;
- buttons;
- confirmations;
- reminders;
- owner/admin digest text where relevant.

### 15.4 Domain values may stay canonical internally

Internal enums, slugs, and event names may remain canonical in one technical language.
User-facing rendering must be localized.

---

## 16. Notifications and reminder UX rules

### 16.1 Notifications must be meaningful

Do not send reminders or operational messages “because we can”.
Each outbound message should have a clear reason.

### 16.2 Message timing must match user need

Examples:

- booking confirmation immediately;
- reminder in advance;
- post-visit care message after the visit;
- care recommendation tied to relevant treatment context.

### 16.3 Avoid duplicate outbound noise

If the same state change already generated a durable message, do not produce near-identical duplicates.

### 16.4 Reminders must allow action

A reminder should often include a direct action path where appropriate:

- confirm;
- reschedule;
- cancel;
- open instructions.

---

## 17. Sheets sync and external editing rules

DentFlow may rely on Google Sheets or similar low-friction operational tools early.
This must be reflected as a product and implementation rule, not treated as accidental side tooling.

### 17.1 Sync is an integration layer, not product truth

Google Sheets may support operational editing, but must not silently replace canonical truth in core domains.

### 17.2 UI must not depend on spreadsheet shape leaking into chat

Users should not see spreadsheet terminology or awkward field structures just because sync exists.

### 17.3 Sync changes must reconcile cleanly

When sync affects bookable services, product lists, or operational options, UI behavior must remain predictable and localized.

---

## 18. Performance and responsiveness rules

### 18.1 Fast perceived response matters

Telegram UX feels broken quickly if nothing happens.
Where full work takes time, the system should still acknowledge the action promptly.

### 18.2 Heavy operations must not freeze chat flows

Search, ranking, sync, analytics, and external lookups should not make the active flow feel dead.

### 18.3 Recovery beats silent failure

If a panel cannot be updated due to stale state or temporary subsystem issues, the user should receive a short recovery path.

---

## 19. Product guardrails for implementation

These are not pure UI notes. They are implementation constraints.

### 19.1 New features must fit existing navigation

Do not bolt new functionality on as isolated menu islands.
Every new feature must answer:

- where it lives;
- how it is reached;
- how it returns;
- what panel owns it;
- what stale-state behavior exists.

### 19.2 New features must respect one-panel discipline

No module may ignore the one-active-panel rule unless there is a strong explicit justification.

### 19.3 New flows must be localizable from day one

A feature without localization wiring is incomplete.

### 19.4 New operational flows must define search entry and return path

If a user enters via patient search, the flow must define how they return or continue from the patient context.

### 19.5 UI work must not outrun state design

If a flow has no clear state model, it is not ready to be implemented. Pretty buttons do not fix conceptual chaos.

---

## 20. Relationship to development discipline

The system should be implemented under these complementary engineering rules:

- baseline-only migration discipline during active development;
- no migration pile-up while the model is still changing heavily;
- reuse of existing proven UI patterns where applicable;
- source-of-truth separation between transactional data and projections.

A dedicated development-rules document may expand this later, but implementers should already behave accordingly.

---

## 21. Acceptance checklist for any new UI flow

Before a new flow is accepted, it should satisfy the following questions:

1. Is the flow Telegram-native?
2. Is it phone-friendly?
3. Does it respect the one-active-panel rule?
4. Does it avoid duplicate operational spam?
5. Is the input model deliberate?
6. Is there a clear back/return path?
7. Is stale callback behavior defined?
8. Is localization wired from the start?
9. Does it fit existing navigation patterns?
10. Does it degrade gracefully if search/analytics/sync is unavailable?
11. Does it preserve user-facing simplicity?
12. Is it consistent with booking and domain documents?

If the answer to several of these is “no”, the flow is not ready.

---

## 22. Final rule

DentFlow must not become a collection of individually “working” handlers that together form a confusing product.

It must behave like one coherent operating system:

- one interaction philosophy;
- one navigation discipline;
- one panel discipline;
- one localization approach;
- one product logic.

That coherence is not optional.
It is one of the main competitive advantages of the system.
