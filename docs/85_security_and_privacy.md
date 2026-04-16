# DentFlow Security and Privacy

> Security, privacy, access-control, audit and data-handling principles for DentFlow.

## 1. Purpose

This document defines DentFlow’s baseline security and privacy stance.

It exists to protect:
- patient identity and health-related data;
- clinic operational data;
- owner analytics;
- media and generated documents;
- integration credentials and service secrets.

Read this together with:
- `docs/22_access_and_identity_model.md`
- `docs/23_policy_and_configuration_model.md`
- `docs/30_data_model.md`
- `docs/80_integrations_and_infra.md`

---

## 2. Core principles

- least privilege
- clinic-scoped access
- role-based visibility
- minimized projections
- controlled exports
- controlled media access
- synthetic-first dev/test data
- auditable privileged actions

---

## 3. Data categories

## 3.1 Public/low sensitivity
Generic clinic info and non-sensitive catalog content.

## 3.2 Personal data
Names, contacts, birth date, patient photo, language preferences.

## 3.3 Sensitive clinical data
Medical summaries, diagnoses, treatment plans, notes, imaging references, encounter detail.

## 3.4 Business-sensitive data
Owner metrics, revenue trends, doctor/service performance, anomaly views.

## 3.5 Secrets
Bot tokens, DB credentials, integration credentials, AI keys, signed URL material.

---

## 4. Access model stance

DentFlow access is built on:
- explicit actor identity;
- explicit staff membership;
- explicit role assignment;
- clinic/branch scope;
- privileged action checks.

Telegram presence alone is not authorization.

---

## 5. Role visibility guidance

### Patient
Own data only.

### Admin
Operational patient and booking visibility, not unrestricted raw clinical access.

### Doctor
Clinical and current patient visibility relevant to care, not broad owner analytics by default.

### Owner
Clinic/business insight visibility, selected drill-down only where policy allows.

### Service roles
Only the minimum scope required for their job.

---

## 6. Clinic isolation

A deployment is clinic-scoped.
Users and projections must not leak data across clinics.

If future owner federation exists, it must happen through explicit aggregated/federated channels, not accidental cross-clinic database visibility.

---

## 7. Search, events and AI privacy

## Search
Use minimized search projections only.

## Events
Emit IDs and typed summaries, not giant clinical payloads.

## AI
Use scoped projections and summaries.
Do not feed raw unrestricted clinic history by default.

---

## 8. Media and document privacy

Patient photos, problem photos, x-rays and CT links are sensitive.

Requirements:
- controlled access
- non-guessable storage references
- role-aware viewing
- safe handling of external links
- auditable document generation/export where practical

---

## 9. Sheets and external integrations

Google Sheets and external adapters are not privacy exemptions.

Rules:
- explicit scope
- explicit direction
- minimized field export
- controlled credentials
- visible sync failures

---

## 10. Dev/test privacy

Prefer:
- synthetic data
- masked fixtures
- controlled seed packs

Avoid:
- uncontrolled production dumps
- casual screenshot leakage
- raw patient dumps in tickets/chats

---

## 11. Audit expectations

Audit-worthy actions include:
- role changes
- patient updates
- booking changes
- exports
- sync actions
- privileged settings changes
- AI-assisted owner actions if stored as actionable artifacts

---

## 12. Summary

DentFlow security is based on:
- explicit identity and role modeling;
- clinic isolation;
- minimized projections;
- controlled media and export handling;
- scoped AI and integrations;
- synthetic-first development;
- auditable privileged actions.

The system is allowed to be convenient.
It is not allowed to be careless.
