# Care Patient Catalog and Flow

> Patient-facing catalog and interaction model for the DentFlow care-commerce block.

## 1. Purpose

This document defines the **patient-facing commerce model** for DentFlow.

Its role is to make explicit:

- how the patient discovers care products;
- what is shown to the patient and what is intentionally hidden;
- how recommendation-driven care flow works;
- how the narrow catalog behaves;
- how product cards, reserve/pickup, and repeat purchase fit together;
- how patient UX remains bounded and clinically relevant instead of becoming a generic store.

This document does **not** define:
- full catalog authoring
- stock/accounting internals
- detailed recommendation engine logic
- warehouse/admin operation logic

Those belong in neighboring documents.

---

## 2. Product thesis

The patient-facing commerce layer in DentFlow is **not** a marketplace.

It exists to solve a practical clinic problem:

- the patient has a clinically relevant need;
- the clinic recommends useful care products;
- the patient can conveniently reserve or obtain those products;
- the interaction remains clear, bounded, and not spammy.

Therefore the patient-facing model must be:

- recommendation-first;
- narrow-catalog second;
- medically relevant;
- branch-aware;
- reservation-aware;
- compact in Telegram;
- low-friction.

---

## 3. Core patient-commerce principle

# Recommendation-first, but not recommendation-only.

This is the correct balance.

### Why not recommendation-only
If products appear only when explicitly recommended:
- the patient cannot return later and browse related care items;
- the system becomes too dependent on manual issuance;
- repeat purchase / replenishment becomes clumsy.

### Why not full-storefront
If the patient gets a giant shop:
- the bot becomes noisy and bloated;
- the clinical relevance disappears;
- the product layer starts competing with the main clinic experience.

### Therefore
The correct patient model is:

1. **primary discovery through recommendations**
2. **secondary discovery through a narrow catalog called “Care / Уход”**

That is the intended product balance.

---

## 4. Patient entry points

The patient may enter care-commerce through several bounded entry points.

## 4.1 Recommendation entry
This is the primary path.

Typical trigger:
- doctor-issued recommendation
- rule-based recommendation
- encounter/booking completion trigger
- follow-up trigger

The patient sees:
- recommendation card
- explanation/rationale
- linked products or recommendation set
- actions:
  - view products
  - acknowledge
  - accept
  - decline

## 4.2 Narrow catalog entry
This is the secondary path.

Example entry labels:
- `Уход`
- `Care`
- `Товары по уходу`

This entry should lead to:
- category list
- compact product list
- product card
- reserve/pickup path

It should not feel like a giant store.

## 4.3 Repeat purchase / return entry
The patient may return later through:
- prior recommendation
- prior care order
- “buy again” / “reserve again” style narrow shortcut
- care order history entry

This should be possible, but bounded.

---

## 5. Catalog scope visible to patient

The patient-facing catalog must remain intentionally narrow.

## 5.1 Recommended categories
Examples:
- brushes
- toothpaste
- irrigators
- floss / interdental
- post-op care
- ortho care
- pediatric care
- gum care

The categories must be:
- few
- clear
- clinically relevant
- stable

No giant category tree.

## 5.2 Product visibility rule
A product may be visible to the patient if:
- it is active
- it is patient-facing
- it belongs to an allowed category
- it is available in at least one usable clinic branch or can be shown with out-of-stock messaging
- policy does not hide it

Recommendation-linked products should get stronger visibility priority than generic catalog browsing.

---

## 6. Recommendation-driven patient flow

This is the primary patient flow.

## 6.1 Flow outline
1. patient receives recommendation
2. patient opens recommendation card
3. patient sees:
   - title
   - rationale
   - linked products or set
4. patient opens product list
5. patient opens product card
6. patient chooses reserve/pickup
7. patient chooses branch if needed
8. order/reservation is created
9. patient sees order status

## 6.2 Why this works
This preserves:
- clinical context
- clarity
- relevance
- low friction

The patient understands:
- what is recommended
- why it matters
- how to get it

---

## 7. Narrow catalog patient flow

This is the secondary path.

## 7.1 Flow outline
1. patient opens `Care / Уход`
2. sees category list
3. selects category
4. sees compact product list
5. opens product card
6. chooses reserve/pickup
7. chooses branch if needed
8. order/reservation is created
9. sees status

## 7.2 Important difference from recommendation flow
In this path, product discovery is broader, but still bounded.
There may be no doctor-issued rationale text.
So the product card and category model must still be understandable on their own.

---

## 8. Category navigation model

Category navigation should be compact.

Recommended UX:
- one panel with category chips/buttons
- patient taps category
- product list appears
- patient can go back to categories

Do not build:
- giant nested trees
- huge filter menus
- complicated sort controls

This is clinic commerce, not a general mall.

---

## 9. Product list model

The product list should stay compact.

Each row/card should show at minimum:
- product title
- short label or category hint
- compact availability status
- price
- action:
  - open
  - reserve/pickup

Optional:
- one-line justification if coming from recommendation flow
- “recommended” badge
- “buy again” badge

Do not dump full descriptions into the list view.

---

## 10. Product card model

The product card is where detail lives.

## 10.1 Required product card elements
- localized title
- localized description
- price
- category
- compact availability status
- pickup support status
- selected or preferred pickup branch hint if relevant
- media if available
- action:
  - reserve/pickup
  - choose branch
  - back to recommendation or category

## 10.2 Recommendation-aware card behavior
If the product is opened from a recommendation:
- show compact “why this is recommended” text
- preserve connection back to the recommendation
- do not lose the recommendation context

## 10.3 Avoid overloading the card
Do not put:
- giant technical text
- huge warehouse details
- doctor-only internal notes
- admin stock debug info

---

## 11. Branch selection model

Branch selection is a critical part of patient UX.

## 11.1 Branch selection principle
Branch must be:
- explicit
- visible
- overrideable

It must not be:
- hidden magic
- raw ID parameter
- silently guessed with no visibility

## 11.2 Recommended baseline behavior
Use:

### Preferred branch + explicit override

Flow:
- if one preferred branch with stock is available -> preselect it
- patient sees the branch explicitly
- patient can change it
- if multiple branches are valid -> show branch picker
- if selected branch has no stock -> fail clearly and allow another branch

This is the correct balance.

## 11.3 Branch picker contents
At minimum show:
- branch name
- compact availability status
- optional “preferred” marker
- optional “out of stock” marker

No giant branch admin data.

---

## 12. Availability status in patient UX

Patient does not need raw stock numbers in baseline.

Use compact statuses:
- `Есть / In stock`
- `Мало / Low stock`
- `Нет / Out of stock`

Optional later:
- “Available for pickup today”
- “Limited quantity”

But baseline should stay simple.

### Important
Availability message must be honest and branch-aware.
No fake “available” if reservation cannot actually be made.

---

## 13. Reserve / pickup flow

The care layer in DentFlow is reserve/pickup oriented.

## 13.1 Baseline flow
1. patient confirms product
2. patient confirms quantity
3. patient confirms pickup branch
4. order/reservation is created
5. patient sees status:
   - confirmed
   - awaiting payment if applicable
   - ready for pickup
   - issued / fulfilled

## 13.2 Flow constraints
- reservation must depend on actual branch availability
- patient must not “reserve” what is unavailable
- branch choice must persist on the order

## 13.3 Baseline payment stance
This stack does not require full payment complexity.
The order lifecycle may support:
- pay later at pickup
- ready for pickup
- issue / fulfill

That is enough for baseline clinic trade.

---

## 14. Repeat purchase / replenishment model

This is important for practical usability.

The patient should be able to return to care items later without a giant ceremony.

### Good baseline options
- open previous care orders
- “Reserve again” on prior item/order
- open category directly from care section
- open prior recommendation and reuse it

This should remain compact.
Do not build a subscription engine.

---

## 15. Recommendation acceptance vs order creation

These must remain distinct.

### Recommendation acceptance means:
- the patient accepts the recommendation as relevant
- may or may not proceed to product order immediately

### Care order creation means:
- the patient actually enters reserve/pickup flow

This distinction is important for analytics and future behavior.
Do not collapse them into one thing.

---

## 16. Patient-facing recommendation response model

The patient may:
- view
- acknowledge
- accept
- decline

### `accept`
means:
- recommendation is accepted
- but still does not automatically mean product reserved

The patient should still explicitly choose the care order action.
That keeps intent and transaction separate.

---

## 17. Compact status model for patient care orders

The patient-facing order state should remain understandable.

Recommended visible statuses:
- `Подтвержден / Confirmed`
- `Ожидает оплаты / Awaiting payment` (if used)
- `Готов к выдаче / Ready for pickup`
- `Выдан / Issued`
- `Завершен / Fulfilled`
- `Отменен / Canceled`
- `Истек / Expired`

Avoid showing internal reservation jargon as the main patient label.

---

## 18. Patient history surfaces

The patient should have compact access to:
- active recommendations
- active care orders
- maybe a compact past care order list

This should support:
- checking if something is ready
- seeing what was previously recommended
- re-entering reserve/pickup flow later

Do not build a giant portal history view in baseline.

---

## 19. Content rules for patient-facing commerce

Patient-facing commerce content must be:
- localized
- concise
- clinically relevant
- non-manipulative

It must not look like:
- spam
- generic ecommerce hype
- random upsell copy detached from care context

This is especially important for recommendation-driven products.

---

## 20. What patient should never see

The patient should not see:
- raw branch stock numbers unless deliberately designed later
- internal SKU logic unless harmless
- admin notes
- warehouse/control fields
- internal event/reconciliation states
- technical fallback strings
- English hardcodes in localized flow

---

## 21. What remains intentionally out of scope

This patient-facing model does **not** include:
- giant storefront search/filter system
- delivery logistics
- subscription/replenishment engine
- loyalty program logic
- broad patient financial account area
- full order history portal
- dynamic personalization engine
- AI shopping assistant

These are outside the baseline care layer.

---

## 22. Summary

The DentFlow patient-facing care model is:

- recommendation-first
- narrow-catalog second
- branch-aware
- reservation-aware
- compact
- clinically relevant

The patient should be able to:
- understand why something is recommended
- browse a small bounded catalog if needed
- reserve/pick up products without friction
- see order status clearly
- return later to prior care items without chaos

The patient should **not** feel like they accidentally walked into a full retail app.

That is the whole point.
