# DentFlow Seed Data and Demo Fixtures

> Seed, fixture, and demo-data specification for DentFlow.

## 1. Purpose

This document defines the minimum seed and fixture strategy for DentFlow.

It exists because complex clinic systems cannot be validated on:
- an empty database;
- three fake rows;
- one doctor named “Test Testovich.”

That is not testing.
That is performance art.

---

## 2. Goals

Seed and fixture data must allow the team and CODEX to validate:

- patient search;
- repeated surnames;
- multilingual names;
- booking history;
- reminder flows;
- owner metrics;
- care-commerce flows;
- chart/export logic;
- access/role surfaces;
- document generation;
- realistic UI density.

---

## 3. Seed families

Recommended seed families:

1. clinic and branch reference
2. doctors
3. services
4. schedules and slots
5. staff and role bindings
6. patients
7. bookings
8. reminders
9. chart/clinical samples
10. recommendations
11. care catalog and orders
12. media and CT-link stubs
13. owner metrics seed/derived validation

---

## 4. Minimum fixture requirements

## 4.1 Clinic reference fixtures
- one clinic minimum
- optional second branch set
- realistic timezone and locale defaults

## 4.2 Doctor fixtures
At least:
- 4–6 doctors
- mixed specialties
- one premium/protected doctor
- one doctor with public booking disabled
- one doctor with urgent-capable routing
- one doctor with code-only behavior if used

## 4.3 Service fixtures
At least:
- hygiene
- consultation
- urgent pain visit
- pediatric visit
- orthodontic/implant-related visit if product scope includes it

## 4.4 Patient fixtures
Need:
- mixed-language names
- repeated surnames
- patients with only phone
- patients with Telegram binding
- patients with photo
- patients with flags
- patients with reminder preference differences
- patients with previous doctor continuity

## 4.5 Booking fixtures
Need:
- upcoming pending_confirmation bookings
- confirmed bookings
- reschedule_requested bookings
- checked_in bookings
- in_service bookings
- completed bookings
- no_show bookings
- canceled bookings
- waitlist entries
- slot holds close to expiry

## 4.6 Reminder fixtures
Need:
- scheduled reminders
- sent reminders
- acknowledged reminders
- failed reminders
- action-required reminders
- “already_on_my_way” acknowledgements
- non-response cases

## 4.7 Clinical fixtures
Need:
- chart anchor
- encounter summaries
- diagnosis examples
- treatment plan examples
- odontogram snapshot payloads
- imaging references
- CT external-link stubs

## 4.8 Recommendation fixtures
Need:
- issued recommendations
- viewed vs unviewed
- accepted vs declined
- post-hygiene recommendation
- braces/aftercare recommendation

## 4.9 Care fixtures
Need:
- care catalog
- reserve-for-pickup order
- ready-for-pickup order
- fulfilled order
- expired reservation

## 4.10 Staff/access fixtures
Need:
- admin actor
- doctor actors
- owner actor
- role bindings
- branch-scoped role examples if branches enabled

---

## 5. Seed formats

Preferred early formats:
- CSV
- XLSX
- JSON fixture packs
- Python-based seed builders

Use reproducible seed pipelines.
Do not rely on “someone manually inserted a few rows in staging.”

---

## 6. Demo realism rules

Fixtures should contain:
- plausible names
- plausible booking density
- overlapping time windows
- repeated patients
- branch/service variety
- care recommendations tied to actual visits
- reminder chains tied to actual bookings

Do not generate sterile perfection.
The point is to test DentFlow against the messiness clinics actually produce.

---

## 7. Seed profiles

Recommended seed profiles:

### `minimal_dev`
Just enough to boot and smoke-test.

### `workflow_demo`
Enough data to demo booking, search, reminders and owner dashboards.

### `pilot_like`
A denser, more realistic profile for staging and pre-pilot validation.

---

## 8. Privacy rule

Use synthetic or deliberately fabricated data.

Do not use uncontrolled production dumps as default dev/demo fixtures.

---

## 9. Relationship to testing

This document supports:
- `docs/40_search_model.md`
- `docs/50_analytics_and_owner_metrics.md`
- `docs/95_testing_and_launch.md`

Without realistic fixtures:
- search looks better than it is;
- analytics looks cleaner than reality;
- role surfaces look less noisy than they will be;
- exports are under-tested.

---

## 10. Summary

DentFlow seed data must be:
- realistic enough to expose real problems;
- structured enough to be reproducible;
- broad enough to cover booking, search, reminders, clinical data, care flows and owner analytics;
- synthetic enough to avoid privacy stupidity.

That is how the team tests a real system instead of a cardboard prop.

---

## 11. Stack3 booking seed date mode

- `scripts/seed_stack3_booking.py` keeps static/default behavior by default.
- Optional relative mode is available for stale-fixture resilience:
  - `python scripts/seed_stack3_booking.py --relative-dates`
  - `python scripts/seed_stack3_booking.py --relative-dates --start-offset-days 2`
  - `python scripts/seed_stack3_booking.py --relative-dates --source-anchor-date 2026-04-20`
- Relative mode shifts booking/session/slot/waitlist date fields while preserving time-of-day, durations, and IDs.
