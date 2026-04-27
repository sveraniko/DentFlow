from __future__ import annotations

import asyncio
from dataclasses import asdict

from aiogram.types import InlineKeyboardMarkup

import test_p0_05b_my_booking_action_panels as p05b
import test_patient_existing_booking_shortcut_pat_a3_2 as existing
import test_patient_reminder_handoff_pat_a3_1a as reminder
from app.application.booking.orchestration_outcomes import InvalidStateOutcome, OrchestrationSuccess
from app.interfaces.cards import PanelFamily

_ALLOWED_CALLBACK_PREFIXES = (
    "phome:home",
    "phome:book",
    "phome:my_booking",
    "phome:recommendations",
    "phome:care",
    "book:",
    "book:review:",
    "book:review:edit:",
    "book:slots:",
    "book:slot:",
    "mybk:",
    "rsch:",
    "care:",
    "careo:",
    "rec:",
)


def _button_map(markup: InlineKeyboardMarkup) -> dict[str, str]:
    return {button.text: button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def _callback_values(markup: InlineKeyboardMarkup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]


def _latest_callback_edit(callback: existing._Callback) -> tuple[str, object | None]:
    if callback.bot.edits:
        payload = callback.bot.edits[-1]
        return payload["text"], payload.get("reply_markup")
    if callback.message.answers:
        return callback.message.answers[-1]
    if callback.message.edits:
        return callback.message.edits[-1]
    raise AssertionError("expected callback payload")


def _assert_clean_patient_panel(text: str) -> None:
    for forbidden in (
        "Actions:",
        "Канал:",
        "Channel:",
        "telegram",
        "source_channel",
        "booking_mode",
        "booking_id",
        "slot_id",
        "patient_id",
        "doctor_id",
        "service_id",
        "branch_id",
        "branch: -",
        "UTC",
        "MSK",
        "%Z",
        "2026-04-",
    ):
        assert forbidden not in text


def test_p0_05c_card_keyboard_and_no_active_booking_smoke() -> None:
    for locale in ("en", "ru"):
        router, _, booking_flow = p05b._build_router(locale=locale)
        message = p05b._open_my_booking(router)
        text, markup = message.answers[-1]
        assert "📅" in text and "🦷" in text and "👩‍⚕️" in text and "📍" in text and "🔔" in text
        _assert_clean_patient_panel(text)
        buttons = _button_map(markup)
        assert "phome:home" in buttons.values()
        if locale == "ru":
            assert "Tue" not in text
            assert "Apr" not in text

    router, _, booking_flow = p05b._build_router(locale="en")
    booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": "pending_confirmation"})
    pending = p05b._open_my_booking(router, user_id=2001)
    _, pending_markup = pending.answers[-1]
    pending_values = _button_map(pending_markup).values()
    assert sum(1 for cb in pending_values if cb and cb.startswith("c2|")) == 4

    booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": "confirmed"})
    confirmed = p05b._open_my_booking(router, user_id=2002)
    _, confirmed_markup = confirmed.answers[-1]
    confirmed_values = _button_map(confirmed_markup).values()
    assert sum(1 for cb in confirmed_values if cb and cb.startswith("c2|")) == 3

    booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": "reschedule_requested"})
    reschedule_requested = p05b._open_my_booking(router, user_id=2003)
    _, rr_markup = reschedule_requested.answers[-1]
    rr_values = _button_map(rr_markup).values()
    assert sum(1 for cb in rr_values if cb and cb.startswith("c2|")) == 2

    for idx, status in enumerate(("canceled", "completed", "no_show"), start=3000):
        booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": status})
        terminal = p05b._open_my_booking(router, user_id=idx)
        _, terminal_markup = terminal.answers[-1]
        assert _button_map(terminal_markup) == {"🏠 Main menu": "phome:home"}

    booking_flow.resolve_known_patient_kind = "no_match"
    no_booking = p05b._open_my_booking(router, user_id=4001)
    empty_text, empty_markup = no_booking.answers[-1]
    assert "No active booking" in empty_text
    assert "/start" not in empty_text
    assert _callback_values(empty_markup) == ["phome:book", "phome:home"]


def test_p0_05c_runtime_and_legacy_callbacks_smoke() -> None:
    router, runtime, booking_flow = p05b._build_router(locale="en")
    booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": "pending_confirmation"})
    message = p05b._open_my_booking(router)
    _, markup = message.answers[-1]
    buttons = _button_map(markup)
    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    message_id = active.message_id if active else 500

    async def _confirm_existing_booking(**kwargs):  # noqa: ANN003
        booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": "confirmed"})
        return OrchestrationSuccess(kind="success", entity=booking_flow.booking)

    booking_flow.confirm_existing_booking = _confirm_existing_booking  # type: ignore[method-assign]

    confirm = existing._Callback(data=buttons["Confirm booking"], user_id=1001, message_id=message_id)
    asyncio.run(existing._handler(router, "runtime_card_callback", kind="callback")(confirm))
    confirm_text, confirm_markup = _latest_callback_edit(confirm)
    _assert_clean_patient_panel(confirm_text)
    assert "✅ Confirmed" in confirm_text
    assert confirm.answers == []

    confirm_buttons = _button_map(confirm_markup)
    runtime_waitlist = existing._Callback(data=confirm_buttons["Join earlier-slot waitlist"], user_id=1001, message_id=message_id)
    asyncio.run(existing._handler(router, "runtime_card_callback", kind="callback")(runtime_waitlist))
    waitlist_text, waitlist_markup = _latest_callback_edit(runtime_waitlist)
    assert "Earlier-slot request accepted" in waitlist_text
    assert "🏠 Main menu" in _button_map(waitlist_markup)
    assert runtime_waitlist.answers == []

    runtime_reschedule = existing._Callback(data=confirm_buttons["Request reschedule"], user_id=1001, message_id=message_id)
    asyncio.run(existing._handler(router, "runtime_card_callback", kind="callback")(runtime_reschedule))
    rtext, rmarkup = _latest_callback_edit(runtime_reschedule)
    rbuttons = _button_map(rmarkup)
    assert "🔁 Reschedule booking" in rtext
    assert "Select new time" in rbuttons
    assert "📅 Your booking" in rbuttons and "🏠 Main menu" in rbuttons
    assert runtime_reschedule.answers == []

    prompt = existing._Callback(data=confirm_buttons["Cancel booking"], user_id=1001, message_id=message_id)
    asyncio.run(existing._handler(router, "runtime_card_callback", kind="callback")(prompt))
    prompt_text, prompt_markup = _latest_callback_edit(prompt)
    assert "❌ Cancel booking?" in prompt_text
    _assert_clean_patient_panel(prompt_text)
    prompt_buttons = _button_map(prompt_markup)
    assert "❌ Yes, cancel booking" in prompt_buttons
    assert "⬅️ Back to booking" in prompt_buttons
    assert prompt.answers == []

    abort = existing._Callback(data=prompt_buttons["⬅️ Back to booking"], user_id=1001, message_id=message_id)
    asyncio.run(existing._handler(router, "runtime_card_callback", kind="callback")(abort))
    abort_text, abort_markup = _latest_callback_edit(abort)
    assert "was not changed" in abort_text
    assert "Cancel booking" in _button_map(abort_markup)
    assert abort.answers == []

    async def _cancel_booking(**kwargs):  # noqa: ANN003
        booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": "canceled"})
        return OrchestrationSuccess(kind="success", entity=booking_flow.booking)

    booking_flow.cancel_booking = _cancel_booking  # type: ignore[method-assign]
    cancel_confirm = existing._Callback(data=prompt_buttons["❌ Yes, cancel booking"], user_id=1001, message_id=message_id)
    asyncio.run(existing._handler(router, "runtime_card_callback", kind="callback")(cancel_confirm))
    canceled_text, canceled_markup = _latest_callback_edit(cancel_confirm)
    assert "❌ Canceled" in canceled_text
    assert _button_map(canceled_markup) == {"🏠 Main menu": "phome:home"}
    assert cancel_confirm.answers == []

    for payload, handler_name, expected in (
        ("mybk:cancel_prompt:sess_known:b1", "cancel_prompt", "❌ Cancel booking?"),
        ("mybk:cancel_abort:sess_known:b1", "cancel_abort", "was not changed"),
        ("mybk:cancel_confirm:sess_known:b1", "cancel_confirm", "❌ Canceled"),
        ("mybk:waitlist:sess_known:b1", "join_waitlist", "Earlier-slot request accepted"),
        ("mybk:reschedule:sess_known:b1", "request_reschedule", "🔁 Reschedule booking"),
    ):
        callback = existing._Callback(data=payload, user_id=1001)
        asyncio.run(existing._handler(router, handler_name, kind="callback")(callback))
        text, panel_markup = _latest_callback_edit(callback)
        assert expected in text
        _assert_clean_patient_panel(text)
        assert isinstance(panel_markup, InlineKeyboardMarkup)
        assert callback.answers == []


def test_p0_05c_waitlist_failure_and_reschedule_unavailable_smoke() -> None:
    router, _, booking_flow = p05b._build_router(locale="en")
    p05b._open_my_booking(router)

    async def _join_waitlist_fail(**kwargs):  # noqa: ANN003
        return InvalidStateOutcome(kind="invalid_state", reason="test")

    booking_flow.join_earlier_slot_waitlist = _join_waitlist_fail  # type: ignore[method-assign]
    fail = existing._Callback(data="mybk:waitlist:sess_known:b1", user_id=1001)
    asyncio.run(existing._handler(router, "join_waitlist", kind="callback")(fail))
    assert fail.message.answers == [] and fail.bot.edits == []
    assert fail.answers and fail.answers[0].startswith("Booking could not be finalized")

    async def _start_unavailable(**kwargs):  # noqa: ANN003
        return type("StartResult", (), {"kind": "unavailable", "booking": None, "booking_session": None})()

    booking_flow.start_patient_reschedule_session = _start_unavailable  # type: ignore[method-assign]
    unavailable = existing._Callback(data="mybk:reschedule:sess_known:b1", user_id=1001)
    asyncio.run(existing._handler(router, "request_reschedule", kind="callback")(unavailable))
    text, markup = _latest_callback_edit(unavailable)
    buttons = _button_map(markup)
    assert "couldn't open reschedule" in text
    assert "📅 Your booking" in buttons and "🏠 Main menu" in buttons


def test_p0_05c_reschedule_complete_reminder_handoff_and_callback_namespace() -> None:
    router, _, _ = p05b._build_router(locale="en")
    p05b._open_my_booking(router)

    start = existing._Callback(data="mybk:reschedule:sess_known:b1", user_id=1001)
    asyncio.run(existing._handler(router, "request_reschedule", kind="callback")(start))

    confirm = existing._Callback(data="rsch:confirm:sess_rsch_1", user_id=1001)
    asyncio.run(existing._handler(router, "reschedule_confirm", kind="callback")(confirm))
    text, markup = _latest_callback_edit(confirm)
    _assert_clean_patient_panel(text)
    assert "rescheduled successfully" in text
    assert isinstance(markup, InlineKeyboardMarkup)

    collected_callbacks = _callback_values(markup)

    rem_router, _ = reminder._build_router(
        reminder_actions=reminder._ReminderActions(outcome_kind="accepted", outcome_reason="booking_confirmed", booking_id="b1"),
        booking_flow=reminder._BookingFlowStub(status="confirmed"),
    )
    callback = reminder._Callback("rem:confirm:rem_1", user_id=1001)
    asyncio.run(reminder._handler(rem_router, "reminder_action_callback")(callback))
    sent_text, sent_keyboard = callback.message.answers[-1]
    assert "Booking confirmed." in sent_text
    assert sent_keyboard is not None
    assert "🏠 Main menu" in [button.text for row in sent_keyboard.inline_keyboard for button in row]
    _assert_clean_patient_panel(sent_text)
    collected_callbacks.extend(button.callback_data for row in sent_keyboard.inline_keyboard for button in row if button.callback_data)

    for callback_data in collected_callbacks:
        assert callback_data.startswith(_ALLOWED_CALLBACK_PREFIXES) or callback_data.startswith("c2|"), callback_data
