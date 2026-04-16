# DentFlow Analytics and Owner Metrics

> Analytics model and owner-facing decision layer for DentFlow.

## 1. Purpose

This document defines:
- what DentFlow measures;
- how owner-facing projections should be built;
- how owner analytics differs from transactional truth;
- how AI can assist without inventing nonsense.

---

## 2. Core stance

DentFlow owner analytics exists because a clinic owner often has to be:
- clinician,
- chief doctor,
- operator,
- manager,
- business mind,

all at once.

So the owner layer must save time, not demand more archaeology.

---

## 3. Projection-first rule

Owner metrics and dashboards must consume:
- analytics projections;
- curated read models;
- trusted aggregation layers.

They must not constantly interrogate transactional tables in chaotic live form.

---

## 4. Deployment and aggregation stance

## 4.1 Default mode
Analytics is clinic-local by default:
- one deployment;
- one clinic;
- optional branch breakdown.

## 4.2 Branch-ready
Where `branch_id` exists, owner metrics should support:
- branch splits;
- branch comparison;
- branch load visibility.

## 4.3 Future federation
Cross-clinic owner rollups should be implemented through:
- federated projections;
- integration adapters;
- source-clinic-aware owner views.

This is future-friendly without infecting the core booking model.

---

## 5. KPI families

## 5.1 Booking and flow KPIs
- booking starts
- booking completions
- confirmation rate
- reschedule rate
- cancellation rate
- no-show rate
- booking lead time
- waitlist fulfillment rate

## 5.2 Patient KPIs
- new patients
- returning patients
- repeat-booking rate
- follow-up due count
- recall conversion
- lost-patient candidates

## 5.3 Doctor KPIs
- bookings per doctor
- completed visits per doctor
- no-show exposure
- service mix
- recommendation uptake
- care attach influence

## 5.4 Service KPIs
- booking demand by service
- completion by service
- reschedule/cancel rate by service
- retention impact by service
- care-commerce attach by service

## 5.5 Reminder KPIs
- reminder send rate
- acknowledgement rate
- action-required acknowledgement rate
- non-response rate
- failed reminder rate
- “already on my way” usage where enabled

## 5.6 Care-commerce KPIs
- attach rate
- recommendation-to-order conversion
- pickup completion rate
- doctor recommendation uptake
- category performance

---

## 6. Owner surfaces

## 6.1 Daily digest
Should answer:
- what is happening today;
- what failed yesterday;
- what needs attention now.

## 6.2 Today snapshot
Should show:
- expected bookings;
- pending confirmations;
- checked in;
- completed;
- no-shows;
- branch and doctor load.

## 6.3 Doctor performance
Should show:
- doctor throughput;
- no-show exposure;
- recommendation and follow-up patterns;
- branch split if relevant.

## 6.4 Service performance
Should show:
- what services bring demand;
- what services convert to completed care;
- what services support return visits.

## 6.5 Care layer
Should show:
- aftercare uptake;
- reserve/pickup performance;
- missed opportunity estimate.

## 6.6 Exceptions
Should show:
- reminder failure spikes;
- branch anomalies;
- suspicious no-show clusters;
- low confirmation pockets.

---

## 7. AI-assisted owner layer

AI is allowed here because the owner needs time-saving explanation.

But AI must operate over:
- projections;
- metrics;
- anomaly candidates;
- scoped drill-down data.

Not over raw unrestricted tables.

### Good AI jobs
- explain trend shifts
- summarize yesterday/today
- compare branches/doctors/services
- answer grounded questions
- highlight likely missed opportunities

### Forbidden AI jobs
- inventing unsupported business explanations
- mutating core truth
- acting like a medical decision engine

---

## 8. Data quality guardrails

Owner metrics are only useful if data quality is visible.

Track at least:
- projection freshness
- event lag
- reminder delivery completeness
- branch coverage completeness
- missing patient binding rates
- missing doctor/service mapping rates

Bad data should show up as bad data, not as fake confidence.

---

## 9. Summary

DentFlow owner analytics is a projection-driven management layer.

It must help a real owner understand:
- the clinic,
- branches,
- doctors,
- services,
- reminders,
- aftercare,
- failures and opportunities,

without forcing them to build a private BI career at night.
