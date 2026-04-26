# P0-02A Contact Reply Keyboard Carry-Forward Report

## Summary
Implemented a targeted fix in `app/interfaces/bots/patient/router.py` so contact-stage prompts that rely on `ReplyKeyboardMarkup` are always sent as **new messages** rather than edited inline panels. This prevents Telegram reply keyboards from being dropped when entering contact collection from callback paths or when an active panel exists.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `tests/test_patient_first_booking_review_pat_a1_1.py`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `tests/test_patient_existing_booking_shortcut_pat_a3_2.py`

## Exact paths fixed
- `_send_or_edit_panel(...)` now special-cases `reply_keyboard is not None` and sends a fresh message (never `edit_text` with reply keyboard).
- `select_slot(...)` path verified by tests to emit a contact reply keyboard from callback entry.
- `_render_resume_panel(...)` `contact_collection` path verified by tests to emit a contact reply keyboard from callback entry.
- `_enter_existing_booking_lookup(...)` path verified by tests to emit a contact reply keyboard for My Booking lookup.

## Why `ReplyKeyboardMarkup` needed special handling
Telegram reply keyboards are chat-level input controls, not inline message-level controls. Editing an existing panel message (`edit_text`) with inline semantics can silently drop a reply keyboard payload. To make contact prompts reliable, the contact panel must be sent as a new message with `reply_markup=ReplyKeyboardMarkup`, and the runtime active panel binding must be moved to that newly sent message id.

## Tests run (exact commands/results)
- `python -m compileall app tests` — pass.
- `pytest -q tests/test_patient_first_booking_review_pat_a1_1.py tests/test_patient_home_surface_pat_a1_2.py tests/test_patient_existing_booking_shortcut_pat_a3_2.py` — pass.

## Remaining carry-forward for P0-02B
- Monitor adjacent callback flows for any other UI surfaces that might need strict separation between inline-edit panels and fresh-message reply keyboards.
- Keep fake callback/message test doubles synchronized with Telegram semantics (especially `CallbackQuery.message.answer(...)`) for future keyboard-related regressions.

## Callback namespace confirmation
No new callback namespace was introduced in this patch.
