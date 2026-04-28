# P0-06D2A2 matrix

Date: 2026-04-28

## Stack1
- doctors >= 3: **yes**
- public doctors >= 2: **yes**
- services >= 4: **yes**
- doctor access codes >= 3: **yes**
- service locale keys exist RU/EN: **yes**
- access code references valid: **yes**

## Stack2
- patients >= 4: **yes**
- phone contacts >= 2: **yes**
- telegram contacts >= 2: **yes**
- telegram 3001 -> patient_sergey: **yes**
- phone-only patient exists: **yes**
- preferences for demo patients: **yes**

## Stack3
- slots >= 12: **yes**
- slots cover morning/day/evening: **yes**
- slots cover >= 2 doctors: **yes**
- slots cover >= 3 services: **yes**
- booking statuses pending/confirmed/reschedule/canceled: **yes**
- active booking for Sergey/3001: **yes**
- waitlist entry exists: **yes**
- references valid: **yes**

## Relative dates
- shifted slots future-safe: **yes**
- durations preserved: **yes**
- IDs preserved: **yes**
- date windows shifted: **yes**

## Regression
- D2A1 tests: **pass**
- D1 audit: **pass**
- C4 recommendations smoke: **pass**
- B4 care smoke: **pass**
- P0-05C smoke: **pass**
- care or recommendation: **204 passed**
- patient and booking: **105 passed**
