from __future__ import annotations

import asyncio
from dataclasses import asdict

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove

import test_patient_first_booking_review_pat_a1_1 as review
import test_patient_home_surface_pat_a1_2 as home
import test_patient_reschedule_start_pat_a4_1 as reschedule
from app.application.booking.orchestration_outcomes import ConflictOutcome, SlotUnavailableOutcome

_ALLOWED_CALLBACK_PREFIXES = (
    "phome:home",
    "phome:book",
    "phome:my_booking",
    "phome:recommendations",
    "phome:care",
    "phome:lang",
    "book:service:",
    "book:svc:",
    "book:doctor:",
    "book:doctor_any:",
    "book:doc_code:",
    "book:doc:",
    "book:back:services:",
    "book:back:doctors:",
    "book:slot:",
    "book:review:back:",
    "book:review:edit:",
    "book:slots:more:",
    "book:slots:dates:",
    "book:slots:date:",
    "book:slots:windows:",
    "book:slots:window:",
    "book:slots:back:",
    "care:",
    "careo:",
    "rec:",
    "rsch:",
)


def _callback_data(markup: InlineKeyboardMarkup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]


def _assert_expected_prefixes(markups: list[InlineKeyboardMarkup]) -> None:
    for markup in markups:
        for callback_data in _callback_data(markup):
            assert callback_data.startswith(_ALLOWED_CALLBACK_PREFIXES), callback_data


def test_p0_03d_home_service_doctor_smoke_and_callback_namespace() -> None:
    router, runtime, _, recommendation_service, care_service = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="ru",
    )

    start_message = home._Message(text="/start", user_id=1001)
    asyncio.run(home._handler(router, "start")(start_message))
    home_text, home_markup = start_message.answers[-1]
    assert "DentFlow" in home_text
    assert "Добро пожаловать в DentFlow. Выберите действие:" not in home_text
    home_actions = _callback_data(home_markup)
    assert "phome:book" in home_actions
    assert "phome:my_booking" in home_actions
    assert "phome:recommendations" in home_actions
    assert "phome:care" in home_actions

    service_callback = home._Callback(data="qbook:other:sess_1", user_id=1001)
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "care": {}},
        )
    )
    asyncio.run(home._handler(router, "quick_book_other", kind="callback")(service_callback))
    service_text, service_markup = home._latest_callback_panel(service_callback)
    assert service_text
    assert "Выберите услугу для записи." not in service_text
    service_actions = _callback_data(service_markup)
    assert "phome:home" in service_actions

    doctor_callback = home._Callback(data="book:svc:sess_1:service_consult", user_id=1001)
    asyncio.run(home._handler(router, "select_service", kind="callback")(doctor_callback))
    doctor_text, doctor_markup = home._latest_callback_panel(doctor_callback)
    assert "Выберите предпочтение по врачу." not in doctor_text
    doctor_actions = _callback_data(doctor_markup)
    assert "book:doc_code:sess_1" in doctor_actions
    assert "book:back:doctors:sess_1" in doctor_actions
    assert "phome:home" in doctor_actions
    assert any(item.startswith("book:doc:") for item in doctor_actions)

    rec_callback = home._Callback(data="phome:recommendations", user_id=1001)
    recommendation_service.rows = []
    asyncio.run(home._handler(router, "patient_home_recommendations", kind="callback")(rec_callback))
    _, rec_markup = home._latest_callback_panel(rec_callback)
    assert "phome:home" in _callback_data(rec_markup)

    assert care_service is not None
    async def _empty_categories(**kwargs):  # noqa: ANN003
        return []
    care_service.list_catalog_categories = _empty_categories  # type: ignore[method-assign]
    care_callback = home._Callback(data="phome:care", user_id=1001)
    asyncio.run(home._handler(router, "patient_home_care", kind="callback")(care_callback))
    _, care_markup = home._latest_callback_panel(care_callback)
    assert "phome:home" in _callback_data(care_markup)

    _assert_expected_prefixes([home_markup, service_markup, doctor_markup, rec_markup, care_markup])


def test_p0_03d_doctor_code_vs_contact_routing_and_reply_keyboard_remove() -> None:
    router, runtime, booking_flow, _, _ = home._build_router(with_recommendations=False, with_care=False)

    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_doctor_code", "care": {}},
        )
    )
    doctor_code = home._Message(text="ANNA-001")
    asyncio.run(home._handler(router, "on_contact_navigation")(doctor_code))
    assert booking_flow.session.doctor_id == "doctor_1"

    doctor_mode_phone = home._Message(text="+7 999 123-45-67")
    asyncio.run(home._handler(router, "on_contact_navigation")(doctor_mode_phone))
    assert booking_flow.session.contact_phone_snapshot is None

    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_contact", "care": {}},
        )
    )
    contact_mode_code = home._Message(text="ANNA-001")
    asyncio.run(home._handler(router, "on_contact_navigation")(contact_mode_code))
    assert booking_flow.session.doctor_id == "doctor_1"

    go_home = home._Message(text="🏠 Main menu", user_id=1001)
    asyncio.run(home._handler(router, "on_contact_navigation")(go_home))
    assert any(isinstance(reply_markup, ReplyKeyboardRemove) for _, reply_markup in go_home.answers)

    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_contact", "care": {}},
        )
    )
    go_back = home._Message(text="⬅️ Back", user_id=1001)
    asyncio.run(home._handler(router, "on_contact_navigation")(go_back))
    assert any(isinstance(reply_markup, ReplyKeyboardRemove) for _, reply_markup in go_back.answers)
    assert bool(go_back.bot.edits) or any("slots" in text.lower() for text, _ in go_back.answers)


def test_p0_03d_slot_panel_pagination_date_window_smoke() -> None:
    router, runtime, _, _, _ = home._build_router(with_recommendations=False, with_care=False, locale="ru")
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "care": {}},
        )
    )

    first_page = home._Callback(data="book:doc:sess_1:any", user_id=1001)
    asyncio.run(home._handler(router, "select_doctor_preference", kind="callback")(first_page))
    first_text, first_markup = home._latest_callback_panel(first_page)
    slot_labels = [row[0].text for row in first_markup.inline_keyboard if row and (row[0].callback_data or "").startswith("book:slot:")]
    assert slot_labels
    assert all("UTC" not in label and "Tue" not in label and "Apr" not in label for label in slot_labels)
    assert len(slot_labels) <= 5
    actions = _callback_data(first_markup)
    assert "book:slots:more:sess_1" in actions
    assert "book:slots:dates:sess_1" in actions
    assert "book:slots:windows:sess_1" in actions
    assert "book:back:doctors:sess_1" in actions
    assert "phome:home" in actions

    more = home._Callback(data="book:slots:more:sess_1", user_id=1001)
    asyncio.run(home._handler(router, "booking_slots_more", kind="callback")(more))
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["slot_page"] == 1
    assert len(more.answer_payloads) <= 1
    _, second_markup = home._latest_callback_panel(more)
    second_page_slots = [row[0].callback_data for row in second_markup.inline_keyboard if row and (row[0].callback_data or "").startswith("book:slot:")]
    first_page_slots = [row[0].callback_data for row in first_markup.inline_keyboard if row and (row[0].callback_data or "").startswith("book:slot:")]
    assert second_page_slots != first_page_slots

    open_dates = home._Callback(data="book:slots:dates:sess_1", user_id=1001)
    asyncio.run(home._handler(router, "booking_slots_dates", kind="callback")(open_dates))
    _, dates_markup = home._latest_callback_panel(open_dates)
    date_callback = next(button.callback_data for row in dates_markup.inline_keyboard for button in row if (button.callback_data or "").startswith("book:slots:date:sess_1:"))
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "slot_page": 2, "slot_suppressed_ids": ["slot_1"], "care": {}},
        )
    )
    pick_date = home._Callback(data=date_callback, user_id=1001)
    asyncio.run(home._handler(router, "booking_slots_date_select", kind="callback")(pick_date))
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["slot_date_from"] == date_callback.split(":")[-1]
    assert state["slot_page"] == 0
    assert state["slot_suppressed_ids"] == []

    open_windows = home._Callback(data="book:slots:windows:sess_1", user_id=1001)
    asyncio.run(home._handler(router, "booking_slots_windows", kind="callback")(open_windows))
    _, windows_markup = home._latest_callback_panel(open_windows)
    windows = {button.callback_data for row in windows_markup.inline_keyboard for button in row if button.callback_data}
    assert "book:slots:window:sess_1:all" in windows
    assert "book:slots:window:sess_1:morning" in windows
    assert "book:slots:window:sess_1:day" in windows
    assert "book:slots:window:sess_1:evening" in windows

    for window in ("morning", "day", "evening"):
        asyncio.run(
            runtime.bind_actor_session_state(
                scope="patient_flow",
                actor_id=1001,
                payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "slot_page": 2, "slot_suppressed_ids": ["slot_2"], "care": {}},
            )
        )
        choose = home._Callback(data=f"book:slots:window:sess_1:{window}", user_id=1001)
        asyncio.run(home._handler(router, "booking_slots_window_select", kind="callback")(choose))
        state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
        assert state["slot_time_window"] == window
        assert state["slot_page"] == 0
        assert state["slot_suppressed_ids"] == []

    _assert_expected_prefixes([first_markup, second_markup, dates_markup, windows_markup])


def test_p0_03d_slot_outcomes_contact_prompt_and_invalid_state_smoke() -> None:
    router, booking_flow, runtime = review._build_router_and_flow()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "care": {}},
        )
    )

    booking_flow.select_slot_outcome = SlotUnavailableOutcome(kind="slot_unavailable", reason="taken")
    unavailable = review._Callback(data="book:slot:slot_1", user_id=1001, message_id=501)
    asyncio.run(review._handler(router, "select_slot", kind="callback")(unavailable))
    text, keyboard = review._latest_callback_payload(unavailable)
    assert "slot is no longer available" in text.lower()
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert all(show_alert is False for _, show_alert, _ in unavailable.answer_payloads)
    assert len(unavailable.answer_payloads) == 1
    unavailable_state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert "slot_1" in unavailable_state["slot_suppressed_ids"]
    unavailable_callbacks = _callback_data(keyboard)
    assert "book:slot:slot_1" not in unavailable_callbacks

    router, booking_flow, runtime = review._build_router_and_flow()
    booking_flow.select_slot_outcome = ConflictOutcome(kind="conflict", reason="already booked")
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "care": {}},
        )
    )
    conflict = review._Callback(data="book:slot:slot_1", user_id=1001, message_id=501)
    asyncio.run(review._handler(router, "select_slot", kind="callback")(conflict))
    conflict_text, _ = review._latest_callback_payload(conflict)
    assert "slot is no longer available" in conflict_text.lower()
    assert all(show_alert is False for _, show_alert, _ in conflict.answer_payloads)

    router, booking_flow, runtime = review._build_router_and_flow()
    booking_flow.select_slot_outcome = review.InvalidStateOutcome(kind="invalid_state", reason="session moved")
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "care": {}},
        )
    )
    invalid = review._Callback(data="book:slot:slot_1", user_id=1001, message_id=501)
    asyncio.run(review._handler(router, "select_slot", kind="callback")(invalid))
    invalid_text, invalid_markup = review._latest_callback_payload(invalid)
    assert "contact for booking" not in invalid_text.lower()
    assert isinstance(invalid_markup, InlineKeyboardMarkup)
    assert all(show_alert is False for _, show_alert, _ in invalid.answer_payloads)

    router, booking_flow, runtime = review._build_router_and_flow()
    booking_flow.select_slot_outcome = None
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "care": {}},
        )
    )
    success = review._Callback(data="book:slot:slot_1", user_id=1001, message_id=501)
    asyncio.run(review._handler(router, "select_slot", kind="callback")(success))
    success_text, success_keyboard = review._latest_callback_payload(success)
    assert "contact for booking" in success_text.lower()
    assert isinstance(success_keyboard, ReplyKeyboardMarkup)
    rows = [[button.text for button in row] for row in success_keyboard.keyboard]
    assert rows[0] == ["Share contact"]
    assert rows[1] == ["⬅️ Back", "🏠 Main menu"]
    assert "+7 999 123-45-67" in success_text
    assert len(success.answer_payloads) == 1


def test_p0_03d_reschedule_conflict_smoke() -> None:
    flow = reschedule._BookingFlowStub()
    flow.complete_patient_reschedule_outcome = SlotUnavailableOutcome(kind="slot_unavailable", reason="selected slot is unavailable")
    router, runtime, _ = reschedule._build_router(booking_flow=flow)
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_rsch_1", "booking_mode": "reschedule_booking_control", "reschedule_booking_id": "b1"},
        )
    )
    unavailable = reschedule._Callback("rsch:confirm:sess_rsch_1", user_id=1001)
    asyncio.run(reschedule._handler(router, "reschedule_confirm")(unavailable))
    assert all(show_alert is False for _, show_alert in unavailable.answered)
    assert "slot is no longer available" in reschedule._last_callback_text(unavailable).lower()

    flow2 = reschedule._BookingFlowStub()
    flow2.complete_patient_reschedule_outcome = ConflictOutcome(kind="conflict", reason="already booked")
    router2, runtime2, _ = reschedule._build_router(booking_flow=flow2)
    asyncio.run(
        runtime2.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_rsch_1", "booking_mode": "reschedule_booking_control", "reschedule_booking_id": "b1"},
        )
    )
    conflict = reschedule._Callback("rsch:confirm:sess_rsch_1", user_id=1001)
    asyncio.run(reschedule._handler(router2, "reschedule_confirm")(conflict))
    assert all(show_alert is False for _, show_alert in conflict.answered)
    assert "slot is no longer available" in reschedule._last_callback_text(conflict).lower()


def test_p0_03d_no_active_booking_empty_state_has_book_and_home() -> None:
    router, runtime, booking_flow, _, _ = home._build_router(with_recommendations=False, with_care=False)
    booking_flow.known_patient_result_kind = "no_match"
    message = home._Message(text="/my_booking", user_id=1001)

    asyncio.run(home._handler(router, "my_booking_entry")(message))

    text, keyboard = message.answers[-1]
    assert "No active booking" in text
    assert [button.callback_data for row in keyboard.inline_keyboard for button in row] == ["phome:book", "phome:home"]
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "existing_booking_control"
