# DentFlow Localization and i18n

> Language strategy, translation architecture, locale rules, and implementation constraints for multilingual DentFlow deployments.

## 1. Purpose of this document

This document defines how localization and i18n must work in DentFlow.

Its purpose is to prevent the usual disasters that happen when a multilingual product is treated as an afterthought:

- hardcoded UI strings spread across handlers;
- Russian-only assumptions baked into business logic;
- untranslated edge flows;
- locale-dependent bugs in formatting and search;
- a painful later rewrite when a second or third market appears.

DentFlow is being built **RU-first**, but it must be architected from day one to support multiple languages without structural rework.

This document defines:

- language strategy;
- locale model;
- translation architecture;
- fallback rules;
- content ownership;
- runtime switching behavior;
- formatting rules;
- implementation guardrails.

This document complements:

- `README.md`
- `docs/10_architecture.md`
- `docs/15_ui_ux_and_product_rules.md`
- `docs/20_domain_model.md`
- `booking_docs/50_booking_telegram_ui_contract.md`

If implementation conflicts with this document, implementation must be corrected.

---

## 2. Product stance

DentFlow must launch with **two UI languages from the start**:

- **Russian (`ru`)** as the primary authoring language;
- **English (`en`)** as the secondary supported language.

The architecture must make it easy to add more languages later, especially:

- **Georgian (`ka`)**
- **Polish (`pl`)**

This means DentFlow is **not** “Russian text now, translations later.”
It is a multilingual product whose first content authoring workflow happens to start in Russian.

The system must therefore assume:

- every user-visible string is localizable;
- every product surface must behave correctly under language switching;
- every domain flow must support message and panel rendering through the i18n layer;
- adding a locale must be mostly a translation/content task, not a code rewrite.

---

## 3. Goals

Localization in DentFlow must achieve five goals:

### 3.1 Immediate usability

The product must be usable in Russian and English from the first real pilot.

### 3.2 Low-friction future market entry

Adding Georgian, Polish, or another language must not require reworking handlers, state machines, or domain services.

### 3.3 Source-text discipline

Strings must come from translation resources, not inline literals scattered through the codebase.

### 3.4 Locale-safe behavior

Dates, times, amounts, labels, and language-dependent messaging must render correctly per locale.

### 3.5 Telegram-native switching

A user must be able to change the visible interface language through the bot settings/options flow without friction.

---

## 4. Supported language model

## 4.1 Initial supported locales

DentFlow v1 must support:

- `ru`
- `en`

## 4.2 Planned near-future locales

DentFlow must be designed to support near-term addition of:

- `ka`
- `pl`

## 4.3 Locale code stance

Use standard language codes in storage and runtime, for example:

- `ru`
- `en`
- `ka`
- `pl`

If later needed, region-aware locale variants may be introduced, for example:

- `en-GB`
- `en-US`
- `ka-GE`

But region variants must not be introduced prematurely unless there is a concrete formatting or content difference that requires them.

---

## 5. Language selection and preference rules

## 5.1 User-selectable language

The visible interface language must be user-selectable.

There must be a settings/options path in the bot that allows language switching without requiring support/admin intervention.

Typical entry points may include:

- settings;
- profile/options;
- first-run language selection when appropriate;
- explicit “Change language” action.

## 5.2 Locale preference is a user property

Each actor must have a stored locale preference where applicable.

At minimum, locale preference must be stored for:

- patients;
- administrators;
- doctors;
- owners.

Locale preference must not depend only on Telegram client language.
Telegram language may be used as an initial hint, but DentFlow must store and honor its own preference value.

## 5.3 Default locale resolution

Recommended resolution order:

1. explicitly stored DentFlow locale preference;
2. clinic-level default locale if a stored user locale does not exist;
3. Telegram-provided language hint if useful;
4. global system default.

Global default at launch:

- `ru`

## 5.4 Clinic-level default locale

Each clinic deployment should support a clinic-level default locale.

Why this matters:

- one clinic may primarily operate in Russian;
- another may want English default for staff or international patients;
- future deployments may need Georgian or Polish as default.

Clinic default locale must influence:

- first-time patient communication when no user preference exists;
- initial admin/doctor setup;
- default content authoring assumptions.

## 5.5 Per-user override wins

If the user explicitly chooses a language, that preference overrides clinic default.

---

## 6. What must be localized

All user-visible product text must be localizable.

This includes, but is not limited to:

- menu labels;
- button labels;
- panel titles;
- prompts;
- validation errors;
- confirmations;
- notifications;
- reminder text;
- booking flow copy;
- patient instructions templates;
- owner digest headings;
- care-commerce messaging;
- empty-state messages;
- search fallback prompts;
- language selector UI;
- help and guidance text.

The following must **not** remain hardcoded in one language:

- handler-level reply text;
- callback-specific inline button captions;
- system errors shown to the user;
- status labels visible in UI;
- free-standing onboarding text;
- fallback texts like “not found”, “back”, “cancel”, “done”, “confirm”.

---

## 7. What does not belong in the translation layer

Not everything should be solved by plain translation files.

The following concepts must remain domain data or content records, not just translation keys embedded blindly in code:

- clinic names;
- doctor names;
- service names if clinics are allowed to customize them;
- care product names;
- custom clinic notices;
- clinic-authored aftercare texts if these become editable content;
- campaign-specific promotional copy;
- policy text configured per clinic.

These items may still require localization support, but they should be treated as **content entities** with language variants, not just static product strings.

---

## 8. Translation resource architecture

## 8.1 Core rule

All product/system strings must be referenced by stable translation keys.

Example shape:

- `common.back`
- `common.cancel`
- `booking.select_date.title`
- `booking.confirmation.sent`
- `patient.search.no_results`
- `owner.digest.today.header`
- `care.recommendation.post_hygiene.title`

The exact key taxonomy may evolve, but stable namespacing is required.

## 8.2 Resource structure

Recommended translation resource organization:

- namespace by product area / bounded context;
- separate locale files per language;
- no giant unstructured dump file if it becomes large.

Recommended namespace areas:

- `common`
- `navigation`
- `search`
- `booking`
- `patient`
- `admin`
- `doctor`
- `owner`
- `care`
- `commerce`
- `notifications`
- `errors`
- `settings`
- `language`

## 8.3 No raw text in handlers

Handler code, orchestration services, and panel builders must not contain raw user-facing strings except for very narrow and temporary debugging cases that never reach production.

Production behavior must always render via the i18n layer.

## 8.4 Template support

The i18n system must support interpolation placeholders.

Examples:

- patient name;
- doctor name;
- date/time;
- branch name;
- product name;
- count values;
- currency and amount values;
- reminder windows.

Interpolation rules must remain explicit and safe.

---

## 9. Fallback rules

## 9.1 Locale fallback

If a key is missing in the requested locale:

1. use clinic or system fallback locale;
2. log the missing translation event;
3. avoid user-facing placeholder garbage if a fallback exists.

Default product fallback chain at launch:

- requested locale -> `en` or `ru` depending on deployment strategy;
- final hard fallback -> `ru`

Recommended practical stance for v1:

- if `en` is missing, fall back to `ru`;
- if future locale like `ka` or `pl` is incomplete, fall back to `en` or `ru` based on translation policy.

This must be consistent and documented in code.

## 9.2 Missing-key handling

A missing key must never crash the user flow.

It may:

- render fallback text;
- emit structured logs/metrics;
- appear in a developer diagnostics report;
- fail CI checks if translation completeness thresholds are enforced.

## 9.3 No silent translation debt

Missing keys must be observable.

Recommended mechanisms:

- startup validation for required namespaces;
- test coverage for key surfaces;
- optional lint/check script for translation completeness;
- runtime structured logging for missing keys.

---

## 10. Locale-sensitive formatting

Localization is not only text translation.
The following must be locale-aware where relevant:

- dates;
- time;
- day and month labels;
- ordinal wording where used;
- decimal separators;
- amount formatting;
- list joining where natural-language output is generated;
- grammatical plural forms.

## 10.1 Dates and time

All rendering of dates and time in user-facing messages must pass through formatting helpers that are locale-aware.

This is especially important for:

- booking slots;
- reminders;
- owner digests;
- follow-up schedules;
- care-product pickup timing;
- waitlist notifications.

## 10.2 Currency and amount formatting

If prices or deposits are displayed, they must be formatted using locale-aware helpers and clinic/business configuration.

The language layer must not assume one hardcoded number format.

## 10.3 Pluralization

Pluralization must be handled by the i18n layer or helper system.

Do not manually concatenate counts with nouns in handlers.

Examples that require proper plural handling:

- appointments;
- reminders;
- unread items;
- available slots;
- reserved products.

---

## 11. Runtime language switching

## 11.1 User-triggered switching must be immediate

When the user changes language in bot settings, the system must switch subsequent UI rendering immediately.

Recommended behavior:

- confirm the selected language in the newly selected language;
- re-render the current or next relevant panel in that language;
- persist the preference before rendering follow-up content.

## 11.2 Old messages are not retroactively rewritten

DentFlow does not need to retroactively rewrite all prior messages in chat after a language switch.

Language switching affects:

- future messages;
- newly rendered panels;
- edited active panel when appropriate.

## 11.3 Active flow consistency

If language changes in the middle of a flow:

- current flow state must remain valid;
- future prompts in that flow should render in the selected language;
- callback/state semantics must not depend on visible string values.

This means business logic must rely on stable internal enums/keys, not visible language text.

---

## 12. Search and localization

Localization intersects with search in important ways.

## 12.1 Search must be language-tolerant where practical

Patient search and internal retrieval must tolerate:

- Cyrillic vs Latin entry variations;
- transliteration variants;
- mixed-script input;
- STT output imperfections;
- locale-driven text normalization differences.

## 12.2 Search index is not a translation resource

Search projections may contain normalized/searchable text variants, but they are not the same as UI translations.

Keep separate concerns:

- UI language rendering via i18n resources;
- search retrieval via normalization and search indexing.

## 12.3 Voice-assisted retrieval must remain locale-aware

Where voice search is used, STT configuration and normalization should consider the likely language of the user/clinic context.

Examples:

- Russian-speaking admin in a Georgian clinic;
- English-speaking owner;
- mixed-name patient database.

Do not assume one-language STT forever.

---

## 13. Notifications and reminders

Notifications, reminders, and aftercare messaging must be localized according to the recipient's locale preference.

This applies to:

- booking confirmation;
- reminder chains;
- reschedule prompts;
- waitlist alerts;
- aftercare instructions;
- care recommendations;
- owner digests;
- admin operational alerts where localized UI is desired.

If a message template contains structured content and dynamic values, the full rendered result must be locale-aware.

---

## 14. Content ownership model

DentFlow has two categories of localized text.

## 14.1 Product strings

Maintained by the product/codebase.
Examples:

- navigation;
- common actions;
- system prompts;
- validation;
- standard status labels;
- default notifications.

## 14.2 Business/clinic content

Maintained by configuration or clinic-managed content systems later.
Examples:

- custom aftercare text;
- custom campaign wording;
- clinic-specific instructions;
- localized service descriptions if editable;
- localized care-product explanation text.

The architecture must not confuse these two categories.

A static translation file is correct for product strings.
A content record with language variants is correct for clinic-authored content.

---

## 15. Domain model expectations

The domain model must support localization without leaking text into domain logic.

At minimum, the model should be able to represent:

- actor locale preference;
- clinic default locale;
- optional content variant language;
- stable internal status values independent of rendered labels.

The domain model must **not** use visible translated text as identifiers.

Examples of what must remain stable internally:

- booking statuses;
- appointment statuses;
- notification channel types;
- care recommendation types;
- product categories;
- role names;
- language codes.

---

## 16. UI/UX constraints related to language

The rules in `docs/15_ui_ux_and_product_rules.md` still apply in every locale.

Therefore localization must preserve:

- short actionable button labels;
- compact panel titles;
- clean chat discipline;
- shallow navigation;
- one active panel principle.

This means translation cannot be treated as raw literal replacement.

Translators and implementers must consider:

- button width constraints;
- readability on phone screens;
- concise microcopy;
- ambiguity caused by direct literal translation.

Short operational labels matter more than textbook linguistic purity.

---

## 17. Russian-first authoring workflow

Since the project is conceived and described primarily in Russian, DentFlow may use a **RU-first authoring workflow** for initial product copy.

That means:

- initial product text is often authored in Russian;
- English translation is produced and maintained in parallel;
- future locales are added from stable source keys and reviewed copy.

However, RU-first authoring must not become RU-only implementation.

The engineering rule remains:

- no feature is complete if user-visible text exists only as hardcoded Russian literals.

---

## 18. English from day one

English support is not optional future work.
It is part of the launch architecture.

Why:

- it proves that the i18n layer is real;
- it prevents Russian assumptions from infecting handlers and templates;
- it makes future Georgian/Polish rollout easier;
- it supports mixed-language staff and international patients when relevant.

If a flow exists only in Russian, that flow is incomplete.

---

## 19. Adding a new language

Adding a new locale should be operationally simple.

The intended process should look roughly like this:

1. add locale metadata/config;
2. add translation resource files;
3. provide translations for required namespaces;
4. review UI fit for key operational flows;
5. verify date/time/number formatting;
6. verify settings-based language switching;
7. verify reminder and template rendering;
8. verify search/voice behavior if locale affects it materially.

Adding a language must not require:

- changing domain enums;
- rewriting handlers;
- forking panel logic;
- duplicating state machines.

If it does, architecture has been violated.

---

## 20. Testing expectations

Localization must be covered by both automated and manual checks.

## 20.1 Automated expectations

Recommended checks:

- required-key presence by locale;
- missing-key detection;
- interpolation placeholder consistency across locales;
- locale switching persistence tests;
- formatting helper tests;
- panel rendering smoke tests for `ru` and `en`.

## 20.2 Manual expectations

Manual review is still required for:

- awkward or too-long labels;
- broken button layouts;
- truncated operational text;
- poor microcopy in booking and care flows;
- tone inconsistency across languages.

Localization bugs are not only “wrong text” bugs.
They are also UX bugs.

---

## 21. Implementation guardrails

The following rules are mandatory during development:

### 21.1 No hardcoded production strings in handlers

### 21.2 No business logic branching based on visible translated text

### 21.3 No direct use of localized labels as callback payload semantics

### 21.4 No locale-specific hacks hidden in random modules

### 21.5 No merging of translation resources and domain data into one unstructured mess

### 21.6 No feature marked complete if its user-facing strings are only implemented in Russian

### 21.7 No translation key churn without reason

Key stability matters for maintainability.

---

## 22. Acceptance checklist for any new user-facing feature

A feature is not complete unless all of the following are true:

- all user-visible strings are behind translation keys;
- Russian and English variants exist;
- locale preference is respected;
- date/time/number formatting is locale-safe;
- buttons and labels fit mobile Telegram UX;
- language switching does not break the flow state;
- callbacks use stable internal values, not visible labels;
- reminders/notifications use the recipient locale;
- missing translations fail safely.

---

## 23. Final stance

Localization in DentFlow is not a finishing layer.
It is part of the product architecture.

DentFlow must behave like a multilingual system from the beginning, even though Russian is the primary design and authoring language.

The correct implementation strategy is:

- Russian-first authoring;
- Russian and English support from day one;
- easy future addition of Georgian, Polish, and other locales;
- strict separation between product strings, clinic content, and domain logic;
- locale-aware rendering without bloating feature code.

If this discipline is followed, future language expansion is a content operation.
If it is ignored, future language expansion becomes a rewrite.
And humanity has already done enough rewrites to prove that this is a stupid hobby.
