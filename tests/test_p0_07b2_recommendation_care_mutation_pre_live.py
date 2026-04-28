from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from types import SimpleNamespace

import test_patient_home_surface_pat_a1_2 as home

from app.application.booking.orchestration_outcomes import OrchestrationSuccess
from app.application.booking.telegram_flow import BookingPatientFlowService
from app.application.care_commerce.service import CareCommerceService
from app.application.clinic_reference import ClinicReferenceService
from app.application.recommendation.services import RecommendationService
from app.common.i18n import I18nService
from app.domain.booking import BookingSession
from app.infrastructure.db.booking_repository import DbBookingRepository
from app.infrastructure.db.care_commerce_repository import DbCareCommerceRepository
from app.infrastructure.db.patient_repository import find_patient_by_exact_contact
from app.infrastructure.db.recommendation_repository import DbRecommendationRepository
from app.infrastructure.db.repositories import DbClinicReferenceRepository
from app.interfaces.bots.patient.router import make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore
from app.interfaces.cards.runtime_state import InMemoryRedis
from tests.helpers.seed_demo_db_harness import TEST_DB_DSN_ENV, reset_test_db, run_seed_demo_bootstrap_for_tests, safe_test_db_config

FORBIDDEN_TEXT_TOKENS = (
    "Actions:", "Channel:", "Канал:", "source_channel", "booking_mode", "recommendation_id", "care_order_id", "care_product_id",
    "patient_id", "doctor_id", "branch_id", "UTC", "MSK", "%Z", "2026-04-",
)
ALLOWED_CALLBACK_PREFIXES = ("phome:", "book:", "care:", "careo:", "prec:", "rec:", "rsch:")
_RUNTIME_CALLBACK_PREFIX = re.compile(r"^c\d+\|")


class _NoopOrchestration:
    async def start_booking_session(self, *, clinic_id: str, telegram_user_id: int, route_type: str, **kwargs):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        return OrchestrationSuccess(
            kind="success",
            entity=BookingSession(
                booking_session_id="bks_noop_b2",
                clinic_id=clinic_id,
                telegram_user_id=telegram_user_id,
                status="in_progress",
                route_type=route_type,
                expires_at=now + timedelta(hours=1),
                created_at=now,
                updated_at=now,
            ),
        )

    async def attach_resolved_patient_to_session(self, *, booking_session_id: str, patient_id: str):
        return OrchestrationSuccess(kind="success", entity=None)

    async def expire_session(self, *, booking_session_id: str):
        return OrchestrationSuccess(kind="success", entity=None)


class _NoopPatientCreator:
    async def create_minimal_patient(self, *, clinic_id: str, display_name: str, phone: str) -> str:
        raise RuntimeError("not used")

    async def upsert_telegram_contact(self, *, patient_id: str, telegram_user_id: int) -> None:
        raise RuntimeError("not used")


class _NoopReminderActions:
    async def handle_action(self, **kwargs):
        return SimpleNamespace(kind="invalid")


def _handler(router, name: str, *, kind: str = "message"):
    handlers = router.message.handlers if kind == "message" else router.callback_query.handlers
    for item in handlers:
        if item.callback.__name__ == name:
            return item.callback
    raise AssertionError(name)


def _collect_callback_data(markup) -> set[str]:
    if markup is None:
        return set()
    return {button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def _assert_no_leakage(text: str) -> None:
    for token in FORBIDDEN_TEXT_TOKENS:
        assert token not in text


def _assert_allowed_callback_prefixes(values: set[str]) -> None:
    for value in values:
        if _RUNTIME_CALLBACK_PREFIX.match(value):
            continue
        assert value.startswith(ALLOWED_CALLBACK_PREFIXES)


def test_p0_07b2_recommendation_care_mutation_pre_live_db_backed_smoke() -> None:
    db_config = safe_test_db_config()

    async def _run() -> None:
        assert os.getenv(TEST_DB_DSN_ENV), f"{TEST_DB_DSN_ENV} must be set"
        assert os.getenv("INTEGRATIONS_GOOGLE_CALENDAR_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}
        await reset_test_db(db_config)
        stage_counts = await run_seed_demo_bootstrap_for_tests(db_config)
        assert set(stage_counts) == {"stack1", "stack2", "stack3", "care_catalog", "recommendations_care_orders"}

        rec_repo = DbRecommendationRepository(db_config)
        rec_service = RecommendationService(rec_repo)
        care_repo = DbCareCommerceRepository(db_config)
        care_service = CareCommerceService(care_repo)

        rec = await rec_service.get("rec_sergey_hygiene_issued")
        assert rec and rec.status in {"issued", "viewed", "acknowledged"}
        ack = await rec_service.acknowledge(recommendation_id=rec.recommendation_id)
        assert ack and ack.status == "acknowledged" and ack.acknowledged_at is not None
        rec_db = await rec_repo.get("rec_sergey_hygiene_issued")
        assert rec_db and rec_db.status == "acknowledged"
        all_recs = await rec_service.list_for_patient(patient_id="patient_sergey_ivanov", include_terminal=True)
        assert "rec_sergey_hygiene_issued" in {r.recommendation_id for r in all_recs}

        accepted = await rec_service.accept(recommendation_id="rec_sergey_hygiene_issued")
        assert accepted and accepted.status == "accepted" and accepted.accepted_at is not None
        accepted_db = await rec_repo.get("rec_sergey_hygiene_issued")
        assert accepted_db and accepted_db.status == "accepted"

        declined = await rec_service.decline(recommendation_id="rec_elena_post_treatment_viewed")
        assert declined and declined.status == "declined" and declined.declined_at is not None

        expired = await rec_service.get("rec_giorgi_expired")
        assert expired and expired.status == "expired"
        try:
            await rec_service.accept(recommendation_id="rec_giorgi_expired")
            raise AssertionError("expected invalid transition")
        except ValueError:
            pass

        set_res = await care_service.resolve_recommendation_target_result(clinic_id="clinic_main", recommendation_id="rec_sergey_hygiene_issued", recommendation_type=accepted.recommendation_type)
        assert any(p.product.sku == "SKU-BRUSH-SOFT" for p in set_res.products)
        assert any(p.product.sku == "SKU-FLOSS-WAXED" for p in set_res.products)
        assert any(p.product.sku == "SKU-PASTE-SENSITIVE" for p in set_res.products)
        one_res = await care_service.resolve_recommendation_target_result(clinic_id="clinic_main", recommendation_id="rec_sergey_sensitive_ack", recommendation_type="product")
        assert any(p.product.sku == "SKU-PASTE-SENSITIVE" for p in one_res.products)
        direct_res = await care_service.resolve_recommendation_target_result(clinic_id="clinic_main", recommendation_id="rec_sergey_monitoring_accepted", recommendation_type="monitoring")
        assert any(p.product.sku == "SKU-FLOSS-WAXED" for p in direct_res.products)
        invalid_res = await care_service.resolve_recommendation_target_result(clinic_id="clinic_main", recommendation_id="rec_sergey_manual_invalid", recommendation_type="manual")
        assert invalid_res.status == "manual_target_invalid" and invalid_res.manual_target_invalid

        product = await care_repo.get_product_by_code(clinic_id="clinic_main", target_code="SKU-BRUSH-SOFT")
        assert product is not None
        availability = await care_service.get_branch_product_availability(branch_id="branch_central", care_product_id=product.care_product_id)
        assert availability is not None and availability.free_qty > 0

        before_orders = await care_service.list_patient_orders(clinic_id="clinic_main", patient_id="patient_sergey_ivanov")
        order = await care_service.create_order(
            clinic_id="clinic_main", patient_id="patient_sergey_ivanov", payment_mode="pickup", currency_code=product.currency_code,
            pickup_branch_id="branch_central", recommendation_id="rec_sergey_hygiene_issued", booking_id=None, items=[(product, 1)],
        )
        confirmed = await care_service.transition_order(care_order_id=order.care_order_id, to_status="confirmed")
        assert confirmed is not None and confirmed.status == "confirmed"
        reservation = await care_service.create_reservation(care_order_id=order.care_order_id, care_product_id=product.care_product_id, branch_id="branch_central", reserved_qty=1)
        assert reservation.status == "created"
        detail = await care_service.get_order(order.care_order_id)
        assert detail is not None and detail.patient_id == "patient_sergey_ivanov" and detail.total_amount == product.price_amount
        items = await care_repo.list_order_items(order.care_order_id)
        assert items and items[0].care_product_id == product.care_product_id
        reservations = await care_repo.list_reservations_for_order(care_order_id=order.care_order_id)
        assert reservations
        after_orders = await care_service.list_patient_orders(clinic_id="clinic_main", patient_id="patient_sergey_ivanov")
        assert len(after_orders) == len(before_orders) + 1

        gel = await care_repo.get_product_by_code(clinic_id="clinic_main", target_code="SKU-GEL-REMIN")
        assert gel is not None
        failed_order = await care_service.create_order(
            clinic_id="clinic_main", patient_id="patient_sergey_ivanov", payment_mode="pickup", currency_code=gel.currency_code,
            pickup_branch_id="branch_central", recommendation_id=None, booking_id=None, items=[(gel, 1)],
        )
        out = await care_service.reserve_if_available(care_order_id=failed_order.care_order_id, care_product_id=gel.care_product_id, branch_id="branch_central", reserved_qty=1)
        assert not out.ok and out.reason in {"insufficient_stock", "availability_inactive", "availability_missing"}

        repeat = await care_service.repeat_order_as_new(clinic_id="clinic_main", patient_id="patient_sergey_ivanov", source_order_id="co_sergey_confirmed_brush", requested_branch_id="branch_central", allowed_branch_ids=("branch_central", "branch_north"))
        assert repeat.reason in {None, "branch_required", "branch_selection_required", "insufficient_stock", "branch_unavailable"}
        if repeat.ok:
            assert repeat.created_order is not None and repeat.created_order.care_order_id != "co_sergey_confirmed_brush"

        reference_repo = await DbClinicReferenceRepository.load(db_config)
        reference_service = ClinicReferenceService(reference_repo)
        booking_flow = BookingPatientFlowService(orchestration=_NoopOrchestration(), reads=DbBookingRepository(db_config), reference=reference_service, patient_creator=_NoopPatientCreator())
        i18n = I18nService(locales_path=Path("locales"), default_locale="ru")
        runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
        codec = CardCallbackCodec(runtime=runtime)
        router = make_router(i18n=i18n, booking_flow=booking_flow, reference=reference_service, reminder_actions=_NoopReminderActions(), recommendation_service=rec_service, care_commerce_service=care_service, recommendation_repository=rec_repo, default_locale="ru", card_runtime=runtime, card_callback_codec=codec)

        sergey = await find_patient_by_exact_contact(db_config, contact_type="telegram", contact_value="3001")
        assert sergey and sergey["patient_id"] == "patient_sergey_ivanov"
        rec_cb = home._Callback(data="prec:open:rec_sergey_hygiene_issued", user_id=3001)
        await _handler(router, "recommendation_open_callback", kind="callback")(rec_cb)
        rec_text, rec_markup = home._latest_callback_panel(rec_cb)
        assert rec_text
        _assert_no_leakage(rec_text)
        _assert_allowed_callback_prefixes(_collect_callback_data(rec_markup))

    asyncio.run(_run())
