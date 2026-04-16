# DentFlow Bot Flows

> Role-oriented Telegram flow map for DentFlow.

## 1. Purpose

This document defines the major bot-facing flows of DentFlow at a role and product level.

It answers:
- which role surfaces exist;
- what each role is trying to accomplish;
- where role flows begin and end;
- which shared lifecycle they rely on.

It does **not** define every panel contract.
Detailed admin/doctor/owner contract rules live in:
- `docs/72_admin_doctor_owner_ui_contracts.md`

Detailed booking subsystem contract lives in:
- `booking_docs/*`

---

## 2. Role surfaces

DentFlow should be experienced as four role-specific surfaces:

1. PatientBot
2. ClinicAdminBot
3. Doctor-side operational surface
4. OwnerBot

Implementation may share code or even runtime processes where appropriate, but role logic must remain separated.

---

## 3. Shared flow rules

All role surfaces must respect:
- Telegram-first interaction
- phone-first interaction
- one active panel
- no duplicate stale panels
- search-first operational entry for admin/doctor
- localization
- canonical state machines
- thin interface / real service-layer orchestration

---

## 4. PatientBot flow map

PatientBot is responsible for:
- starting or resuming booking;
- confirming, rescheduling, or canceling;
- sending photos/files/links;
- receiving reminders and aftercare;
- receiving recommendations;
- reserve/pickup care flow where enabled;
- switching language.

### Canonical patient flows
- new booking
- returning-patient quick booking
- urgent issue intake
- booking confirmation
- reschedule
- cancel
- media submission
- post-visit guidance
- recommendation response
- care reserve/pickup
- waitlist join and waitlist offer response

Detailed booking specifics remain in `booking_docs/*`.

---

## 5. ClinicAdminBot flow map

ClinicAdminBot is responsible for:
- today operations panel;
- patient search;
- booking queue and confirmations;
- check-in and reschedule handling;
- waitlist processing;
- communication exceptions;
- care pickup queue;
- limited patient operational detail.

### Canonical admin flows
- open today dashboard
- search patient
- open patient quick card
- open booking quick card
- confirm booking
- mark check-in
- process reschedule request
- handle reminder failure
- process care pickup
- escalate to doctor/owner where needed

---

## 6. Doctor flow map

Doctor surface is responsible for:
- seeing who is next;
- identifying the patient fast;
- seeing what matters before or during the visit;
- opening media/imaging references;
- marking encounter progression;
- adding meaningful quick notes;
- issuing recommendations.

### Canonical doctor flows
- open upcoming queue
- search patient
- open current booking
- mark in service
- add quick encounter note
- open media/imaging reference
- issue recommendation
- complete encounter/visit

Doctor surface must stay narrow and operational.
It must not become a pocket-sized bureaucratic nightmare.

---

## 7. OwnerBot flow map

OwnerBot is responsible for:
- daily digest;
- live clinic snapshot;
- doctor/service/branch analytics;
- anomaly and exception view;
- care layer visibility;
- grounded AI-assisted questions over projections.

### Canonical owner flows
- open daily digest
- open live snapshot
- open doctor performance
- open service performance
- open branch split
- open reminder/no-show exceptions
- open care-performance view
- ask grounded AI question

OwnerBot must consume projections and explain them.
It must not become a direct query tunnel into raw transactional chaos.

---

## 8. Cross-role lifecycle views

One lifecycle, multiple surfaces:

### Booking lifecycle
- patient books / confirms / changes
- admin manages / rescues / marks arrival
- doctor starts and completes
- owner sees patterns and anomalies

### Reminder lifecycle
- communication sends and tracks
- patient acknowledges
- admin handles failure
- owner sees aggregate effect

### Recommendation lifecycle
- doctor/admin issues
- patient responds
- owner sees uptake

### Care lifecycle
- doctor/admin recommends
- patient reserves/buys/picks up
- admin fulfills
- owner sees attach rate and missed opportunities

---

## 9. Relationship to UI contracts

This document defines what each role surface must do.

The following define how specific panels, actions and callbacks should look:
- `booking_docs/50_booking_telegram_ui_contract.md`
- `docs/72_admin_doctor_owner_ui_contracts.md`

General rule:
- `70_bot_flows` = role map
- contract docs = concrete UI behavior

---

## 10. Summary

DentFlow role flows are built around:
- PatientBot for care entry and patient-side action;
- ClinicAdminBot for clinic operations;
- doctor surface for fast medical/operational action;
- OwnerBot for insight and control.

The roles see the same system truth through different, disciplined Telegram surfaces.
