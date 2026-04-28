from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import test_patient_home_surface_pat_a1_2 as home

from app.application.booking.orchestration import BookingOrchestrationService
from app.application.booking.orchestration_outcomes import InvalidStateOutcome, OrchestrationSuccess
from app.application.booking.patient_resolution import BookingPatientResolutionService
from app.application.booking.state_services import BookingSessionStateService, BookingStateService, SlotHoldStateService, WaitlistStateService
from app.application.booking.telegram_flow import BookingPatientFlowService
from app.application.care_commerce.service import CareCommerceService
from app.application.clinic_reference import ClinicReferenceService
from app.application.communication import BookingReminderPlanner, BookingReminderService
from app.application.policy import PolicyResolver
from app.application.recommendation.services import RecommendationService
from app.common.i18n import I18nService
from app.infrastructure.db.booking_repository import DbBookingRepository
from app.infrastructure.db.care_commerce_repository import DbCareCommerceRepository
from app.infrastructure.db.communication_repository import DbReminderJobRepository
from app.infrastructure.db.patient_repository import DbCanonicalPatientCreator, DbPatientPreferenceReader, find_patient_by_exact_contact, find_patients_by_exact_contact, find_patients_by_external_id
from app.infrastructure.db.recommendation_repository import DbRecommendationRepository
from app.infrastructure.db.repositories import DbClinicReferenceRepository, DbPolicyRepository
from app.interfaces.bots.patient.router import make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore
from app.interfaces.cards.runtime_state import InMemoryRedis
from tests.helpers.seed_demo_db_harness import TEST_DB_DSN_ENV, reset_test_db, run_seed_demo_bootstrap_for_tests, safe_test_db_config

FORBIDDEN_TEXT_TOKENS = (
    "Actions:", "Channel:", "Канал:", "source_channel", "booking_mode", "booking_id", "slot_id", "patient_id", "doctor_id", "service_id", "branch_id", "care_order_id", "care_product_id", "recommendation_id", "UTC", "MSK", "%Z", "2026-04-",
)
ALLOWED_CALLBACK_PREFIXES = ("phome:", "book:", "care:", "careo:", "prec:", "rec:", "rsch:")
_RUNTIME_CALLBACK_PREFIX = re.compile(r"^c\d+\|")


class _RuntimePatientFinder:
    def __init__(self, db_config) -> None:
        self._db = db_config

    async def find_patients_by_exact_contact(self, *, contact_type: str, contact_value: str) -> list[dict]:
        return await find_patients_by_exact_contact(self._db, contact_type=contact_type, contact_value=contact_value)

    async def find_patients_by_external_id(self, *, external_system: str, external_id: str) -> list[dict]:
        return await find_patients_by_external_id(self._db, external_system=external_system, external_id=external_id)


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


def test_p0_07b3_consolidated_mutation_pre_live_gate() -> None:
    db_config = safe_test_db_config()

    async def _run() -> None:
        assert os.getenv(TEST_DB_DSN_ENV), f"{TEST_DB_DSN_ENV} must be set"
        assert os.getenv("INTEGRATIONS_GOOGLE_CALENDAR_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}
        await reset_test_db(db_config)
        stage_counts = await run_seed_demo_bootstrap_for_tests(db_config)
        assert set(stage_counts) == {"stack1", "stack2", "stack3", "care_catalog", "recommendations_care_orders"}

        reference_repo = await DbClinicReferenceRepository.load(db_config)
        policy_repo = await DbPolicyRepository.load(db_config)
        reference_service = ClinicReferenceService(reference_repo)
        booking_repo = DbBookingRepository(db_config)
        patient_creator = DbCanonicalPatientCreator(db_config)
        policy_resolver = PolicyResolver(policy_repo)
        reminder_service = BookingReminderService(
            repository=DbReminderJobRepository(db_config),
            planner=BookingReminderPlanner(policy_resolver),
            policy_resolver=policy_resolver,
            patient_preference_reader=DbPatientPreferenceReader(db_config),
        )
        orchestration = BookingOrchestrationService(
            repository=booking_repo,
            booking_session_state_service=BookingSessionStateService(booking_repo),
            slot_hold_state_service=SlotHoldStateService(booking_repo),
            booking_state_service=BookingStateService(booking_repo),
            waitlist_state_service=WaitlistStateService(booking_repo),
            patient_resolution_service=BookingPatientResolutionService(_RuntimePatientFinder(db_config)),
            policy_resolver=policy_resolver,
            reminder_service=reminder_service,
        )
        booking_flow = BookingPatientFlowService(orchestration=orchestration, reads=booking_repo, reference=reference_service, patient_creator=patient_creator)

        rec_repo = DbRecommendationRepository(db_config)
        rec_service = RecommendationService(rec_repo)
        care_repo = DbCareCommerceRepository(db_config)
        care_service = CareCommerceService(care_repo)

        assert "doctor_irina" not in {row.doctor_id for row in booking_flow.list_doctors(clinic_id="clinic_main")}
        irina_access = reference_service.resolve_doctor_access_code(clinic_id="clinic_main", code="IRINA-TREAT", service_id="service_treatment", branch_id="branch_central")
        assert irina_access is not None and irina_access.doctor_id == "doctor_irina"
        assert reference_service.resolve_doctor_access_code(clinic_id="clinic_main", code="IRINA-TREAT", service_id="service_consult", branch_id="branch_central") is None

        maria = await find_patient_by_exact_contact(db_config, contact_type="telegram", contact_value="3004")
        assert maria and maria["patient_id"] == "patient_maria_petrova"

        session = await booking_flow.start_or_resume_session(clinic_id="clinic_main", telegram_user_id=3004, branch_id="branch_central")
        await booking_flow.update_service(booking_session_id=session.booking_session_id, service_id="service_treatment")
        await booking_flow.update_doctor_preference(booking_session_id=session.booking_session_id, doctor_preference_type="specific", doctor_id="doctor_irina")
        slots = await booking_flow.list_slots_for_session(booking_session_id=session.booking_session_id, limit=20)
        first = next(slot for slot in slots if slot.doctor_id == "doctor_irina" and slot.start_at > datetime.now(timezone.utc))
        assert isinstance(await booking_flow.select_slot(booking_session_id=session.booking_session_id, slot_id=first.slot_id), OrchestrationSuccess)
        selected = await booking_flow.get_booking_session(booking_session_id=session.booking_session_id)
        old_hold_id = selected.selected_hold_id
        assert isinstance(await booking_flow.release_selected_slot_for_reselect(booking_session_id=session.booking_session_id), OrchestrationSuccess)
        old_hold = await booking_repo.get_slot_hold(old_hold_id)
        assert old_hold and old_hold.status == "released"
        second = next(slot for slot in slots if slot.slot_id != first.slot_id)
        assert isinstance(await booking_flow.select_slot(booking_session_id=session.booking_session_id, slot_id=second.slot_id), OrchestrationSuccess)
        resolved = await booking_flow.resolve_patient_for_new_booking_contact(booking_session_id=session.booking_session_id, phone="+7 (999) 888-44-00", fallback_display_name="Maria Petrova")
        assert resolved.kind == "exact_match"
        assert isinstance(await booking_flow.mark_review_ready(booking_session_id=session.booking_session_id), OrchestrationSuccess)
        finalized = await booking_flow.finalize(booking_session_id=session.booking_session_id)
        assert isinstance(finalized, OrchestrationSuccess)
        booking = finalized.entity
        assert booking.patient_id == "patient_maria_petrova" and booking.service_id == "service_treatment" and booking.doctor_id == "doctor_irina"
        assert booking.slot_id == second.slot_id and booking.scheduled_start_at == second.start_at

        existing = await booking_flow.resolve_existing_booking_for_known_patient(clinic_id="clinic_main", telegram_user_id=3001, patient_id="patient_sergey_ivanov")
        confirmed = await booking_flow.confirm_existing_booking(clinic_id="clinic_main", telegram_user_id=3001, callback_session_id=existing.booking_session.booking_session_id, booking_id="bkg_sergey_pending")
        assert isinstance(confirmed, OrchestrationSuccess)
        assert (await booking_flow.get_booking(booking_id="bkg_sergey_pending")).status == "confirmed"
        assert isinstance(await booking_flow.confirm_existing_booking(clinic_id="clinic_main", telegram_user_id=3001, callback_session_id=existing.booking_session.booking_session_id, booking_id="bkg_sergey_pending"), InvalidStateOutcome)

        ack = await rec_service.acknowledge(recommendation_id="rec_sergey_hygiene_issued")
        assert ack and ack.status == "acknowledged"
        accepted = await rec_service.accept(recommendation_id="rec_sergey_hygiene_issued")
        assert accepted and accepted.status == "accepted"
        declined = await rec_service.decline(recommendation_id="rec_elena_post_treatment_viewed")
        assert declined and declined.status == "declined"
        try:
            await rec_service.accept(recommendation_id="rec_giorgi_expired")
            raise AssertionError("expected invalid state")
        except ValueError:
            pass
        assert (await rec_repo.get("rec_sergey_hygiene_issued")).status == "accepted"

        product = await care_repo.get_product_by_code(clinic_id="clinic_main", target_code="SKU-BRUSH-SOFT")
        order = await care_service.create_order(clinic_id="clinic_main", patient_id="patient_sergey_ivanov", payment_mode="pickup", currency_code=product.currency_code, pickup_branch_id="branch_central", recommendation_id="rec_sergey_hygiene_issued", booking_id=None, items=[(product, 1)])
        assert (await care_service.transition_order(care_order_id=order.care_order_id, to_status="confirmed")).status == "confirmed"
        assert (await care_service.create_reservation(care_order_id=order.care_order_id, care_product_id=product.care_product_id, branch_id="branch_central", reserved_qty=1)).status == "created"
        detail = await care_service.get_order(order.care_order_id)
        assert detail and detail.total_amount == product.price_amount
        assert await care_repo.list_order_items(order.care_order_id)
        assert await care_repo.list_reservations_for_order(care_order_id=order.care_order_id)

        gel = await care_repo.get_product_by_code(clinic_id="clinic_main", target_code="SKU-GEL-REMIN")
        failed_order = await care_service.create_order(clinic_id="clinic_main", patient_id="patient_sergey_ivanov", payment_mode="pickup", currency_code=gel.currency_code, pickup_branch_id="branch_central", recommendation_id=None, booking_id=None, items=[(gel, 1)])
        out = await care_service.reserve_if_available(care_order_id=failed_order.care_order_id, care_product_id=gel.care_product_id, branch_id="branch_central", reserved_qty=1)
        assert not out.ok and out.reason in {"insufficient_stock", "availability_inactive", "availability_missing"}
        assert await care_repo.list_reservations_for_order(care_order_id=failed_order.care_order_id) == []
        failed_detail = await care_service.get_order(failed_order.care_order_id)
        assert failed_detail is not None and failed_detail.status not in {"confirmed", "ready_for_pickup", "active"}

        all_orders = await care_service.list_patient_orders(clinic_id="clinic_main", patient_id="patient_sergey_ivanov")
        failed_from_list = [o for o in all_orders if o.care_order_id == failed_order.care_order_id]
        assert failed_from_list and all(o.status not in {"confirmed", "ready_for_pickup", "active"} for o in failed_from_list)

        repeat = await care_service.repeat_order_as_new(clinic_id="clinic_main", patient_id="patient_sergey_ivanov", source_order_id="co_sergey_confirmed_brush", requested_branch_id="branch_central", allowed_branch_ids=("branch_central", "branch_north"))
        assert repeat.reason in {None, "branch_required", "branch_selection_required", "insufficient_stock", "branch_unavailable"}

        i18n = I18nService(locales_path=Path("locales"), default_locale="ru")
        runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
        codec = CardCallbackCodec(runtime=runtime)
        router = make_router(i18n=i18n, booking_flow=booking_flow, reference=reference_service, reminder_actions=_NoopReminderActions(), recommendation_service=rec_service, care_commerce_service=care_service, recommendation_repository=rec_repo, default_locale="ru", card_runtime=runtime, card_callback_codec=codec)

        my_booking = home._Callback(data="phome:my_booking", user_id=3004)
        await _handler(router, "patient_home_my_booking", kind="callback")(my_booking)
        booking_text, booking_markup = home._latest_callback_panel(my_booking)
        _assert_no_leakage(booking_text)

        rec_open = home._Callback(data="prec:open:rec_sergey_hygiene_issued", user_id=3001)
        await _handler(router, "recommendation_open_callback", kind="callback")(rec_open)
        rec_text, rec_markup = home._latest_callback_panel(rec_open)
        _assert_no_leakage(rec_text)
        rec_callbacks = _collect_callback_data(rec_markup)
        _assert_allowed_callback_prefixes(rec_callbacks)
        assert not any(value.startswith(("rec:ack:", "rec:accept:", "rec:decline:")) for value in rec_callbacks)

        care_open = home._Callback(data="care:orders", user_id=3001)
        await _handler(router, "care_orders_callback", kind="callback")(care_open)
        care_text, care_markup = home._latest_callback_panel(care_open)
        _assert_no_leakage(care_text)

        callbacks = _collect_callback_data(booking_markup) | rec_callbacks | _collect_callback_data(care_markup)
        _assert_allowed_callback_prefixes(callbacks)

    asyncio.run(_run())
