# DentFlow Search Model

> Canonical search architecture and retrieval model for DentFlow.

## 1. Purpose of this document

This document defines how search works in DentFlow.

Its purpose is to ensure that search is designed as a first-class subsystem from the beginning rather than bolted on after the rest of the product has already hardened around bad assumptions.

DentFlow search must support:

- patient lookup;
- doctor lookup;
- service lookup;
- booking flow assistance;
- voice-assisted retrieval;
- multilingual and transliterated input;
- fast mobile-first operational use for admin, doctor, owner and patient flows;
- safe degradation when the search layer is unavailable or confidence is low.

This document complements:

- `README.md`
- `docs/10_architecture.md`
- `docs/15_ui_ux_and_product_rules.md`
- `docs/17_localization_and_i18n.md`
- `docs/18_development_rules_and_baseline.md`
- `docs/20_domain_model.md`
- `docs/25_state_machines.md`
- `docs/30_data_model.md`
- `docs/35_event_catalog.md`
- `booking_docs/*`

This is the canonical search specification for DentFlow.

---

## 2. Why search is first-class in DentFlow

DentFlow is not a website with a search box for decorative purposes.

Search in DentFlow is an operational surface.

That means bad search is not just annoying. Bad search directly damages:

- booking speed;
- admin productivity;
- doctor productivity;
- patient recognition;
- reminder routing;
- repeat-visit handling;
- owner visibility into actual operations.

Search must therefore be treated as a system capability, not a convenience.

### In practical terms, DentFlow search must solve four different jobs:

1. **Patient retrieval**
   - find the right person fast;
   - tolerate typo-heavy names;
   - tolerate transliteration differences;
   - support voice input;
   - show enough context to avoid selecting the wrong patient.

2. **Doctor retrieval**
   - locate doctor by name, specialty, or booking context;
   - support quick operational assignment;
   - support patient-facing booking guidance.

3. **Service retrieval**
   - support patient booking by symptom or intent;
   - support staff lookup by service name, alias, category, or specialty group;
   - support multilingual discoverability.

4. **Search-assisted workflow routing**
   - use search results to open the right patient card, booking card, slot selection flow, or doctor schedule;
   - support voice-assisted retrieval and operational shortcuts.

---

## 3. Core search principles

## 3.1 Search is not source of truth

Search indexes and search documents are projections.

Canonical truth remains in transactional storage:

- patient truth in Patient Registry / related contexts;
- doctor, service, branch, slot truth in Booking contexts;
- reminder truth in Communication;
- clinical truth in Clinical;
- commerce truth in Care Commerce.

If search fails, DentFlow must degrade to slower lookup or explicit manual refinement.
It must not lose truth.

## 3.2 Search must be usable from day one

Search is an early subsystem, not a post-MVP embellishment.

This means the data model, seed fixtures, UI flows and event model must already support search projection and search-based workflows during early development.

## 3.3 Search must be multilingual and transliteration-aware

DentFlow starts RU + EN from day one and must be easy to extend to Georgian and Polish later.

Search must therefore handle:

- Cyrillic input;
- Latin input;
- transliterated versions of names;
- mixed-script queries;
- locale-aware tokenization;
- imperfect user input.

## 3.4 Search must be operationally safe

Being “smart” is not enough.
The system must avoid dangerous false positives in sensitive flows.

Examples:

- opening the wrong patient because two names are similar;
- selecting the wrong doctor from fuzzy results without explicit confirmation;
- auto-attaching an action to the wrong booking because voice input matched the wrong surname.

Therefore search must support:

- ranked candidates;
- confidence thresholds;
- clarification steps when confidence is insufficient;
- compact result cards with disambiguating fields.

## 3.5 Search should prefer useful speed over theoretical completeness

Search is designed for mobile, Telegram-first operations.

That means:

- top results matter more than long lists;
- relevance must be optimized for first-screen decision making;
- result cards must be concise but informative;
- filtering and refinement must stay lightweight.

---

## 4. Search surfaces in DentFlow

Search is exposed through several user surfaces.

## 4.1 Patient search surface

Used by:

- admin;
- doctor;
- owner (limited operational overview);
- patient flow when reusing an existing profile or linking a returning patient;
- voice-assisted retrieval.

Search entry points:

- explicit “Find patient” action;
- booking flow when user indicates returning patient;
- admin panel;
- doctor quick actions;
- owner drilldown;
- reply/callback-based fast search;
- voice-first command.

## 4.2 Doctor search surface

Used by:

- booking flow;
- admin reassignment;
- owner analytics drilldown;
- doctor-side navigation;
- patient booking by doctor name.

## 4.3 Service search surface

Used by:

- patient booking;
- admin booking;
- patient symptom-to-service routing;
- voice booking assistance;
- internal discovery.

## 4.4 Search-assisted action surfaces

Search does not end with “found item”.
It should immediately support action.

Examples:

- open patient card;
- create booking;
- open upcoming bookings;
- mark check-in;
- attach note;
- open doctor schedule;
- continue booking flow;
- open recommendation card.

---

## 5. Search domains and document types

DentFlow search should use distinct search document types/projections rather than one undifferentiated blob.

Recommended primary searchable projections:

1. `patient_search_document`
2. `doctor_search_document`
3. `service_search_document`
4. `branch_search_document` *(secondary but useful)*
5. `booking_lookup_document` *(secondary operational projection)*

The first three are mandatory from the early product phase.

---

## 6. Patient search model

Patient search is the most important retrieval surface in DentFlow.

### 6.1 Design goals

Patient search must:

- find patients by name, surname, patronymic, phone, card number, aliases, or voice input;
- tolerate spelling variation;
- tolerate transliteration differences;
- show patient recognition cues;
- support repeated names without chaos;
- be safe enough for real clinic work.

### 6.2 Recommended patient search document

`patient_search_document` should be a denormalized projection derived from transactional truth.

### Core fields

- `patient_id`
- `clinic_id`
- `patient_number`
- `display_name`
- `full_name_legal`
- `first_name`
- `last_name`
- `middle_name`
- `name_tokens`
- `name_tokens_normalized`
- `translit_tokens`
- `alias_tokens`
- `phone_primary_normalized`
- `phone_other_normalized`
- `birth_date`
- `age_bucket` *(derived, optional)*
- `preferred_language`
- `primary_photo_preview_ref`
- `last_doctor_display_name`
- `last_service_label`
- `last_visit_at`
- `upcoming_booking_at`
- `active_patient_flags`
- `search_status`
- `search_rank_features_json`

### Optional but valuable fields

- `sex_marker`
- `city_or_locality` *(if actually useful and legally acceptable in the deployment)*
- `notes_short_operational`
- `has_ct_link`
- `has_primary_photo`

### Important rule

The patient search document is not the full patient card.
It is a retrieval-optimized summary.

---

## 7. Doctor search model

Doctor search must be optimized for both patient-facing and operator-facing retrieval.

### 7.1 Design goals

Doctor search must support:

- name lookup;
- specialty lookup;
- booking routing;
- multilingual doctor display;
- future branch-aware filtering.

### 7.2 Recommended doctor search document

- `doctor_id`
- `clinic_id`
- `display_name`
- `full_name`
- `name_tokens`
- `translit_tokens`
- `specialty_code`
- `specialty_label_ru`
- `specialty_label_en`
- `specialty_alias_tokens`
- `branch_ids`
- `is_active`
- `rank_weight`
- `photo_preview_ref` *(optional)*

### Important note

Doctor search must support retrieval by specialty even if the exact doctor name is unknown.
This is especially important in patient booking flows.

---

## 8. Service search model

Service search must bridge the gap between:

- clinic-internal service language;
- patient natural language;
- multilingual presentation.

Patients often do not know the official service title.
They search by pain, problem, or intention.

### 8.1 Design goals

Service search must support:

- exact service name lookup;
- alias lookup;
- symptom-to-service routing;
- specialty-group lookup;
- multilingual labels;
- voice-assisted booking.

### 8.2 Recommended service search document

- `service_id`
- `clinic_id`
- `service_code`
- `title_ru`
- `title_en`
- `title_default`
- `description_short_ru`
- `description_short_en`
- `search_aliases_ru`
- `search_aliases_en`
- `symptom_tags`
- `specialty_group`
- `booking_mode`
- `default_duration_minutes`
- `is_active`
- `rank_weight`

### 8.3 Symptom mapping principle

Service search should support patient-intent language such as:

- “болит зуб”;
- “откололся зуб”;
- “чистка”;
- “нужен имплант”;
- “брекеты”;
- “кровоточат десны”.

This does not mean the search index diagnoses the patient.
It means service discovery must be able to route from problem language to likely booking category.

---

## 9. Branch search model

Branch search is secondary but useful in larger clinics.

### Recommended fields

- `branch_id`
- `clinic_id`
- `title_ru`
- `title_en`
- `address_text`
- `city_tokens`
- `geo_reference`
- `is_active`

Useful for:

- branch-aware booking;
- owner/admin lookup;
- pickup routing;
- patient-facing navigation.

---

## 10. Booking lookup projection

This is not a general search document for everyone, but an operational lookup projection.

Useful for:

- admin opening upcoming booking by patient or doctor;
- doctor opening today's patients;
- quick operational filtering.

### Recommended fields

- `booking_id`
- `clinic_id`
- `patient_id`
- `patient_display_name`
- `doctor_id`
- `doctor_display_name`
- `service_id`
- `service_title_default`
- `branch_id`
- `status`
- `scheduled_start_at`
- `scheduled_end_at`
- `patient_photo_preview_ref`
- `priority_flags`

This can be served by transactional queries or a dedicated projection depending on complexity.

---

## 11. Normalization pipeline

Search quality depends more on normalization discipline than on raw engine cleverness.

DentFlow search must apply a normalization pipeline before indexing and before querying.

## 11.1 Core normalization steps

For indexed fields and user queries:

- trim whitespace;
- lowercase;
- collapse duplicate spaces;
- remove noisy punctuation where appropriate;
- normalize phone numbers to canonical search form;
- normalize common dash/apostrophe/quote variants;
- normalize mixed-script confusion where safe;
- tokenize according to locale-aware rules.

## 11.2 Name normalization

Names should support:

- exact tokens;
- normalized tokens;
- transliterated tokens;
- concatenated variants where useful;
- patronymic/middle-name tolerance;
- surname-first and first-name-first patterns.

### Examples of operational need

The system must remain useful when the user searches using:

- legal spelling;
- colloquial spelling;
- transliterated form;
- partial surname;
- phone number;
- voice-transcribed approximation.

## 11.3 Phone normalization

Phone search must normalize to a canonical digit-only representation with deployment-aware country handling.

Search should support:

- full number;
- tail digits;
- with/without country code;
- copy-pasted messy formatting.

### Important rule

Phone normalization must be deterministic and shared between:

- import scripts;
- transaction writes;
- search indexing;
- user query normalization.

## 11.4 Transliteration support

DentFlow must support transliteration-aware retrieval.

This means indexed documents should keep transliteration variants for fields where this matters, especially:

- patient names;
- doctor names;
- service aliases if cross-lingual discovery is expected.

### Requirements

- reversible perfection is not required;
- practical retrieval usefulness is required;
- transliteration rules must be centralized, not improvised in random handlers.

## 11.5 Alias handling

Search should support aliases where operationally useful.

Examples:

- service nickname vs formal title;
- doctor common short form;
- patient known alternate translit;
- symptom phrase mapping to service intent.

Alias systems must remain controlled and auditable.
Not every random substring deserves to become an alias forever.

---

## 12. Fuzzy search rules

DentFlow search must be typo-tolerant, but not recklessly permissive.

## 12.1 Where fuzzy search is appropriate

Appropriate for:

- patient name search;
- doctor name search;
- service alias search;
- voice-transcribed query correction.

## 12.2 Where fuzzy search must be constrained

Fuzzy matching must be more conservative when:

- the result could open the wrong patient;
- the result could attach a command to the wrong person;
- multiple close matches exist;
- the query is short and ambiguous.

## 12.3 Confidence strategy

Search results should conceptually produce or imply confidence tiers:

- **high confidence**: can safely show compact result set with likely top match;
- **medium confidence**: require user selection from a shortlist;
- **low confidence**: ask for refinement, alternate identifier, or manual input.

Do not silently auto-select low-confidence patient matches.

---

## 13. Voice-assisted retrieval

Voice-assisted retrieval is an early product surface in DentFlow.
It is not deferred luxury.

But it must remain narrow and useful.

## 13.1 What voice-assisted retrieval is

It is a focused voice entry surface for actions such as:

- find patient;
- find doctor;
- find service;
- continue booking;
- open booking by patient;
- attach quick operational action after search result selection.

## 13.2 What it is not

It is not a universal free-form AI agent that should understand every chaotic monologue in existence.

Do not build theatrical voice complexity where a strong retrieval surface is enough.

## 13.3 Voice retrieval pipeline

Recommended logical flow:

1. user activates voice search;
2. voice audio is transcribed;
3. transcription is normalized;
4. intent surface is known by context or explicit search mode;
5. query is executed against relevant search document(s);
6. ranked candidates are returned;
7. user confirms selection if needed;
8. action continues.

## 13.4 Voice search modes

Recommended modes:

- patient search mode;
- doctor search mode;
- service search mode;
- contextual search mode inside booking flow.

This reduces ambiguity and improves retrieval quality.

## 13.5 Low-confidence behavior

If STT confidence or search confidence is low:

- present top candidates;
- allow repeat voice attempt;
- allow text refinement;
- allow fallback to phone or patient number.

### Important rule

Never execute sensitive patient actions based only on a weak, unconfirmed voice match.

---

## 14. Search architecture

## 14.1 Recommended architecture

DentFlow search should use a dedicated search layer / index.

Conceptually:

- transactional contexts write truth;
- important entity changes emit events;
- search projection builders consume those events;
- search index stores retrieval-optimized documents;
- search UI queries the search layer;
- fallback query path exists for degraded mode.

## 14.2 Projection build sources

Search projections should update based on important events such as:

- `patient.created`
- `patient.updated`
- `patient.contact_added`
- `patient.contact_updated`
- `patient.preference_updated`
- `patient.photo_updated`
- `booking.created`
- `booking.completed`
- `doctor` entity changes
- `service` entity changes
- branch changes where relevant

## 14.3 Rebuild capability

Search projections must be rebuildable from source-of-truth data.

This means:

- index corruption must not become catastrophic;
- reindex should be possible from baseline data;
- seed fixtures should populate search surfaces during test/bootstrap.

## 14.4 Fallback mode

If search layer is unavailable:

- use transactional fallback queries for essential patient/doctor/service retrieval where feasible;
- expose degraded-mode UX clearly if response quality is reduced;
- avoid pretending search still behaves normally.

Fallback is for continuity, not for pretending nothing happened.

---

## 15. Search ranking principles

Search ranking must be domain-aware.

## 15.1 Patient ranking factors

Potential ranking factors:

- exact phone match;
- exact patient number match;
- exact normalized full-name match;
- exact surname + first-name match;
- transliterated match;
- fuzzy distance;
- recent activity;
- upcoming booking;
- active patient status;
- presence of patient photo;
- relevance to current context/clinic/branch.

## 15.2 Doctor ranking factors

Potential ranking factors:

- exact name match;
- specialty match;
- patient-facing booking context;
- clinic/branch availability;
- active status.

## 15.3 Service ranking factors

Potential ranking factors:

- exact title match;
- alias match;
- symptom-tag match;
- specialty-group match;
- booking suitability;
- current clinic availability.

## 15.4 Contextual ranking

Search should use context where available.

Examples:

- inside booking flow, prioritize active bookable doctors/services;
- inside admin patient lookup, prioritize recent patients and upcoming bookings;
- inside owner drilldown, prioritize entity relevance to current filter.

---

## 16. Search result presentation rules

Search results must follow the UI/UX rules of DentFlow.

## 16.1 General result card rules

Result cards should be:

- compact;
- scannable;
- mobile-friendly;
- action-oriented;
- safe for disambiguation.

## 16.2 Patient result card should typically show

- patient display name;
- secondary identifier (phone tail, birth date, patient number, or similar);
- patient photo preview if available;
- last doctor or last visit cue;
- upcoming booking cue if relevant;
- active warning flags if operationally important.

## 16.3 Doctor result card should typically show

- doctor display name;
- specialty;
- branch cue if needed;
- available action.

## 16.4 Service result card should typically show

- service title;
- short category or specialty group;
- short description or intent cue;
- action to continue booking.

## 16.5 Result set sizing

Preferred behavior:

- small shortlist first;
- explicit refine/load-more path if needed;
- do not flood chat with giant dumps.

---

## 17. Search flows by role

## 17.1 PatientBot

Search uses:

- doctor lookup;
- service lookup;
- symptom-to-service routing;
- returning-patient retrieval where supported;
- voice-assisted lookup in selected flows.

## 17.2 ClinicAdminBot

Search uses:

- patient retrieval;
- doctor retrieval;
- service retrieval;
- booking lookup;
- quick operational jump surfaces.

This is the heaviest search consumer.

## 17.3 Doctor-side flows

Search uses:

- patient retrieval;
- today's bookings;
- quick open by voice or text;
- media/document access through patient context.

## 17.4 OwnerBot

Search uses:

- drilldown into patient, doctor, service, and booking context;
- operational summary navigation;
- exception follow-through.

Owner search should stay compact and context-aware, not become a full admin console clone.

---

## 18. Search and localization

Search must be consistent with the localization strategy.

## 18.1 Search index language handling

Recommended approach:

- store canonical multilingual fields explicitly;
- store normalized search tokens independent of UI locale;
- support locale-aware formatting in results;
- preserve RU and EN retrieval from the start.

## 18.2 Search query locale

Where available, search should use:

- user locale preference;
- clinic default locale;
- explicit flow context.

But locale must not block retrieval if the user types in another script or language.

## 18.3 Future language extension

Adding Georgian or Polish later should mostly mean:

- new localized display fields;
- updated alias dictionaries;
- updated transliteration/normalization rules where useful;
- no rewrite of core search architecture.

---

## 19. Search and import/seed strategy

Search must be testable before Google Sheets integration exists.

Therefore first-launch development must support:

- scripted doctor import;
- scripted service import;
- scripted fake patient import;
- scripted booking history import;
- projection build from seed data.

Search quality cannot be evaluated on an empty database with two fake rows and a heroic imagination.

## 19.1 Seed requirements for search testing

Search fixtures should include:

- repeated surnames;
- mixed-script names;
- transliterated variants;
- phone formatting variations;
- multiple doctors per specialty;
- overlapping service aliases;
- patients with and without photos;
- patients with and without prior visits.

That is how real search weaknesses reveal themselves before production humiliates everyone.

---

## 20. Search and Google Sheets

Google Sheets sync is an integration surface, not a replacement for search modeling.

### Important rules

- search documents must be built from DentFlow truth and controlled sync paths;
- Sheets may feed doctor/service/patient import workflows if explicitly supported later;
- search field assumptions must not depend on spreadsheet improvisation;
- normalization must happen inside DentFlow-controlled pipelines.

Do not let search quality depend on however someone typed names in a sheet five minutes before lunch.

---

## 21. Search event dependencies

Search projection builders will typically consume these event families:

- `patient.*`
- selected `booking.*`
- doctor entity updates
- service entity updates
- branch updates where relevant
- `patient.photo_updated`
- `patient.flag_set`
- `patient.flag_cleared`

Search itself may emit internal projection events such as:

- `search_projection.patient_rebuilt`
- `search_projection.doctor_rebuilt`
- `search_projection.service_rebuilt`

These are operational signals, not business truth.

---

## 22. Security and privacy considerations for search

Search deals with sensitive information.

Therefore:

- patient result cards must be scoped by clinic and permissions;
- owner search should not expose more than owner-facing scope permits;
- not every role should see every clinical detail in search results;
- search payloads should remain retrieval-oriented rather than dumping full private records;
- external links to CT or imaging must not be sprayed carelessly into broad result sets.

Search should help people work.
It should not help them casually overexpose patient data.

---

## 23. Explicit non-goals

This document does not define:

- the final search engine vendor choice;
- exact tokenizer implementation;
- exact transliteration library choice;
- exact scoring formula;
- final STT provider choice;
- final caching strategy;
- full ACL model.

Those belong in implementation and infrastructure layers.

This document defines the retrieval model and architectural contract.

---

## 24. Summary

DentFlow search is a first-class subsystem.

It must:

- serve patients, admins, doctors and owners;
- support patient, doctor and service retrieval;
- be multilingual and transliteration-aware;
- support voice-assisted retrieval early;
- update from event-driven projections;
- degrade safely when search confidence or availability is low;
- stay compact, mobile-friendly and operationally useful;
- remain clearly separated from source-of-truth transactional storage.

Good search in DentFlow is not “nice UX”.
It is part of the operating system of the clinic.
