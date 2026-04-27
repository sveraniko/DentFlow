from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove

import test_patient_first_booking_review_pat_a1_1 as review
import test_p0_03d_patient_booking_smoke_gate as p0_03d_smoke
import test_patient_reschedule_start_pat_a4_1 as reschedule
from app.common.i18n import I18nService
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, Service
from app.interfaces.bots.patient.router import make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore
from app.interfaces.cards.runtime_state import InMemoryRedis

_ALLOWED_CALLBACK_PREFIXES = (
    "book:confirm:",
    "book:review:back:",
    "book:review:edit:",
    "book:svc:",
    "book:doc:",
    "book:doc_code:",
    "book:back:doctors:",
    "book:slot:",
    "book:slots:back:",
    "phome:home",
    "phome:my_booking",
    "rsch:confirm:",
)


def _callback_data(markup: InlineKeyboardMarkup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]


def _latest_callback_payload(callback: review._Callback) -> tuple[str, object | None]:
    for payload in reversed(callback.answer_payloads):
        if payload[0] or payload[2] is not None:
            return payload[0], payload[2]
    if callback.message.edits:
        return callback.message.edits[-1]
    if callback.bot.edits:
        return callback.bot.edits[-1]["text"], callback.bot.edits[-1].get("reply_markup")
    raise AssertionError("expected callback payload")


def test_p0_04c_review_contact_edit_success_finalize_failure_smoke() -> None:
    router, booking_flow, runtime = review._build_router_and_flow(locale="en")
    asyncio.run(runtime.bind_actor_session_state(scope="patient_flow", actor_id=1001, payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_contact", "care": {}}))

    msg = review._Message(text="+1 555 123 1234", user_id=1001)
    asyncio.run(review._handler(router, "on_contact_text")(msg))
    review_text, review_keyboard = msg.answers[-1]

    assert isinstance(review_keyboard, InlineKeyboardMarkup)
    assert any(isinstance(kb, ReplyKeyboardRemove) for _, kb in msg.answers)
    for token in ("📋 Review your booking", "Service:", "Doctor:", "Date:", "Time:", "Branch:", "Phone:"):
        assert token in review_text
    for forbidden in ("UTC", "MSK", "%Z", "pending_confirmation", "branch:", "service:", "doctor:", "Actions:", " -"):
        assert forbidden not in review_text

    callbacks = _callback_data(review_keyboard)
    assert callbacks == [
        "book:confirm:sess_1",
        "book:review:edit:service:sess_1",
        "book:review:edit:doctor:sess_1",
        "book:review:edit:time:sess_1",
        "book:review:edit:phone:sess_1",
        "book:review:back:sess_1",
        "phome:home",
    ]
    assert all(data.startswith(_ALLOWED_CALLBACK_PREFIXES) for data in callbacks)

    back_cb = review._Callback(data="book:review:back:sess_1", user_id=1001, message_id=501)
    asyncio.run(review._handler(router, "booking_review_back", kind="callback")(back_cb))
    back_text, back_keyboard = _latest_callback_payload(back_cb)
    assert "Contact for booking" in back_text
    assert isinstance(back_keyboard, ReplyKeyboardMarkup)
    assert len(back_cb.answer_payloads) == 1

    edit_service = review._Callback(data="book:review:edit:service:sess_1", user_id=1001, message_id=501)
    asyncio.run(review._handler(router, "booking_review_edit", kind="callback")(edit_service))
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert booking_flow.release_selected_slot_calls == 1
    assert booking_flow.session.selected_slot_id is None and booking_flow.session.selected_hold_id is None
    assert state["booking_mode"] == "review_edit_service"
    assert state["slot_page"] == 0 and state["slot_date_from"] == "" and state["slot_time_window"] == "all" and state["slot_suppressed_ids"] == []

    async def _update_service(*, booking_session_id: str, service_id: str):  # noqa: ARG001
        return booking_flow.session

    booking_flow.update_service = _update_service  # type: ignore[method-assign]
    service_pick = review._Callback(data="book:svc:sess_1:service_consult", user_id=1001, message_id=502)
    asyncio.run(review._handler(router, "select_service", kind="callback")(service_pick))
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "review_edit_doctor"

    edit_doctor = review._Callback(data="book:review:edit:doctor:sess_1", user_id=1001, message_id=503)
    asyncio.run(review._handler(router, "booking_review_edit", kind="callback")(edit_doctor))
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "review_edit_doctor"

    edit_time = review._Callback(data="book:review:edit:time:sess_1", user_id=1001, message_id=505)
    asyncio.run(review._handler(router, "booking_review_edit", kind="callback")(edit_time))
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "review_edit_time"

    booking_flow.session = review.BookingSession(**{**asdict(booking_flow.session), "contact_phone_snapshot": "+15551230000", "resolved_patient_id": "pat_1"})
    pick_slot = review._Callback(data="book:slot:slot_2", user_id=1001, message_id=506)
    asyncio.run(review._handler(router, "select_slot", kind="callback")(pick_slot))
    slot_text, slot_keyboard = _latest_callback_payload(pick_slot)
    assert "Review your booking" in slot_text
    assert isinstance(slot_keyboard, InlineKeyboardMarkup)
    assert booking_flow.mark_review_ready_calls >= 1

    edit_phone = review._Callback(data="book:review:edit:phone:sess_1", user_id=1001, message_id=507)
    booking_flow.session = review.BookingSession(**{**asdict(booking_flow.session), "selected_slot_id": "slot_2", "selected_hold_id": "hold_slot_2"})
    asyncio.run(review._handler(router, "booking_review_edit", kind="callback")(edit_phone))
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "review_edit_phone"
    assert booking_flow.release_selected_slot_calls == 3
    assert booking_flow.session.selected_slot_id == "slot_2"
    _, phone_keyboard = _latest_callback_payload(edit_phone)
    assert isinstance(phone_keyboard, ReplyKeyboardMarkup)

    phone_submit = review._Message(text="+1 555 987 0000", user_id=1001)
    asyncio.run(review._handler(router, "on_contact_text")(phone_submit))
    assert any(isinstance(kb, ReplyKeyboardRemove) for _, kb in phone_submit.answers)
    assert any(isinstance(kb, InlineKeyboardMarkup) for _, kb in phone_submit.answers) or any(
        isinstance(edit.get("reply_markup"), InlineKeyboardMarkup) for edit in phone_submit.bot.edits
    )

    back_from_phone = review._Message(text="⬅️ Back", user_id=1001)
    asyncio.run(runtime.bind_actor_session_state(scope="patient_flow", actor_id=1001, payload={"booking_session_id": "sess_1", "booking_mode": "review_edit_phone", "care": {}}))
    asyncio.run(review._handler(router, "on_contact_navigation")(back_from_phone))
    assert any(isinstance(kb, ReplyKeyboardRemove) for _, kb in back_from_phone.answers)
    assert back_from_phone.bot.edits and "Review your booking" in back_from_phone.bot.edits[-1]["text"]

    home_from_phone = review._Message(text="🏠 Main menu", user_id=1001)
    asyncio.run(runtime.bind_actor_session_state(scope="patient_flow", actor_id=1001, payload={"booking_session_id": "sess_1", "booking_mode": "review_edit_phone", "care": {}}))
    asyncio.run(review._handler(router, "on_contact_navigation")(home_from_phone))
    assert any(isinstance(kb, ReplyKeyboardRemove) for _, kb in home_from_phone.answers)

    confirm_ok = review._Callback(data="book:confirm:sess_1", user_id=1001, message_id=508)
    asyncio.run(review._handler(router, "confirm_new_booking", kind="callback")(confirm_ok))
    success_text = confirm_ok.bot.edits[-1]["text"]
    success_callbacks = _callback_data(confirm_ok.bot.edits[-1]["reply_markup"])
    for token in ("✅ Booking created", "Service:", "Doctor:", "Date:", "Time:", "Branch:", "Status:"):
        assert token in success_text
    for forbidden in ("pending_confirmation", "telegram", "Actions:", "branch: -", "UTC", "MSK"):
        assert forbidden not in success_text
    assert success_callbacks == ["phome:my_booking", "phome:home"]

    booking_flow.finalize_result = "slot_unavailable"
    unavailable = review._Callback(data="book:confirm:sess_1", user_id=1001, message_id=509)
    asyncio.run(review._handler(router, "confirm_new_booking", kind="callback")(unavailable))
    unavailable_text, unavailable_markup = _latest_callback_payload(unavailable)
    assert "no longer available" in unavailable_text.lower()
    assert "book:slots:back:sess_1" in _callback_data(unavailable_markup)
    assert "phome:home" in _callback_data(unavailable_markup)
    assert all(show_alert is False for _, show_alert, _ in unavailable.answer_payloads)

    booking_flow.finalize_result = "conflict"
    conflict = review._Callback(data="book:confirm:sess_1", user_id=1001, message_id=510)
    asyncio.run(review._handler(router, "confirm_new_booking", kind="callback")(conflict))
    conflict_text, conflict_markup = _latest_callback_payload(conflict)
    assert "no longer available" in conflict_text.lower()
    assert "phome:home" in _callback_data(conflict_markup)

    booking_flow.finalize_result = "invalid"
    invalid = review._Callback(data="book:confirm:sess_1", user_id=1001, message_id=511)
    asyncio.run(review._handler(router, "confirm_new_booking", kind="callback")(invalid))
    invalid_text, invalid_markup = _latest_callback_payload(invalid)
    assert "could not confirm" in invalid_text.lower()
    assert _callback_data(invalid_markup) == ["phome:home"]


def test_p0_04c_reschedule_review_datetime_polish_ru_smoke() -> None:
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    i18n = I18nService(locales_path=Path("locales"), default_locale="ru")
    flow = reschedule._BookingFlowStub()
    # 2026-04-28 11:00 UTC -> 14:00 Europe/Moscow
    flow.booking = review.Booking(**{**asdict(flow.booking), "scheduled_start_at": datetime(2026, 4, 28, 11, 0, tzinfo=timezone.utc)})

    async def _slot(**kwargs):  # noqa: ANN003
        return review.AvailabilitySlot(
            slot_id="slot_new_1",
            clinic_id="clinic_main",
            branch_id="branch_1",
            doctor_id="doctor_1",
            start_at=datetime(2026, 4, 28, 11, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 4, 28, 11, 30, tzinfo=timezone.utc),
            status="open",
            visibility_policy="public",
            service_scope=None,
            source_ref=None,
            updated_at=datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc),
        )

    flow.get_availability_slot = _slot  # type: ignore[method-assign]
    repo = InMemoryClinicReferenceRepository()
    repo.upsert_clinic(Clinic(clinic_id="clinic_main", code="MAIN", display_name="Main", timezone="Europe/Moscow", default_locale="ru"))
    repo.upsert_branch(Branch(branch_id="branch_1", clinic_id="clinic_main", display_name="Main Branch", address_text="-", timezone="Europe/Moscow"))
    repo.upsert_service(Service(service_id="service_consult", clinic_id="clinic_main", code="CONSULT", title_key="service.consult", duration_minutes=30))
    repo.upsert_doctor(Doctor(doctor_id="doctor_1", clinic_id="clinic_main", display_name="Dr One", specialty_code="dent", branch_id="branch_1"))
    reference = ClinicReferenceService(repo)

    router = make_router(
        i18n=i18n,
        booking_flow=flow,
        reference=reference,
        reminder_actions=reschedule._ReminderActions(),
        recommendation_service=None,
        care_commerce_service=None,
        recommendation_repository=reschedule._RepoNone(),
        default_locale="ru",
        card_runtime=runtime,
        card_callback_codec=codec,
    )

    asyncio.run(runtime.bind_actor_session_state(scope="patient_flow", actor_id=1001, payload={"booking_session_id": "sess_rsch_1", "booking_mode": "reschedule_booking_control", "reschedule_booking_id": "b1", "care": {}}))
    callback = review._Callback(data="book:slot:slot_new_1", user_id=1001, message_id=701)
    asyncio.run(reschedule._handler(router, "select_slot")(callback))
    text, keyboard = _latest_callback_payload(callback)
    assert "28 апреля 2026" in text
    assert "14:00" in text
    for forbidden in ("UTC", "MSK", "%Z", "2026-04-", "Tue", "Apr"):
        assert forbidden not in text
    assert isinstance(keyboard, InlineKeyboardMarkup)
    callbacks = _callback_data(keyboard)
    assert "rsch:confirm:sess_rsch_1" in callbacks
    assert "phome:home" in callbacks
    assert "book:slots:back:sess_rsch_1" in callbacks
    assert all(data.startswith(_ALLOWED_CALLBACK_PREFIXES) for data in callbacks)


def test_p0_04c_callback_namespace_review_prefixes_smoke() -> None:
    assert "book:review:back:" in p0_03d_smoke._ALLOWED_CALLBACK_PREFIXES
    assert "book:review:edit:" in p0_03d_smoke._ALLOWED_CALLBACK_PREFIXES
