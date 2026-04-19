# Card Media and Navigation Rules

> Canonical media behavior, navigation flow, and panel transition rules for the DentFlow unified card system.

## 1. Purpose

This document defines the **media and navigation behavior** for the unified card system in DentFlow.

If:
- `16_unified_card_system.md` defines the shared shell,
- `16-1_card_profiles.md` defines profile payloads,
- `16-2_card_callback_contract.md` defines callback semantics,

then this document defines:

- how cards open from lists and return back;
- how compact and expanded modes transition;
- how media is shown on demand;
- when to edit an existing message and when to send a new one;
- how gallery/media navigation works;
- how nested object cards preserve source context;
- how to keep Telegram chat clean.

This document is critical because even a good card shell can become miserable if:
- media floods the chat,
- Back returns to nonsense,
- cards lose their list context,
- gallery navigation breaks state,
- or every detail action creates a new message forever.

That is how otherwise decent Telegram systems become exhausting to use.

---

## 2. Core principle

# DentFlow cards must preserve context and minimize chat clutter.

That means:

- media should be on-demand, not always dumped inline;
- object navigation must preserve where the user came from;
- Back must mean something precise;
- list → card → expanded → nested object → back must remain coherent;
- edits should be preferred over new messages when interaction semantics allow it.

This is not aesthetics.
This is operational survival.

---

## 3. Scope

This document applies to all card-based DentFlow UI flows, including:
- product cards
- patient cards
- doctor cards
- booking cards
- recommendation cards
- care order cards

And to all related navigation patterns:
- list to card
- card to expanded details
- card to media
- card to linked object
- back to source list
- pagination / load more
- queue views
- recommendation-driven product opens
- doctor/admin operational object opens

This document does **not** redefine the callback payload grammar in full.
It relies on:
- `16-2_card_callback_contract.md`

---

## 4. Navigation model overview

The navigation model is built on the following layers:

1. **source panel**
2. **object card compact**
3. **object card expanded**
4. **media overlay/panel**
5. **nested linked object**
6. **return to source**

These are not six unrelated UI events.
They are one consistent navigation tree.

---

## 5. Source panel rule

Every card interaction starts from a source panel.

Examples:
- search result list
- category product list
- doctor queue
- admin booking list
- recommendation detail
- care order list
- owner alert list

### Core rule
Every object card must know its source panel.
No card may behave as if it appeared from the void.

### Why
Without source panel knowledge:
- Back becomes random
- pager state is lost
- nested opens become confusing
- stale handling becomes inconsistent

---

## 6. Compact → Expanded rule

Compact mode is the first-class open mode.

### Rule
A card should normally open in `compact` mode first.

Then:
- `Подробнее`
- or a profile-specific open-details action
moves it to `expanded`

### Why
This keeps:
- first contact light
- scanning fast
- Telegram messages readable

### Expanded mode must:
- remain the same object
- preserve the same source context
- preserve the same identity
- not become a different screen species

---

## 7. Back behavior rules

Back behavior must be deterministic.

## 7.1 Back from compact card
Returns to the source panel.

Examples:
- product compact card opened from recommendation list -> back returns to recommendation product picker
- patient compact card opened from doctor queue -> back returns to doctor queue
- booking compact card opened from admin confirmations -> back returns to admin confirmations

## 7.2 Back from expanded card
Returns to the compact version of the same object if compact still exists in flow,
or directly to source panel if the flow uses replacement rather than two-step card open.

This depends on implementation style, but the rule must be consistent per profile.

## 7.3 Back from media view
Returns to the object card that opened the media.

## 7.4 Back from nested linked object
Returns to the parent object card, not generic home.

Example:
recommendation -> product -> back returns to recommendation detail, not patient home.

### Important
Back must never be “whatever was easiest to code.”

---

## 8. Home vs Back vs Close

These three actions are not the same.

## 8.1 Back
Return to immediate source context.

## 8.2 Home
Return to role home/root surface.
Should be explicit.
Must not silently replace Back.

## 8.3 Close
Dismiss modal or object-view context where appropriate.
Rarely needed in baseline Telegram flow.
Use carefully.

### Rule
If the system conflates Back and Home, the user will get lost quickly.

---

## 9. Message editing vs new message creation

This is one of the most important operational rules.

## 9.1 Default preference
Prefer:
# edit / replace / update existing panel

over:
# sending a new message

### Why
Because:
- Telegram chats get polluted quickly
- stale action surfaces multiply
- users lose track of “current object”
- operational work slows down

## 9.2 When editing is preferred
Use edit/replace for:
- switching compact ↔ expanded
- moving inside the same list context
- changing branch on same product card
- paging inside same category/search list
- showing next state of same object card
- rendering stale/error/empty replacement for same context

## 9.3 When a new message may be acceptable
Use a new message only when:
- media behavior requires it and cannot be safely edited into the current card
- Telegram media/edit constraints make replacement impractical
- a distinct parallel object/message truly improves clarity
- the interaction is intentionally persistent and separate

### Important
“Because it was easier” is not a good reason.

---

## 10. Media strategy overview

Media must be:
- on-demand
- context-preserving
- non-spammy
- easy to return from

The card system supports:
- cover
- gallery
- later possibly video

### Default rule
Do NOT auto-open all media when opening a card.

That is how chat cleanliness dies.

---

## 11. Cover behavior

`Cover` is the primary single media preview for an object.

### Cover rules
- shown on explicit action if media is not already embedded
- returns to originating card on Back
- if no cover exists, user gets compact localized feedback
- cover should not create a detached dead-end message

### Acceptable patterns
1. Cover is embedded into expanded card when practical
2. Cover opens as separate message/panel with back/navigation metadata
3. Cover replaces card temporarily with media-aware state

Choose one implementation pattern, but keep it consistent.

---

## 12. Gallery behavior

Gallery is a navigable set of media items.

### Required capabilities
- open gallery from card
- move next/previous where more than one item exists
- preserve current index
- return to originating object card

### Required safety
- missing/removed media item fails safely
- stale gallery action does not jump to unrelated object
- gallery index must not be guessed from the current visible message text

### Display rule
Gallery should still remain bounded.
Do not make the user scroll through a chaotic media dump.

---

## 13. Video behavior

Video is optional in baseline, but rules must still be defined now.

If video is supported:
- it must be on-demand
- it must preserve object context
- it must not auto-play or spam every card open

If video is not yet supported:
- the UI should fail safely
- or simply not expose the button

---

## 14. Media absence behavior

If:
- object has no cover
- object has no gallery
- media reference is broken
- asset no longer exists

the system must:
- fail safely
- return compact localized message
- preserve navigation context

No raw storage/debug garbage in patient/admin/doctor UI.

---

## 15. List navigation rules

List-based contexts need special care.

Examples:
- search results
- category product list
- doctor queue
- admin confirmations
- waitlist
- care order list

## 15.1 Pagination / load more
If the list exceeds compact size:
- use `next / prev`
or
- `load more`

The chosen pattern must preserve:
- current list identity
- filter/query context
- source context
- selected item return path

## 15.2 Return from opened card
When opening an item from a list:
- Back must return to the same list page/cursor if possible
- not to the beginning unless unavoidable

### Why
If every open resets the user to page 1, list browsing becomes punishment.

---

## 16. Nested object navigation

The system must support object-to-object navigation cleanly.

Examples:
- booking -> patient
- patient -> recommendation
- recommendation -> product
- care order -> product
- owner alert -> booking

### Rules
- the child card inherits source context = parent object context
- Back returns to parent card
- the parent card still knows its own source
- nested open must not erase the navigation chain

This is essential for DentFlow because objects are connected by design.

---

## 17. Navigation depth rule

Nested navigation must remain bounded.

Recommended baseline:
- source panel
- object card
- linked object
- maybe one more level

Do not create arbitrarily deep nesting in Telegram.
If the chain becomes too deep, rethink the flow.

Telegram is not a tree explorer.

---

## 18. Source-aware rendering

Cards may render slightly differently depending on source.

Example:
- product opened from recommendation:
  - show recommendation rationale
- same product opened from narrow catalog:
  - show category context instead

This is allowed and useful.

### But:
The shell and navigation model must remain consistent.

Do not create a different species of product card for every source.

---

## 19. State token and navigation freshness

Every meaningful card/media/navigation transition must still rely on stale-safe callback validation.

This means:
- gallery next/prev
- expand/collapse
- branch change
- reserve
- open linked object
- back to paged source list

must all remain bound to:
- correct entity
- correct source context
- correct state token

Navigation must not bypass stale protection.

---

## 20. Empty-state and failure-state navigation

When a list or media action yields:
- no results
- no media
- invalid linked object
- stale context
- permission denial

the user must still remain in a recoverable navigation path.

Examples:
- show compact message with “Back”
- show compact message with “Refresh list”
- show compact message with “Return to card”

Never strand the user in a dead end.

---

## 21. Role-safe navigation

Navigation must not become an access bypass.

Example:
- product opened from patient recommendation is fine
- same callback pattern must not allow patient to jump into admin card variants
- doctor nested open to patient chart summary must still validate access
- admin open to doctor detail must still validate role

Source context does not override access rules.
It only guides navigation.

---

## 22. Panel replacement rules

DentFlow must define when a panel is replaced versus layered.

### Replace panel
Recommended for:
- compact -> expanded
- changing branch on same card
- moving between product pages in same source list
- refresh due to state update
- stale invalidation

### Layer panel / open new
Use sparingly for:
- media if replacement is awkward
- distinctly separate object context that benefits from separate presence
- explicit operator flows where preserving previous panel in chat is useful

The burden of proof should be on sending a new message, not on editing.

---

## 23. Human-readable navigation expectations

The user should always understand:

- what object am I looking at?
- where did I come from?
- what happens if I press Back?
- is this still the same object, just expanded?
- if I open media, how do I return?

If the answer depends on lucky memory, the navigation design is wrong.

---

## 24. Profile-specific navigation examples

## 24.1 Product
category list -> product compact -> product expanded -> cover/gallery -> back -> product expanded -> back -> category list

## 24.2 Patient
search results -> patient compact -> patient expanded -> bookings -> booking compact -> back -> patient expanded -> back -> search results

## 24.3 Booking
admin confirmations -> booking compact -> booking expanded -> patient card -> back -> booking expanded -> back -> confirmations

## 24.4 Recommendation
recommendation list -> recommendation expanded -> linked product -> back -> recommendation expanded -> back -> list

## 24.5 Care order
care order list -> order compact -> order expanded -> linked product -> back -> order expanded -> back -> list

These flows must feel predictable and consistent.

---

## 25. Media and chat cleanliness

This deserves its own explicit statement.

### The system must prefer:
- one current active panel
- on-demand media
- replace over spam
- bounded nesting

### The system must avoid:
- stacking six messages for one object
- forcing the user to scroll up to find the source list
- leaving stale cards with working-looking buttons
- opening media without any way back

DentFlow must feel controlled, not messy.

---

## 26. Telemetry / logging rules for navigation

Navigation/media actions should be loggable enough for debugging, but not noisy.

Okay to log:
- profile
- action
- source context
- entity id
- stale/denied/success result
- gallery index if useful

Do not log:
- sensitive free text
- patient detail payloads
- giant serialized context objects

---

## 27. What this document does NOT define

This document does not define:
- the exact callback grammar in low-level encoding terms
- the exact profile payload fields
- domain access rules in detail

It relies on:
- `16-1_card_profiles.md`
- `16-2_card_callback_contract.md`

This document defines **how movement between cards and media must behave**.

---

## 28. Required consistency outcome

After this document is applied in implementation, the system should feel like:

- one coherent card language
- one coherent back model
- one coherent media model
- one coherent stale policy
- one coherent list navigation pattern

This is how a Telegram system begins to feel “designed” instead of merely “coded”.

---

## 29. Summary

DentFlow card media and navigation rules are built on these ideas:

- source panel is always known
- compact first, expanded second
- Back is deterministic
- media is on-demand
- list context is preserved
- nested opens keep the chain
- stale safety still applies everywhere
- edit/replace is preferred over message spam
- role safety does not disappear during navigation

This is the layer that keeps the card system usable under real operational pressure.

Without it, even good cards become annoying very quickly.
