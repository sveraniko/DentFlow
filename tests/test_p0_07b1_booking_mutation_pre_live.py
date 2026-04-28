from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import test_patient_home_surface_pat_a1_2 as home

from app.application.booking.orchestration import BookingOrchestrationService
from app.application.booking.orchestration_outcomes import InvalidStateOutcome, OrchestrationSuccess, SlotUnavailableOutcome
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
    "source_channel",
    "booking_mode",
    "booking_id",
    "slot_id",
    "patient_id",
    "doctor_id",
    "service_id",
    "branch_id",
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
_RUNTIME_CALLBACK_PREFIX = re.compile(r"^c\d+\|")


class _RuntimePatientFinder:
    def __init__(self, db_config) -> None:
        self._db = db_config

    async def find_patients_by_exact_contact(self, *, contact_type: str, contact_value: str) -> list[dict]:
        return await find_patients_by_exact_contact(self._db, contact_type=contact_type, contact_value=contact_value)

    async def find_patients_by_external_id(self, *, external_system: str, external_id: str) -> list[dict]:
        return await find_patients_by_external_id(self._db, external_system=external_system, external_id=external_id)


class _NoopReminderActions:
    async def handle_action(self, **kwargs):  # noqa: ANN003
        return SimpleNamespace(kind="invalid")


def _assert_no_leakage(text: str) -> None:
    for token in FORBIDDEN_TEXT_TOKENS:
        assert token not in text


def _collect_callback_data(markup) -> set[str]:
    if markup is None:
        return set()
    return {button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


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


def test_p0_07b1_booking_mutation_pre_live_db_backed_smoke() -> None:
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
        booking_flow = BookingPatientFlowService(
            orchestration=orchestration,
            reads=booking_repo,
            reference=reference_service,
            patient_creator=patient_creator,
        )

        # doctor visibility + code semantics
        public_doctors = booking_flow.list_doctors(clinic_id="clinic_main")
        assert "doctor_irina" not in {row.doctor_id for row in public_doctors}

        irina_access = reference_service.resolve_doctor_access_code(
            clinic_id="clinic_main",
            code="IRINA-TREAT",
            service_id="service_treatment",
            branch_id="branch_central",
        )
        assert irina_access is not None
        assert irina_access.doctor_id == "doctor_irina"
        assert reference_service.resolve_doctor_access_code(
            clinic_id="clinic_main",
            code="IRINA-TREAT",
            service_id="service_consult",
            branch_id="branch_central",
        ) is None
        assert reference_service.resolve_doctor_access_code(
            clinic_id="clinic_main",
            code="IRINA-TREAT",
            service_id="service_treatment",
            branch_id="branch_north",
        ) is None

        maria = await find_patient_by_exact_contact(db_config, contact_type="telegram", contact_value="3004")
        assert maria and maria["patient_id"] == "patient_maria_petrova"

        # Scenario A: code-only doctor path
        session_a = await booking_flow.start_or_resume_session(clinic_id="clinic_main", telegram_user_id=3004, branch_id="branch_central")
        session_a = await booking_flow.update_service(booking_session_id=session_a.booking_session_id, service_id="service_treatment")
        session_a = await booking_flow.update_doctor_preference(
            booking_session_id=session_a.booking_session_id,
            doctor_preference_type="specific",
            doctor_id=irina_access.doctor_id,
        )
        await orchestration.update_session_context(booking_session_id=session_a.booking_session_id, doctor_code_raw="IRINA-TREAT")

        slots_a = await booking_flow.list_slots_for_session(booking_session_id=session_a.booking_session_id, limit=20)
        irina_slot = next(
            slot
            for slot in slots_a
            if slot.doctor_id == "doctor_irina" and slot.branch_id == "branch_central" and slot.start_at > datetime.now(timezone.utc)
        )
        selected_a = await booking_flow.select_slot(booking_session_id=session_a.booking_session_id, slot_id=irina_slot.slot_id)
        assert isinstance(selected_a, OrchestrationSuccess)

        resolved_a = await booking_flow.resolve_patient_for_new_booking_contact(
            booking_session_id=session_a.booking_session_id,
            phone="+7 (999) 888-44-00",
            fallback_display_name="Maria Petrova",
        )
        assert resolved_a.kind == "exact_match"

        review_a = await booking_flow.mark_review_ready(booking_session_id=session_a.booking_session_id)
        assert isinstance(review_a, OrchestrationSuccess)
        finalized_a = await booking_flow.finalize(booking_session_id=session_a.booking_session_id)
        assert isinstance(finalized_a, OrchestrationSuccess)
        booking_a = finalized_a.entity
        assert booking_a.patient_id == "patient_maria_petrova"
        assert booking_a.service_id == "service_treatment"
        assert booking_a.doctor_id == "doctor_irina"
        assert booking_a.branch_id == "branch_central"
        assert booking_a.scheduled_start_at > datetime.now(timezone.utc)
        assert booking_a.status in {"pending_confirmation", "confirmed"}

        session_a_after = await booking_flow.get_booking_session(booking_session_id=session_a.booking_session_id)
        assert session_a_after is not None and session_a_after.selected_hold_id
        hold_a = await booking_repo.get_slot_hold(session_a_after.selected_hold_id)
        assert hold_a is not None
        assert hold_a.status == "consumed"

        session_a_reuse = await booking_flow.start_or_resume_session(clinic_id="clinic_main", telegram_user_id=3002, branch_id="branch_central")
        await booking_flow.update_service(booking_session_id=session_a_reuse.booking_session_id, service_id="service_treatment")
        await booking_flow.update_doctor_preference(
            booking_session_id=session_a_reuse.booking_session_id,
            doctor_preference_type="specific",
            doctor_id="doctor_irina",
        )
        unavailable_reuse = await booking_flow.select_slot(booking_session_id=session_a_reuse.booking_session_id, slot_id=irina_slot.slot_id)
        assert isinstance(unavailable_reuse, SlotUnavailableOutcome)

        # Scenario B: edit time before finalize
        session_b = await booking_flow.start_or_resume_session(clinic_id="clinic_main", telegram_user_id=3004, branch_id="branch_central")
        session_b = await booking_flow.update_service(booking_session_id=session_b.booking_session_id, service_id="service_consult")
        session_b = await booking_flow.update_doctor_preference(
            booking_session_id=session_b.booking_session_id,
            doctor_preference_type="specific",
            doctor_id="doctor_anna",
        )
        slots_b = await booking_flow.list_slots_for_session(booking_session_id=session_b.booking_session_id, limit=20)
        first_slot = slots_b[0]
        second_slot = next(slot for slot in slots_b if slot.slot_id != first_slot.slot_id)

        first_selected = await booking_flow.select_slot(booking_session_id=session_b.booking_session_id, slot_id=first_slot.slot_id)
        assert isinstance(first_selected, OrchestrationSuccess)
        session_b_selected = await booking_flow.get_booking_session(booking_session_id=session_b.booking_session_id)
        assert session_b_selected is not None and session_b_selected.selected_hold_id
        old_hold_id = session_b_selected.selected_hold_id

        released = await booking_flow.release_selected_slot_for_reselect(booking_session_id=session_b.booking_session_id)
        assert isinstance(released, OrchestrationSuccess)
        old_hold = await booking_repo.get_slot_hold(old_hold_id)
        assert old_hold is not None
        assert old_hold.status == "released"

        second_selected = await booking_flow.select_slot(booking_session_id=session_b.booking_session_id, slot_id=second_slot.slot_id)
        assert isinstance(second_selected, OrchestrationSuccess)

        resolved_b = await booking_flow.resolve_patient_for_new_booking_contact(
            booking_session_id=session_b.booking_session_id,
            phone="+7 (999) 888-44-00",
            fallback_display_name="Maria Petrova",
        )
        assert resolved_b.kind == "exact_match"
        review_b = await booking_flow.mark_review_ready(booking_session_id=session_b.booking_session_id)
        assert isinstance(review_b, OrchestrationSuccess)
        finalized_b = await booking_flow.finalize(booking_session_id=session_b.booking_session_id)
        assert isinstance(finalized_b, OrchestrationSuccess)
        booking_b = finalized_b.entity
        assert booking_b.slot_id == second_slot.slot_id
        assert booking_b.scheduled_start_at == second_slot.start_at
        assert booking_b.status in {"pending_confirmation", "confirmed"}

        # Existing booking action mutation: patient confirm
        existing = await booking_flow.resolve_existing_booking_for_known_patient(
            clinic_id="clinic_main",
            telegram_user_id=3001,
            patient_id="patient_sergey_ivanov",
        )
        assert existing.kind == "exact_match"
        assert existing.booking_session is not None
        confirm_outcome = await booking_flow.confirm_existing_booking(
            clinic_id="clinic_main",
            telegram_user_id=3001,
            callback_session_id=existing.booking_session.booking_session_id,
            booking_id="bkg_sergey_pending",
        )
        assert isinstance(confirm_outcome, OrchestrationSuccess)
        updated_pending = await booking_flow.get_booking(booking_id="bkg_sergey_pending")
        assert updated_pending is not None and updated_pending.status == "confirmed"

        # Handler-level My Booking read + callback/text leakage checks
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

        my_booking = home._Callback(data="phome:my_booking", user_id=3004)
        await _handler(router, "patient_home_my_booking", kind="callback")(my_booking)
        booking_text, booking_markup = home._latest_callback_panel(my_booking)
        assert "📅" in booking_text and "👩‍⚕️" in booking_text and "🦷" in booking_text and "📍" in booking_text
        assert "Dr. Irina" in booking_text or "Dr. Anna" in booking_text
        _assert_no_leakage(booking_text)
        _assert_allowed_callback_prefixes(_collect_callback_data(booking_markup))

        stale_confirm = await booking_flow.confirm_existing_booking(
            clinic_id="clinic_main",
            telegram_user_id=3001,
            callback_session_id=existing.booking_session.booking_session_id,
            booking_id="bkg_sergey_pending",
        )
        assert isinstance(stale_confirm, InvalidStateOutcome)

    asyncio.run(_run())
