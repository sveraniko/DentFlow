# Unified Card System

> Canonical unified card shell and interaction model for DentFlow Telegram UI.

## 1. Purpose

This document defines the **unified card system** for DentFlow.

Its goal is to stop the project from growing a separate ad hoc UI pattern for every entity:
- one card for product,
- another random card for patient,
- a third card for doctor,
- a fourth card for booking,
- and five more accidental inventions later.

Instead, DentFlow must use:

# one unified card shell  
# + profile-specific content blocks  
# + profile-specific action sets

This document is the foundation for all future card-based UI layers.

It is intentionally strict because interface improvisation is one of the fastest ways to turn a strong product into a confusing mess.

---

## 2. Core thesis

The card system is not a visual decoration layer.

It is a **runtime interaction contract** for Telegram.

A card in DentFlow must simultaneously solve:

- compact summary view
- expandable detail view
- source-aware navigation
- safe callback behavior
- media handling
- profile-specific actions
- list integration
- panel consistency
- one-active-panel discipline

This is why the card system must be designed once and reused everywhere.

---

## 3. Scope

This document defines the **shared shell** for cards across the system.

It applies to:
- product card
- patient card
- doctor card
- booking card
- recommendation card
- care order card
- future operational object cards if they fit the same model

This document does **not** define the exact content of each profile in detail.
That belongs to follow-up docs:
- `16-1_card_profiles.md`
- `16-2_card_callback_contract.md`
- `16-3_card_media_and_navigation_rules.md`

This document defines the **common shell and common behavior rules**.

---

## 4. Design goals

The unified card system must be:

### 4.1 Compact
Telegram is not a desktop dashboard.
Cards must show the minimum useful information first.

### 4.2 Expandable
The user must be able to reveal more detail without being thrown into a giant new UI world.

### 4.3 Context-aware
A card must know where it was opened from and where “Back” returns.

### 4.4 Role-safe
A card must not expose content/actions the current role should not see.

### 4.5 Profile-consistent
The shell remains the same, while content/actions vary by entity profile.

### 4.6 One-active-panel compliant
The system must avoid chat spam and stale clutter.

### 4.7 Media-aware
Cards must support on-demand media handling consistently.

### 4.8 Callback-safe
A stale button must not mutate the wrong object or the wrong state.

---

## 5. What a card is

A card is a **rendered object panel** with a stable interaction model.

Each card has:
- entity identity
- card profile
- render mode
- source context
- visible content blocks
- action set
- navigation contract

This means a card is not just text.
It is a **stateful UI object**.

---

## 6. Core card anatomy

Every card, regardless of profile, is composed from the same top-level zones.

## 6.1 Header zone
Contains:
- title
- subtitle / secondary line
- optional badge chips
- optional quick state indicators

This must immediately answer:
- what object is this?
- why do I care?

## 6.2 Media zone
Optional.
Contains:
- cover preview
- media action buttons
- gallery/video entry

The media zone is on-demand aware.
It must not always flood the chat.

## 6.3 Meta zone
Compact structured facts:
- price
- availability
- phone hint
- status
- branch
- doctor
- date/time
depending on profile

This zone must stay scan-friendly.

## 6.4 Detail zone
Only visible in expanded mode or on detail open.

Contains:
- longer description
- rationale
- summary text
- structured secondary fields

This is where more context lives, but it must still remain bounded.

## 6.5 Action zone
Profile-specific actions live here.

Examples:
- `Подробнее`
- `Рекомендации`
- `Записи`
- `Забрать в клинике`
- `Изменить филиал`
- `Сегодня`
- `Подтвердить`
- `Отменить`

The action zone must remain organized and predictable.

## 6.6 Navigation zone
Contains:
- back
- previous/next page where relevant
- close / collapse where relevant
- return to source panel

This is a separate concern and must not be improvised per handler.

---

## 7. Card modes

The card system must support explicit modes.

## 7.1 `compact`
Purpose:
- fast scan
- list row replacement
- summary state
- operational density

This is the default mode.

### Compact mode rules
- show only high-signal content
- do not show long descriptions
- show only the minimum safe buttons
- must fit comfortably in Telegram without becoming a wall

## 7.2 `expanded`
Purpose:
- show richer details
- reveal structured secondary information
- add media/navigation options
- preserve same object context

### Expanded mode rules
- still bounded
- no giant dump of every field
- must remain related to the same card shell, not a new random interface

## 7.3 `list_row`
Optional internal render mode for lists.
This is not a separate conceptual UI.
It is a compressed card representation inside a list/picker.

## 7.4 `inline_picker`
Optional profile-specific mode for selection flows.
Still must reuse card semantics, not invent separate display logic.

---

## 8. Card behavior rules

## 8.1 Compact first
All cards open in compact mode unless there is a strong reason not to.

## 8.2 Expand by explicit action
Expansion is user-triggered.
Typical action:
- `Подробнее`
- or profile-specific detail action

## 8.3 Same object, same identity
Expanded mode must not become a different object context.

## 8.4 Minimal surprise
If a user opens a card from a list, then expands, they must still feel in the same object flow.

---

## 9. Context model

Every card must carry **source context**.

Examples:
- opened from search results
- opened from recommendation
- opened from queue
- opened from patient card
- opened from booking detail
- opened from category list
- opened from owner alert

This matters because:
- back navigation depends on it
- action availability may depend on it
- list paging may depend on it
- stale callback checks may depend on it

### Core rule
No card may exist as “floating contextless object” once interactive actions are involved.

---

## 10. Navigation contract

The card system must define clear return behavior.

## 10.1 Back
Back returns to the **source panel**, not just some generic home.

## 10.2 Home
Home is explicit and should not be mixed with Back.

## 10.3 Close
Close is only used where the object flow is modal enough to justify it.

## 10.4 List paging
If card is part of a paged list:
- previous/next or load-more must preserve context
- expanding an item must not destroy the list context

---

## 11. One-active-panel discipline

This is non-negotiable.

DentFlow must not produce endless message spam for every card state mutation.

### Required behavior
- edit/replace/update current panel when possible
- only create new message if the interaction semantics truly need it
- stale action panels must be invalidated clearly
- source panel and opened card must not multiply uncontrollably

### Why
Because Telegram quickly becomes unusable if every detail open becomes a new chat block.

---

## 12. Callback identity model

Every interactive card action must be tied to:

- entity type
- entity id
- card profile
- card mode
- source context
- current page/index where relevant
- state token/version where needed

This is required so that:
- stale buttons fail safely
- wrong-entity mutation does not happen
- actions stay bound to the correct object

This system must be formalized in `16-2_card_callback_contract.md`.

---

## 13. Stale callback rule

A stale callback must:

- not mutate data
- not open a different object silently
- not reuse unrelated context
- fail safely with compact localized feedback

Examples:
- “карточка устарела”
- “обновите список”
- “объект изменился”

The card system must anticipate staleness instead of pretending it does not exist.

---

## 14. Role-safe rendering

The same card shell may render differently by role.

Example:
- patient product card
- admin product card
- doctor patient card
- admin patient card

The shell remains shared.
The data blocks and actions differ.

### Important rule
Do not create separate UI species where profile-specific configuration is enough.

But also:
do not force all roles into one giant universal card with half the fields hidden.
The shell is shared, not the full payload.

---

## 15. Media model in cards

The card system must support media consistently.

## 15.1 Cover
One compact main visual if available.

## 15.2 Gallery
Additional visuals on demand.

## 15.3 Video
Optional later, but same principles:
on-demand, explicit, not noisy.

## 15.4 Missing media
Missing media must not break the card.
The card must degrade gracefully.

---

## 16. Media interaction rules

Media should generally be:
- on-demand
- context-safe
- returnable to the originating card

Recommended actions:
- `Cover`
- `Gallery`
- maybe `Video` later

Do not auto-dump large media into every list flow.
That destroys chat cleanliness and operational speed.

---

## 17. Content density rules

The shell must separate:

### High-signal content
Belongs in compact mode.

### Secondary content
Belongs in expanded mode.

### Deep content
Usually belongs in a dedicated related screen, not the card itself.

This prevents the common mistake:
“let’s just put all fields into the card and call it done.”

---

## 18. Action density rules

Do not overload compact cards with too many actions.

### Compact mode
Use only:
- primary action(s)
- detail open
- one or two contextually critical actions

### Expanded mode
May include:
- secondary actions
- media actions
- context-specific next-step actions

If a card needs twelve buttons, the design is wrong.

---

## 19. Badge / chip model

Cards may show compact badges/chips for quick meaning.

Examples:
- status
- recommendation
- low stock
- preferred branch
- new
- unresolved
- active flag present

Badges must stay compact and meaningful.
Do not turn them into decorative emoji soup.

---

## 20. Formatting rules

The unified card system should support:
- consistent heading hierarchy
- consistent emoji/icon semantics
- consistent spacing
- consistent separators
- consistent button grouping

The formatting should feel:
- compact
- clean
- legible
- high-signal

Not:
- cluttered
- random
- over-styled
- emotionally unstable

---

## 21. Telegram-specific constraints

The shell must respect Telegram realities:

- limited horizontal space
- callback button constraints
- message edit behavior
- media-message interaction quirks
- chat history clutter risk
- mobile-first reading

This is why:
- compact first
- expanded second
- media on demand
- one-active-panel discipline
all matter so much.

---

## 22. Profile family model

The shell supports a family of card profiles.

At minimum the system must be designed to support:
- `product`
- `patient`
- `doctor`
- `booking`
- `recommendation`
- `care_order`

Each profile will define:
- compact blocks
- expanded blocks
- allowed actions
- media usage
- source contexts
- role filters

The shell remains shared.

---

## 23. Profile transition examples

These examples show how the same shell idea applies.

### Product
- compact: title, price, availability
- expanded: description, branch, media, reserve

### Patient
- compact: name, phone hint, flags
- expanded: recommendations, bookings, chart summary

### Doctor
- compact: name, specialty, branch
- expanded: schedule summary, today load

### Booking
- compact: time, patient, status
- expanded: service, branch, notes, actions

The system becomes consistent through shell reuse, not through identical content.

---

## 24. Source-aware open patterns

The same object may open differently depending on source.

Example: patient card opened from
- search
- booking
- doctor queue
- owner alert

The shell should allow:
- same entity
- same core structure
- different emphasis or actions based on source context

That is the correct way to adapt behavior without reinventing UI.

---

## 25. Error and empty-state handling

Cards and card-driven flows must support safe states.

Examples:
- unavailable object
- no linked recommendations
- no media
- no active booking
- invalid stale callback

These states must be:
- compact
- localized
- bounded
- non-destructive

No stack traces disguised as UI copy.

---

## 26. What the card system is NOT

The card system is not:
- a giant schema for every field in the product
- a replacement for all screens
- a CMS
- a dashboard
- a workaround for weak domain modeling

It is a **unified shell**, not a universal blob.

---

## 27. Why build this before more commerce UX

Because the upcoming commerce and operational layers need:
- product card
- patient card
- doctor card
- booking card

If those are implemented ad hoc first, then unified later,
the system pays twice:
- once to build inconsistent cards
- once to refactor them

That is unnecessary pain.

---

## 28. Required follow-up documents

This document must be followed by:

- `16-1_card_profiles.md`
- `16-2_card_callback_contract.md`
- `16-3_card_media_and_navigation_rules.md`

Without them, Codex will still have room to improvise badly.

---

## 29. Summary

The DentFlow unified card system is:

- one shared shell
- compact-first
- expandable
- source-aware
- role-safe
- callback-safe
- media-aware
- Telegram-appropriate

It is the correct foundation for:
- product cards
- patient cards
- doctor cards
- booking cards
- recommendation cards
- care order cards

The shell is shared.
The content and actions are profile-specific.

That is the right balance.

Anything looser leads to UI drift.
Anything more universal becomes a monster.
