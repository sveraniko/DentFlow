from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import test_patient_home_surface_pat_a1_2 as home

from app.application.booking.telegram_flow import BookingPatientFlowService
from app.application.care_commerce.service import CareCommerceService
from app.application.clinic_reference import ClinicReferenceService
from app.application.recommendation.services import RecommendationService
from app.common.i18n import I18nService
from app.infrastructure.db.booking_repository import DbBookingRepository
from app.infrastructure.db.care_commerce_repository import DbCareCommerceRepository
from app.infrastructure.db.patient_repository import find_patient_by_exact_contact
from app.infrastructure.db.recommendation_repository import DbRecommendationRepository
from app.infrastructure.db.repositories import DbClinicReferenceRepository
from app.interfaces.bots.patient.router import RECOMMENDATION_LIST_PAGE_SIZE, make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore
from app.interfaces.cards.runtime_state import InMemoryRedis
from tests.helpers.seed_demo_db_harness import (
    TEST_DB_DSN_ENV,
    reset_test_db,
    run_seed_demo_bootstrap_for_tests,
    safe_test_db_config,
)


FORBIDDEN_TEXT_TOKENS = (
    "Actions:",
    "Channel:",
    "Канал:",
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
)

ALLOWED_CALLBACK_PREFIXES = (
    "phome:",
    "book:",
    "care:",
    "careo:",
    "prec:",
    "rec:",
    "rsch:",
)
_RUNTIME_CALLBACK_PREFIX = re.compile(r"^c\\d+\\|")


class _NoopOrchestration:
    pass


class _NoopPatientCreator:
    async def create_minimal_patient(self, *, clinic_id: str, display_name: str, phone: str) -> str:
        raise RuntimeError("not used in read smoke")

    async def upsert_telegram_contact(self, *, patient_id: str, telegram_user_id: int) -> None:
        raise RuntimeError("not used in read smoke")


class _NoopReminderActions:
    async def handle_action(self, **kwargs):  # noqa: ANN003
        return SimpleNamespace(kind="invalid")


def _button_map(markup) -> dict[str, str]:
    return {button.text: button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def _collect_callback_data(markup) -> set[str]:
    return {button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def _assert_no_leakage(text: str) -> None:
    for token in FORBIDDEN_TEXT_TOKENS:
        assert token not in text


def _assert_allowed_callback_prefixes(values: set[str]) -> None:
    for value in values:
        if _RUNTIME_CALLBACK_PREFIX.match(value):
            continue
        assert value.startswith(ALLOWED_CALLBACK_PREFIXES), f"unexpected callback namespace: {value}"


def _handler(router, name: str, *, kind: str = "message"):
    handlers = router.message.handlers if kind == "message" else router.callback_query.handlers
    for item in handlers:
        if item.callback.__name__ == name:
            return item.callback
    raise AssertionError(name)


def test_p0_07a_patient_read_surfaces_pre_live_db_backed_smoke() -> None:
    db_config = safe_test_db_config()

    async def _run() -> None:
        assert os.getenv(TEST_DB_DSN_ENV), f"{TEST_DB_DSN_ENV} must be set"
        await reset_test_db(db_config)
        stage_counts = await run_seed_demo_bootstrap_for_tests(db_config)
        assert set(stage_counts) == {"stack1", "stack2", "stack3", "care_catalog", "recommendations_care_orders"}
        assert "google" not in " ".join(stage_counts.keys()).lower()

        reference_repo = await DbClinicReferenceRepository.load(db_config)
        reference_service = ClinicReferenceService(reference_repo)
        booking_repo = DbBookingRepository(db_config)
        booking_flow = BookingPatientFlowService(
            orchestration=_NoopOrchestration(),
            reads=booking_repo,
            reference=reference_service,
            patient_creator=_NoopPatientCreator(),
        )
        care_repo = DbCareCommerceRepository(db_config)
        care_service = CareCommerceService(care_repo)
        recommendation_repo = DbRecommendationRepository(db_config)
        recommendation_service = RecommendationService(recommendation_repo)

        i18n = I18nService(locales_path=Path("locales"), default_locale="ru")
        runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
        codec = CardCallbackCodec(runtime=runtime)
        router = make_router(
            i18n=i18n,
            booking_flow=booking_flow,
            reference=reference_service,
            reminder_actions=_NoopReminderActions(),
            recommendation_service=recommendation_service,
            care_commerce_service=care_service,
            recommendation_repository=recommendation_repo,
            default_locale="ru",
            card_runtime=runtime,
            card_callback_codec=codec,
        )

        callbacks_seen: set[str] = set()

        # 2) patient home read smoke
        start_msg = home._Message(text="/start", user_id=3001)
        await _handler(router, "start")(start_msg)
        start_text, start_markup = start_msg.answers[-1]
        start_buttons = _button_map(start_markup)
        assert set(start_buttons.values()) >= {"phome:book", "phome:my_booking", "phome:recommendations", "phome:care"}
        assert "Добро пожаловать в DentFlow. Выберите действие:" not in start_text
        _assert_no_leakage(start_text)
        callbacks_seen |= _collect_callback_data(start_markup)

        # 3) My Booking read smoke
        sergey = await find_patient_by_exact_contact(db_config, contact_type="telegram", contact_value="3001")
        assert sergey and sergey["patient_id"] == "patient_sergey_ivanov"
        my_booking = home._Callback(data="phome:my_booking", user_id=3001)
        await _handler(router, "patient_home_my_booking", kind="callback")(my_booking)
        booking_text, booking_markup = home._latest_callback_panel(my_booking)
        assert "📅" in booking_text and "👩‍⚕️" in booking_text and "🦷" in booking_text and "📍" in booking_text and "🔔" in booking_text
        assert "🏠" in " ".join(_button_map(booking_markup).keys())
        _assert_no_leakage(booking_text)
        callbacks_seen |= _collect_callback_data(booking_markup)

        # 4) booking picker read smoke
        services = booking_flow.list_services(clinic_id="clinic_main")
        service_codes = {row.code.lower() for row in services}
        assert {"consult", "cleaning", "treatment", "urgent"}.issubset(service_codes)
        doctors = booking_flow.list_doctors(clinic_id="clinic_main")
        doctor_names = {row.display_name for row in doctors}
        assert "Dr. Anna" in doctor_names and "Dr. Boris" in doctor_names
        assert reference_service.resolve_doctor_access_code(clinic_id="clinic_main", code="ANNA-001") is not None
        assert reference_service.resolve_doctor_access_code(clinic_id="clinic_main", code="BORIS-HYG") is not None
        assert reference_service.resolve_doctor_access_code(
            clinic_id="clinic_main", code="IRINA-TREAT", service_id="svc_implant_consult"
        ) is not None

        session = await booking_flow.get_booking_session(booking_session_id="bks_001")
        assert session is not None
        slots = await booking_flow.list_slots_for_session(booking_session_id=session.booking_session_id, limit=30)
        assert len(slots) > RECOMMENDATION_LIST_PAGE_SIZE
        assert all(row.start_at > datetime.now(timezone.utc) for row in slots)

        await runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=3001,
            payload={
                "booking_session_id": "bks_001",
                "booking_mode": "new_booking_flow",
                "quick_booking_prefill": {
                    "service_id": "svc_implant_consult",
                    "doctor_id": "doc_anna",
                    "branch_id": "branch_central",
                },
                "care": {},
            },
        )
        picker_callback = home._Callback(data="qbook:other:bks_001", user_id=3001)
        await _handler(router, "quick_book_other", kind="callback")(picker_callback)
        service_text, service_markup = home._latest_callback_panel(picker_callback)
        assert service_text
        callbacks_seen |= _collect_callback_data(service_markup)

        service_pick = home._Callback(data="book:svc:bks_001:svc_implant_consult", user_id=3001)
        await _handler(router, "select_service", kind="callback")(service_pick)
        doctor_text, doctor_markup = home._latest_callback_panel(service_pick)
        assert "ANNA-001" not in doctor_text
        callbacks_seen |= _collect_callback_data(doctor_markup)

        doctor_any = home._Callback(data="book:doc:bks_001:any", user_id=3001)
        await _handler(router, "select_doctor_preference", kind="callback")(doctor_any)
        slots_callback = doctor_any
        slots_text, slots_markup = home._latest_callback_panel(slots_callback)
        assert "UTC" not in slots_text and "Tue" not in slots_text and "Apr" not in slots_text
        callbacks_seen |= _collect_callback_data(slots_markup)
        assert any("more" in button.text.lower() or "ещё" in button.text.lower() for row in slots_markup.inline_keyboard for button in row)

        # 5) care catalog read smoke
        categories = {item.lower() for item in await care_service.list_catalog_categories(clinic_id="clinic_main")}
        assert {"toothbrush", "toothpaste", "floss", "rinse", "irrigator"}.issubset(categories)
        assert any("remin" in item for item in categories)
        toothbrush = await care_service.list_catalog_products_by_category(clinic_id="clinic_main", category="toothbrush")
        brush = next((row for row in toothbrush if row.sku == "SKU-BRUSH-SOFT"), None)
        assert brush is not None

        care_entry = home._Callback(data="phome:care", user_id=3001)
        await _handler(router, "patient_home_care", kind="callback")(care_entry)
        care_text, care_markup = home._latest_callback_panel(care_entry)
        assert care_text
        callbacks_seen |= _collect_callback_data(care_markup)

        care_category_cb = next((cb for cb in _collect_callback_data(care_markup) if cb.startswith("care:cat:")), None)
        assert care_category_cb is not None
        care_products = home._Callback(data=care_category_cb, user_id=3001)
        await _handler(router, "care_category_pick", kind="callback")(care_products)
        _, care_products_markup = home._latest_callback_panel(care_products)
        product_cb = next((cb for cb in _collect_callback_data(care_products_markup) if cb.startswith("care:product:")), None)
        assert product_cb is not None
        product_open = home._Callback(data=product_cb, user_id=3001)
        await _handler(router, "care_product_pick", kind="callback")(product_open)
        product_text, product_markup = home._latest_callback_panel(product_open)
        assert "SKU-BRUSH-SOFT" in product_text
        assert "📂" in product_text and "💶" in product_text and "📦" in product_text and "📍" in product_text
        _assert_no_leakage(product_text)
        callbacks_seen |= _collect_callback_data(product_markup)

        # 6) care orders read smoke
        care_orders = home._Callback(data="care:orders", user_id=3001)
        await _handler(router, "care_orders_callback", kind="callback")(care_orders)
        orders_text, orders_markup = home._latest_callback_panel(care_orders)
        assert "📦" in orders_text
        callbacks_seen |= _collect_callback_data(orders_markup)
        order_open_cb = next((cb for cb in _collect_callback_data(orders_markup) if cb.startswith("careo:open:")), None)
        assert order_open_cb is not None
        order_open = home._Callback(data=order_open_cb, user_id=3001)
        await _handler(router, "care_order_open_callback", kind="callback")(order_open)
        order_text, order_markup = home._latest_callback_panel(order_open)
        assert "co_sergey_confirmed_brush" not in order_text
        assert "🧾" in order_text and "📍" in order_text
        _assert_no_leakage(order_text)
        callbacks_seen |= _collect_callback_data(order_markup)

        # 7/8) recommendations list + detail
        recommendations = home._Callback(data="phome:recommendations", user_id=3001)
        await _handler(router, "patient_home_recommendations", kind="callback")(recommendations)
        rec_text, rec_markup = home._latest_callback_panel(recommendations)
        assert "active" in rec_text.lower() or "актив" in rec_text.lower()
        assert "history" in rec_text.lower() or "истор" in rec_text.lower()
        callbacks_seen |= _collect_callback_data(rec_markup)
        rec_open_cb = next((cb for cb in _collect_callback_data(rec_markup) if cb.startswith("prec:open:")), None)
        assert rec_open_cb is not None
        rec_open = home._Callback(data=rec_open_cb, user_id=3001)
        await _handler(router, "recommendation_open_callback", kind="callback")(rec_open)
        rec_detail_text, rec_detail_markup = home._latest_callback_panel(rec_open)
        assert "📌" in rec_detail_text and "🏷" in rec_detail_text
        _assert_no_leakage(rec_detail_text)
        callbacks_seen |= _collect_callback_data(rec_detail_markup)

        # 9) recommendation products handoff
        for rec_id, rec_type, sku in (
            ("rec_sergey_hygiene_issued", "hygiene_support", "SKU-BRUSH-SOFT"),
            ("rec_sergey_sensitive_ack", "general_guidance", "SKU-PASTE-SENSITIVE"),
            ("rec_sergey_monitoring_accepted", "monitoring", "SKU-FLOSS-WAXED"),
        ):
            resolution = await care_service.resolve_recommendation_target_result(
                clinic_id="clinic_main",
                recommendation_id=rec_id,
                recommendation_type=rec_type,
            )
            assert any(getattr(row.product, "sku", "") == sku for row in resolution.products)

        manual_invalid = await care_service.resolve_recommendation_target_result(
            clinic_id="clinic_main",
            recommendation_id="rec_sergey_manual_invalid",
            recommendation_type="general_guidance",
        )
        assert manual_invalid.status == "manual_target_invalid"

        rec_products = home._Callback(data="prec:products:rec_sergey_hygiene_issued", user_id=3001)
        await _handler(router, "recommendation_products_callback", kind="callback")(rec_products)
        rec_products_text, rec_products_markup = home._latest_callback_panel(rec_products)
        assert rec_products_text
        callbacks_seen |= _collect_callback_data(rec_products_markup)

        rec_products_invalid = home._Callback(data="prec:products:rec_sergey_manual_invalid", user_id=3001)
        await _handler(router, "recommendation_products_callback", kind="callback")(rec_products_invalid)
        invalid_text, invalid_markup = home._latest_callback_panel(rec_products_invalid)
        assert "unavailable" in invalid_text.lower() or "недоступ" in invalid_text.lower()
        callbacks_seen |= _collect_callback_data(invalid_markup)

        # 10) cross-service readiness matrix
        assert sergey and sergey["patient_id"] == "patient_sergey_ivanov"
        assert await booking_flow.get_booking(booking_id="bkg_sergey_confirmed") is not None
        assert await recommendation_service.list_for_patient(patient_id="patient_sergey_ivanov", include_terminal=True)
        assert await care_service.list_patient_orders(clinic_id="clinic_main", patient_id="patient_sergey_ivanov")

        elena = await find_patient_by_exact_contact(db_config, contact_type="telegram", contact_value="3002")
        assert elena and elena["patient_id"] == "patient_elena_ivanova"
        elena_bookings = await booking_repo.list_bookings_by_patient(patient_id="patient_elena_ivanova")
        assert any(item.status == "reschedule_requested" for item in elena_bookings)
        assert (
            await recommendation_service.list_for_patient(patient_id="patient_elena_ivanova", include_terminal=True)
            or await care_service.list_patient_orders(clinic_id="clinic_main", patient_id="patient_elena_ivanova")
        )

        maria = await find_patient_by_exact_contact(db_config, contact_type="telegram", contact_value="3004")
        assert maria and maria["patient_id"] == "patient_maria_kim"
        assert (
            await recommendation_service.list_for_patient(patient_id="patient_maria_kim", include_terminal=True)
            or await care_service.list_patient_orders(clinic_id="clinic_main", patient_id="patient_maria_kim")
        )

        giorgi = await find_patient_by_exact_contact(db_config, contact_type="phone", contact_value="+995598123456")
        assert giorgi and giorgi["patient_id"] == "patient_giorgi_beridze"
        giorgi_bookings = await booking_repo.list_bookings_by_patient(patient_id="patient_giorgi_beridze")
        assert any(item.status in {"canceled", "completed", "no_show"} for item in giorgi_bookings)

        # 11) no live integration calls
        assert os.getenv("INTEGRATIONS_GOOGLE_CALENDAR_ENABLED", "0") in {"0", "false", "False", ""}

        # 12) callback namespace + leakage guard
        _assert_allowed_callback_prefixes(callbacks_seen)
        for text in [
            start_text,
            booking_text,
            slots_text,
            product_text,
            order_text,
            rec_text,
            rec_detail_text,
            rec_products_text,
            invalid_text,
        ]:
            _assert_no_leakage(text)

    asyncio.run(_run())
