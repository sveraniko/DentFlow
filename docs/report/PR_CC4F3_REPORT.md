# PR_CC4F3_REPORT

## 1. Objective
Implement CC-4F3 so **reserve-again** is a true care-order object action in the patient care-order journey, with runtime revalidation and a coherent result state that keeps historical truth intact.

## 2. Production files modified
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`

## 3. Reserve-again object UX strategy
- Kept reserve-again on care-order object surfaces (list-row and expanded care-order card actions).
- Reworked repeat handling so callback-driven reserve-again now renders inside the care panel (`_send_or_edit_panel`) rather than detached ad-hoc replies.
- Added a structured reserve-again result state with explicit fields:
  - product,
  - quantity,
  - new order id,
  - branch,
  - status,
  - next step.
- Added journey-coherent action buttons after repeat:
  - **Open new order**,
  - **Back to orders**.
- Branch reselect states now stay in the same card/runtime callback journey and include a stable return action.

## 4. Revalidation strategy
Revalidation remains in the application service repeat path and is used by object callbacks:
- source order exists and belongs to current patient/clinic,
- source item exists,
- product is still active,
- branch is valid in allowed branch scope,
- branch availability row is active,
- free quantity is sufficient,
- stale/invalid branch returns safe branch reselect options.

## 5. New order/reservation result flow notes
- Successful reserve-again creates a **new order** and reservation; old order is unchanged historical truth.
- Result panel now explicitly communicates creation outcome and next step.
- Result panel provides direct navigation into the newly created order object and coherent back to order list.

## 6. Commands run
- `rg -n "reserve_again|repeat_order|care_order_repeat|CARE_ORDER|repeat" app/interfaces/bots/patient/router.py app/application/care_commerce/service.py tests/test_patient_care_ui_cc4f.py tests/test_patient_care_ui_cc4c.py tests/test_care_commerce_stack11a.py`
- `pytest -q tests/test_care_commerce_stack11a.py tests/test_patient_care_ui_cc4c.py tests/test_patient_care_ui_cc4f.py`

## 7. Test results
- `tests/test_care_commerce_stack11a.py`: pass
- `tests/test_patient_care_ui_cc4c.py`: pass
- `tests/test_patient_care_ui_cc4f.py`: pass

## 8. Remaining limitations
- `/care_order_repeat` compatibility command remains for fallback; object callback journey is the primary UX.
- Repeat still uses first order item semantics (existing baseline behavior).
