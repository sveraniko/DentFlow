from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import test_patient_home_surface_pat_a1_2 as home
from app.interfaces.bots.patient.router import RECOMMENDATION_LIST_PAGE_SIZE


FORBIDDEN_TEXT_TOKENS = (
    "Actions:",
    "Channel:",
    "Канал:",
    "telegram",
    "source_channel",
    "recommendation_id",
    "patient_id",
    "booking_id",
    "doctor_id",
    "None",
    "UTC",
    "MSK",
    "%Z",
    "2026-04-",
)

ALLOWED_CALLBACK_PREFIXES = (
    "phome:home",
    "phome:my_booking",
    "phome:recommendations",
    "phome:care",
    "prec:list:",
    "prec:open:",
    "prec:act:",
    "prec:products:",
    "care:",
    "careo:",
    "rec:",
    "book:",
    "rsch:",
    "c2|",  # runtime card callback used by product picker
)


class _UnresolvedRepo:
    async def find_patient_id_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> str | None:
        _ = clinic_id, telegram_user_id
        return None


class _OtherPatientRepo:
    async def find_patient_id_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> str:
        _ = clinic_id, telegram_user_id
        return "pat_other"


def _button_map(markup) -> dict[str, str]:
    return {button.text: button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def _button_callback_data(markup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]


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


def _assert_no_leakage(text: str) -> None:
    for token in FORBIDDEN_TEXT_TOKENS:
        assert token not in text


def _assert_callbacks_allowed(markup) -> None:
    for callback_data in _button_callback_data(markup):
        assert any(
            callback_data == prefix or callback_data.startswith(prefix) for prefix in ALLOWED_CALLBACK_PREFIXES
        ), f"unexpected callback prefix: {callback_data}"


def test_p0_06c4_entry_smoke_states_and_recovery() -> None:
    router_unavailable, _, _, _, _ = home._build_router(with_recommendations=False, with_care=False, locale="en")
    unavailable = home._Callback(data="phome:recommendations", user_id=1001, message_id=1000)
    asyncio.run(home._handler(router_unavailable, "patient_home_recommendations", kind="callback")(unavailable))
    text_u, markup_u = home._latest_callback_panel(unavailable)
    assert "Recommendations unavailable" in text_u
    assert "This section is currently unavailable." not in text_u
    assert _button_map(markup_u) == {"📅 My booking": "phome:my_booking", "🏠 Main menu": "phome:home"}

    router_unresolved, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    unresolved = home._Callback(data="phome:recommendations", user_id=1001, message_id=1001)
    asyncio.run(home._handler(router_unresolved, "patient_home_recommendations", kind="callback")(unresolved))
    text_r, markup_r = home._latest_callback_panel(unresolved)
    assert "could not safely resolve your patient profile" in text_r.lower()
    assert "📅 My booking" in _button_map(markup_r)
    assert "🏠 Main menu" in _button_map(markup_r)

    router_empty, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None
    recommendation_service.rows = []
    empty = home._Callback(data="phome:recommendations", user_id=1001, message_id=1002)
    asyncio.run(home._handler(router_empty, "patient_home_recommendations", kind="callback")(empty))
    text_e, markup_e = home._latest_callback_panel(empty)
    assert "No recommendations yet" in text_e
    assert "after your visit" in text_e
    assert "unavailable" not in text_e.lower()
    assert "📅 My booking" in _button_map(markup_e)
    assert "🏠 Main menu" in _button_map(markup_e)


def test_p0_06c4_list_filters_and_leakage_smoke() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None
    now = datetime(2026, 4, 22, 11, 0, tzinfo=timezone.utc)
    recommendation_service.rows = [
        _seed_row(recommendation_id="rec_issued", status="issued", title="Issued row", recommendation_type="follow_up", stamp=now),
        _seed_row(recommendation_id="rec_viewed", status="viewed", title="Viewed row", recommendation_type="aftercare", stamp=now - timedelta(minutes=3)),
        _seed_row(recommendation_id="rec_ack", status="acknowledged", title="Ack row", recommendation_type="monitoring", stamp=now - timedelta(minutes=6)),
        _seed_row(recommendation_id="rec_terminal", status="accepted", title="History row", recommendation_type="aftercare", stamp=now - timedelta(days=1)),
        _seed_row(recommendation_id="rec_draft", status="draft", title="Draft row", recommendation_type="general_guidance", stamp=now - timedelta(days=2)),
    ]

    active_default = home._Callback(data="phome:recommendations", user_id=1001, message_id=1003)
    asyncio.run(home._handler(router, "patient_home_recommendations", kind="callback")(active_default))
    active_text, active_markup = home._latest_callback_panel(active_default)
    buttons = _button_map(active_markup)
    assert "💬 Doctor recommendations" in active_text
    assert "Section: 🟢 Active" in active_text
    assert "Issued row" in active_text and "Viewed row" in active_text and "Ack row" in active_text
    assert "History row" not in active_text
    assert any("🟢 Active" in key for key in buttons)
    assert any("📚 History" in key for key in buttons)
    assert any("📋 All" in key for key in buttons)
    _assert_no_leakage(active_text)

    history = home._Callback(data="prec:list:history:0", user_id=1001, message_id=1004)
    asyncio.run(home._handler(router, "recommendation_list_callback", kind="callback")(history))
    history_text, _ = home._latest_callback_panel(history)
    assert "Section: 📚 History" in history_text
    assert "History row" in history_text

    all_rows = home._Callback(data="prec:list:all:0", user_id=1001, message_id=1005)
    asyncio.run(home._handler(router, "recommendation_list_callback", kind="callback")(all_rows))
    all_text, _ = home._latest_callback_panel(all_rows)
    assert "Issued row" in all_text and "History row" in all_text and "Draft row" in all_text

    recommendation_service.rows = [_seed_row(recommendation_id="rec_only_hist", status="declined", title="Only history", recommendation_type="aftercare", stamp=now)]
    history_default = home._Callback(data="phome:recommendations", user_id=1001, message_id=1006)
    asyncio.run(home._handler(router, "patient_home_recommendations", kind="callback")(history_default))
    history_default_text, _ = home._latest_callback_panel(history_default)
    assert "Section: 📚 History" in history_default_text


def test_p0_06c4_list_pagination_and_malformed_smoke() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None
    now = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
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

    assert RECOMMENDATION_LIST_PAGE_SIZE == 5

    page0 = home._Callback(data="prec:list:active:0", user_id=1001, message_id=1007)
    asyncio.run(home._handler(router, "recommendation_list_callback", kind="callback")(page0))
    text0, markup0 = home._latest_callback_panel(page0)
    assert "Row 0" in text0 and "Row 5" not in text0
    buttons0 = _button_map(markup0)
    assert "Next ➡️" in buttons0 and "⬅️ Prev" not in buttons0

    page1 = home._Callback(data=buttons0["Next ➡️"], user_id=1001, message_id=1008)
    asyncio.run(home._handler(router, "recommendation_list_callback", kind="callback")(page1))
    text1, markup1 = home._latest_callback_panel(page1)
    assert "Row 0" not in text1 and "Row 5" in text1
    assert "⬅️ Prev" in _button_map(markup1)

    clamped = home._Callback(data="prec:list:active:99", user_id=1001, message_id=1009)
    asyncio.run(home._handler(router, "recommendation_list_callback", kind="callback")(clamped))
    text_clamped, _ = home._latest_callback_panel(clamped)
    assert "Page: 2/2" in text_clamped

    malformed = home._Callback(data="prec:list:bad", user_id=1001, message_id=1010)
    asyncio.run(home._handler(router, "recommendation_list_callback", kind="callback")(malformed))
    assert malformed.answers
    assert "no longer available" in malformed.answers[-1]


def test_p0_06c4_detail_open_keyboard_and_action_smoke() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None

    recommendation = next(row for row in recommendation_service.rows if row.recommendation_id == "rec_latest")
    recommendation.status = "issued"

    opened = home._Callback(data="prec:open:rec_latest", user_id=1001, message_id=1011)
    asyncio.run(home._handler(router, "recommendation_open_callback", kind="callback")(opened))
    open_text, open_markup = home._latest_callback_panel(opened)
    open_buttons = _button_map(open_markup)
    assert "💬 Doctor recommendation" in open_text
    assert "🏷 Type:" in open_text and "📌 Status:" in open_text
    assert "👁 Viewed" in open_text
    assert open_buttons["✅ Confirm reading"] == "prec:act:ack:rec_latest"
    assert open_buttons["👍 Accept"] == "prec:act:accept:rec_latest"
    assert open_buttons["👎 Decline"] == "prec:act:decline:rec_latest"
    assert open_buttons["⬅️ Back to recommendations"] == "phome:recommendations"
    assert open_buttons["🏠 Main menu"] == "phome:home"
    assert len(opened.answer_payloads) <= 1

    recommendation.status = "acknowledged"
    acked = home._Callback(data="prec:open:rec_latest", user_id=1001, message_id=1012)
    asyncio.run(home._handler(router, "recommendation_open_callback", kind="callback")(acked))
    ack_buttons = _button_map(home._latest_callback_panel(acked)[1])
    assert "✅ Confirm reading" not in ack_buttons
    assert "👍 Accept" in ack_buttons and "👎 Decline" in ack_buttons

    for terminal in ("accepted", "declined", "withdrawn", "expired", "draft", "prepared"):
        recommendation.status = terminal
        callback = home._Callback(data="prec:open:rec_latest", user_id=1001, message_id=1013)
        asyncio.run(home._handler(router, "recommendation_open_callback", kind="callback")(callback))
        buttons = _button_map(home._latest_callback_panel(callback)[1])
        assert "✅ Confirm reading" not in buttons
        assert "👍 Accept" not in buttons
        assert "👎 Decline" not in buttons
        assert "⬅️ Back to recommendations" in buttons
        assert "🏠 Main menu" in buttons


def test_p0_06c4_open_and_action_recovery_paths_are_inline_not_popup_only() -> None:
    router_unresolved, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    unresolved_open = home._Callback(data="prec:open:rec_latest", user_id=1001, message_id=1014)
    asyncio.run(home._handler(router_unresolved, "recommendation_open_callback", kind="callback")(unresolved_open))
    text_open, _ = home._latest_callback_panel(unresolved_open)
    assert "could not safely resolve your patient profile" in text_open.lower()

    unresolved_act = home._Callback(data="prec:act:ack:rec_latest", user_id=1001, message_id=1015)
    asyncio.run(home._handler(router_unresolved, "recommendation_action_callback", kind="callback")(unresolved_act))
    text_act, _ = home._latest_callback_panel(unresolved_act)
    assert "could not safely resolve your patient profile" in text_act.lower()

    router_other, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_OtherPatientRepo(),
    )
    not_found = home._Callback(data="prec:open:rec_latest", user_id=1001, message_id=1016)
    asyncio.run(home._handler(router_other, "recommendation_open_callback", kind="callback")(not_found))
    assert "Recommendation not found" in home._latest_callback_panel(not_found)[0]


def test_p0_06c4_action_callbacks_success_and_invalid_state_smoke() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None

    recommendation = next(row for row in recommendation_service.rows if row.recommendation_id == "rec_latest")
    recommendation.status = "viewed"

    ack = home._Callback(data="prec:act:ack:rec_latest", user_id=1001, message_id=1017)
    asyncio.run(home._handler(router, "recommendation_action_callback", kind="callback")(ack))
    ack_text, _ = home._latest_callback_panel(ack)
    assert "✅ Action saved." in ack_text and "Current status: Acknowledged" in ack_text
    assert len(ack.answer_payloads) <= 1

    recommendation.status = "viewed"
    accept = home._Callback(data="prec:act:accept:rec_latest", user_id=1001, message_id=1018)
    asyncio.run(home._handler(router, "recommendation_action_callback", kind="callback")(accept))
    accept_text, accept_markup = home._latest_callback_panel(accept)
    accept_buttons = _button_map(accept_markup)
    assert "✅ Action saved." in accept_text and "Current status: Accepted" in accept_text
    assert "✅ Confirm reading" not in accept_buttons and "👍 Accept" not in accept_buttons and "👎 Decline" not in accept_buttons

    recommendation.status = "viewed"
    decline = home._Callback(data="prec:act:decline:rec_latest", user_id=1001, message_id=1019)
    asyncio.run(home._handler(router, "recommendation_action_callback", kind="callback")(decline))
    decline_text, _ = home._latest_callback_panel(decline)
    assert "✅ Action saved." in decline_text and "Current status: Declined" in decline_text

    async def _raise_value_error(*, recommendation_id: str):
        _ = recommendation_id
        raise ValueError("invalid state")

    recommendation_service.acknowledge = _raise_value_error  # type: ignore[method-assign]
    invalid_state = home._Callback(data="prec:act:ack:rec_latest", user_id=1001, message_id=1020)
    asyncio.run(home._handler(router, "recommendation_action_callback", kind="callback")(invalid_state))
    invalid_text, _ = home._latest_callback_panel(invalid_state)
    assert "⚠️ Action unavailable." in invalid_text
    assert "Please review the current recommendation card." in invalid_text

    unknown = home._Callback(data="prec:act:weird:rec_latest", user_id=1001, message_id=1021)
    asyncio.run(home._handler(router, "recommendation_action_callback", kind="callback")(unknown))
    assert unknown.answers
    assert "no longer available" in unknown.answers[-1]


def test_p0_06c4_products_handoff_and_recovery_smoke() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None

    detail = home._Callback(data="prec:open:rec_latest", user_id=1001, message_id=1022)
    asyncio.run(home._handler(router, "recommendation_open_callback", kind="callback")(detail))
    _, detail_markup = home._latest_callback_panel(detail)
    assert _button_map(detail_markup)["🪥 Open recommended products"] == "prec:products:rec_latest"

    async def _resolve_content(**kwargs):  # noqa: ANN003
        _ = kwargs
        return SimpleNamespace(title="Post-cleaning soft toothbrush", short_label="AF-BRUSH", description="", usage_hint="", media_refs=())

    care_service.resolve_product_content = _resolve_content  # type: ignore[method-assign]

    success = home._Callback(data="prec:products:rec_latest", user_id=1001, message_id=1023)
    asyncio.run(home._handler(router, "recommendation_products_callback", kind="callback")(success))
    success_text, success_markup = home._latest_callback_panel(success)
    assert "Recommended care products" in success_text
    assert any(callback.startswith("c2|") for callback in _button_callback_data(success_markup))

    async def _manual_invalid(**kwargs):  # noqa: ANN003
        _ = kwargs
        return SimpleNamespace(status="manual_target_invalid", products=[])

    care_service.resolve_recommendation_target_result = _manual_invalid  # type: ignore[method-assign]
    manual_invalid = home._Callback(data="prec:products:rec_latest", user_id=1001, message_id=1024)
    asyncio.run(home._handler(router, "recommendation_products_callback", kind="callback")(manual_invalid))
    manual_text, manual_markup = home._latest_callback_panel(manual_invalid)
    assert "Recommended product unavailable" in manual_text
    manual_buttons = _button_map(manual_markup)
    assert manual_buttons["⬅️ Back to recommendation"] == "prec:open:rec_latest"
    assert manual_buttons["🪥 Open care catalog"] == "phome:care"
    assert manual_buttons["🏠 Main menu"] == "phome:home"

    async def _empty(**kwargs):  # noqa: ANN003
        _ = kwargs
        return SimpleNamespace(status="resolved", products=[])

    care_service.resolve_recommendation_target_result = _empty  # type: ignore[method-assign]
    empty = home._Callback(data="prec:products:rec_latest", user_id=1001, message_id=1025)
    asyncio.run(home._handler(router, "recommendation_products_callback", kind="callback")(empty))
    assert "No products are linked to this recommendation yet" in home._latest_callback_panel(empty)[0]

    router_nf, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_OtherPatientRepo(),
    )
    not_found = home._Callback(data="prec:products:rec_latest", user_id=1001, message_id=1026)
    asyncio.run(home._handler(router_nf, "recommendation_products_callback", kind="callback")(not_found))
    assert "Recommendation not found" in home._latest_callback_panel(not_found)[0]

    router_unresolved, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    unresolved = home._Callback(data="prec:products:rec_latest", user_id=1001, message_id=1027)
    asyncio.run(home._handler(router_unresolved, "recommendation_products_callback", kind="callback")(unresolved))
    assert "could not safely resolve your patient profile" in home._latest_callback_panel(unresolved)[0].lower()


def test_p0_06c4_command_fallback_smoke_integration() -> None:
    router, _, _, recommendation_service, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None and care_service is not None

    open_usage = home._Message(text="/recommendation_open", user_id=1001)
    asyncio.run(home._handler(router, "recommendations_open")(open_usage))
    assert "/recommendation_open <recommendation_id>" in open_usage.answers[-1][0]

    recommendation_service.rows[1].status = "viewed"
    action_ok = home._Message(text="/recommendation_action accept rec_latest", user_id=1001)
    asyncio.run(home._handler(router, "recommendations_action")(action_ok))
    action_panel_text = action_ok.answers[-1][0] if action_ok.answers else action_ok.bot.edits[-1]["text"]
    assert "Status: Accepted" in action_panel_text

    products_usage = home._Message(text="/recommendation_products", user_id=1001)
    asyncio.run(home._handler(router, "recommendation_products")(products_usage))
    assert "Products for recommendation" in products_usage.answers[-1][0]


def test_p0_06c4_callback_namespace_double_answer_and_leakage_guards() -> None:
    router, _, _, recommendation_service, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None and care_service is not None

    async def _resolve_content(**kwargs):  # noqa: ANN003
        _ = kwargs
        return SimpleNamespace(title="Post-cleaning soft toothbrush", short_label="AF-BRUSH", description="", usage_hint="", media_refs=())

    care_service.resolve_product_content = _resolve_content  # type: ignore[method-assign]

    callbacks: list[home._Callback] = []
    for message_id, data, handler in [
        (1028, "phome:recommendations", "patient_home_recommendations"),
        (1029, "prec:list:active:0", "recommendation_list_callback"),
        (1030, "prec:open:rec_latest", "recommendation_open_callback"),
        (1031, "prec:act:ack:rec_latest", "recommendation_action_callback"),
        (1032, "prec:products:rec_latest", "recommendation_products_callback"),
    ]:
        callback = home._Callback(data=data, user_id=1001, message_id=message_id)
        asyncio.run(home._handler(router, handler, kind="callback")(callback))
        callbacks.append(callback)

    for callback in callbacks:
        assert len(callback.answer_payloads) <= 1
        text, markup = home._latest_callback_panel(callback)
        _assert_no_leakage(text)
        _assert_callbacks_allowed(markup)
