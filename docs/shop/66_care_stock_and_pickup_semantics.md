# Care Stock and Pickup Semantics

> Canonical stock, reservation, branch pickup, and fulfillment semantics for the DentFlow care-commerce block.

## 1. Purpose

This document defines the **operational semantics** of stock baseline, reservation, pickup, and fulfillment for the DentFlow care-commerce block.

Its role is to answer:

- what “availability” means in DentFlow;
- what truth lives in workbook / Google Sheets and what truth lives in DentFlow DB;
- how reservation works;
- how branch choice works;
- how issue / fulfill affect stock semantics;
- what baseline operational guarantees must exist;
- what is intentionally excluded to avoid turning the subsystem into a warehouse ERP.

This document is critical because stock and pickup semantics are where many product teams accidentally create either:
- fake inventory,
- silent overselling,
- or a miniature accounting religion they never wanted to maintain.

DentFlow should do neither.

---

## 2. Product thesis

The DentFlow care layer is **pickup-oriented clinic commerce**, not a warehouse system.

The stock model must therefore be:
- simple enough to operate;
- strong enough to prevent obvious reservation lies;
- explicit enough to support branch-aware patient/admin flows;
- limited enough to avoid ERP creep.

The purpose of this layer is:
- show whether the clinic can reserve/pick up the product;
- let the patient choose a branch;
- let admin issue/fulfill coherently;
- keep the system honest.

That is enough for baseline.

---

## 3. Source-of-truth model

This is the most important section.

## 3.1 Workbook / Google Sheets truth
Authoring layer provides:

- `on_hand_qty`
- `availability_enabled`
- `low_stock_threshold`
- `preferred_pickup`
- optional product-level/default branch hints

This is **baseline stock authoring truth**.

It defines what the clinic says exists in a branch as the current baseline stock level.

## 3.2 DentFlow DB truth
DentFlow DB is canonical for runtime operations:

- care orders
- care reservations
- reservation status
- reservation release
- reservation consume
- issue / fulfill state
- active reserved quantity
- derived free quantity

This is **runtime operational truth**.

## 3.3 Why the split exists
If everything lives only in Sheets:
- reservations become untrustworthy
- issue/fulfill becomes inconsistent
- race conditions become comedy

If everything becomes warehouse DB truth:
- operators lose simple authoring
- the product turns into a giant admin burden

The split is intentional and correct.

---

## 4. Baseline stock model

## 4.1 Branch product availability
The baseline unit of stock truth is:

**one product in one branch**

This is represented by:
- `branch_id`
- `care_product_id` or `sku`
- `on_hand_qty`
- `availability_enabled`
- `low_stock_threshold`
- optional `preferred_pickup`

## 4.2 On-hand quantity
`on_hand_qty` means:

> baseline physically available quantity in this branch according to current catalog authoring state

It is not:
- free quantity
- reserved quantity
- shipped quantity
- accounting quantity

It is simply the baseline branch stock level.

## 4.3 Reserved quantity
`reserved_qty` means:

> quantity currently blocked by active reservations in DentFlow DB

It is runtime-derived and must not be authored in workbook.

## 4.4 Free quantity
The operational free quantity is:

`free_qty = on_hand_qty - active_reserved_qty`

This is the number that matters for:
- reserve flow
- branch availability
- low-stock signaling
- issue readiness

This value may be computed on the fly or materialized in service logic.
It remains derived, not authored.

---

## 5. Availability status model

Patient/admin UI should not rely only on raw numbers.

Recommended compact statuses:

- `in_stock`
- `low_stock`
- `out_of_stock`

## 5.1 Baseline derivation
A coherent derivation rule is:

### `out_of_stock`
if:
- `availability_enabled = false`
or
- `free_qty <= 0`

### `low_stock`
if:
- `free_qty > 0`
and
- `free_qty <= low_stock_threshold`

### `in_stock`
if:
- `free_qty > low_stock_threshold`
and
- `availability_enabled = true`

This is sufficient for baseline patient/admin UX.

## 5.2 Important rule
The UI may show:
- “Есть / In stock”
- “Мало / Low stock”
- “Нет / Out of stock”

It must not show “available” if reservation would fail.
That would be both stupid and avoidable.

---

## 6. Branch selection semantics

## 6.1 Branch choice must be explicit
Pickup branch must not be hidden magic.

Branch may be:
- preselected,
- suggested,
- preferred,
but it must be visible and overrideable in patient flow.

## 6.2 Preferred branch model
A preferred branch may come from:
- product-level default pickup branch
- branch availability row (`preferred_pickup=true`)
- clinic policy (`care.default_pickup_branch_id`)
- prior patient context later, if added intentionally

## 6.3 Correct UX rule
Use:
**preferred branch + explicit override**

This means:
- if a suitable preferred branch exists and has stock, it is preselected
- the patient sees it
- the patient may change it
- if no suitable preferred branch exists, picker is shown
- if selected branch lacks stock, flow fails clearly and asks for another branch

## 6.4 No hidden forced branch
Even if a default branch exists, it must not silently lock the patient into pickup there without visibility.

---

## 7. Reservation semantics

Reservation must be a real operational act, not symbolic paperwork.

## 7.1 Reservation meaning
A reservation means:

> a quantity of a product is blocked for a patient/order in a specific branch and should no longer be treated as freely available

## 7.2 Reservation precondition
Reservation may be created only if:
- product is active
- pickup is supported if reserve/pickup path is used
- branch is valid
- branch availability is enabled
- free quantity is sufficient

If any of those fail, reservation must fail explicitly.

## 7.3 Reservation quantity
Baseline quantity may remain simple:
- default = 1
- optional support for custom quantity if patient/admin flow already carries quantity coherently

Do not overcomplicate quantity logic if the rest of the flow does not need it yet.

## 7.4 Reservation lifecycle
Canonical reservation states may include:
- `created`
- `active`
- `released`
- `consumed`
- `expired`
- `canceled`

The exact lifecycle is defined elsewhere, but stock semantics must align with it.

---

## 8. Reservation and stock update rules

This section is the operational heart of the layer.

## 8.1 On reservation create
When an active reservation is created:
- `reserved_qty` increases
- `free_qty` decreases accordingly

`on_hand_qty` does **not** change at reservation time.

## 8.2 On reservation release
When an active reservation is released:
- `reserved_qty` decreases
- `free_qty` increases accordingly

`on_hand_qty` does **not** change on release.

## 8.3 On reservation consume
When reservation is consumed due to issue/fulfillment:
- `reserved_qty` decreases
- `on_hand_qty` decreases
- `free_qty` reflects the new baseline

This is the correct baseline logic.

### Why
Because consume means the item has physically left the branch stock for the patient.

## 8.4 On reservation expire
Expiration should behave like release unless a different explicit business rule exists.
Baseline recommendation:
- expiration frees reservation
- does not reduce `on_hand_qty`

## 8.5 On order cancel
If order is canceled while reservation is active:
- reservation must be released
- `reserved_qty` decreases
- `on_hand_qty` remains unchanged

---

## 9. Order vs reservation distinction

This distinction must remain explicit.

## 9.1 Care order
Represents:
- patient intent / transaction flow
- selected product(s)
- selected branch
- order-level status
- payment mode
- patient-facing state

## 9.2 Care reservation
Represents:
- stock block in a branch for a specific order/item

One order may involve one or more reservations.
Reservation is not the same as order state.

## 9.3 Why this matters
If reservation is collapsed into order:
- stock semantics become muddy
- issue/fulfill becomes unclear
- release/consume cannot be modeled cleanly

---

## 10. Issue and fulfill semantics

## 10.1 Ready for pickup
Means:
- the branch has accepted/prepared the order for pickup
- reservation should already exist or be created by the time the order is truly ready

Baseline recommendation:
- reservation should be active by or before `ready_for_pickup`

## 10.2 Issued
Means:
- the item was handed over to the patient

At this point:
- reservation is consumed
- `on_hand_qty` decreases
- `reserved_qty` decreases

## 10.3 Fulfilled
Means:
- the order lifecycle is operationally complete

In some clinic flows:
- `issued` and `fulfilled` may be near-consecutive
- but they should remain conceptually distinct if the order model already supports both

---

## 11. Admin stock operations baseline

This layer needs minimal admin operations, not a giant dashboard.

At minimum, admin or authorized operator should be able to:

- open branch stock for a product
- set stock
- increase stock
- decrease stock

These operations affect:
- `on_hand_qty`
- optionally `availability_enabled`
- optionally `low_stock_threshold`

They do **not**:
- edit reservation truth directly
- bypass runtime order/reservation semantics

This keeps stock baseline practical.

---

## 12. Concurrency safety baseline

This part is critical.

## 12.1 Why it matters
Without concurrency safety:
- two users reserve the last item
- admin sees stock lie
- patient gets false confirmation
- everyone blames the software, correctly

## 12.2 Baseline requirement
Reservation creation must use a transaction-safe check/update path.

At minimum:
- load branch availability under a coherent transaction path
- compute free quantity based on current active reservations
- reserve only if sufficient stock remains
- commit atomically enough that two concurrent reservations do not naively oversell the last unit

## 12.3 What is enough for baseline
You do **not** need:
- enterprise inventory locking mythology

You do need:
- practical transaction-safe reservation logic

That is enough.

---

## 13. Patient-facing stock semantics

The patient should understand:
- where pickup happens
- whether the product is available
- whether reservation succeeded
- what branch was chosen

The patient should **not** need to understand:
- raw stock math
- reservation ledger semantics
- internal stock corrections

Show:
- branch
- compact availability
- order status

Hide:
- internal stock mechanics

---

## 14. Admin-facing stock semantics

The admin should understand:
- selected branch
- whether reservation exists
- whether reservation was released/consumed
- whether stock is enough
- whether issue/fulfill is allowed

The admin should not need:
- giant warehouse screen
- supplier model
- accounting truth

This remains clinic ops, not stock management as a profession.

---

## 15. What lives in Sheets and what does not

## 15.1 Sheet / XLSX
Lives there:
- `on_hand_qty`
- `availability_enabled`
- `low_stock_threshold`
- `preferred_pickup`
- product/branch baseline availability rows

## 15.2 DentFlow DB
Lives there:
- `reserved_qty`
- active reservations
- consume/release state
- orders
- issue / fulfill
- derived free quantity
- event emission

### Important
If someone later tries to push reservations into Sheets:
that is the wrong direction and should be rejected.

---

## 16. Failure and explicit outcomes

The reserve/pickup layer must fail explicitly when needed.

Examples:
- branch invalid
- branch unavailable
- product inactive
- free quantity insufficient
- reservation no longer valid
- issue attempted without active reservation

These must result in:
- explicit typed failure/outcome in service layer
- compact clear patient/admin feedback in UI layer

Do not silently “kind of succeed”.

---

## 17. Explicit non-goals

This stock/pickup semantics layer does **not** include:
- stock movement ledger
- valuation
- cost accounting
- supplier workflows
- inbound purchase receiving
- warehouse transfers
- shipping logistics
- multi-warehouse optimization

If those are ever needed, they should be added intentionally and separately.

---

## 18. Summary

The DentFlow stock and pickup baseline is built on these rules:

- branch availability baseline is authored outside runtime;
- runtime reservations/orders remain canonical in DB;
- free quantity is derived, not authored;
- branch choice is explicit and visible;
- reservation is real and stock-aware;
- release and consume have distinct meanings;
- issue and fulfill remain operationally coherent;
- stock baseline stays practical, not ERP-sized.

This is the right amount of truth for clinic commerce.

Anything much smaller becomes fake.
Anything much bigger becomes a monster.
