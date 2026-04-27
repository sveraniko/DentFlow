from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import test_patient_home_surface_pat_a1_2 as home
from app.interfaces.bots.patient.router import RECOMMENDATION_LIST_PAGE_SIZE


def _button_map(markup) -> dict[str, str]:
    return {button.text: button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def _button_texts(markup) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


def _seed_row(*, recommendation_id: str, status: str, title: str, recommendation_type: str, stamp: datetime) -> SimpleNamespace:
    return SimpleNamespace(
        recommendation_id=recommendation_id,
        patient_id="pat_1",
        recommendation_type=recommendation_type,
        status=status,
        title=title,
        body_text=f"Body for {title}",
        rationale_text=None,
        clinic_id="clinic_main",
        booking_id=None,
        issued_at=stamp - timedelta(hours=2),
        created_at=stamp - timedelta(hours=4),
        updated_at=stamp,
    )


def test_p0_06c3_default_list_prefers_active_and_hides_history_rows() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None
    now = datetime(2026, 4, 22, 11, 0, tzinfo=timezone.utc)
    recommendation_service.rows = [
        _seed_row(recommendation_id="rec_issued", status="issued", title="Issued row", recommendation_type="follow_up", stamp=now),
        _seed_row(recommendation_id="rec_viewed", status="viewed", title="Viewed row", recommendation_type="aftercare", stamp=now - timedelta(minutes=10)),
        _seed_row(recommendation_id="rec_ack", status="acknowledged", title="Ack row", recommendation_type="monitoring", stamp=now - timedelta(minutes=20)),
        _seed_row(recommendation_id="rec_acc", status="accepted", title="Accepted history", recommendation_type="aftercare", stamp=now - timedelta(days=1)),
        _seed_row(recommendation_id="rec_dec", status="declined", title="Declined history", recommendation_type="next_step", stamp=now - timedelta(days=2)),
    ]
    callback = home._Callback(data="phome:recommendations", user_id=1001, message_id=900)
    asyncio.run(home._handler(router, "patient_home_recommendations", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "💬 Doctor recommendations" in text
    assert "Active: 3" in text and "History: 2" in text
    assert "Section: 🟢 Active" in text
    assert "Issued row" in text and "Viewed row" in text and "Ack row" in text
    assert "Accepted history" not in text and "Declined history" not in text
    assert any("🟢 Active" in key for key in buttons)
    assert any("📚 History" in key for key in buttons)
    assert any("📋 All" in key for key in buttons)
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"
    assert "recommendation_id" not in text and "patient_id" not in text and "booking_id" not in text and "doctor_id" not in text
    assert "source_channel" not in text and "telegram" not in text and "Actions:" not in text and "Channel:" not in text and "None" not in text


def test_p0_06c3_default_list_falls_back_to_history_when_no_active() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=False, locale="en")
    assert recommendation_service is not None
    now = datetime(2026, 4, 22, 11, 0, tzinfo=timezone.utc)
    recommendation_service.rows = [
        _seed_row(recommendation_id="rec_acc", status="accepted", title="Accepted only", recommendation_type="aftercare", stamp=now),
        _seed_row(recommendation_id="rec_dec", status="declined", title="Declined only", recommendation_type="follow_up", stamp=now - timedelta(hours=2)),
    ]

    callback = home._Callback(data="phome:recommendations", user_id=1001, message_id=901)
    asyncio.run(home._handler(router, "patient_home_recommendations", kind="callback")(callback))
    text, _ = home._latest_callback_panel(callback)
    assert "Section: 📚 History" in text
    assert "Accepted only" in text and "Declined only" in text


def test_p0_06c3_all_filter_shows_mixed_statuses_sorted_desc() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=False, locale="en")
    assert recommendation_service is not None
    now = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
    recommendation_service.rows = [
        _seed_row(recommendation_id="rec_old", status="accepted", title="Third", recommendation_type="aftercare", stamp=now - timedelta(days=3)),
        _seed_row(recommendation_id="rec_new", status="issued", title="First", recommendation_type="follow_up", stamp=now),
        _seed_row(recommendation_id="rec_mid", status="prepared", title="Second", recommendation_type="general_guidance", stamp=now - timedelta(days=1)),
    ]
    callback = home._Callback(data="prec:list:all:0", user_id=1001, message_id=902)
    asyncio.run(home._handler(router, "recommendation_list_callback", kind="callback")(callback))
    text, _ = home._latest_callback_panel(callback)
    assert "First" in text and "Second" in text and "Third" in text
    assert text.index("First") < text.index("Second") < text.index("Third")


def test_p0_06c3_history_filter_shows_only_terminal_rows_and_nav() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None
    now = datetime(2026, 4, 22, 11, 0, tzinfo=timezone.utc)
    recommendation_service.rows = [
        _seed_row(recommendation_id="rec_live", status="issued", title="Live", recommendation_type="aftercare", stamp=now),
        _seed_row(recommendation_id="rec_hist", status="withdrawn", title="History", recommendation_type="monitoring", stamp=now - timedelta(days=1)),
    ]
    callback = home._Callback(data="prec:list:history:0", user_id=1001, message_id=903)
    asyncio.run(home._handler(router, "recommendation_list_callback", kind="callback")(callback))
    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "Section: 📚 History" in text
    assert "History" in text and "Live" not in text
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06c3_filter_empty_states_for_active_and_history() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None
    now = datetime(2026, 4, 22, 11, 0, tzinfo=timezone.utc)
    recommendation_service.rows = [_seed_row(recommendation_id="rec_hist", status="accepted", title="History", recommendation_type="aftercare", stamp=now)]

    callback_active = home._Callback(data="prec:list:active:0", user_id=1001, message_id=904)
    asyncio.run(home._handler(router, "recommendation_list_callback", kind="callback")(callback_active))
    active_text, active_markup = home._latest_callback_panel(callback_active)
    assert "There are no active recommendations in this section yet." in active_text
    assert "📅 My booking" in _button_texts(active_markup) and "🏠 Main menu" in _button_texts(active_markup)

    recommendation_service.rows = [_seed_row(recommendation_id="rec_live", status="issued", title="Active", recommendation_type="aftercare", stamp=now)]
    callback_history = home._Callback(data="prec:list:history:0", user_id=1001, message_id=905)
    asyncio.run(home._handler(router, "recommendation_list_callback", kind="callback")(callback_history))
    history_text, history_markup = home._latest_callback_panel(callback_history)
    assert "Recommendation history is empty so far." in history_text
    assert "📅 My booking" in _button_texts(history_markup) and "🏠 Main menu" in _button_texts(history_markup)


def test_p0_06c3_pagination_open_buttons_and_page_clamp() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None
    now = datetime(2026, 4, 22, 11, 0, tzinfo=timezone.utc)
    recommendation_service.rows = [
        _seed_row(
            recommendation_id=f"rec_{idx}",
            status="issued",
            title=f"Row {idx}",
            recommendation_type="aftercare",
            stamp=now - timedelta(minutes=idx),
        )
        for idx in range(RECOMMENDATION_LIST_PAGE_SIZE + 2)
    ]

    callback0 = home._Callback(data="prec:list:active:0", user_id=1001, message_id=906)
    asyncio.run(home._handler(router, "recommendation_list_callback", kind="callback")(callback0))
    text0, markup0 = home._latest_callback_panel(callback0)
    buttons0 = _button_map(markup0)
    assert "Row 0" in text0 and f"Row {RECOMMENDATION_LIST_PAGE_SIZE}" not in text0
    assert "Next ➡️" in buttons0 and "⬅️ Prev" not in buttons0
    for idx in range(1, RECOMMENDATION_LIST_PAGE_SIZE + 1):
        assert f"Open {idx}" in _button_texts(markup0)
    assert "rec_" not in " ".join(_button_texts(markup0))

    callback1 = home._Callback(data=buttons0["Next ➡️"], user_id=1001, message_id=907)
    asyncio.run(home._handler(router, "recommendation_list_callback", kind="callback")(callback1))
    text1, markup1 = home._latest_callback_panel(callback1)
    buttons1 = _button_map(markup1)
    assert "Row 0" not in text1 and f"Row {RECOMMENDATION_LIST_PAGE_SIZE}" in text1
    assert "⬅️ Prev" in buttons1

    callback_clamp = home._Callback(data="prec:list:active:99", user_id=1001, message_id=908)
    asyncio.run(home._handler(router, "recommendation_list_callback", kind="callback")(callback_clamp))
    clamp_text, _ = home._latest_callback_panel(callback_clamp)
    assert "Page: 2/2" in clamp_text


def test_p0_06c3_open_button_still_routes_to_detail_card() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None
    now = datetime(2026, 4, 22, 11, 0, tzinfo=timezone.utc)
    recommendation_service.rows = [_seed_row(recommendation_id="rec_open", status="issued", title="Openable", recommendation_type="aftercare", stamp=now)]

    callback = home._Callback(data="prec:list:active:0", user_id=1001, message_id=909)
    asyncio.run(home._handler(router, "recommendation_list_callback", kind="callback")(callback))
    _, markup = home._latest_callback_panel(callback)
    open_callback = next(button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data == "prec:open:rec_open")

    open_event = home._Callback(data=open_callback, user_id=1001, message_id=910)
    asyncio.run(home._handler(router, "recommendation_open_callback", kind="callback")(open_event))
    detail_text, _ = home._latest_callback_panel(open_event)
    assert "💬 Doctor recommendation" in detail_text
    assert "Openable" in detail_text


def test_p0_06c3_malformed_list_callback_uses_safe_alert_and_no_double_answer() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    malformed = home._Callback(data="prec:list:broken", user_id=1001, message_id=911)
    asyncio.run(home._handler(router, "recommendation_list_callback", kind="callback")(malformed))
    assert malformed.answers
    assert "no longer available" in malformed.answers[-1]

    valid = home._Callback(data="prec:list:history:0", user_id=1001, message_id=912)
    asyncio.run(home._handler(router, "recommendation_list_callback", kind="callback")(valid))
    assert len(valid.answer_payloads) <= 1

    home_entry = home._Callback(data="phome:recommendations", user_id=1001, message_id=913)
    asyncio.run(home._handler(router, "patient_home_recommendations", kind="callback")(home_entry))
    assert len(home_entry.answer_payloads) <= 1


def test_p0_06c3_recommendations_command_uses_polished_list() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    msg = home._Message(text="/recommendations", user_id=1001)
    asyncio.run(home._handler(router, "recommendations_list")(msg))

    text, markup = msg.answers[-1]
    assert "💬 Doctor recommendations" in text
    assert "Latest recommendation" not in text and "Open latest recommendation" not in " ".join(_button_texts(markup))
    assert "UTC" not in text and "MSK" not in text and "2026-04-" not in text
