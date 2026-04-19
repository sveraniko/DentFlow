# Card Callback Contract

> Canonical callback payload, state-binding, and stale-safety contract for the DentFlow unified card system.

## 1. Purpose

This document defines the **callback contract** for the unified card system in DentFlow.

Its job is to make explicit:

- what a callback payload must contain;
- how object identity is encoded;
- how source context is preserved;
- how stale protection works;
- how navigation returns to the correct place;
- how role-safe action validation must behave;
- how callbacks must be versioned and kept bounded.

This document exists because card systems do not break on pretty text.
They break on:
- weak callback identity,
- floating context,
- stale button reuse,
- wrong-object mutation,
- back-navigation nonsense,
- and optimistic assumptions that the chat state will somehow remain pure.

That fantasy dies early. This contract prevents it.

---

## 2. Core principle

# Every interactive card action must be bound to:
- the correct entity,
- the correct card profile,
- the correct mode,
- the correct source context,
- the correct role,
- the correct state version where needed.

If one of those is weak or missing, the UI is lying.

---

## 3. Scope

This callback contract applies to all card-based DentFlow Telegram surfaces, including:
- product cards
- patient cards
- doctor cards
- booking cards
- recommendation cards
- care order cards

And to all card interactions such as:
- open compact card
- expand details
- open linked object
- media actions
- next/back/list paging
- operational actions
- reserve / confirm / issue / accept / decline
- quick context opens

This document defines the callback layer.
It does not define the exact data shown in each profile.
That belongs in:
- `16_unified_card_system.md`
- `16-1_card_profiles.md`
- `16-3_card_media_and_navigation_rules.md`

---

## 4. Design goals

The callback contract must be:

- explicit
- compact
- parseable
- versionable
- stale-safe
- source-aware
- role-safe
- future-extensible without becoming unreadable

It must not depend on:
- hidden global state
- implicit “current object”
- wishful back behavior
- lucky ordering of prior panels

---

## 5. What a callback represents

A callback is not “just a button string”.

A callback is a **bounded UI command** that means:

> perform action X  
> on entity Y  
> in profile Z  
> from source context S  
> in mode M  
> against state/version token T  
> for actor role R if valid

This must be true conceptually even if the actual Telegram payload stays compact.

---

## 6. Callback payload layers

The contract has two layers:

## 6.1 Visible compact payload
The actual Telegram callback string.
This must remain short enough for Telegram constraints.

## 6.2 Resolved semantic payload
What DentFlow reconstructs after parsing the compact payload:
- profile
- entity type
- entity id
- action
- mode
- source context
- page/index
- token/version
- optional extras

The runtime may use a compact encoding, but the semantic model must remain explicit.

---

## 7. Required semantic fields

Every card callback must be able to resolve the following fields.

## 7.1 `profile`
Which card profile is being acted on.

Examples:
- `product`
- `patient`
- `doctor`
- `booking`
- `recommendation`
- `care_order`

## 7.2 `entity_type`
Canonical object family.
Usually equals profile, but do not assume forever.

Examples:
- `care_product`
- `patient`
- `doctor`
- `booking`
- `recommendation`
- `care_order`

## 7.3 `entity_id`
Stable identifier of the target object.

Examples:
- `prod_...`
- `pat_...`
- `doc_...`
- `bk_...`
- `rec_...`
- `ord_...`

No card action may rely on “current entity in memory” alone.

## 7.4 `action`
What the callback wants to do.

Examples:
- `open`
- `expand`
- `collapse`
- `back`
- `cover`
- `gallery`
- `reserve`
- `change_branch`
- `recommendations`
- `bookings`
- `confirm`
- `cancel`
- `issue`
- `accept`
- `decline`

Actions must be bounded and explicit.

## 7.5 `mode`
Current card mode.

Examples:
- `compact`
- `expanded`
- `list_row`
- `picker`

This allows rendering and back behavior to remain coherent.

## 7.6 `source_context`
Where the card came from.

Examples:
- `search_results`
- `doctor_queue`
- `booking_detail`
- `recommendation_detail`
- `care_catalog_category`
- `care_order_list`
- `owner_alert`
- `admin_today`
- `admin_confirmations`

This is mandatory.
Without source context, back-navigation becomes dumb guesswork.

## 7.7 `source_ref`
Reference to the source panel/list/session where relevant.

Examples:
- list id
- query token
- page cursor
- workdesk section key
- recommendation id if card was opened from recommendation

Not every callback needs it, but many do.

## 7.8 `page_or_index`
Optional but important for list/pager/card navigation.

Examples:
- page number
- item index
- cursor token
- gallery index

## 7.9 `state_token`
A stale-safety/version token.

This is one of the most important fields.
It allows the system to detect:
- stale cards
- outdated state
- old list generations
- invalid reused buttons

## 7.10 `role_scope`
Not necessarily encoded directly in callback, but validation must know:
- who is allowed to execute this action
- in which role context

Role must not be guessed from the button alone.

---

## 8. Callback namespace model

Callbacks must use a bounded namespace strategy.

Recommended conceptual shape:

`card:<profile>:<action>:<entity_id>:<context...>`

The actual compact implementation may compress this.
But the namespace must stay human-auditable in design.

### Example conceptual callbacks
- `card:product:open:prod_123:src=recommendation:rec_55:page=1:tok=abc`
- `card:patient:bookings:pat_77:src=search_results:q_12:tok=def`
- `card:booking:confirm:bk_908:src=admin_today:page=2:tok=ghi`

Do not build a random bag of callback strings with no systematic grammar.

---

## 9. Callback versioning

The callback contract itself should be versionable.

Recommended baseline:
- one callback version namespace, implicit or explicit
- when major contract shape changes, support parsing old version safely or invalidate clearly

This matters because Telegram buttons can remain in chat history.
Eventually someone will click something old.
The system must behave like an adult when that happens.

---

## 10. Stale callback protection

This section is non-negotiable.

## 10.1 Why stale happens
Staleness is normal because:
- cards get edited
- data changes
- lists refresh
- orders change
- bookings are confirmed elsewhere
- recommendation state changes
- queue contents move
- the user taps an old message from 2 hours ago

This is not exceptional.
It is reality.

## 10.2 Required stale protection rule
If callback state token or source context no longer matches current valid state:
- do not mutate anything
- do not open the wrong object silently
- do not fallback to “current item”
- return safe localized feedback

Examples:
- “карточка устарела”
- “обновите список”
- “объект уже изменился”

## 10.3 What stale safety must block
- confirming already-changed booking from old card
- opening wrong patient from outdated list row
- reserving product with outdated branch/availability assumptions
- accepting recommendation already withdrawn
- acting on outdated owner/admin queue item

---

## 11. State token semantics

The state token does not have to be globally magical.
But it must be meaningful.

Acceptable token sources include:
- message generation token
- list generation token
- object updated_at hash/version
- session revision
- panel revision id

### Requirements
It must change when relevant action context becomes invalid.

It does not need to encode every field.
It only needs to invalidate meaningfully stale callbacks.

---

## 12. Source context contract

Source context is what makes “Back” and contextual action safety correct.

## 12.1 Required source context categories
At minimum support contexts like:
- search result list
- doctor queue
- admin today
- admin confirmations
- recommendation detail
- care category list
- care order list
- booking list
- owner alerts

## 12.2 Back behavior
Back must return to the appropriate source context.
Not just:
- generic home
- or previous random panel

## 12.3 Why source context matters beyond navigation
Some actions are only meaningful in source context.

Example:
- a recommendation-opened product card may show recommendation rationale
- the same product card opened from category list may not

So source context influences not only Back, but content and action shaping too.

---

## 13. Role-safe callback validation

Every action must be validated against role and access scope.

Examples:
- patient cannot execute admin booking action
- doctor cannot open unrelated patient chart through patient card callback
- owner cannot be given silent operational mutation buttons by mistake
- admin cannot issue doctor-only chart action if not allowed

Role validation must happen on action handling, not assumed at rendering time only.

Rendering-time filtering is necessary.
It is not sufficient.

---

## 14. Entity revalidation on action

Even if callback parsed correctly, the system must revalidate:
- entity still exists
- entity is visible to current role
- entity is in valid state for the requested action
- source context is still coherent if required

Example:
A `booking.confirm` callback must still confirm:
- booking exists
- booking belongs to visible scope
- booking is still confirmable
- callback token is not stale

No action may trust the callback string alone.

---

## 15. Safe handling of missing entities

If entity referenced in callback:
- is missing
- archived beyond visibility
- hidden by role rules
- no longer belongs to the current actor scope

then system must:
- fail safely
- return localized compact message
- not reveal whether this is “missing” or “forbidden” in a privacy-leaking way where that matters

This is especially important for:
- patient
- chart
- recommendation
- order
- booking

---

## 16. List and paging contract

Card callbacks often originate in lists.

The contract must support:
- page number or cursor
- item index when relevant
- reload/return to same page
- next/prev page actions
- consistent object open from list row

If list state changes:
- stale page/index must be handled safely
- not mapped to a different row silently

---

## 17. Nested object opening

A card may open another card.

Examples:
- booking card -> patient card
- recommendation card -> product card
- patient card -> booking card
- care order card -> product card

The callback contract must preserve:
- original source context
- nested source relation
- correct back behavior

This is where weak callback contracts usually fall apart.

---

## 18. Action taxonomy

Actions should be grouped into bounded families.

## 18.1 View actions
- open
- expand
- collapse
- cover
- gallery
- more_details

## 18.2 Navigation actions
- back
- home
- next
- prev
- page

## 18.3 Operational actions
- confirm
- cancel
- check_in
- in_service
- complete
- reserve
- issue
- fulfill
- accept
- decline
- acknowledge

## 18.4 Contextual open actions
- recommendations
- bookings
- chart
- orders
- schedule

This taxonomy keeps callback growth sane.

---

## 19. Callback payload size discipline

Telegram callback data is bounded.
So implementation must be compact.

This document does not dictate exact encoding,
but it does require:
- compact field naming or compact encoded contract
- bounded source refs
- no giant serialized JSON blobs in callback data
- no stuffing arbitrary human text into callbacks

If richer context is needed, the system should use:
- compact IDs/tokens
- server-side state lookup
not callback bloat.

---

## 20. Server-side lookup vs encoded state

The callback contract should use a healthy balance.

## Encode directly:
- profile
- action
- entity_id
- small source token
- page/index if short
- state token

## Resolve server-side:
- full source context details
- list generation context
- large filters
- expanded rendering state if too large
- role access truth
- current entity state

Do not encode the whole world into the callback string.

---

## 21. Logging rules

Callback handling logs must be useful, but not reckless.

Okay to log:
- callback family
- action
- profile
- entity id
- source context id
- stale/denied/success outcome

Do not log:
- sensitive user content
- full patient text payload
- raw chat contents
- giant serialized objects

Logs must support debugging without becoming privacy sabotage.

---

## 22. Testing requirements

The callback contract must be testable.

At minimum, card callback tests should prove:
- parse works
- invalid callback fails safely
- stale token blocks action
- wrong role blocks action
- wrong entity/scope blocks action
- nested source context returns correctly
- list back/page behavior remains coherent

If callback safety is not tested, it is not real.

---

## 23. Relationship to media/navigation rules

This document does not define:
- gallery stepping details
- media return paths
- cover/gallery/video rendering behavior
in full detail.

That belongs in:
- `16-3_card_media_and_navigation_rules.md`

But this document defines the callback primitives those rules rely on.

---

## 24. Relationship to future object cards

Future cards should not invent a separate callback world.

If new profile appears later:
- it must plug into this contract
- or explicitly justify why it cannot

This is how UI entropy is controlled.

---

## 25. Explicit anti-patterns

The following are unacceptable:

- callback that only contains action and assumes “current entity”
- callback that uses naked `patient_id` without source/state/token validation
- callback that silently opens the nearest matching object
- callback that performs mutation without revalidating entity state
- back action that just jumps to home because source context is missing
- stale callback that mutates current data anyway
- giant JSON payload hidden inside callback
- callback contract varying wildly by profile with no shared grammar

These are exactly how good systems become stupid.

---

## 26. Summary

The DentFlow card callback contract exists to make card UI:
- explicit
- safe
- contextual
- stale-resistant
- role-aware
- reusable

Every interactive card action must be able to resolve:

- profile
- entity type
- entity id
- action
- mode
- source context
- source reference
- page/index where relevant
- state token
- role-safe execution path

That is the minimum required for a serious Telegram card system.

Anything weaker becomes guesswork.
Guesswork is how systems betray users.
