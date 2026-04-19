# Card Profiles

> Canonical profile definitions for the DentFlow unified card system.

## 1. Purpose

This document defines the **profile layer** on top of `16_unified_card_system.md`.

If `16_unified_card_system.md` defines the shared shell,
this document defines:

- what each card profile may show;
- what each profile must show in compact mode;
- what each profile may reveal in expanded mode;
- which actions belong to which profile;
- which role may see which profile variant;
- what must never be mixed into the wrong card.

This document is intentionally explicit, because if profile definitions remain vague,
Codex will happily produce a mutant interface that is:
- too dense,
- too random,
- too inconsistent,
- and then we will waste two more waves dragging it back to civilization.

---

## 2. Core principle

A card profile is:

- one object family
- rendered through the shared card shell
- with profile-specific fields
- with profile-specific actions
- with role-specific visibility rules

The shell is shared.
The payload is not.

This means:
- product card is not patient card,
- patient card is not doctor card,
- booking card is not recommendation card,
but all of them should still feel like they belong to one system.

---

## 3. Supported profiles in this wave

This document defines these profiles:

1. `product`
2. `patient`
3. `doctor`
4. `booking`
5. `recommendation`
6. `care_order`

All six must be designed now.
Booking does **not** get deferred.
If it is deferred, it will come back later as UI debt wearing a fake mustache.

---

## 4. Profile design rules

For every profile below, define:

- identity
- compact mode fields
- expanded mode fields
- actions
- role visibility
- profile-specific prohibitions

### Shared rule
Compact mode must be:
- enough to scan
- enough to decide whether to open

Expanded mode must be:
- richer
- still bounded
- still in the same object context

---

# 5. Product profile

## 5.1 Purpose

The product card exists to let the patient/admin view a care product and act on it without turning DentFlow into a generic store.

The product profile is primarily used in:
- recommendation-driven product flow
- narrow patient catalog
- admin operational care flow
- future care order item detail flow

## 5.2 Identity

Canonical identity:
- `care_product_id`
- operator-facing stable key:
  - `sku`
  - `product_code` if needed

## 5.3 Compact mode

Compact product card must show:

- localized title
- short label or compact descriptor
- price
- compact availability status
- selected/preferred pickup branch hint if relevant
- recommendation badge/context if opened from recommendation

### Compact mode must NOT show:
- long description
- giant specs block
- admin stock internals
- warehouse fields
- multiple media panels at once

## 5.4 Expanded mode

Expanded product card may show:

- localized title
- localized description
- usage hint
- recommendation rationale / justification
- category
- compact specs block if useful
- availability status
- selected/preferred branch
- media actions (`Cover`, `Gallery`, later maybe `Video`)
- reserve/pickup action
- change-branch action
- back action

### Expanded mode still must remain bounded
Do not dump:
- raw low-level stock math
- technical field names
- giant marketing text
- internal notes

## 5.5 Actions

Allowed primary actions:
- `Подробнее`
- `Забрать в клинике`
- `Сменить филиал`
- `Назад`

Optional contextual actions:
- `Открыть рекомендацию`
- `Reserve again`
- `Открыть заказ`

## 5.6 Role visibility

### Patient
May see patient-facing product card.

### Admin
May see operational product card with branch/order context if relevant.

### Doctor
May see product card in recommendation or care context, but product card should not become warehouse UI.

### Owner
Not a primary user of product cards in baseline.

## 5.7 Profile-specific prohibition

Product card must not become:
- full product admin editor
- stock console
- media CMS
- warehouse object card

---

# 6. Patient profile

## 6.1 Purpose

The patient card exists to let admin/doctor work with a person fast:
- identify them
- open their operational context
- navigate to bookings/recommendations/care/chart summary

It is not a full chart or a CRM monster.

## 6.2 Identity

Canonical identity:
- `patient_id`
- `patient_number` if available

## 6.3 Compact mode

Compact patient card must show:

- display name
- patient number if available
- compact contact hint
- photo/presence indicator
- active flags summary
- current or upcoming booking snippet if useful

### Compact mode must NOT show:
- deep chart text
- diagnosis details
- giant note history
- owner metrics
- warehouse/care internals beyond a small hint

## 6.4 Expanded mode

Expanded patient card may show:

- display name
- contact block
- active flags
- current/upcoming booking block
- recommendation summary block
- care order summary block
- chart summary entry
- branch/doctor context where useful
- quick action area

### Expanded mode must still remain compact enough for Telegram
Do not dump:
- full chart notes
- entire recommendation history
- full commerce history
- all bookings ever made unless a dedicated view is opened

## 6.5 Actions

Typical actions:
- `Записи`
- `Рекомендации`
- `Карта`
- `Заказы`
- `Открыть`
- `Назад`

Role-specific quick actions may include:
- confirm/open booking
- open chart summary
- open care order detail

## 6.6 Role visibility

### Admin
Operational patient card.

### Doctor
Doctor-safe patient card with chart entry and booking context.

### Patient self-view
Not necessarily the same profile.
Patient self-profile is a different UX concern and should not blindly reuse admin card payload.

### Owner
Patient card visibility should remain bounded and not default to deep operational use.

## 6.7 Profile-specific prohibition

Patient card must not become:
- chart replacement
- owner analytics card
- giant patient dossier dump

---

# 7. Doctor profile

## 7.1 Purpose

The doctor card exists to:
- identify the doctor
- provide quick operational context
- open schedule / queue / doctor detail

It is not an HR record.

## 7.2 Identity

Canonical identity:
- `doctor_id`

Useful visible identity:
- display name
- specialty
- branch

## 7.3 Compact mode

Compact doctor card must show:

- doctor display name
- specialty label/code
- branch
- active/public booking indicator if useful
- small load hint if already available

### Compact mode must NOT show:
- full schedule
- giant metrics
- unrelated staff metadata

## 7.4 Expanded mode

Expanded doctor card may show:

- display name
- specialty
- branch
- today queue summary
- availability/schedule summary
- relevant service tags
- quick open actions

## 7.5 Actions

Typical actions:
- `Сегодня`
- `Расписание`
- `Открыть`
- `Назад`

Later operational extensions may add:
- queue shortcuts
- branch switch context

## 7.6 Role visibility

### Admin
May see operational doctor card.

### Doctor
May see own profile card if useful.

### Owner
May later see doctor card in owner views, but that is not the primary baseline path here.

## 7.7 Profile-specific prohibition

Doctor card must not become:
- owner metrics dashboard
- HR personnel file
- giant schedule spreadsheet in card form

---

# 8. Booking profile

## 8.1 Purpose

The booking card is one of the most important profiles in the system.

It exists to provide a unified way to view:
- one booking
- its status
- patient/doctor/service context
- next valid actions

This profile must be designed now, not “later”.

## 8.2 Identity

Canonical identity:
- `booking_id`

Context anchors:
- `patient_id`
- `doctor_id`
- `service_id`
- `branch_id`

## 8.3 Compact mode

Compact booking card must show:

- time/date
- patient display name
- doctor display name (if not implied by source context)
- service label
- branch
- current status
- compact flags
- one or two most relevant quick actions

### Compact mode must NOT show:
- long notes
- chart detail
- reminder technical internals
- full patient history
- giant issue history

## 8.4 Expanded mode

Expanded booking card may show:

- all compact fields
- booking source/channel if useful
- booking note snippet
- reminder state summary if useful
- linked recommendation/care order hint if relevant
- patient quick-open
- chart summary entry
- operational action area
- back/navigation area

### Expanded mode should still not become:
- chart
- admin workdesk clone
- issue ledger wall

## 8.5 Actions

Typical actions vary by role.

### Patient-facing
- `Подтвердить`
- `Перенести`
- `Отменить`
- `Назад`

### Admin-facing
- `Подтвердить`
- `Отметить приход`
- `Перенос`
- `Отмена`
- `Открыть пациента`

### Doctor-facing
- `В работе`
- `Завершить`
- maybe `Открыть карту`

### Owner-facing
Usually read-only or drill-down oriented in baseline.

## 8.6 Role visibility

### Patient
Only own booking card.

### Admin
Operational booking card.

### Doctor
Own bookings / permitted operational context only.

### Owner
Read-only summary/drill-down context only, no random operational mutation by default.

## 8.7 Profile-specific prohibition

Booking card must not become:
- schedule spreadsheet
- full patient chart
- owner analytics dashboard
- reminder debug console

---

# 9. Recommendation profile

## 9.1 Purpose

The recommendation card exists to present recommendation truth as a first-class object.

It is not:
- a reminder clone
- a product card
- a note

## 9.2 Identity

Canonical identity:
- `recommendation_id`

Context anchors:
- `patient_id`
- `booking_id` if relevant
- `encounter_id` if relevant

## 9.3 Compact mode

Compact recommendation card must show:

- title
- recommendation type/status
- compact rationale
- issued/source context if useful
- quick action or linked products count

### Compact mode must NOT show:
- giant text wall
- all linked products expanded inline
- deep chart context

## 9.4 Expanded mode

Expanded recommendation card may show:

- title
- body
- rationale
- linked products or set summary
- status
- issued by / issued at
- response actions:
  - acknowledge
  - accept
  - decline
- open linked products

## 9.5 Actions

Typical actions:
- `Открыть`
- `Товары`
- `Принять`
- `Отклонить`
- `Понятно`
- `Назад`

## 9.6 Role visibility

### Patient
May view and respond.

### Doctor
May view issued recommendation in context.

### Admin
May open recommendation only if role/policy allows and operational need exists.

### Owner
Not primary in baseline.

## 9.7 Profile-specific prohibition

Recommendation card must not become:
- product card
- reminder debug card
- free-form note dump

---

# 10. Care order profile

## 10.1 Purpose

The care order card exists to show a patient/admin the operational state of a care order.

It is not a warehouse order form.

## 10.2 Identity

Canonical identity:
- `care_order_id`

Context anchors:
- `patient_id`
- `recommendation_id`
- `booking_id`
- `pickup_branch_id`

## 10.3 Compact mode

Compact care order card must show:

- order identity hint
- product/set summary
- branch
- status
- maybe pickup readiness
- one or two relevant actions

### Compact mode must NOT show:
- stock internals
- accounting internals
- reservation debug info

## 10.4 Expanded mode

Expanded care order card may show:

- product items
- branch
- status timeline summary
- reservation state hint
- ready/issued/fulfilled markers
- repeat order / reserve again entry if allowed
- back navigation

## 10.5 Actions

### Patient-facing
- `Открыть`
- `Повторить`
- `Назад`

### Admin-facing
- `Готов к выдаче`
- `Выдать`
- `Завершить`
- `Отменить`

## 10.6 Role visibility

### Patient
Own care orders only.

### Admin
Operational care order handling.

### Doctor
Usually not primary consumer except contextual linkage.

### Owner
Read-only summary if needed later.

## 10.7 Profile-specific prohibition

Care order card must not become:
- warehouse stock console
- invoice/billing platform
- recommendation replacement

---

# 11. Cross-profile consistency rules

The following must stay consistent across all profiles.

## 11.1 Header hierarchy
- title
- subtitle
- badges

## 11.2 Meta structure
Compact facts must stay visually consistent.

## 11.3 Action placement
Primary actions should appear in predictable positions.

## 11.4 Back behavior
Must return to source context, not generic home by surprise.

## 11.5 Media handling
Media actions must feel consistent.
No one profile should invent its own media universe.

---

# 12. Role-specific action filtering

The same object profile may expose different actions depending on role.

Example:
- booking profile for patient
- booking profile for admin
- booking profile for doctor

This must be implemented by profile action configuration, not by building completely different card species if avoidable.

---

# 13. Compact vs expanded boundary

This is one of the most important rules.

## Compact mode should answer:
- what is this?
- what state is it in?
- do I need to open it?

## Expanded mode should answer:
- what else do I need to know right now?
- what is the next action?
- what linked context matters?

If expanded mode tries to answer every possible question, the design is wrong.

---

# 14. Profile-level stale handling

Stale callback behavior must remain consistent across profiles.

If a card is stale:
- actions fail safely
- user gets compact localized feedback
- wrong entity/state must not be mutated

Profile-specific detail may differ,
but stale safety must remain universal.

---

# 15. What this document does NOT define

This document does not yet define:
- callback payload schema in detail
- media navigation behavior in detail
- source-context contract in detail

Those belong in:
- `16-2_card_callback_contract.md`
- `16-3_card_media_and_navigation_rules.md`

---

# 16. Summary

The DentFlow card system uses one shell with multiple profiles.

This document defines those profiles as:

- `product`
- `patient`
- `doctor`
- `booking`
- `recommendation`
- `care_order`

For each profile, it sets:
- purpose
- identity
- compact payload
- expanded payload
- actions
- role visibility
- explicit prohibitions

This is how the system stays consistent without becoming uniform in the stupid sense.

The shell is shared.
The profile behavior is specific.

That is the correct design.
