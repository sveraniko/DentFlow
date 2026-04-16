# DentFlow Care Commerce

> Care-commerce model for DentFlow.  
> Defines how clinical recommendations, patient education, aftercare products, reservations, pickup flows, and related analytics work together without turning the system into a generic marketplace or a medical paperwork monster.

## 1. Purpose of this document

This document defines the DentFlow care-commerce subsystem.

Its purpose is to:

- formalize care-commerce as a first-class DentFlow context;
- connect recommendations and aftercare products to real patient journeys;
- support post-visit and condition-based product suggestions without degrading trust;
- define product catalog, reserve, pickup, issue, and fulfillment flows;
- connect care-commerce with reminders, owner analytics, search, booking, and patient context;
- ensure that the subsystem remains clinically relevant and operationally lightweight.

This document complements:

- `README.md`
- `docs/10_architecture.md`
- `docs/15_ui_ux_and_product_rules.md`
- `docs/20_domain_model.md`
- `docs/25_state_machines.md`
- `docs/30_data_model.md`
- `docs/35_event_catalog.md`
- `docs/50_analytics_and_owner_metrics.md`

---

## 2. Why DentFlow needs care-commerce

In private dental practice, aftercare and hygiene products are not just merchandise.
They are often a practical continuation of treatment.

Examples:
- after professional hygiene, the patient should often replace the toothbrush;
- with periodontal issues, an irrigator or suitable hygiene tools may be clinically helpful;
- with braces or aligner-related care, specific cleaning tools are often highly relevant;
- after surgery or implant-related care, certain soft-care or guided-care products may be appropriate;
- for children, age-appropriate brushes and routines may be part of treatment adherence.

The problem in many clinics is that products exist physically in the clinic, but sales are weak because:
- the patient does not understand what is relevant;
- the patient is shy about asking;
- the patient does not want to be “sold to” in an obvious way;
- the clinic staff is busy and does not systematically explain products;
- recommendations are not timed well.

DentFlow solves this by turning aftercare sales into **care-commerce**:

- recommendation-led;
- medically contextualized;
- low-friction;
- optionally reserve-and-pickup based;
- tied to visits, diagnoses, treatment stage, and care plans;
- visible to owner analytics as a distinct revenue and adherence layer.

This is not a generic marketplace.
This is a structured aftercare and treatment-support layer.

---

## 3. Core product thesis

Care-commerce in DentFlow must behave like:

- guided care support,
- contextual recommendation,
- operational convenience,
- retention support,
- revenue augmentation.

It must **not** behave like:

- random up-selling spam,
- generic e-commerce catalog bloat,
- an aggressive marketplace inside the clinic chat,
- unrelated retail noise.

### Product principle

A product should be offered because it makes sense **for this patient, in this situation, at this time**.

That means care-commerce must be driven by:
- visit type;
- clinical recommendation;
- treatment stage;
- patient context;
- follow-up timing;
- prior purchases or usage patterns;
- owner-configured clinic policy.

---

## 4. Care-commerce scope

DentFlow care-commerce covers:

### 4.1 Included in scope
- hygiene tools;
- toothbrushes;
- irrigators;
- floss / interdental tools;
- post-hygiene recommendations;
- braces / orthodontic care tools;
- selected aftercare kits;
- reserve-and-pickup;
- issue at visit;
- follow-up reminders for recommended products;
- recommendation-to-product flows;
- owner analytics around attach rate and care-product uptake.

### 4.2 Conditionally included
- home delivery, if clinic policy supports it;
- bundled care kits;
- replenishment reminders;
- doctor-specific recommended products;
- limited stock handling at branch level;
- payment at order time or payment at pickup.

### 4.3 Out of scope for v1
- full online shop for arbitrary consumer goods;
- large warehouse ERP;
- broad price-engine complexity;
- marketplace with unrelated dental cosmetics and random catalog clutter;
- complex supplier procurement flows;
- omnichannel ecommerce complexity with shipping logistics comparable to a retail company.

DentFlow is not being built to become “Dental Amazon”. Civilization has enough problems already.

---

## 5. Product principles

## 5.1 Care before commerce

The message must begin from patient benefit, not from sale intent.

Good:
- “After your hygiene visit, replacing the toothbrush is recommended.”
- “For your case, the doctor recommended soft cleaning tools and an irrigator.”
- “With braces, these cleaning tools help maintain results more effectively.”

Bad:
- “Buy our new brush now.”
- “Special offer on irrigators today.”

## 5.2 Recommendation-led, not catalog-led

The catalog may exist, but the main flow should be recommendation-driven.

Typical user entry points:
- after completed visit;
- from doctor recommendation;
- from admin-issued care advice;
- from reminder flow;
- from patient asking “what should I use?”.

## 5.3 Small choice sets, not endless shelves

The patient should usually see a curated, limited choice set.

Preferred pattern:
- essential option;
- better option;
- premium option.

Not:
- 18 similar brushes;
- 11 irrigators with no guidance;
- 7 pastes that all look interchangeable.

## 5.4 Low-friction fulfillment

DentFlow should support practical pickup-oriented flows:
- reserve now, collect later;
- add to upcoming visit;
- pay now, pick up at clinic;
- reserve without payment if clinic policy allows;
- issue directly during or after visit.

## 5.5 Clinic-safe operational complexity

Care-commerce must remain simple enough for clinics that do not have a dedicated ecommerce team.

That means:
- modest catalog size;
- branch-aware but not warehouse-crazy stock logic;
- simple order states;
- clear reserve/pickup/issue flows;
- minimal operator burden.

---

## 6. Where care-commerce fits in DentFlow architecture

Care-commerce is its own bounded context.

It interacts with:

- Booking, through visit outcomes and timing;
- Clinical, through recommendation source and care relevance;
- Communication, through reminders and follow-up prompts;
- Search, for product/search surfaces if needed;
- Analytics and Owner layer, for revenue and attach-rate tracking;
- Media/Documents, for product media or guide attachments;
- Integration, for optional Sheets sync or external systems later.

Care-commerce does **not** own:
- patient identity truth;
- appointment truth;
- diagnosis truth;
- treatment-plan truth.

It consumes those contexts and produces its own order/reservation/revenue truth.

---

## 7. Main care-commerce use cases

## 7.1 Post-hygiene product recommendation

### Trigger
- visit completed;
- service group = hygiene / professional cleaning.

### Typical recommendation set
- replace toothbrush;
- optional paste or maintenance item;
- optional interdental tools.

### Typical timing
- immediately after visit;
- later same day;
- next morning if clinic prefers softer timing.

### Primary value
- preserve hygiene result;
- increase attach rate to a clinically plausible product;
- improve feeling of care continuity.

---

## 7.2 Periodontal / gum care recommendation

### Trigger
- diagnosis or doctor/admin recommendation;
- relevant visit type;
- flagged oral/gum care need.

### Typical recommendation set
- soft toothbrush;
- irrigator;
- interdental cleaning tools;
- appropriate hygiene aid bundle.

### Primary value
- guidance for home care;
- better adherence;
- higher trust than passive shelf display.

---

## 7.3 Braces / orthodontic support

### Trigger
- orthodontic visit;
- braces / aligner-related patient segment.

### Typical recommendation set
- orthodontic brush;
- irrigator;
- interdental tools;
- wax or care accessories if clinic supports such items;
- follow-up reminders for usage/replenishment.

### Primary value
- repeated care-commerce potential;
- strong ongoing relationship;
- high contextual fit.

---

## 7.4 Pediatric dental care

### Trigger
- child patient segment;
- pediatric visit;
- first-visit guidance.

### Typical recommendation set
- age-appropriate brush;
- age-appropriate paste;
- parent guidance material;
- starter care kit.

### Primary value
- supports family retention;
- builds long-term relationship with parents;
- feels educational rather than salesy.

---

## 7.5 Surgical / implant aftercare

### Trigger
- relevant surgery / implant encounter;
- clinician-issued recommendation.

### Typical recommendation set
- soft-care hygiene tools;
- aftercare-supportive items allowed by clinic policy;
- follow-up reminder with usage guidance.

### Important rule
These flows must remain restrained and clinically appropriate.
This is not where we throw a random product carousel at a patient who just had an invasive procedure.

---

## 7.6 Reserve before arrival / pickup at clinic

### Trigger
- patient chooses product after recommendation;
- patient wants item held until visit or pickup.

### Flow
1. patient sees curated recommendation;
2. patient selects item;
3. reserve / pay / confirm pickup mode;
4. admin/clinic prepares item;
5. item marked ready;
6. patient collects;
7. clinic issues order;
8. system marks fulfillment complete.

This is especially useful for clinics where in-person display exists but spontaneous browsing is weak.

---

## 8. Care-commerce actors

## 8.1 Patient
Can:
- receive recommendations;
- view curated products;
- reserve products;
- place order;
- confirm pickup;
- optionally pay;
- view order status;
- decline recommendation.

## 8.2 Admin
Can:
- issue manual recommendation;
- confirm/reserve/prepare product;
- mark ready for pickup;
- issue product;
- cancel reservation/order;
- view care-product queue.

## 8.3 Doctor
Can:
- attach recommendation;
- mark a product or bundle as clinically recommended;
- choose recommendation rationale;
- optionally choose recommended level or priority.

Doctor should not be forced into retail operations.
Doctor input should be fast and clinically meaningful.

## 8.4 Owner
Can:
- monitor attach rate;
- view product/category performance;
- compare doctors/services by recommendation uptake;
- detect missed care-commerce opportunities;
- view pickup / issue bottlenecks;
- use AI-assisted summaries.

---

## 9. Core concepts and entities

Care-commerce entities are defined at the data-model level in `docs/30_data_model.md`.
This section explains how they behave conceptually.

## 9.1 CareProduct
A product or curated care item sold or reserved through the clinic.

### Typical fields
- SKU;
- title;
- category;
- short description;
- use-case tags;
- price;
- branch availability or stock mode;
- pickup/delivery support;
- active status.

## 9.2 CareBundle
Optional curated group of products.

Examples:
- post-hygiene kit;
- braces care starter kit;
- sensitive gums care kit;
- child first-visit kit.

Bundles are useful because they reduce decision friction and increase attach rate while remaining clinically understandable.

## 9.3 RecommendationProductLink
Explains why a given product is linked to a recommendation.

This must support:
- relevance ranking;
- justification key;
- optional custom doctor/admin explanation.

## 9.4 CareOrder
Represents a patient-facing order or reservation intent.

Possible fulfillment modes:
- reserve and pickup;
- order and pay before pickup;
- issue during visit;
- fulfill directly after recommendation.

## 9.5 CareReservation
Represents stock allocation or held quantity.

This is more granular than order state.
One order may have multiple reservations.

---

## 10. Recommendation-to-product logic

This is the heart of care-commerce.

A product should normally appear because one of these happened:

### 10.1 Visit-type trigger
Example:
- hygiene visit completed -> toothbrush replacement recommended.

### 10.2 Clinical context trigger
Example:
- gum care context -> soft hygiene tools and irrigator recommended.

### 10.3 Doctor-issued trigger
Example:
- doctor explicitly recommends product/bundle.

### 10.4 Admin-issued trigger
Example:
- admin sends follow-up recommendation based on visit outcome.

### 10.5 Schedule or follow-up trigger
Example:
- after braces care interval, patient receives replenishment reminder.

### 10.6 Patient-initiated guidance trigger
Example:
- patient asks what they should use.

### Recommendation selection inputs
The recommendation engine should be able to use:
- visit type;
- service group;
- diagnosis category or clinical tag;
- patient segment;
- age segment;
- treatment stage;
- previous recommendation outcomes;
- previous purchases;
- clinic policy and branch availability;
- doctor-specific preferred products.

### Recommendation output format
Recommended output is not “full catalog”.
It is:
- reason;
- up to a few options;
- optional product comparison;
- action buttons.

---

## 11. Doctor-issued recommendations

Doctor-issued recommendations deserve first-class support.

Why:
- trust is much higher;
- recommendation feels medically grounded;
- conversion improves;
- owner can measure doctor recommendation uptake.

### Minimal doctor-side pattern
Doctor should be able to do something like:
- choose “recommend care item”;
- pick one product or bundle;
- pick reason template;
- send to patient.

### Example reason templates
- after hygiene replacement;
- braces hygiene support;
- gum-care support;
- soft post-procedure care;
- daily maintenance support.

Doctor does not need retail dashboard complexity.
They need a fast “recommend” action surface.

---

## 12. Product catalog model

The DentFlow care catalog should stay compact and clinic-oriented.

## 12.1 Product categories
Recommended product categories:
- toothbrushes;
- irrigators;
- floss / interdental tools;
- post-hygiene kits;
- braces / orthodontic care;
- gum-care support;
- children’s care;
- other clinic-approved aftercare items.

## 12.2 Product metadata
Recommended metadata includes:
- title;
- short description;
- care category;
- use-case tags;
- branch availability;
- price;
- pickup support;
- stock mode;
- product media;
- optional “doctor recommended” badge support.

## 12.3 Stock strategy
V1 should support modest stock logic only.

Recommended options:
- `untracked`
- `simple_branch_stock`
- `reservation_only`

Do not build full warehouse complexity unless the clinic truly needs it.

---

## 13. Fulfillment modes

## 13.1 Reserve and pickup
Most practical clinic-first model.

Flow:
- patient reserves;
- clinic holds item;
- item becomes ready;
- patient collects;
- clinic issues item.

## 13.2 Pay before pickup
Useful for selected products or clinic policy.

Flow:
- patient selects item;
- payment required;
- after payment, item is prepared;
- pickup happens later.

## 13.3 Issue during visit
Useful when recommendation happens in clinic and patient decides immediately.

Flow:
- recommendation shown;
- product attached;
- admin or doctor confirms issue;
- order closes quickly.

## 13.4 Delivery (optional later)
This may exist later but must not distort v1 design.

---

## 14. Care order lifecycle

Canonical lifecycle states are defined in `docs/25_state_machines.md`.
This section explains their operational meaning for care-commerce.

### Typical path
- `draft`
- `created`
- `awaiting_confirmation`
- `confirmed`
- `awaiting_payment` (if needed)
- `paid` (if needed)
- `awaiting_fulfillment`
- `ready_for_pickup`
- `issued`
- `fulfilled`

### Alternative path
- `draft`
- `created`
- `confirmed`
- `awaiting_fulfillment`
- `issued`
- `fulfilled`

### Failure / stop path
- `created`
- `canceled`

### Timeout path
- `ready_for_pickup`
- `expired`

Order state and reservation state must remain separate.

---

## 15. Reservation model

Care reservations protect the clinic from chaos where product appears “held” informally in someone’s head.

### Reservation purpose
- allocate item quantity for a patient/order;
- protect against accidental double issue;
- support pickup flow;
- allow expiry and release.

### Reservation lifecycle
Defined in `docs/25_state_machines.md`.

Typical path:
- `created`
- `active`
- `consumed`

Alternative endings:
- `released`
- `expired`
- `canceled`

### V1 rule
Reservation logic should stay simple and branch-aware.
No warehouse opera.

---

## 16. Messaging and UI behavior for care-commerce

Care-commerce UI must follow `docs/15_ui_ux_and_product_rules.md`.

## 16.1 Main UX rules
- recommendation-first, not catalog-first;
- one active panel per flow;
- compact and actionable messages;
- no spammy product walls;
- no duplicate panels for the same order;
- clear next action.

## 16.2 Preferred action surfaces
Examples:
- view recommended options;
- reserve;
- pay now;
- add to upcoming visit;
- ready for pickup;
- cancel reservation.

## 16.3 Microcopy tone
Care-commerce messages must sound like:
- guidance,
- support,
- continuation of care.

Not like:
- discount blast,
- pushy retail promotion,
- marketplace chatter.

## 16.4 Patient-facing examples
Good concepts:
- “After your hygiene visit, it is recommended to replace the toothbrush.”
- “For your case, the doctor recommended the following care option.”
- “You can reserve it now and pick it up at the clinic.”

---

## 17. AI role in care-commerce

AI can strengthen care-commerce, but must remain grounded.

## 17.1 Allowed AI uses
- explanation of why a product is relevant;
- plain-language care guidance;
- owner summaries of care-commerce performance;
- recommendation rationale phrasing;
- anomaly explanations;
- segmentation suggestions based on actual system data.

## 17.2 Not allowed or tightly constrained
- inventing medical claims;
- making diagnosis;
- replacing doctor judgment;
- recommending products without a grounded rule or supported context;
- hallucinating stock, price, or recommendation source.

## 17.3 AI source grounding
AI output must be grounded in:
- visit type;
- known recommendation source;
- product metadata;
- patient segment rules;
- clinic-configured policy;
- actual metrics and history.

AI must not become a poet of dental retail nonsense.

---

## 18. Search implications

Care-commerce does not make DentFlow a generic product-search app, but search still matters.

### Search surfaces that may exist
- admin product lookup;
- product selection during doctor/admin recommendation;
- owner browsing of product performance;
- patient product lookup in limited guided contexts.

### Recommendation
Keep search tightly scoped:
- staff-facing search may be more flexible;
- patient-facing search should usually remain recommendation-oriented;
- do not open the door to full catalog chaos unless product strategy later truly requires it.

---

## 19. Analytics and owner metrics for care-commerce

Care-commerce must feed owner analytics as a distinct, measurable layer.

## 19.1 Core metrics
- care-commerce revenue;
- orders created;
- orders fulfilled;
- reservation volume;
- pickup completion rate;
- payment-before-pickup conversion;
- product/category performance;
- attach rate after relevant visits;
- recommendation acceptance rate;
- doctor-issued recommendation uptake;
- service-linked care-commerce performance.

## 19.2 Attach-rate metrics
Attach rate is one of the key metrics.

Examples:
- percentage of hygiene visits followed by care-product purchase/reservation;
- percentage of orthodontic visits leading to care uptake;
- percentage of doctor-issued recommendations accepted.

## 19.3 Owner questions this should answer
- Are we missing obvious aftercare opportunities?
- Which doctors issue recommendations that patients actually follow?
- Which services create the best care-commerce attachment?
- Which categories move well and which just collect dust?
- Where are products being reserved but not picked up?
- Is this helping patient care or just creating noise?

## 19.4 AI-assisted owner insight
AI can summarize:
- missed opportunities;
- branch/category bottlenecks;
- weak recommendation uptake;
- patient segment opportunities;
- likely reasons for weak attach rate.

But conclusions must remain grounded in real DentFlow data.

---

## 20. Event implications

Care-commerce events are defined in `docs/35_event_catalog.md`.

Key event families:
- `recommendation.*`
- `care_product.*`
- `care_order.*`
- `care_reservation.*`

### Important integration points
- `booking.completed` may trigger recommendation generation;
- `recommendation.accepted` may trigger order creation or care flow progression;
- `care_order.ready_for_pickup` may trigger reminder flow;
- `care_order.fulfilled` feeds owner metrics and retention logic.

---

## 21. Data model implications

The physical data strategy is defined in `docs/30_data_model.md`.

Important care-commerce entities include:
- `care_product`
- `care_order`
- `care_order_item`
- `care_reservation`
- `recommendation_product_link`

### Key ownership rule
Care-commerce owns order/reservation/product truth.
It does **not** own:
- patient truth;
- booking truth;
- diagnosis truth.

---

## 22. Google Sheets and operational editing

In later stages, selected parts of care-commerce may benefit from Google Sheets integration.

Reasonable use cases:
- product catalog maintenance;
- branch availability adjustments;
- price updates;
- simple campaign tagging;
- bundle definitions.

### Important rule
Sheets may serve as operator-friendly maintenance surface.
They must not silently become undocumented source of truth.

If Sheets sync is used, it must define:
- ownership of truth;
- sync direction;
- conflict rules;
- audit expectations.

---

## 23. Seed and test data strategy

Care-commerce must be testable before external integrations exist.

Required seed data for meaningful testing:
- curated product set;
- category examples;
- branch availability;
- recommendation links;
- fake orders;
- fake reservation states;
- visit-trigger examples;
- owner analytics sample density.

Without realistic product and order examples, care-commerce testing becomes fake theater.
And we already have enough theater in the world.

---

## 24. Security and access notes

Care-commerce is not as sensitive as clinical charting, but still requires role discipline.

### Patient
- can only see their own recommendations, orders, statuses.

### Admin
- can manage preparation, pickup, issue, cancellation, catalog updates according to role policy.

### Doctor
- can issue and view recommendation-linked care context;
- should not automatically gain broad retail management powers.

### Owner
- sees revenue and analytics;
- may see catalog and performance details;
- should not be forced into operational product handling views unless desired.

---

## 25. What v1 should deliver

A good v1 for care-commerce should include:
- compact care-product catalog;
- recommendation-to-product mapping;
- post-visit recommendation trigger support;
- doctor/admin-issued recommendation support;
- reserve-and-pickup flow;
- issue during visit flow;
- care-order lifecycle;
- owner attach-rate and revenue visibility;
- basic reminder support for pickup or follow-up.

### V1 should not try to include
- full online retail complexity;
- broad delivery logistics;
- advanced inventory accounting;
- giant promotional campaign engine;
- supplier ERP.

---

## 26. Summary

DentFlow care-commerce is a structured aftercare and patient-support layer.

It exists to:
- improve care continuity;
- increase relevant product uptake;
- support clinic convenience;
- create measurable revenue lift;
- help the owner understand what is working.

Its success depends on one central rule:

**care-commerce must feel like useful clinical support with convenient fulfillment, not like a generic shop awkwardly glued onto a dental clinic.**

That is how it stays valuable instead of becoming just another digital nuisance.
