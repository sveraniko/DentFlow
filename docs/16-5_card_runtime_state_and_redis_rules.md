# Card Runtime State and Redis Rules

> Canonical runtime-state, callback-token, panel lifecycle, and Redis-backed coordination rules for the DentFlow unified card system.

## 1. Purpose

This document defines the **runtime-state layer** of the unified card system.

If:
- `16_unified_card_system.md` defines the shared card shell,
- `16-1_card_profiles.md` defines profile payloads,
- `16-2_card_callback_contract.md` defines callback semantics,
- `16-3_card_media_and_navigation_rules.md` defines navigation/media behavior,
- `16-4_booking_card_profile.md` defines the central booking profile,

then this document defines the missing operational foundation:

- where callback tokens live;
- where active panel state lives;
- how cards survive beyond one in-memory process;
- how stale/expired card actions are detected;
- how one-active-panel discipline works in shared runtime;
- how restart/multi-worker behavior must be handled;
- why Redis (or equivalent shared runtime store) is mandatory.

This document exists because process-local in-memory registries are acceptable only for throwaway prototypes.
DentFlow is no longer a prototype.

---

## 2. Core thesis

# Card runtime state must not depend on one bot process memory.

This is the non-negotiable rule.

Why:
- Telegram messages outlive one process lifetime.
- Users click old buttons.
- Workers restart.
- Deploys happen.
- More than one worker/process may handle updates.
- Cards must not silently die just because memory was cleared.

Therefore:

### Production path must use shared runtime state
Recommended baseline:
- Redis

Not:
- plain in-memory dicts
- local process-only registries
- “it works if the bot never restarts” optimism

---

## 3. What lives in runtime state

The card runtime state layer must hold only **ephemeral UI-operational state**.

This includes:
- callback token registry
- active panel registry
- source context binding
- page/index binding
- state token / revision token
- temporary card/session correlation info
- panel lifecycle metadata

This does **not** include canonical business truth such as:
- bookings
- patients
- recommendations
- care orders
- chart facts

Those remain in DB truth.

Runtime card state is not business truth.
It is **interaction truth**.

---

## 4. Why Redis is the right baseline

Redis is the right baseline because the problem here is:
- shared
- short-lived
- tokenized
- low-latency
- TTL-sensitive
- restart-sensitive

This is exactly the kind of state Redis is good at.

### Why not DB for everything here
A relational DB can store this, but for card runtime state it is often heavier than needed.
These are ephemeral panel/callback tokens, not legal records.

### Why not process-local memory
Because process-local memory fails at the first real operational stress:
- deploy/restart
- multiple workers
- stale message click
- background task ordering differences

---

## 5. Runtime-state categories

The runtime layer should distinguish these categories clearly.

## 5.1 Callback token state
Maps a compact Telegram callback token to the semantic callback contract.

## 5.2 Active panel state
Tracks which panel/message is currently considered active for an actor and panel family.

## 5.3 Source context state
Tracks where the current card/list came from.

## 5.4 Pagination/list state
Tracks page/index/cursor context for lists and list-opened cards.

## 5.5 Session correlation state
Optional short-lived correlation between related nested card interactions.

These may share infrastructure, but their semantics must remain explicit.

---

## 6. Callback token registry model

## 6.1 Purpose
Telegram callback data is short.
The full semantic callback contract is not.

Therefore the runtime may send a compact token in Telegram callback_data and resolve it server-side.

## 6.2 Required token mapping
Each callback token must map to a semantic callback payload that can reconstruct at minimum:
- profile
- entity_type
- entity_id
- action
- mode
- source_context
- source_ref
- page_or_index where relevant
- state_token

## 6.3 Storage rule
This token mapping must live in Redis/shared runtime store in production path.

## 6.4 TTL rule
Callback tokens must have TTL.

Recommended baseline:
- short-lived enough to avoid indefinite garbage
- long-lived enough to support realistic user behavior

Suggested baseline:
- 15 to 60 minutes, depending on panel family and workflow criticality

Exact TTL may be configurable.

## 6.5 Expiry behavior
If token expires:
- callback must fail safely
- no mutation occurs
- user gets compact localized message
- caller may be told to reopen or refresh

Expired token is normal.
It is not a crash.

---

## 7. Active panel registry model

## 7.1 Purpose
The system needs to know:
- which message/panel is currently active for a user in a given interaction family
- whether a new render should edit or replace
- whether an old panel should be treated as stale

## 7.2 Required stored fields
At minimum active panel state should track:
- actor_id
- chat_id
- message_id
- panel_family
- profile (optional but useful)
- entity_id where relevant
- source_context
- source_ref
- page_or_index where relevant
- state_token
- updated_at
- expires_at or TTL

## 7.3 Storage rule
Active panel state must live in shared runtime storage, not process-local memory.

## 7.4 One-active-panel rule
For a given:
- actor
- panel family
- active conversational context

there should be one canonical active panel.

The system may still leave older messages in chat history, but they must no longer be treated as active truth.

---

## 8. Panel family model

One-active-panel discipline should not be global and naive.

It must understand **panel families**.

Examples:
- patient_home
- patient_catalog
- recommendation_flow
- doctor_queue
- admin_today
- booking_detail
- care_order_flow
- search_results

### Why panel families matter
A user may legitimately have:
- one active booking card
- one active care order card
- one active search results panel

But should not have:
- five “current” admin_today panels all pretending to be canonical

Panel family is the unit of active-state replacement.

---

## 9. Source context persistence

The runtime state layer must preserve source context explicitly.

At minimum source context state should include:
- source_context kind
- source_ref
- page/index/cursor where relevant
- parent object reference if nested
- last known active token

This is necessary for:
- Back behavior
- nested object open
- stale validation
- correct list return

Without persistent source context, cards become disoriented quickly.

---

## 10. State token / revision semantics

The runtime state layer must use revision/state tokens to protect against stale actions.

A state token should change when:
- the list generation is refreshed
- the object render context meaningfully changes
- a panel is superseded
- source context is replaced
- action availability changes materially

State tokens do not need to encode every DB field.
They only need to invalidate stale UI meaningfully.

---

## 11. Stale callback rule

If callback is stale because:
- token missing
- token expired
- state token mismatch
- source_ref mismatch
- wrong page/index
- active panel superseded
- panel family mismatch

then:
- action must not mutate anything
- action must not silently target another object
- user gets compact localized stale feedback
- system may suggest reopen/refresh

This is required for safety, not optional polish.

---

## 12. Restart behavior

Redis/shared runtime state must make restart behavior safe enough.

### On process restart:
- old callback tokens may still be valid if TTL remains and Redis survives
- active panel state may still be valid if TTL remains
- no in-memory wipe should instantly kill all recent cards

### If Redis is flushed/restarted:
- callbacks fail safely as expired/stale
- business truth remains intact
- user is instructed to reopen/refresh

No hidden mutation should rely on local memory survival.

---

## 13. Multi-worker behavior

If multiple workers/instances handle updates:

- any worker must be able to resolve callback token
- any worker must be able to validate active panel state
- one-active-panel behavior must remain coherent across workers
- no worker should assume it “owns” all card state in RAM

This is one of the main reasons process-local registries are not acceptable as production path.

---

## 14. Read vs write behavior

Runtime card state operations should be explicit.

## 14.1 Write operations
Examples:
- store callback token mapping
- bind/update active panel
- supersede panel
- invalidate panel
- store navigation cursor/source state

## 14.2 Read operations
Examples:
- resolve callback token
- resolve active panel for actor/panel family
- compare source/state token
- fetch source context for Back

This separation should be reflected in service/store design.

---

## 15. Invalidation rules

The system must support explicit invalidation.

### When to invalidate
- panel superseded by newer panel in same family
- workflow completed
- object action changed current valid state significantly
- actor switched context
- object removed/hidden beyond safe use

### Invalidation effect
- old callbacks fail safely
- old panel is no longer treated as active
- new panel token becomes canonical

---

## 16. Expiration strategy

Not every runtime state entry needs the same TTL.

Recommended categories:
- callback token TTL
- active panel TTL
- source/list context TTL

### Suggested baseline principle
- callback tokens shorter
- active panel state medium
- source/list context medium or tied to active panel

Example baseline:
- callback token: 30 minutes
- active panel: 1-3 hours
- search/list context: 30-60 minutes

These are examples, not dogma.
The rule is: TTL must be explicit and documented.

---

## 17. Relationship to business truth

This must remain explicit:

Runtime card state:
- may expire
- may be rebuilt
- may be invalidated
- must never become canonical business truth

Therefore:
- booking status never lives only in Redis
- patient identity never lives only in Redis
- recommendation lifecycle never lives only in Redis

Redis runtime state is only there to safely drive the UI.

---

## 18. Localized failure messaging

Redis/runtime failures must degrade safely and locally.

Examples:
- stale panel
- expired callback
- invalid context
- unavailable action
- reopen required

These messages must be:
- localized
- compact
- non-technical
- not vague

Do not leak internal runtime implementation details to the user.

---

## 19. Minimal observability

The runtime state layer should be observable enough to debug real problems.

Safe to log:
- token created
- token resolved/missing/expired
- active panel superseded
- stale callback rejected
- panel family mismatch
- source_ref mismatch

Do not log:
- sensitive business payloads
- raw patient data blobs
- full chat contents

---

## 20. Key naming and namespacing

Redis keys must be namespaced and explicit.

Recommended conceptual namespaces:
- `card:cb:<token>`
- `card:panel:<actor_id>:<panel_family>`
- `card:ctx:<actor_id>:<context_id>`

Exact shape may vary, but namespacing must be systematic.

Do not create random flat keys.

---

## 21. Data model compactness

Runtime payloads stored in Redis should remain compact.

Store:
- structured callback semantic payload
- state token
- source refs
- message binding
- panel family

Do not store:
- giant rendered text bodies
- full DB objects
- long clinical payloads
- media blobs

Redis is for interaction state, not shadow copies of business records.

---

## 22. Access and security rules

Redis/shared runtime state must not weaken role safety.

Even if token resolves:
- action must still validate role
- action must still validate entity access
- token presence does not grant permission

Runtime state is not authorization.

---

## 23. Graceful degradation if Redis unavailable

This must be explicitly defined.

Recommended baseline:
- if Redis/shared state is unavailable, card actions should fail safely rather than mutate under uncertainty
- creation of new card interactions may be degraded or temporarily disabled
- business truth must remain safe

Do NOT silently drop into unsafe local-memory fallback in production path unless explicitly designed and documented as a bounded degraded mode.

Safety first.

---

## 24. Testing requirements

The runtime-state layer must be tested for:

- callback token write/read/expire
- active panel write/read/supersede/invalidate
- stale callback rejection after supersession
- source_ref mismatch rejection
- page/index mismatch rejection where relevant
- restart-safe behavior assumptions at the service level
- role validation still enforced after token resolution

If these are not tested, the runtime layer is not ready.

---

## 25. Required implementation consequences

Any future card implementation must assume:

- callback token registry is shared-state backed
- active panel registry is shared-state backed
- stale handling is explicit
- source context survives beyond one process lifetime
- “current panel” is not a local in-memory illusion

This is now a hard architectural rule.

---

## 26. Explicit anti-patterns

These are forbidden:

- process-local callback registry as production truth
- process-local active panel registry as production truth
- no TTL on callback tokens
- no invalidation on superseded panel
- role checks skipped because token resolved
- local-memory fallback silently used after Redis failure
- keeping giant business payloads in runtime state store

These anti-patterns are how UI systems become untrustworthy.

---

## 27. Summary

The DentFlow card runtime state layer must be:

- Redis/shared-state backed
- TTL-aware
- stale-safe
- source-aware
- panel-family aware
- restart-safe enough
- multi-worker safe enough
- authorization-neutral (not a permission source)

Redis is used here because card and panel state are:

- shared
- ephemeral
- tokenized
- latency-sensitive
- restart-sensitive

This is the correct place to use it.

Anything weaker turns card UI into a fragile local illusion.
