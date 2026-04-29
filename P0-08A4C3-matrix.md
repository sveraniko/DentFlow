# P0-08A4C3 matrix

## Service
- class exists: yes
- start_questionnaire: yes
- get/list questionnaires: yes
- save answer: yes
- bulk save answers: yes
- delete answer: yes
- complete questionnaire: yes
- latest by booking/patient: yes

## Validation
- questionnaire_type: yes
- version: yes
- question_key: yes
- answer_type: yes
- visibility: yes
- JSON serializable answer_value: yes

## Behavior
- deterministic answer_id: yes
- same question updates same answer id: yes
- repository delegation: yes

## Truth boundary
- no UI: yes
- no schema changes: yes
- no Alembic/migrations: yes

## Regression
- C3 tests: pass
- C2/C1 tests: pass
- B4/B3/B2/B1 tests: pass/skipped
- A4A/A3/A2/A1 tests: pass
- care/recommendation: passed count = 230
- patient/booking: 381 passed, 6 failed, 2 skipped
