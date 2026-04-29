# P0-08A4C2 matrix

## Family service
- class exists: yes
- list linked profiles: yes
- list relationships: yes
- add relationship: yes
- deactivate relationship: yes
- validation rules tested: yes

## Booking selector
- class exists: yes
- resolve_for_telegram: yes
- resolve_for_phone: yes
- select_patient: yes
- phone_required mode: yes
- minimal_name_required mode: yes
- single_match mode: yes
- multiple_profiles mode: yes
- no_match mode: yes

## Truth boundary
- no UI changes: yes
- no schema changes: yes
- no Alembic/migrations: yes

## Regression
- C2 tests: pass
- C1 tests: pass
- B4 DB smoke: skipped
- B3/B2/B1 tests: pass
- A4A/A3/A2/A1 tests: pass
- care/recommendation: passed count = 230
- patient/booking: passed count = 106
