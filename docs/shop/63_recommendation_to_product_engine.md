# Recommendation to Product Engine

> Canonical recommendation-to-product mapping model for the DentFlow care-commerce block.

## 1. Purpose

This document defines the **recommendation engine baseline** for DentFlow commerce.

Its role is to make explicit:

- how recommendation types map to products and sets;
- what part of the engine is automatic;
- what part is doctor-controlled;
- how recommendation context influences suggested care products;
- how recommendation-driven product suggestions become patient-facing;
- how the system stays explainable and bounded instead of becoming a vague “AI recommendation cloud”.

This document does **not** define:
- the full patient-facing catalog UX in detail;
- the full stock/pickup model;
- care order/reservation runtime truth;
- AI recommendation logic.

Those belong in neighboring documents.

---

## 2. Product thesis

DentFlow recommendations must not behave like random product spam.

The recommendation engine exists to solve a simple clinic problem:

- the clinic already knows that some care products are appropriate after some procedures or in some care contexts;
- the doctor or manager should be able to send those suggestions quickly;
- the patient should receive them in a structured, understandable way;
- the system should know whether recommendation was viewed / accepted / declined;
- care-commerce should begin from recommendation relevance, not from random storefront noise.

Therefore the engine must be:

- explainable;
- bounded;
- recommendation-first;
- rule-based at baseline;
- doctor-overridable;
- ready for future AI assist, but not dependent on AI now.

---

## 3. Core engine principles

## 3.1 Recommendation is first-class truth
Recommendation is not:
- just a note,
- just a reminder,
- just a product card,
- just a chart comment.

Recommendation is its own canonical entity with status and history.

## 3.2 Product suggestion must be explicit
The system must know:
- why this product is shown,
- which recommendation type it belongs to,
- whether it came from rule baseline or doctor override,
- whether it points to a product or a set.

## 3.3 Baseline engine is rule-based
The first version of the engine is not AI.

It uses:
- recommendation type
- service/booking/encounter context
- optional diagnosis/clinical tags
- recommendation sets
- explicit doctor override

## 3.4 Doctor remains the final human authority
The engine may suggest.
The doctor may override, add, remove, or issue a recommendation manually.

The engine must help the doctor, not replace judgment.

## 3.5 Recommendation-first does not mean recommendation-only
Patient may later browse a narrow catalog,
but the primary discovery path remains recommendation-driven.

---

## 4. Engine layers

The recommendation engine has three layers.

## Layer 1. Rule baseline
Maps recommendation context to products or recommendation sets.

## Layer 2. Doctor override
Allows doctor (or authorized manager) to:
- choose a different set,
- attach specific products,
- adjust recommendation text,
- issue recommendation manually.

## Layer 3. Patient response
Patient may:
- view
- acknowledge
- accept
- decline

That response becomes part of the recommendation lifecycle truth.

---

## 5. Recommendation source model

Every recommendation must have an explicit `source_kind`.

Recommended baseline values:
- `doctor_manual`
- `booking_trigger`
- `encounter_trigger`
- `clinical_trigger`
- `system_template`

### Interpretation

#### `doctor_manual`
Doctor explicitly chose what to recommend.

#### `booking_trigger`
Recommendation created due to booking/service milestone.

Example:
- hygiene completed -> aftercare hygiene recommendation

#### `encounter_trigger`
Recommendation created from encounter action.

Example:
- doctor finishes current encounter and triggers aftercare/next-step recommendation

#### `clinical_trigger`
Recommendation created due to diagnosis/clinical condition or chart context.

#### `system_template`
System used a known template and issued it in a bounded way.

---

## 6. Recommendation type model

Recommendation type is a bounded, explicit semantic category.

Recommended baseline types:
- `aftercare`
- `follow_up`
- `next_step`
- `hygiene_support`
- `monitoring`
- `orthodontic_support`
- `post_op_support`
- `periodontal_support`
- `daily_maintenance`

These types may later expand, but must remain explicit and manageable.

### Why this matters
Recommendation type is what connects:
- clinic logic
- recommendation sets
- patient-facing text
- product suggestions
- analytics later

Without explicit type, everything becomes arbitrary.

---

## 7. Product targeting model

The engine supports two target kinds:

- `product`
- `set`

## 7.1 Product target
Use when:
- the doctor wants a specific SKU
- the recommendation only needs one item
- a simple direct recommendation is enough

## 7.2 Set target
Use when:
- the context usually requires multiple products together
- the clinic wants to simplify recommendation issuance
- the operator should not type SKU lists every time

### Default preference
The baseline engine should prefer **set-based mapping** where sensible, because:
- it is easier for doctors/managers
- it is more stable operationally
- it is easier to revise later in one place

Single-product targeting still must remain available.

---

## 8. Recommendation rule inputs

The engine may use these baseline inputs:

### 8.1 Booking/service context
Examples:
- service code
- service category
- booking completed
- booking type

### 8.2 Encounter context
Examples:
- doctor explicitly triggers recommendation from encounter
- encounter note category
- encounter completion action

### 8.3 Clinical context
Examples:
- diagnosis tag
- treatment plan tag
- post-op support need
- sensitivity / periodontal / ortho support markers

### 8.4 Manual doctor input
Examples:
- explicit set selection
- explicit product code selection
- explicit rationale

### Important rule
Baseline engine does **not** require giant chart intelligence.
It only needs enough structured context to produce bounded and explainable recommendations.

---

## 9. Recommendation rule outputs

The engine should produce one or more of:

- prepared recommendation draft
- issued recommendation
- linked product list
- linked set
- recommendation justification
- recommendation title/body baseline

This must remain explicit.
The engine should not produce hidden side effects.

---

## 10. Baseline rule matrix

The engine baseline should support a simple rule matrix.

### Example structure
One rule row may contain:
- `rule_code`
- `active`
- `trigger_type`
- `trigger_value`
- `recommendation_type`
- `target_kind`
- `target_code`
- `relevance_rank`
- `issue_mode`
- `justification_key`
- `notes`

### Trigger examples

#### `trigger_type = service_code`
- `hygiene_completed`
- `ortho_consult`
- `post_op_followup`

#### `trigger_type = diagnosis_tag`
- `periodontal`
- `sensitivity`
- `post_op`

#### `trigger_type = encounter_action`
- `doctor_aftercare_trigger`
- `doctor_followup_trigger`

### `issue_mode`
Recommended values:
- `suggest_only`
- `auto_prepare`
- `auto_issue`

Baseline recommendation:
- use `suggest_only` or `auto_prepare` more often than `auto_issue`
- `auto_issue` only for very safe narrow cases

That keeps the system bounded and trustworthy.

---

## 11. Doctor override model

The doctor must be able to override baseline rules quickly.

Doctor override should allow:
- replacing a suggested set with another set
- adding/removing one product
- switching from set to product target
- editing rationale
- issuing recommendation manually

### Important rule
Doctor override should not require rebuilding the rule engine.
It is an operational layer on top of it.

This means the system should preserve:
- original recommendation type
- final target selection
- source_kind indicating doctor influence where appropriate

---

## 12. Fast issuance modes for doctor

The doctor-facing UX should support practical issuance modes.

## Mode A. Choose set
Doctor sees a short list of suitable sets and picks one.

## Mode B. Quick aftercare
Doctor triggers a context-specific recommendation quickly from booking/encounter completion.

## Mode C. Enter product codes
Power-user fallback:
- input product codes via space/comma/semicolon separated values

This should remain available, but should not be the primary UX.

### Why
Doctors think in care scenarios, not SKU spreadsheets.
The engine should match that.

---

## 13. Patient-facing recommendation delivery model

Patient should receive recommendation in a structured way.

A recommendation should contain:
- title
- body/rationale
- linked products or linked set contents
- compact explanation why it is relevant
- actions:
  - acknowledge
  - accept
  - decline
  - open related products

### Important
Patient should not receive:
- giant text wall
- hidden product spam
- unexplained product list with no care context

---

## 14. Recommendation lifecycle and product linkage

Product linkage must not replace lifecycle.

A recommendation may move through:
- `draft`
- `prepared`
- `issued`
- `viewed`
- `acknowledged`
- `accepted`
- `declined`
- `withdrawn`
- `expired`

The linked products/sets stay attached as recommendation targets.

This lets the system answer:
- what was recommended?
- by whom?
- why?
- did the patient respond?
- what products were linked?

One patient note column with `nm2 nm3 nm17` cannot answer these questions cleanly.
That is why this model exists.

---

## 15. Recommendation sets as operator abstraction

Recommendation sets deserve special emphasis.

Without sets, every doctor/manager ends up:
- typing SKUs manually
- inventing local habits
- creating hidden inconsistency

With sets:
- the same care scenario maps to the same consistent group of products
- operators maintain one artifact centrally
- recommendations become easier to issue and revise

This is one of the most practical design wins in the whole commerce block.

---

## 16. Manual patient-level assignment model

There is a practical question:
where should a doctor/manager assign concrete recommendations for a patient?

### Wrong baseline
A single patient column with product codes as the only source of truth.

### Better baseline
A dedicated patient recommendation record, optionally authored from:
- doctor UI
- manager UI
- import/sync sheet row
- rule engine

### Practical compromise
If operator authoring through workbook is needed, use a dedicated tab like:
- `patient_recommendations`

One row = one recommendation assignment

Fields may include:
- `patient_ref`
- `source_kind`
- `recommendation_type`
- `set_code`
- `product_codes`
- `booking_ref`
- `encounter_ref`
- `author_ref`
- `status`
- `issued_at`
- `expires_at`
- `comment`

This is a valid operator shortcut layer.

But it must still become canonical recommendation truth in DB after import/sync.
It must not replace the recommendation entity model.

---

## 17. AI future role

AI is not baseline engine behavior.

Future AI may:
- suggest likely set/product targets
- suggest better rationale wording
- surface probable follow-up recommendations

But AI should be:
- assistive
- bounded
- human-confirmed

Baseline recommendation engine must remain rule-based and explainable without AI.

---

## 18. What is automatic vs manual

This must be explicit.

## Automatic baseline
Allowed:
- context -> suggestion
- context -> prepared recommendation
- narrow safe auto-issue in clearly defined cases

## Manual baseline
Allowed:
- doctor/manual issue
- manager/manual issue where role permits
- doctor override of rule suggestion

### Recommended current stance
For DentFlow baseline:
- auto-suggest and auto-prepare are the main strategy
- doctor-confirmed issue remains the default for many recommendation contexts

This keeps the system clinically sane.

---

## 19. Recommendation event readiness

The engine must remain event-friendly.

Important lifecycle transitions should emit:
- `recommendation.created`
- `recommendation.issued`
- `recommendation.viewed`
- `recommendation.acknowledged`
- `recommendation.accepted`
- `recommendation.declined`
- `recommendation.expired`
- `recommendation.withdrawn`

The engine model should preserve enough structure for future analytics like:
- uptake rate by type
- doctor acceptance/decline patterns
- service-linked recommendation performance

This is readiness, not full analytics scope.

---

## 20. Explicit non-goals

This engine does **not** include:
- giant AI recommender
- patient marketplace personalization engine
- free-form marketing campaign engine
- care-commerce order logic itself
- stock logic
- shipping/delivery decisions
- owner recommendation analytics UI

Those are neighboring layers, not this one.

---

## 21. Summary

The DentFlow recommendation-to-product engine is built on these principles:

- recommendation is canonical and first-class;
- baseline engine is rule-based and explainable;
- doctor override is supported;
- set-based mapping is preferred where practical;
- patient receives structured recommendation, not random product spam;
- patient-level recommendation truth must remain a real entity, not a cell with product codes;
- future AI may assist, but must not replace the baseline engine.

This is the layer that turns recommendation from a vague idea into a controllable system.

That is the point.
