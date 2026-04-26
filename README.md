# DentFlow

> Telegram-first, phone-first operating system for private dental clinics.

## Operational security note

- Do not commit `.env`.
- Do not include `.env` in archives/reports shared with external tools.
- If `.env` was shared, rotate Telegram bot tokens immediately.

## 1. Purpose of this document

This README is the **main index and authority map** for the DentFlow wiki.

It exists to make one thing completely unambiguous for the team and for CODEX:

- what is being built;
- which documents are authoritative for which concerns;
- which architectural decisions are already frozen;
- which words mean the same thing everywhere;
- where implementation must **not** improvise.

DentFlow is a complex system.
So the wiki must behave like a navigation system, not like a box of interesting essays.

---

## 2. Product thesis

DentFlow is **not** just a booking bot.

DentFlow is a **Telegram-first, phone-first operational layer for a private dental clinic**.

It is built for the real environment of small and mid-sized clinics where:

- doctors often work from phones;
- owners often combine medical work with management;
- admins work in interruptions and chat-driven routines;
- booking, reminders, patient lookup, follow-up, care recommendations and analytics are fragmented;
- the clinic may have weak desktop infrastructure but strong day-to-day Telegram usage.

DentFlow must unify:

- patient entry and communication;
- booking and rescheduling;
- reminders and confirmation discipline;
- patient search and quick recognition;
- doctor/admin operational work;
- owner visibility and analytics;
- aftercare and care-commerce;
- document/export readiness;
- future integrations without architectural collapse.

---

## 3. Working name

**Project name: `DentFlow`.**

This is the product and wiki name.

---

## 4. Frozen decisions

These decisions are already fixed and must not be casually reinvented in code.

## 4.1 Deployment stance

DentFlow is **single-clinic per deployment by default**.

That means:

- one live runtime is designed around one clinic instance;
- `clinic_id` still exists in canonical models for clean ownership, exports, analytics and adapter work;
- `branch_id` is supported as an **optional internal branch dimension** inside one clinic deployment;
- cross-clinic owner aggregation is a **future federation/integration layer**, not a reason to turn the booking core into a shared multi-tenant swamp in v1.

## 4.2 Canonical patient ownership

Canonical patient truth lives in **Patient Registry**.

Booking does **not** own a second patient registry.

Booking may use:
- `patient_id` references;
- patient context projections;
- session snapshots.

It must not introduce competing patient truth.

## 4.3 Canonical reminder ownership

Canonical reminders live in **Communication / Reminders**.

Booking produces events and scheduling intent.
Booking does **not** own a second reminder truth.

Booking-specific reminder behavior must map onto:
- `communication.reminder_job`
- `communication.message_delivery`

and related reminder services/read models.

## 4.4 Canonical booking entity

The canonical final appointment entity is **`Booking`**.

Use:
- bounded context = `Booking / Scheduling`
- aggregate/entity = `Booking`
- storage namespace = `booking`
- primary final table = `booking.bookings`

Do not split truth between “bookings” and “appointments” as separate business objects.

`Appointment` may appear in explanatory prose for humans.
`Booking` is the canonical modeled entity.

## 4.5 Canonical booking status set

For the final booking aggregate, the canonical persisted status set is:

- `pending_confirmation`
- `confirmed`
- `reschedule_requested`
- `canceled`
- `checked_in`
- `in_service`
- `completed`
- `no_show`

Additional facts like “created”, “rescheduled” and “archived” belong in:
- history,
- events,
- projections,

not as competing alternative truths in random tables.

## 4.6 043 / export stance

DentFlow does **not** model the runtime UI as a paper form.

The system stores structured facts in:
- operational profile,
- chart/encounter structures,
- document/export projections.

Form-043-style output is generated as:
- PDF/export,
- editable export source when required,
- adapter payload when needed.

The runtime system is not allowed to become an xls-shaped torture device.

## 4.7 Bot topology stance

DentFlow is modeled as role-specific Telegram surfaces:

- PatientBot
- ClinicAdminBot
- Doctor-side operational surface
- OwnerBot

Implementation may technically share runtimes where practical, but **role logic must remain separated**.

## 4.8 UI discipline

UI is governed by:

- one active panel;
- no duplicated active surfaces for the same job;
- Telegram-first interaction;
- phone-first interaction;
- search-first operational entry for admin/doctor;
- no mandatory WebApp for MVP.

## 4.9 CODEX stance

If documentation and implementation diverge, implementation is wrong until docs are deliberately updated.

CODEX must not invent:
- second registries,
- hidden reminder systems,
- parallel state enums,
- silent config stores,
- ad hoc access models.

---

## 5. Authority and precedence map

When two documents overlap, use this order of precedence.

## 5.1 Project-wide authority

1. `README.md`
2. `docs/10_architecture.md`
3. `docs/18_development_rules_and_baseline.md`

These define the project-wide strategic and engineering frame.

## 5.2 Identity, access, and policy authority

- `docs/22_access_and_identity_model.md`
- `docs/23_policy_and_configuration_model.md`
- `docs/85_security_and_privacy.md`

These define who is allowed to do what, and where settings live.

## 5.3 Runtime domain authority

- `docs/20_domain_model.md`
- `docs/25_state_machines.md`
- `docs/30_data_model.md`
- `docs/35_event_catalog.md`

These define canonical entities, lifecycles, storage strategy and events.

## 5.4 Functional subsystem authority

- `docs/40_search_model.md`
- `docs/50_analytics_and_owner_metrics.md`
- `docs/60_care_commerce.md`
- `docs/shop/00_shop_readme.md`
- `docs/shop/61_care_catalog_model.md`
- `docs/shop/62_care_catalog_workbook_spec.md`
- `docs/shop/63_recommendation_to_product_engine.md`
- `docs/shop/64_care_patient_catalog_and_flow.md`
- `docs/shop/66_care_stock_and_pickup_semantics.md`
- `docs/shop/67_care_media_and_content_rules.md`
- `docs/65_document_templates_and_043_mapping.md`
- `docs/68_admin_reception_workdesk.md`
- `docs/69_google_calendar_schedule_projection.md`
- `docs/70_bot_flows.md`
- `docs/72_admin_doctor_owner_ui_contracts.md`

These define how major subsystems behave.

General rule:
- `60_care_commerce.md` = high-level commerce overview
- `docs/shop/*` = detailed care-commerce package
- `68_admin_reception_workdesk.md` = admin operational workdesk truth
- `69_google_calendar_schedule_projection.md` = calendar mirror truth

## 5.5 Infrastructure and delivery authority

- `docs/80_integrations_and_infra.md`
- `docs/90_pr_plan.md`
- `docs/92_seed_data_and_demo_fixtures.md`
- `docs/95_testing_and_launch.md`

These define how the system is built, seeded, integrated and launched.

## 5.6 Booking-specific authority

`booking_docs/*` is authoritative for **booking subsystem specifics**.

However it must remain aligned with project-wide canonical decisions from:
- `docs/20_domain_model.md`
- `docs/25_state_machines.md`
- `docs/30_data_model.md`
- `docs/35_event_catalog.md`

General rule:

- project-wide docs define global truth,
- booking docs define subsystem detail,
- they are not allowed to diverge.

---

## 6. Reading order for CODEX

Recommended reading order before implementation:

1. `README.md`
2. `docs/10_architecture.md`
3. `docs/12_repo_structure_and_code_map.md`
4. `docs/15_ui_ux_and_product_rules.md`
5. `docs/17_localization_and_i18n.md`
6. `docs/18_development_rules_and_baseline.md`
7. `docs/20_domain_model.md`
8. `docs/22_access_and_identity_model.md`
9. `docs/23_policy_and_configuration_model.md`
10. `docs/25_state_machines.md`
11. `docs/30_data_model.md`
12. `docs/35_event_catalog.md`
13. `docs/40_search_model.md`
14. `docs/50_analytics_and_owner_metrics.md`
15. `docs/60_care_commerce.md`
16. `docs/shop/00_shop_readme.md`
17. `docs/shop/61_care_catalog_model.md`
18. `docs/shop/62_care_catalog_workbook_spec.md`
19. `docs/shop/63_recommendation_to_product_engine.md`
20. `docs/shop/64_care_patient_catalog_and_flow.md`
21. `docs/shop/66_care_stock_and_pickup_semantics.md`
22. `docs/shop/67_care_media_and_content_rules.md`
23. `docs/65_document_templates_and_043_mapping.md`
24. `docs/68_admin_reception_workdesk.md`
25. `docs/69_google_calendar_schedule_projection.md`
26. `docs/70_bot_flows.md`
27. `docs/72_admin_doctor_owner_ui_contracts.md`
28. `docs/80_integrations_and_infra.md`
29. `docs/85_security_and_privacy.md`
30. `docs/90_pr_plan.md`
31. `docs/92_seed_data_and_demo_fixtures.md`
32. `docs/95_testing_and_launch.md`
33. `booking_docs/00_booking_readme.md`
34. the rest of `booking_docs/*`

### Pilot launch quick pointer
- Runbook: `docs/PILOT_LAUNCH_RUNBOOK.md`
- Safe preflight smoke checks: `make smoke-import`, `make smoke-settings`, `make smoke-worker-modes`, `make smoke-dispatcher`, or full `make smoke-launch`

---

## 7. Project document structure

```text
README.md
SYNC_NOTES.md
AUDIT_READINESS.md

docs/
  10_architecture.md
  12_repo_structure_and_code_map.md
  15_ui_ux_and_product_rules.md
  17_localization_and_i18n.md
  18_development_rules_and_baseline.md
  20_domain_model.md
  22_access_and_identity_model.md
  23_policy_and_configuration_model.md
  25_state_machines.md
  30_data_model.md
  35_event_catalog.md
  40_search_model.md
  50_analytics_and_owner_metrics.md
  60_care_commerce.md
  65_document_templates_and_043_mapping.md
  68_admin_reception_workdesk.md
  69_google_calendar_schedule_projection.md
  70_bot_flows.md
  72_admin_doctor_owner_ui_contracts.md
  80_integrations_and_infra.md
  85_security_and_privacy.md
  90_pr_plan.md
  92_seed_data_and_demo_fixtures.md
  95_testing_and_launch.md
  shop/
    00_shop_readme.md
    61_care_catalog_model.md
    62_care_catalog_workbook_spec.md
    63_recommendation_to_product_engine.md
    64_care_patient_catalog_and_flow.md
    66_care_stock_and_pickup_semantics.md
    67_care_media_and_content_rules.md

booking_docs/
  00_booking_readme.md
  10_booking_flow_dental.md
  20_booking_domain_model.md
  30_booking_routing_and_slot_ranking.md
  40_booking_state_machine.md
  50_booking_telegram_ui_contract.md
  60_booking_integrations_and_ops.md
  90_booking_mvp_plan.md
  booking_db_schema.md
  booking_api_contracts.md
  booking_test_scenarios.md
```

There is intentionally **no duplicate alias** for the booking flow file.
One canonical file is enough.
Humanity does not need two truths where one is perfectly sufficient.

---

## 8. What DentFlow is not trying to be in v1

DentFlow v1 is **not**:

- a clone of 1C:Medicine;
- a full hospital information system;
- a giant desktop-first EMR;
- a PACS replacement;
- a universal multi-tenant healthcare platform;
- an AI doctor.

DentFlow v1 is:

- a strong clinic operating core;
- booking-first but not booking-only;
- structured enough to support charting and document export;
- simple enough to survive real Telegram usage;
- modular enough to grow.

---

## 9. Final strategic statement

DentFlow is a **Telegram-first dental clinic operating system**.

It must be built from already-proven patterns:

- structured bot flows;
- transactional operational core;
- search as a first-class operational capability;
- reminders as a first-class care and discipline mechanism;
- owner-facing projections separated from core truth;
- strong identity/access boundaries;
- policy/configuration modeled explicitly;
- exports generated from structured facts;
- modular architecture that can absorb future growth without tearing itself apart.
