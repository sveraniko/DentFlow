from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path

from aiogram.types import InlineKeyboardMarkup

import test_patient_existing_booking_shortcut_pat_a3_2 as existing
from app.application.booking.orchestration_outcomes import InvalidStateOutcome, OrchestrationSuccess
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.common.i18n import I18nService
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, Service
from app.interfaces.bots.patient.router import make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore, PanelFamily
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
    async def _join_earlier_slot_waitlist(**kwargs):  # noqa: ANN003
        return OrchestrationSuccess(kind="success", entity=booking_flow.booking)

    async def _complete_patient_reschedule(**kwargs):  # noqa: ANN003
        return OrchestrationSuccess(kind="success", entity=booking_flow.booking)

    booking_flow.join_earlier_slot_waitlist = _join_earlier_slot_waitlist  # type: ignore[attr-defined]
    booking_flow.complete_patient_reschedule = _complete_patient_reschedule  # type: ignore[attr-defined]
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
    raise AssertionError("expected callback payload")


def _open_my_booking(router, user_id: int = 1001):
    message = existing._Message(text="/my_booking", user_id=user_id)
    asyncio.run(existing._handler(router, "my_booking_entry")(message))
    return message


def test_p0_05b_cancel_runtime_prompt_abort_confirm_polish() -> None:
    router, runtime, booking_flow = _build_router(locale="en")
    booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": "confirmed"})

    message = _open_my_booking(router)
    _, markup = message.answers[-1]
    cancel_payload = _button_map(markup)["Cancel booking"]

    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    prompt_callback = existing._Callback(data=cancel_payload, user_id=1001, message_id=active.message_id if active else 500)
    asyncio.run(existing._handler(router, "runtime_card_callback", kind="callback")(prompt_callback))
    prompt_text, prompt_markup = _latest_callback_edit(prompt_callback)
    prompt_buttons = _button_map(prompt_markup)

    assert "❌ Cancel booking?" in prompt_text
    assert "🦷 Service:" in prompt_text and "👩‍⚕️ Doctor:" in prompt_text and "📅 Date:" in prompt_text and "🕒 Time:" in prompt_text
    assert "cannot be undone" in prompt_text
    assert "❌ Yes, cancel booking" in prompt_buttons
    assert "⬅️ Back to booking" in prompt_buttons
    assert prompt_buttons["🏠 Main menu"] == "phome:home"
    for forbidden in ("Actions:", "Channel:", "telegram", "booking_id", "UTC", "MSK", "2026-04-"):
        assert forbidden not in prompt_text

    abort_callback = existing._Callback(data=prompt_buttons["⬅️ Back to booking"], user_id=1001, message_id=active.message_id if active else 500)
    asyncio.run(existing._handler(router, "runtime_card_callback", kind="callback")(abort_callback))
    abort_text, abort_markup = _latest_callback_edit(abort_callback)
    assert "Cancellation canceled. Your booking was not changed." in abort_text
    assert "📅 Your booking" in abort_text
    assert "Cancel booking" in _button_map(abort_markup)
    assert abort_callback.answers == []

    async def _cancel_booking(**kwargs):  # noqa: ANN003
        booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": "canceled"})
        return OrchestrationSuccess(kind="success", entity=booking_flow.booking)

    booking_flow.cancel_booking = _cancel_booking  # type: ignore[method-assign]
    confirm_callback = existing._Callback(data=prompt_buttons["❌ Yes, cancel booking"], user_id=1001, message_id=active.message_id if active else 500)
    asyncio.run(existing._handler(router, "runtime_card_callback", kind="callback")(confirm_callback))
    confirm_text, confirm_markup = _latest_callback_edit(confirm_callback)
    assert "❌ Canceled" in confirm_text
    assert _button_map(confirm_markup) == {"🏠 Main menu": "phome:home"}


def test_p0_05b_cancel_legacy_prompt_abort_confirm_polish() -> None:
    router, _, booking_flow = _build_router(locale="en")
    booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": "confirmed"})
    _open_my_booking(router)

    prompt = existing._Callback(data="mybk:cancel_prompt:sess_known:b1", user_id=1001)
    asyncio.run(existing._handler(router, "cancel_prompt", kind="callback")(prompt))
    prompt_text, prompt_markup = _latest_callback_edit(prompt)
    buttons = _button_map(prompt_markup)
    assert "❌ Cancel booking?" in prompt_text
    assert "❌ Yes, cancel booking" in buttons and "⬅️ Back to booking" in buttons and "🏠 Main menu" in buttons

    abort = existing._Callback(data="mybk:cancel_abort:sess_known:b1", user_id=1001)
    asyncio.run(existing._handler(router, "cancel_abort", kind="callback")(abort))
    abort_text, abort_markup = _latest_callback_edit(abort)
    assert "Cancellation canceled. Your booking was not changed." in abort_text
    assert "Cancel booking" in _button_map(abort_markup)

    async def _cancel_booking(**kwargs):  # noqa: ANN003
        booking_flow.booking = existing.Booking(**{**asdict(booking_flow.booking), "status": "canceled"})
        return OrchestrationSuccess(kind="success", entity=booking_flow.booking)

    booking_flow.cancel_booking = _cancel_booking  # type: ignore[method-assign]
    confirm = existing._Callback(data="mybk:cancel_confirm:sess_known:b1", user_id=1001)
    asyncio.run(existing._handler(router, "cancel_confirm", kind="callback")(confirm))
    confirm_text, confirm_markup = _latest_callback_edit(confirm)
    assert "❌ Canceled" in confirm_text
    assert _button_map(confirm_markup) == {"🏠 Main menu": "phome:home"}


def test_p0_05b_waitlist_runtime_and_legacy_success_and_failure_panels() -> None:
    router, runtime, booking_flow = _build_router(locale="en")
    open_panel = _open_my_booking(router)
    _, markup = open_panel.answers[-1]
    waitlist_payload = _button_map(markup)["Join earlier-slot waitlist"]

    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    runtime_callback = existing._Callback(data=waitlist_payload, user_id=1001, message_id=active.message_id if active else 500)
    asyncio.run(existing._handler(router, "runtime_card_callback", kind="callback")(runtime_callback))
    text, panel_markup = _latest_callback_edit(runtime_callback)
    assert "⏱ Earlier-slot request accepted" in text
    assert "Your current booking remains active:" in text
    assert "📅 Your booking" in text
    assert "🏠 Main menu" in _button_map(panel_markup)

    legacy = existing._Callback(data="mybk:waitlist:sess_known:b1", user_id=1001)
    asyncio.run(existing._handler(router, "join_waitlist", kind="callback")(legacy))
    legacy_text, legacy_markup = _latest_callback_edit(legacy)
    assert "⏱ Earlier-slot request accepted" in legacy_text
    assert "🏠 Main menu" in _button_map(legacy_markup)

    async def _join_waitlist_fail(**kwargs):  # noqa: ANN003
        return InvalidStateOutcome(kind="invalid_state", reason="test")

    booking_flow.join_earlier_slot_waitlist = _join_waitlist_fail  # type: ignore[method-assign]
    fail = existing._Callback(data="mybk:waitlist:sess_known:b1", user_id=1001)
    asyncio.run(existing._handler(router, "join_waitlist", kind="callback")(fail))
    assert any("Booking could not be finalized" in item for item in fail.answers)


def test_p0_05b_reschedule_runtime_legacy_and_unavailable_panels() -> None:
    router, runtime, booking_flow = _build_router(locale="en")
    message = _open_my_booking(router)
    _, markup = message.answers[-1]
    reschedule_payload = _button_map(markup)["Request reschedule"]

    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    runtime_callback = existing._Callback(data=reschedule_payload, user_id=1001, message_id=active.message_id if active else 500)
    asyncio.run(existing._handler(router, "runtime_card_callback", kind="callback")(runtime_callback))
    runtime_text, runtime_markup = _latest_callback_edit(runtime_callback)
    buttons = _button_map(runtime_markup)
    assert "🔁 Reschedule booking" in runtime_text
    assert "Select new time" in buttons
    assert "📅 Your booking" in buttons
    assert "🏠 Main menu" in buttons

    legacy = existing._Callback(data="mybk:reschedule:sess_known:b1", user_id=1001)
    asyncio.run(existing._handler(router, "request_reschedule", kind="callback")(legacy))
    legacy_text, legacy_markup = _latest_callback_edit(legacy)
    legacy_buttons = _button_map(legacy_markup)
    assert "🔁 Reschedule booking" in legacy_text
    assert "Select new time" in legacy_buttons and "📅 Your booking" in legacy_buttons and "🏠 Main menu" in legacy_buttons

    async def _start_unavailable(**kwargs):  # noqa: ANN003
        return type("StartResult", (), {"kind": "unavailable", "booking": None, "booking_session": None})()

    booking_flow.start_patient_reschedule_session = _start_unavailable  # type: ignore[method-assign]
    unavailable = existing._Callback(data="mybk:reschedule:sess_known:b1", user_id=1001)
    asyncio.run(existing._handler(router, "request_reschedule", kind="callback")(unavailable))
    unavailable_text, unavailable_markup = _latest_callback_edit(unavailable)
    unavailable_buttons = _button_map(unavailable_markup)
    assert "couldn't open reschedule" in unavailable_text
    assert "📅 Your booking" in unavailable_buttons and "🏠 Main menu" in unavailable_buttons


def test_p0_05b_reschedule_complete_success_clean_my_booking() -> None:
    router, _, booking_flow = _build_router(locale="en")
    _open_my_booking(router)

    start = existing._Callback(data="mybk:reschedule:sess_known:b1", user_id=1001)
    asyncio.run(existing._handler(router, "request_reschedule", kind="callback")(start))

    confirm = existing._Callback(data="rsch:confirm:sess_rsch_1", user_id=1001)
    asyncio.run(existing._handler(router, "reschedule_confirm", kind="callback")(confirm))
    text, markup = _latest_callback_edit(confirm)
    assert "rescheduled successfully" in text
    assert "📅 Your booking" in text
    assert isinstance(markup, InlineKeyboardMarkup)
    for forbidden in ("Actions:", "Channel:", "telegram", "booking_id", "slot_id", "UTC", "MSK"):
        assert forbidden not in text


def test_p0_05b_no_double_callback_answers_on_valid_paths() -> None:
    router, runtime, _ = _build_router(locale="en")
    message = _open_my_booking(router)
    _, markup = message.answers[-1]
    payloads = _button_map(markup)

    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    actions = [payloads["Cancel booking"], payloads["Join earlier-slot waitlist"], payloads["Request reschedule"]]
    for data in actions:
        callback = existing._Callback(data=data, user_id=1001, message_id=active.message_id if active else 500)
        asyncio.run(existing._handler(router, "runtime_card_callback", kind="callback")(callback))
        # valid paths should update panel and avoid alert popups
        assert callback.answers == []
