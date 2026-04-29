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

## Regression (exact command results)
- C3 tests: `9 passed`
- C2/C1 tests: `9 passed`, `8 passed`
- B4/B3/B2/B1 tests: `1 skipped`; `5 passed, 3 skipped`; `5 passed, 3 skipped`; `6 passed`
- A4A/A3/A2/A1 tests: `6 passed`; `6 passed`; `6 passed`; `6 passed`
- care/recommendation selector (`pytest -q tests -k "care or recommendation"`): `230 passed, 1 skipped, 633 deselected`
- patient and booking selector (`pytest -q tests -k "patient and booking"`): `107 passed, 757 deselected`
- classification: previously reported `381 passed, 6 failed, 2 skipped` was from broader non-acceptance selector (`patient or booking`), not this acceptance selector.
