# DentFlow PR Plan

> Layered implementation plan for DentFlow.

## 1. Purpose

This document defines the implementation sequence for DentFlow so that CODEX always has a stable base to stand on.

It exists to prevent:
- random feature ordering;
- cross-cutting rewrites from missing foundations;
- coding ahead of model clarity;
- “we’ll fix the architecture later” mythology.

---

## 2. Planning principles

## 2.1 Build by layers
Each later layer must stand on a stable earlier one.

## 2.2 Anchor every stack in docs
Every implementation phase must name its authoritative docs.

## 2.3 Booking first, but not alone
Booking is the first pillar.
It must not be implemented in ways that sabotage patient registry, reminders, search, charting or owner analytics later.

## 2.4 CODEX needs explicit non-goals
Every stack should say what is **not** being built yet.

---

## 3. Logical implementation layers

### Layer 0. Repo and platform foundation
- repo/code map
- config grouping
- runtime skeleton
- baseline DB discipline
- localization bootstrap

### Layer 1. Identity, policy and reference foundation
- clinic/branch/doctor/service
- access and identity
- policy and configuration

### Layer 2. Operational patient and booking core
- patient registry
- booking sessions / slots / holds / bookings
- reminder baseline

### Layer 3. Search and clinic operation speed
- patient/doctor/service search
- voice-assisted retrieval
- admin and doctor quick cards

### Layer 4. Clinical progression
- chart anchor
- encounter core
- note/diagnosis/treatment-plan baseline
- media/imaging references

### Layer 5. Events, projections and owner visibility
- event foundation
- analytics projections
- owner digest
- anomaly candidates

### Layer 6. Recommendations and care layer
- recommendation lifecycle
- care catalog
- reserve/pickup flow
- care metrics

### Layer 7. Export and integrations
- 043/document mapping
- generated documents
- Sheets sync
- external adapter groundwork

### Layer 8. AI-assisted layer and pilot hardening
- owner AI
- grounded Q&A
- launch smoke and rollback confidence

---

## 4. PR stack sequence

## Stack 0. Repository foundation
References:
- `README.md`
- `docs/10_architecture.md`
- `docs/12_repo_structure_and_code_map.md`
- `docs/17_localization_and_i18n.md`
- `docs/18_development_rules_and_baseline.md`

Outcome:
- clean project skeleton
- grouped config bootstrap
- worker/runtime skeleton
- localization resources skeleton

## Stack 1. Access, policy and clinic reference
References:
- `docs/20_domain_model.md`
- `docs/22_access_and_identity_model.md`
- `docs/23_policy_and_configuration_model.md`
- `docs/30_data_model.md`

Outcome:
- clinic/branch/doctor/service core
- explicit staff/role bindings
- explicit policy/config store

## Stack 2. Patient Registry core
References:
- `docs/20_domain_model.md`
- `docs/30_data_model.md`
- `docs/40_search_model.md`
- `docs/85_security_and_privacy.md`

Outcome:
- canonical patient model
- contact/preferences/flags/photo baseline

## Stack 3. Booking core
References:
- `booking_docs/*`
- `docs/25_state_machines.md`
- `docs/30_data_model.md`

Outcome:
- booking session
- slot search/hold
- final booking aggregate
- canonical status use

## Stack 4. Communication and reminder core
References:
- `docs/25_state_machines.md`
- `docs/35_event_catalog.md`
- `booking_docs/60_booking_integrations_and_ops.md`

Outcome:
- reminder jobs
- acknowledgement path
- action-required reminder baseline
- failure visibility

## Stack 5. Search and voice retrieval
References:
- `docs/40_search_model.md`
- `docs/72_admin_doctor_owner_ui_contracts.md`

Outcome:
- patient/doctor/service search
- admin/doctor search-first flows
- focused voice-assisted retrieval

## Stack 6. Doctor and admin operational surfaces
References:
- `docs/70_bot_flows.md`
- `docs/72_admin_doctor_owner_ui_contracts.md`

Outcome:
- admin quick cards
- doctor queue and quick note path
- check-in / in-service progression

## Stack 7. Clinical chart baseline
References:
- `docs/30_data_model.md`
- `docs/65_document_templates_and_043_mapping.md`

Outcome:
- chart anchor
- encounter core
- diagnosis/treatment plan baseline
- imaging/media references

## Stack 8. Event and projection foundation
References:
- `docs/35_event_catalog.md`
- `docs/80_integrations_and_infra.md`

Outcome:
- outbox/event path
- search/analytics projection baseline

## Stack 9. Owner analytics baseline
References:
- `docs/50_analytics_and_owner_metrics.md`

Outcome:
- owner digest
- today snapshot
- booking/doctor/service/branch baseline metrics

## Stack 10. Recommendations
References:
- `docs/25_state_machines.md`
- `docs/60_care_commerce.md`

Outcome:
- recommendation model and flow
- post-visit recommendation path

## Stack 11. Care-commerce baseline
References:
- `docs/60_care_commerce.md`
- `docs/50_analytics_and_owner_metrics.md`

Outcome:
- reserve/pickup
- care order lifecycle
- attach-rate baseline metrics

## Stack 12. Document generation and 043 export
References:
- `docs/65_document_templates_and_043_mapping.md`
- `docs/80_integrations_and_infra.md`

Outcome:
- generated documents
- 043-style export baseline

## Stack 13. Sheets and adapter groundwork
References:
- `docs/80_integrations_and_infra.md`
- `docs/85_security_and_privacy.md`

Outcome:
- explicit sync jobs
- controlled Sheets integration
- external adapter readiness

## Stack 14. AI-assisted owner layer
References:
- `docs/50_analytics_and_owner_metrics.md`
- `docs/85_security_and_privacy.md`

Outcome:
- grounded owner AI summaries and Q&A

## Stack 15. Pilot hardening
References:
- `docs/92_seed_data_and_demo_fixtures.md`
- `docs/95_testing_and_launch.md`

Outcome:
- realistic fixtures
- smoke confidence
- rollback confidence

---

## 5. Recommended wave grouping

### Wave 1
Stacks 0–2

### Wave 2
Stacks 3–4

### Wave 3
Stacks 5–7

### Wave 4
Stacks 8–9

### Wave 5
Stacks 10–12

### Wave 6
Stacks 13–15

---

## 6. CODEX usage rule

Every implementation prompt to CODEX should include:
- target stack
- target docs
- explicit scope
- explicit non-goals
- acceptance expectations
- whether docs must be updated in the same cycle

CODEX must not jump ahead just because a later stack looks entertaining.

---

## 7. Summary

DentFlow implementation order is:

- repo foundation
- access/policy/reference foundation
- patient + booking + reminders
- search/admin/doctor speed
- clinical progression
- events and owner visibility
- recommendations and care layer
- export/integrations
- AI and pilot hardening

This sequence is designed to keep the system layered instead of collapsing into random simultaneous invention.
