# P0-08A4C1 matrix

## Profile service
- class exists: yes
- save profile details: yes
- get completion state: yes
- completion state rules tested: yes
- email/country validation: yes

## Preference service
- class exists: yes
- update notifications: yes
- channel validation: yes
- recipient strategy validation: yes
- quiet hours validation: yes
- timezone validation: yes
- update branch preference: yes
- branch validation: yes

## Truth boundary
- no UI: yes
- no schema changes: yes
- no Alembic/migrations: yes

## Regression
- C1 tests: pass
- B4 DB smoke: pass
- B3/B2/B1 tests: pass
- A4A/A3/A2/A1 tests: pass
- care/recommendation: passed count = 230
- patient/booking: passed count = 371
