# DentFlow Document Templates and 043 Mapping

> Runtime-to-document mapping strategy for DentFlow, including 043-style export principles.

## 1. Purpose

This document defines how DentFlow handles document generation, especially the mapping between:

- operational patient data,
- clinical chart data,
- encounter data,
- treatment plan data,
- media/imaging references,
- and a 043-style export document.

It exists to prevent a disastrous misunderstanding:

DentFlow is **not** supposed to become a paper-form simulator just because a paper form exists.

---

## 2. Core stance

Runtime truth is stored as structured facts.

Document outputs are generated from those facts.

This means:
- runtime UX stays usable;
- search and mass patient handling stay fast;
- export stays legally and operationally useful;
- missing paper-like details can be completed in controlled ways without corrupting runtime design.

---

## 3. Document families

DentFlow should eventually support at least these document families:

- 043-style patient card export
- treatment plan export
- aftercare instruction PDF
- recommendation PDF or printable summary
- consent/supporting legal docs later
- integration packet exports

Not every family must ship at once.
But the mapping strategy must already be coherent.

---

## 4. Template model

Recommended entities:
- `DocumentTemplate`
- `GeneratedDocument`

Each template should define:
- document type
- clinic scope
- locale
- template version
- rendering engine
- required source fields
- optional source fields
- fallback behavior for missing sections

---

## 5. Mapping philosophy

Map runtime structures into document sections.
Do not force document sections back into runtime as primary UI layout.

### Good model
- patient identity fields stored once
- complaint stored structurally
- diagnosis stored structurally
- treatment plan stored structurally
- encounter notes stored structurally
- imaging references stored structurally
- export renderer assembles them into a 043-style layout

### Bad model
- runtime screen tries to mirror five sheets of narrow lines because paper once looked like that

That road leads to pain and bad data entry.

---

## 6. 043-style export sections

A practical 043-style mapping should support these logical sections:

1. patient identity block
2. opening / chart metadata
3. presenting complaint and history block
4. relevant medical history block
5. objective exam block
6. dental status / odontogram block
7. diagnosis block
8. treatment plan block
9. visit/treatment record block
10. imaging / additional reference block
11. attachments block
12. signatures / manual-completion block if clinic workflow requires it

---

## 7. Suggested DentFlow -> 043 mapping

## 7.1 Identity block
Source:
- `core_patient.patients`
- `core_patient.patient_contacts`
- `core_patient.patient_preferences`

Mapped fields may include:
- chart/patient number
- full name
- birth date / age if available
- sex marker if used
- contact details
- preferred reminder channel

## 7.2 Chart metadata block
Source:
- `clinical.patient_charts`

Mapped fields may include:
- chart number
- open date
- clinic / branch identity

## 7.3 Presenting complaint / present illness
Source:
- `clinical.presenting_complaints`
- booking reason snapshot if needed for first encounter context

## 7.4 Medical history block
Source:
- `clinical.medical_history_entries`
- `core_patient.patient_medical_summaries`

## 7.5 Objective exam block
Source:
- `clinical.oral_exam_summaries`
- `clinical.encounter_notes`
- `clinical.odontogram_snapshots`

## 7.6 Diagnosis block
Source:
- `clinical.diagnoses`

## 7.7 Treatment plan block
Source:
- `clinical.treatment_plans`

## 7.8 Visit/treatment records
Source:
- `clinical.clinical_encounters`
- `clinical.encounter_notes`

## 7.9 Imaging block
Source:
- `clinical.imaging_references`
- `clinical.radiation_dose_records` where applicable

## 7.10 Attachment block
Source:
- `media_docs.media_assets`
- related linked references

---

## 8. Manual-completion strategy

Some documents may still need manual completion.

Recommended rule:
- DentFlow prefills what it knows confidently;
- missing items are shown clearly as blank/placeholder/manual sections;
- editable export source may be generated where clinic workflow requires it;
- manual completion must not force the runtime model to become worse.

---

## 9. Export modes

Recommended export modes:

## 9.1 PDF export
Read-only or near-read-only printable artifact.

## 9.2 Editable export source
Controlled editable format for clinic-side completion when required.

## 9.3 Adapter payload
Structured export for external systems.

---

## 10. Runtime constraints

The following runtime anti-patterns are forbidden:

- making patient/admin/doctor UI look like the paper form;
- requiring the patient to fill every future document field at booking time;
- storing whole generated documents as primary truth instead of structured runtime facts;
- letting document template weirdness dictate the booking or search model.

---

## 11. Relationship to legal workflow

DentFlow supports legal/operational document generation by:
- keeping structured data;
- generating controlled exports;
- tracking generated artifacts.

It does not magically solve every paper process.
But it must make export predictable and non-chaotic.

---

## 12. Summary

DentFlow treats 043-style documents as:
- important,
- exportable,
- supported,

but not as the runtime center of the product.

That is the correct balance between useful documentation and not turning the clinic system into clerical punishment.
