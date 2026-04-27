from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path

from aiogram.types import InlineKeyboardMarkup

import test_patient_existing_booking_shortcut_pat_a3_2 as existing
from app.application.booking.orchestration_outcomes import OrchestrationSuccess
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.common.i18n import I18nService
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, Service
from app.interfaces.bots.patient.router import make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore
from app.interfaces.cards.runtime_state import InMemoryRedis


def _reference(locale: str) -> ClinicReferenceService:
    repo = InMemoryClinicReferenceRepository()
    repo.upsert_clinic(Clinic(clinic_id="clinic_main", code="MAIN", display_name="Main", timezone="Europe/Moscow", default_locale=locale))
    repo.upsert_branch(Branch(branch_id="branch_1", clinic_id="clinic_main", display_name="Main Branch", address_text="-", timezone="Europe/Moscow"))
    repo.upsert_service(Service(service_id="service_consult", clinic_id="clinic_main", code="CONSULT", title_key="service.consult", duration_minutes=30))
    repo.upsert_doctor(Doctor(doctor_id="doctor_1", clinic_id="clinic_main", display_name="Dr One", specialty_code="dent", branch_id="branch_1"))
    return ClinicReferenceService(repo)


def _build_router(*, locale: str = "en"):
    i18n = I18nService(locales_path=Path("locales"), default_locale=locale)
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    booking_flow = existing._BookingFlowStub()
    reminder_actions = existing._ReminderActions()
    router = make_router(
        i18n=i18n,
        booking_flow=booking_flow,
        reference=_reference(locale),
        reminder_actions=reminder_actions,
        recommendation_service=None,
        care_commerce_service=None,
        recommendation_repository=existing._RepoUnique(),
        default_locale=locale,
        card_runtime=runtime,
        card_callback_codec=codec,
    )
    return router, runtime, booking_flow


def _button_map(markup: InlineKeyboardMarkup) -> dict[str, str]:
    return {button.text: button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def _latest_callback_edit(callback: existing._Callback) -> tuple[str, object | None]:
    if callback.bot.edits:
        payload = callback.bot.edits[-1]
        return payload["text"], payload.get("reply_markup")
    if callback.message.answers:
        return callback.message.answers[-1]
    if callback.message.edits:
        return callback.message.edits[-1]
    raise AssertionError("expected callback payload")


def test_p0_05a_my_booking_exact_match_readable_card_en_and_ru() -> None:
    for locale in ("en", "ru"):
        router, _, _ = _build_router(locale=locale)
        message = existing._Message(text="/my_booking", user_id=1001)
        asyncio.run(existing._handler(router, "my_booking_entry")(message))

        text, _ = message.answers[-1]
        required = (
            "📅",
            "🦷",
            "👩‍⚕️",
            "📍",
            "🔔",
            "✅",
        )
        for token in required:
            assert token in text
        forbidden = (
            "Actions:",
            "Channel:",
            "Канал:",
            "telegram",
            "booking_id",
            "slot_id",
            "patient_id",
            "doctor_id",
            "service_id",
            "branch_id",
            "branch: -",
            "source_channel",
            "booking_mode",
            "UTC",
            "MSK",
            "%Z",
            "2026-04-",
        )
        for token in forbidden:
            assert token not in text
        if locale == "ru":
            assert "Tue" not in text
            assert "Apr" not in text


def test_p0_05a_my_booking_keyboard_pending_confirmation() -> None:
    router, _, booking_flow = _build_router(locale="en")
    booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": "pending_confirmation"})

    message = existing._Message(text="/my_booking", user_id=1001)
    asyncio.run(existing._handler(router, "my_booking_entry")(message))
    _, markup = message.answers[-1]
    assert isinstance(markup, InlineKeyboardMarkup)
    buttons = _button_map(markup)
    assert "Confirm booking" in buttons and buttons["Confirm booking"].startswith("c2|")
    assert "Request reschedule" in buttons
    assert "Join earlier-slot waitlist" in buttons
    assert "Cancel booking" in buttons
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_05a_my_booking_keyboard_confirmed_and_terminal() -> None:
    router, _, booking_flow = _build_router(locale="en")

    booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": "confirmed"})
    message_confirmed = existing._Message(text="/my_booking", user_id=1001)
    asyncio.run(existing._handler(router, "my_booking_entry")(message_confirmed))
    _, confirmed_markup = message_confirmed.answers[-1]
    confirmed_buttons = _button_map(confirmed_markup)
    assert "Confirm booking" not in confirmed_buttons
    assert "Request reschedule" in confirmed_buttons
    assert "Join earlier-slot waitlist" in confirmed_buttons
    assert "Cancel booking" in confirmed_buttons
    assert confirmed_buttons["🏠 Main menu"] == "phome:home"

    for idx, status in enumerate(("canceled", "completed", "no_show"), start=2002):
        booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": status})
        message_terminal = existing._Message(text="/my_booking", user_id=idx)
        asyncio.run(existing._handler(router, "my_booking_entry")(message_terminal))
        _, terminal_markup = message_terminal.answers[-1]
        terminal_buttons = _button_map(terminal_markup)
        assert terminal_buttons == {"🏠 Main menu": "phome:home"}


def test_p0_05a_confirm_and_cancel_rerender_clean_card_with_controls() -> None:
    router, runtime, booking_flow = _build_router(locale="en")
    booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": "pending_confirmation"})

    open_panel = existing._Message(text="/my_booking", user_id=1001)
    asyncio.run(existing._handler(router, "my_booking_entry")(open_panel))
    _, panel_markup = open_panel.answers[-1]
    panel_buttons = _button_map(panel_markup)
    confirm_callback_data = panel_buttons["Confirm booking"]

    async def _confirm_existing_booking(**kwargs):  # noqa: ANN003
        booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": "confirmed"})
        return OrchestrationSuccess(kind="success", entity=booking_flow.booking)

    async def _cancel_booking(**kwargs):  # noqa: ANN003
        booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": "canceled"})
        return OrchestrationSuccess(kind="success", entity=booking_flow.booking)

    booking_flow.confirm_existing_booking = _confirm_existing_booking  # type: ignore[method-assign]
    booking_flow.cancel_booking = _cancel_booking  # type: ignore[method-assign]

    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=existing.PanelFamily.BOOKING_DETAIL))
    confirm_callback = existing._Callback(data=confirm_callback_data, user_id=1001, message_id=active.message_id if active else 500)
    asyncio.run(existing._handler(router, "runtime_card_callback", kind="callback")(confirm_callback))
    confirm_text, confirm_markup = _latest_callback_edit(confirm_callback)
    assert "Actions:" not in confirm_text
    assert isinstance(confirm_markup, InlineKeyboardMarkup)
    assert "Cancel booking" in _button_map(confirm_markup)

    cancel_prompt = next(data for text, data in _button_map(confirm_markup).items() if text == "Cancel booking")
    cancel_prompt_callback = existing._Callback(data=cancel_prompt, user_id=1001, message_id=active.message_id if active else 500)
    asyncio.run(existing._handler(router, "runtime_card_callback", kind="callback")(cancel_prompt_callback))
    _, cancel_prompt_markup = _latest_callback_edit(cancel_prompt_callback)
    assert isinstance(cancel_prompt_markup, InlineKeyboardMarkup)
    cancel_confirm_payload = cancel_prompt_markup.inline_keyboard[0][0].callback_data
    assert cancel_confirm_payload and cancel_confirm_payload.startswith("c2|")
    cancel_confirm = existing._Callback(data=cancel_confirm_payload, user_id=1001, message_id=active.message_id if active else 500)
    asyncio.run(existing._handler(router, "runtime_card_callback", kind="callback")(cancel_confirm))
    cancel_text, cancel_markup = _latest_callback_edit(cancel_confirm)
    assert "Actions:" not in cancel_text
    cancel_buttons = _button_map(cancel_markup)
    assert cancel_buttons == {"🏠 Main menu": "phome:home"}


def test_p0_05a_no_active_booking_state_keeps_book_home_actions() -> None:
    router, _, booking_flow = _build_router(locale="en")
    booking_flow.resolve_known_patient_kind = "no_match"
    message = existing._Message(text="/my_booking", user_id=1001)

    asyncio.run(existing._handler(router, "my_booking_entry")(message))

    text, markup = message.answers[-1]
    assert "No active booking" in text
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]
    assert callbacks == ["phome:book", "phome:home"]
