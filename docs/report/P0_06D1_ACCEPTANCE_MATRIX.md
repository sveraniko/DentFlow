# P0-06D1 Matrix

Audit date: 2026-04-27 (UTC).

## Seed files
- stack1 parsed: yes
- stack2 parsed: yes
- stack3 parsed: yes
- reference links valid: yes

## Clinic/reference
- clinic present: yes
- branch timezone: yes
- doctors enough: no
- services enough: no
- doctor code present: yes

## Booking
- future slots enough: yes
- slot pagination coverage: yes
- date/time-window coverage: no
- active booking present: no
- booking statuses enough: no
- stale dates classified: yes

## Patients
- telegram-bound patient: no
- phone patient: yes
- active booking link: no

## Recommendations
- real seed recommendations present: no
- active/history statuses: no
- product-linked recommendation: no

## Care
- real seed care categories/products present: no
- stock/branch availability present: no
- care orders present: no

## Seed scripts
- reproducible load path documented: yes
- one-command load exists: no
- care catalog sync path documented: yes

## Readiness
- blocker gaps listed: yes
- D2 implementation target concrete: yes
- no fake live DB claims: yes

## Regression
- C4 recommendations smoke: pass
- B4 care smoke: pass
- P0-05C My Booking smoke: pass
- care or recommendation: passed count 2/2
- patient and booking: passed count 1/1

## Basis
- Structural and readiness signals are based on the D1 readiness audit report and seed-content audit test.
- Regression statuses are based on local smoke-gate test run for C4, B4, and P0-05C.
