from __future__ import annotations

import asyncio

import test_patient_home_surface_pat_a1_2 as home


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


def test_p0_06c2_action_ack_success_inline_notice_and_no_double_answer() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None
    recommendation = next(row for row in recommendation_service.rows if row.recommendation_id == "rec_latest")
    recommendation.status = "viewed"

    callback = home._Callback(data="prec:act:ack:rec_latest", user_id=1001, message_id=801)
    asyncio.run(home._handler(router, "recommendation_action_callback", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "✅ Action saved." in text
    assert "Current status: Acknowledged" in text
    assert "💬 Doctor recommendation" in text
    assert "✅ Confirm reading" not in buttons
    assert "👍 Accept" in buttons and "👎 Decline" in buttons
    assert len(callback.answer_payloads) <= 1


def test_p0_06c2_action_accept_success_inline_notice_terminal_buttons_hidden() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None
    recommendation = next(row for row in recommendation_service.rows if row.recommendation_id == "rec_latest")
    recommendation.status = "viewed"

    callback = home._Callback(data="prec:act:accept:rec_latest", user_id=1001, message_id=802)
    asyncio.run(home._handler(router, "recommendation_action_callback", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "✅ Action saved." in text
    assert "Current status: Accepted" in text
    assert "✅ Confirm reading" not in buttons
    assert "👍 Accept" not in buttons and "👎 Decline" not in buttons
    assert len(callback.answer_payloads) <= 1


def test_p0_06c2_action_decline_success_inline_notice_terminal_buttons_hidden() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None
    recommendation = next(row for row in recommendation_service.rows if row.recommendation_id == "rec_latest")
    recommendation.status = "viewed"

    callback = home._Callback(data="prec:act:decline:rec_latest", user_id=1001, message_id=803)
    asyncio.run(home._handler(router, "recommendation_action_callback", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "✅ Action saved." in text
    assert "Current status: Declined" in text
    assert "✅ Confirm reading" not in buttons
    assert "👍 Accept" not in buttons and "👎 Decline" not in buttons
    assert len(callback.answer_payloads) <= 1


def test_p0_06c2_action_invalid_state_renders_inline_warning_and_current_detail() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None
    recommendation = next(row for row in recommendation_service.rows if row.recommendation_id == "rec_latest")
    recommendation.status = "acknowledged"

    async def _raise_value_error(*, recommendation_id: str):
        _ = recommendation_id
        raise ValueError("invalid state")

    recommendation_service.acknowledge = _raise_value_error  # type: ignore[method-assign]
    callback = home._Callback(data="prec:act:ack:rec_latest", user_id=1001, message_id=804)
    asyncio.run(home._handler(router, "recommendation_action_callback", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "⚠️ Action unavailable." in text
    assert "Please review the current recommendation card." in text
    assert "💬 Doctor recommendation" in text
    assert "✅ Confirm reading" not in buttons
    assert "👍 Accept" in buttons and "👎 Decline" in buttons
    assert len(callback.answer_payloads) <= 1


def test_p0_06c2_action_unresolved_patient_renders_inline_resolution_panel() -> None:
    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    callback = home._Callback(data="prec:act:ack:rec_latest", user_id=1001, message_id=805)
    asyncio.run(home._handler(router, "recommendation_action_callback", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "could not safely resolve your patient profile" in text.lower()
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"
    assert len(callback.answer_payloads) <= 1


def test_p0_06c2_action_not_found_renders_inline_not_found_recovery() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    callback = home._Callback(data="prec:act:ack:rec_missing", user_id=1001, message_id=806)
    asyncio.run(home._handler(router, "recommendation_action_callback", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "Recommendation not found" in text
    assert buttons["💬 Recommendations"] == "phome:recommendations"
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"
    assert len(callback.answer_payloads) <= 1


def test_p0_06c2_action_not_owned_renders_inline_not_found_recovery() -> None:
    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_OtherPatientRepo(),
    )
    callback = home._Callback(data="prec:act:ack:rec_latest", user_id=1001, message_id=807)
    asyncio.run(home._handler(router, "recommendation_action_callback", kind="callback")(callback))

    text, _ = home._latest_callback_panel(callback)
    assert "Recommendation not found" in text
    assert len(callback.answer_payloads) <= 1


def test_p0_06c2_action_unknown_action_uses_unavailable_alert_without_crash() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    callback = home._Callback(data="prec:act:weird:rec_latest", user_id=1001, message_id=808)
    asyncio.run(home._handler(router, "recommendation_action_callback", kind="callback")(callback))

    assert callback.answers
    assert "no longer available" in callback.answers[-1]


def test_p0_06c2_products_not_found_renders_inline_recovery_no_popup() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    callback = home._Callback(data="prec:products:rec_missing", user_id=1001, message_id=809)
    asyncio.run(home._handler(router, "recommendation_products_callback", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "Recommendation not found" in text
    assert buttons["💬 Recommendations"] == "phome:recommendations"
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"
    assert len(callback.answer_payloads) <= 1


def test_p0_06c2_products_success_still_renders_picker() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None

    async def _resolve_content(**kwargs):  # noqa: ANN003
        _ = kwargs
        return type("Content", (), {"title": "Post-cleaning soft toothbrush", "short_label": "AF-BRUSH"})()

    care_service.resolve_product_content = _resolve_content  # type: ignore[method-assign]
    callback = home._Callback(data="prec:products:rec_latest", user_id=1001, message_id=810)
    asyncio.run(home._handler(router, "recommendation_products_callback", kind="callback")(callback))

    text, _ = home._latest_callback_panel(callback)
    assert "Recommended care products" in text
    assert len(callback.answer_payloads) <= 1
