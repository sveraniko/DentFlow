# P0-01 Patient Navigation Recovery Report

## Summary
Emergency UX recovery completed for patient dead-ends and empty-state navigation in the patient Telegram router. Added stable Home/Back recovery paths, improved contact instructions, and upgraded recommendations/care/my-booking empty states with actionable markup.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `locales/ru.json`
- `locales/en.json`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `tests/test_patient_first_booking_review_pat_a1_1.py`
- `tests/test_patient_existing_booking_shortcut_pat_a3_2.py`

## Patient surfaces fixed
- Recommendations empty panel now shows readable explanation + **My Booking** and **Home** actions.
- Care catalog unavailable panel now shows readable explanation + **Home** action.
- No-active-booking (`Моя запись` no match) now shows readable state + **Book appointment** and **Home** actions.
- Contact phone prompts now explain:
  - why phone is needed;
  - contact-share or manual input options;
  - example format `+7 999 123-45-67`.
- Contact reply keyboard now includes recovery navigation:
  - `⬅️ Назад` in new-booking contact collection;
  - `🏠 Главное меню` always.
- Added text navigation handler to process contact-stage `Back/Home` reply buttons without requiring `/start`.
- Booking success keeps stable navigation to **My Booking** and **Home**.

## Callback/navigation map used
- Existing home callback reused: `phome:home`.
- Existing patient actions reused: `phome:book`, `phome:my_booking`, `phome:recommendations`, `phome:care`.
- Existing contextual back target preserved where already valid (example: recommendation detail back to `phome:recommendations`).
- No new callback namespace introduced.

## Tests run with exact commands and results
1. `python -m compileall app tests`  
   - **PASS**
2. `pytest -q`  
   - **FAIL** (repository has pre-existing unrelated failures in booking reminders, DB/runtime integration, and async/plugin/hydration tests).
3. `pytest -q tests/test_patient_home_surface_pat_a1_2.py tests/test_patient_first_booking_review_pat_a1_1.py tests/test_patient_existing_booking_shortcut_pat_a3_2.py`  
   - **FAIL** (4 failures in quick-book service-stub coverage expecting missing `title_key`; not introduced by P0-01 navigation changes).
4. `pytest -q tests/test_patient_home_surface_pat_a1_2.py tests/test_patient_first_booking_review_pat_a1_1.py`  
   - **PASS** (40 passed).

## Grep checks run
Command:
- `rg "Рекомендаций пока нет\.$|Каталог ухода сейчас недоступен\.$|Поделитесь контактом телефона или введите номер в чат" app/interfaces/bots/patient app tests`

Result:
- No matches in `app/interfaces/bots/patient` or `app/tests` runtime surfaces.

## Known carry-forward for P0-02/P0-03/P0-04
- Quick-book tests in `tests/test_patient_existing_booking_shortcut_pat_a3_2.py` still depend on service stubs that omit fields expected by current service panel renderer.
- Full repository test suite remains red from unrelated reminder/runtime/DB-hydration issues.
- Contact-stage navigation currently relies on reply-keyboard text matching; deeper stateful back-stack can be handled in follow-up UX hardening.

## Risky areas / intentionally not changed
- Did not refactor `CardShellRenderer`.
- Did not split `patient/router.py`.
- Did not redesign slot pagination or service/doctor pickers.
- Did not alter booking orchestration/domain/database schema.
- Kept callback contracts stable and reused existing callbacks.
