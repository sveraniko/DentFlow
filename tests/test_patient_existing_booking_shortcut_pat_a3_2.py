from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application.booking.telegram_flow import BookingResumePanel
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.common.i18n import I18nService
from app.domain.booking import Booking, BookingSession
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, Service
from app.interfaces.bots.patient.router import make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore, PanelFamily
from app.interfaces.cards.runtime_state import InMemoryRedis


class _Bot:
    async def edit_message_text(self, **kwargs):  # noqa: ANN003
        return None


class _Message:
    def __init__(self, text: str, user_id: int = 1001) -> None:
        self.text = text
        self.bot = _Bot()
        self.chat = SimpleNamespace(id=9001)
        self.from_user = SimpleNamespace(id=user_id, full_name="Pat One")
        self.answers: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None):
        self.answers.append((text, reply_markup))
        return SimpleNamespace(chat=self.chat, message_id=500 + len(self.answers))


class _CallbackMessage:
    def __init__(self, message_id: int = 500) -> None:
        self.chat = SimpleNamespace(id=9001)
        self.message_id = message_id
        self.answers: list[tuple[str, object | None]] = []

    async def edit_text(self, text: str, reply_markup=None):
        self.answers.append((text, reply_markup))

    async def edit_reply_markup(self, reply_markup=None):
        return None

    async def answer(self, text: str, reply_markup=None):
        self.answers.append((text, reply_markup))
        return SimpleNamespace(chat=self.chat, message_id=900 + len(self.answers))


class _Callback:
    def __init__(self, data: str, *, user_id: int, message_id: int = 500) -> None:
        self.data = data
        self.bot = _Bot()
        self.chat = SimpleNamespace(id=9001)
        self.from_user = SimpleNamespace(id=user_id)
        self.message = _CallbackMessage(message_id=message_id)
        self.answers: list[str] = []

    async def answer(self, text: str = "", show_alert: bool = False, reply_markup=None) -> None:  # noqa: ARG002
        if text:
            self.answers.append(text)
        return SimpleNamespace(chat=self.chat, message_id=self.message.message_id)


class _ReminderActions:
    def __init__(self) -> None:
        self.outcome_kind = "invalid"
        self.outcome_reason = "message_mismatch"
        self.outcome_booking_id = "b1"

    async def handle_action(self, **kwargs):  # noqa: ANN003
        return SimpleNamespace(kind=self.outcome_kind, reason=self.outcome_reason, booking_id=self.outcome_booking_id)


class _BookingFlowStub:
    def __init__(self) -> None:
        now = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
        self.session = BookingSession(
            booking_session_id="sess_1",
            clinic_id="clinic_main",
            branch_id="branch_1",
            telegram_user_id=1001,
            resolved_patient_id="pat_1",
            status="awaiting_contact_confirmation",
            route_type="service_first",
            service_id="service_consult",
            urgency_type=None,
            requested_date_type=None,
            requested_date=None,
            time_window=None,
            doctor_preference_type="any",
            doctor_id=None,
            doctor_code_raw=None,
            selected_slot_id=None,
            selected_hold_id=None,
            contact_phone_snapshot=None,
            notes=None,
            expires_at=now,
            created_at=now,
            updated_at=now,
        )
        self.booking = Booking(
            booking_id="b1",
            clinic_id="clinic_main",
            branch_id="branch_1",
            patient_id="pat_1",
            doctor_id="doctor_1",
            service_id="service_consult",
            slot_id="slot_1",
            booking_mode="patient_bot",
            source_channel="telegram",
            scheduled_start_at=now,
            scheduled_end_at=now,
            status="confirmed",
            reason_for_visit_short=None,
            patient_note=None,
            confirmation_required=True,
            confirmed_at=None,
            canceled_at=None,
            checked_in_at=None,
            in_service_at=None,
            completed_at=None,
            no_show_at=None,
            created_at=now,
            updated_at=now,
        )
        self.start_or_resume_existing_calls = 0
        self.resolve_known_patient_calls = 0
        self.resolve_known_patient_kind = "exact_match"
        self.raise_on_resolve_known_patient = False

    async def start_or_resume_existing_booking_session(self, **kwargs):  # noqa: ANN003
        self.start_or_resume_existing_calls += 1
        return self.session

    async def resolve_existing_booking_for_known_patient(self, **kwargs):  # noqa: ANN003
        self.resolve_known_patient_calls += 1
        if self.raise_on_resolve_known_patient:
            raise RuntimeError("lookup unavailable")
        result_session = BookingSession(
            **{**asdict(self.session), "booking_session_id": "sess_known", "route_type": "existing_booking_control", "status": "in_progress"}
        )
        bookings = (self.booking,) if self.resolve_known_patient_kind == "exact_match" else ()
        return SimpleNamespace(kind=self.resolve_known_patient_kind, bookings=bookings, booking_session=result_session)

    async def determine_resume_panel(self, **kwargs):  # noqa: ANN003
        return BookingResumePanel(panel_key="contact_collection", booking_session=self.session)

    async def start_existing_booking_control_for_booking(self, **kwargs):  # noqa: ANN003
        session = SimpleNamespace(booking_session_id="sess_rem_1")
        return SimpleNamespace(kind="ready", booking=self.booking, booking_session=session)

    def build_booking_snapshot(self, **kwargs):  # noqa: ANN003
        from app.interfaces.cards import BookingRuntimeSnapshot

        return BookingRuntimeSnapshot(
            booking_id="b1",
            state_token="sess_rem_1",
            role_variant="patient",
            scheduled_start_at=self.booking.scheduled_start_at,
            timezone_name="UTC",
            patient_label="You",
            doctor_label="Dr One",
            service_label="Consultation",
            branch_label="Main Branch",
            status=self.booking.status,
            source_channel="telegram",
            patient_contact=None,
            chart_summary_entry=None,
            recommendation_summary=None,
            care_order_summary=None,
            next_step_note_key="booking.next_step.confirmed",
            compact_flags=(),
            reminder_summary=None,
            reschedule_summary=None,
        )

    async def set_contact_phone(self, **kwargs):  # noqa: ANN003
        raise AssertionError("contact must not be parsed while in existing_booking_control mode")

    async def resolve_patient_from_contact(self, **kwargs):  # noqa: ANN003
        raise AssertionError("contact must not be parsed while in existing_booking_control mode")


class _RepoUnique:
    async def find_patient_ids_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> list[str]:
        return ["pat_1"]


class _RepoMultiple:
    async def find_patient_ids_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> list[str]:
        return ["pat_1", "pat_2"]


class _RepoUnavailable:
    async def find_patient_ids_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int):
        raise RuntimeError("repository unavailable")


class _RepoLegacyInvalid:
    async def find_patient_id_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int):
        return ["pat_1", "pat_2"]


def _reference() -> ClinicReferenceService:
    repo = InMemoryClinicReferenceRepository()
    repo.upsert_clinic(Clinic(clinic_id="clinic_main", code="MAIN", display_name="Main", timezone="UTC", default_locale="en"))
    repo.upsert_branch(Branch(branch_id="branch_1", clinic_id="clinic_main", display_name="Main Branch", address_text="-", timezone="UTC"))
    repo.upsert_service(Service(service_id="service_consult", clinic_id="clinic_main", code="CONSULT", title_key="service.consult", duration_minutes=30))
    repo.upsert_doctor(Doctor(doctor_id="doctor_1", clinic_id="clinic_main", display_name="Dr One", specialty_code="dent", branch_id="branch_1"))
    return ClinicReferenceService(repo)


def _handler(router, name: str, *, kind: str = "message"):
    handlers = router.message.handlers if kind == "message" else router.callback_query.handlers
    for h in handlers:
        if h.callback.__name__ == name:
            return h.callback
    raise AssertionError(name)


def _build_router(*, recommendation_repository):
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    booking_flow = _BookingFlowStub()
    reminder_actions = _ReminderActions()
    router = make_router(
        i18n=i18n,
        booking_flow=booking_flow,
        reference=_reference(),
        reminder_actions=reminder_actions,
        recommendation_service=None,
        care_commerce_service=None,
        recommendation_repository=recommendation_repository,
        default_locale="en",
        card_runtime=runtime,
        card_callback_codec=codec,
    )
    return router, runtime, booking_flow, reminder_actions


def test_my_booking_direct_opens_with_trusted_unique_identity() -> None:
    router, runtime, booking_flow, _ = _build_router(recommendation_repository=_RepoUnique())

    asyncio.run(_handler(router, "my_booking_entry")(_Message(text="/my_booking", user_id=1001)))

    assert booking_flow.resolve_known_patient_calls == 1
    assert booking_flow.start_or_resume_existing_calls == 0
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "existing_booking_control"


def test_home_callback_my_booking_uses_same_trusted_shortcut() -> None:
    router, runtime, booking_flow, _ = _build_router(recommendation_repository=_RepoUnique())

    callback = _Callback(data="phome:my_booking", user_id=1001)
    asyncio.run(_handler(router, "patient_home_my_booking", kind="callback")(callback))

    assert booking_flow.resolve_known_patient_calls == 1
    assert booking_flow.start_or_resume_existing_calls == 0
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "existing_booking_control"


def test_trusted_identity_without_live_booking_renders_no_match_without_prompt() -> None:
    router, _, booking_flow, _ = _build_router(recommendation_repository=_RepoUnique())
    booking_flow.resolve_known_patient_kind = "no_match"
    message = _Message(text="/my_booking", user_id=1001)

    asyncio.run(_handler(router, "my_booking_entry")(message))

    assert booking_flow.resolve_known_patient_calls == 1
    assert booking_flow.start_or_resume_existing_calls == 0
    assert "upcoming booking for this contact" in message.answers[-1][0]


def test_missing_trusted_identity_falls_back_to_contact_prompt() -> None:
    router, _, booking_flow, _ = _build_router(recommendation_repository=None)
    message = _Message(text="/my_booking", user_id=1001)

    asyncio.run(_handler(router, "my_booking_entry")(message))

    assert booking_flow.resolve_known_patient_calls == 0
    assert booking_flow.start_or_resume_existing_calls == 1
    assert "share the same phone" in message.answers[-1][0]


def test_multiple_candidate_patients_fall_back_to_contact_prompt() -> None:
    router, _, booking_flow, _ = _build_router(recommendation_repository=_RepoMultiple())
    message = _Message(text="/my_booking", user_id=1001)

    asyncio.run(_handler(router, "my_booking_entry")(message))

    assert booking_flow.resolve_known_patient_calls == 0
    assert booking_flow.start_or_resume_existing_calls == 1
    assert "share the same phone" in message.answers[-1][0]


def test_lookup_unavailable_or_invalid_outcome_falls_back_to_contact_prompt() -> None:
    router_unavailable, _, booking_flow_unavailable, _ = _build_router(recommendation_repository=_RepoUnavailable())
    message_unavailable = _Message(text="/my_booking", user_id=1001)
    asyncio.run(_handler(router_unavailable, "my_booking_entry")(message_unavailable))
    assert booking_flow_unavailable.resolve_known_patient_calls == 0
    assert booking_flow_unavailable.start_or_resume_existing_calls == 1

    router_invalid, _, booking_flow_invalid, _ = _build_router(recommendation_repository=_RepoUnique())
    booking_flow_invalid.resolve_known_patient_kind = "invalid_state"
    message_invalid = _Message(text="/my_booking", user_id=1001)
    asyncio.run(_handler(router_invalid, "my_booking_entry")(message_invalid))
    assert booking_flow_invalid.resolve_known_patient_calls == 1
    assert booking_flow_invalid.start_or_resume_existing_calls == 1

    router_legacy_invalid, _, booking_flow_legacy, _ = _build_router(recommendation_repository=_RepoLegacyInvalid())
    message_legacy = _Message(text="/my_booking", user_id=1001)
    asyncio.run(_handler(router_legacy_invalid, "my_booking_entry")(message_legacy))
    assert booking_flow_legacy.resolve_known_patient_calls == 0
    assert booking_flow_legacy.start_or_resume_existing_calls == 1


def test_contact_input_outside_contact_prompt_mode_is_ignored() -> None:
    router, runtime, booking_flow, reminder_actions = _build_router(recommendation_repository=_RepoUnique())
    reminder_actions.outcome_kind = "accepted"
    reminder_actions.outcome_reason = "booking_confirmed"
    callback = _Callback(data="rem:confirm:rem_1", user_id=1001)
    asyncio.run(_handler(router, "reminder_action_callback", kind="callback")(callback))

    on_contact_text = _handler(router, "on_contact_text")
    contact = _Message(text="+15550101099", user_id=1001)
    asyncio.run(on_contact_text(contact))

    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "existing_booking_control"
    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    assert active is not None
    assert booking_flow.start_or_resume_existing_calls == 0


def test_pat_a3_2_no_migration_directories_present() -> None:
    assert not Path("migrations").exists()
    assert not Path("alembic").exists()
