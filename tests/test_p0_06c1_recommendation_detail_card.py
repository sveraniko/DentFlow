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


def _open_detail(*, locale: str = "en", status: str = "issued", repo=None):
    router, _, _, recommendation_service, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale=locale,
        recommendation_repository=repo,
    )
    assert recommendation_service is not None
    recommendation = next(row for row in recommendation_service.rows if row.recommendation_id == "rec_latest")
    recommendation.status = status
    callback = home._Callback(data="prec:open:rec_latest", user_id=1001, message_id=700)
    asyncio.run(home._handler(router, "recommendation_open_callback", kind="callback")(callback))
    text, markup = home._latest_callback_panel(callback)
    return recommendation_service, callback, text, markup


def test_p0_06c1_detail_card_readable_en_and_ru_without_internal_leaks() -> None:
    _, _, text_en, _ = _open_detail(locale="en", status="issued")
    assert "💬 Doctor recommendation" in text_en
    assert "👁 Viewed" in text_en
    assert "🧾 Topic:" in text_en and "🏷 Type:" in text_en and "📌 Status:" in text_en
    assert "Latest body" in text_en

    _, _, text_ru, _ = _open_detail(locale="ru", status="issued")
    assert "💬 Рекомендация врача" in text_ru
    assert "👁 Просмотрена" in text_ru
    assert "🧾 Тема:" in text_ru and "🏷 Тип:" in text_ru and "📌 Статус:" in text_ru

    forbidden = ("recommendation_id", "patient_id", "booking_id", "doctor_id", "telegram", "source_channel", "Actions:", "Channel:")
    for token in forbidden:
        assert token not in text_en
        assert token not in text_ru
    for raw_status in ("issued", "viewed", "acknowledged", "accepted", "declined"):
        assert f"📌 Status: {raw_status}" not in text_en


def test_p0_06c1_status_aware_actions_for_issued_and_viewed_show_ack_accept_decline_products() -> None:
    _, _, _, markup_issued = _open_detail(locale="en", status="issued")
    buttons_issued = _button_map(markup_issued)
    assert buttons_issued["✅ Confirm reading"] == "prec:act:ack:rec_latest"
    assert buttons_issued["👍 Accept"] == "prec:act:accept:rec_latest"
    assert buttons_issued["👎 Decline"] == "prec:act:decline:rec_latest"
    assert buttons_issued["🪥 Open recommended products"] == "prec:products:rec_latest"
    assert buttons_issued["⬅️ Back to recommendations"] == "phome:recommendations"
    assert buttons_issued["🏠 Main menu"] == "phome:home"

    _, _, _, markup_viewed = _open_detail(locale="en", status="viewed")
    buttons_viewed = _button_map(markup_viewed)
    assert "✅ Confirm reading" in buttons_viewed
    assert "👍 Accept" in buttons_viewed
    assert "👎 Decline" in buttons_viewed


def test_p0_06c1_status_aware_actions_for_acknowledged_hide_ack_keep_accept_decline() -> None:
    _, _, _, markup = _open_detail(locale="en", status="acknowledged")
    buttons = _button_map(markup)
    assert "✅ Confirm reading" not in buttons
    assert "👍 Accept" in buttons and "👎 Decline" in buttons
    assert "🪥 Open recommended products" in buttons
    assert "⬅️ Back to recommendations" in buttons and "🏠 Main menu" in buttons


def test_p0_06c1_terminal_statuses_hide_mutation_buttons_and_hide_products_for_withdrawn_expired() -> None:
    for status in ("accepted", "declined", "withdrawn", "expired"):
        _, _, _, markup = _open_detail(locale="en", status=status)
        buttons = _button_map(markup)
        assert "✅ Confirm reading" not in buttons
        assert "👍 Accept" not in buttons
        assert "👎 Decline" not in buttons
        assert "⬅️ Back to recommendations" in buttons and "🏠 Main menu" in buttons
        if status in {"withdrawn", "expired"}:
            assert "🪥 Open recommended products" not in buttons


def test_p0_06c1_draft_and_prepared_hide_mutation_buttons_keep_nav() -> None:
    for status in ("draft", "prepared"):
        _, _, _, markup = _open_detail(locale="en", status=status)
        buttons = _button_map(markup)
        assert "✅ Confirm reading" not in buttons
        assert "👍 Accept" not in buttons
        assert "👎 Decline" not in buttons
        assert "⬅️ Back to recommendations" in buttons
        assert "🏠 Main menu" in buttons


def test_p0_06c1_products_handoff_still_works_from_detail() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None

    async def _resolve_content(**kwargs):  # noqa: ANN003
        _ = kwargs
        return type("Content", (), {"title": "Post-cleaning soft toothbrush", "short_label": "AF-BRUSH"})()

    care_service.resolve_product_content = _resolve_content  # type: ignore[method-assign]
    detail = home._Callback(data="prec:open:rec_latest", user_id=1001, message_id=710)
    asyncio.run(home._handler(router, "recommendation_open_callback", kind="callback")(detail))
    _, markup = home._latest_callback_panel(detail)
    buttons = _button_map(markup)
    assert buttons["🪥 Open recommended products"] == "prec:products:rec_latest"

    products = home._Callback(data="prec:products:rec_latest", user_id=1001, message_id=711)
    asyncio.run(home._handler(router, "recommendation_products_callback", kind="callback")(products))
    text, _ = home._latest_callback_panel(products)
    assert "Recommended care products" in text


def test_p0_06c1_prec_open_unresolved_patient_renders_inline_resolution_panel_no_double_answer() -> None:
    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    callback = home._Callback(data="prec:open:rec_latest", user_id=1001)
    asyncio.run(home._handler(router, "recommendation_open_callback", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "could not safely resolve your patient profile" in text.lower()
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"
    assert len(callback.answer_payloads) <= 1


def test_p0_06c1_prec_open_not_found_not_owned_renders_inline_recovery_panel_no_double_answer() -> None:
    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_OtherPatientRepo(),
    )
    callback = home._Callback(data="prec:open:rec_latest", user_id=1001)
    asyncio.run(home._handler(router, "recommendation_open_callback", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "Recommendation not found" in text
    assert buttons["💬 Recommendations"] == "phome:recommendations"
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"
    assert len(callback.answer_payloads) <= 1


def test_p0_06c1_mark_viewed_on_open_and_viewed_badge_is_rendered() -> None:
    recommendation_service, callback, text, _ = _open_detail(locale="en", status="issued")
    assert recommendation_service.mark_viewed_calls == ["rec_latest"]
    assert "👁 Viewed" in text
    assert len(callback.answer_payloads) <= 1
