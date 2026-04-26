from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from aiogram.types import ReplyKeyboardMarkup

from app.application.booking.orchestration_outcomes import OrchestrationSuccess
from app.application.booking.telegram_flow import BookingResumePanel, RecentBookingPrefill, ReturningPatientStartResult
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.common.i18n import I18nService
from app.domain.booking import AvailabilitySlot, Booking, BookingSession
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, Service
from app.interfaces.bots.patient.router import make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore, PanelFamily
from app.interfaces.cards.runtime_state import InMemoryRedis


class _Bot:
    def __init__(self) -> None:
        self.edits: list[dict] = []

    async def edit_message_text(self, **kwargs):  # noqa: ANN003
        self.edits.append(kwargs)
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
        self.slot = AvailabilitySlot(
            slot_id="slot_1",
            clinic_id="clinic_main",
            branch_id="branch_1",
            doctor_id="doctor_1",
            start_at=now,
            end_at=now,
            status="open",
            visibility_policy="public",
            service_scope=None,
            source_ref=None,
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
        self.request_reschedule_calls = 0
        self.start_or_resume_returning_calls = 0
        self.last_returning_kwargs: dict[str, object] | None = None
        self.recent_prefill: RecentBookingPrefill | None = None
        self.apply_prefill_calls = 0
        self.apply_same_doctor_prefill_calls = 0

    async def start_or_resume_returning_patient_booking(self, **kwargs):  # noqa: ANN003
        self.start_or_resume_returning_calls += 1
        self.last_returning_kwargs = kwargs
        trusted_patient_id = kwargs.get("trusted_patient_id")
        trusted_phone_snapshot = kwargs.get("trusted_phone_snapshot")
        session = self.session
        if isinstance(trusted_patient_id, str) and trusted_patient_id and isinstance(trusted_phone_snapshot, str) and trusted_phone_snapshot:
            session = BookingSession(
                **{
                    **asdict(self.session),
                    "resolved_patient_id": trusted_patient_id,
                    "contact_phone_snapshot": trusted_phone_snapshot,
                    "selected_slot_id": "slot_1",
                    "status": "in_progress",
                }
            )
        self.session = session
        return ReturningPatientStartResult(booking_session=self.session, trusted_shortcut_applied=bool(trusted_patient_id and trusted_phone_snapshot))

    async def get_recent_booking_prefill(self, **kwargs):  # noqa: ANN003
        return self.recent_prefill

    async def apply_recent_booking_prefill(self, **kwargs):  # noqa: ANN003
        self.apply_prefill_calls += 1
        self.session = BookingSession(
            **{
                **asdict(self.session),
                "service_id": kwargs["service_id"],
                "branch_id": kwargs["branch_id"],
                "doctor_preference_type": "specific",
                "doctor_id": kwargs["doctor_id"],
            }
        )
        return self.session

    async def apply_recent_booking_same_doctor_prefill(self, **kwargs):  # noqa: ANN003
        self.apply_same_doctor_prefill_calls += 1
        self.session = BookingSession(
            **{
                **asdict(self.session),
                "branch_id": kwargs["branch_id"],
                "doctor_preference_type": "specific",
                "doctor_id": kwargs["doctor_id"],
                "service_id": None,
            }
        )
        return self.session

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
        panel_key = "review_finalize" if self.session.selected_slot_id and self.session.contact_phone_snapshot and self.session.resolved_patient_id else "contact_collection"
        return BookingResumePanel(panel_key=panel_key, booking_session=self.session)

    async def validate_active_session_callback(self, **kwargs):  # noqa: ANN003
        return True

    async def start_existing_booking_control_for_booking(self, **kwargs):  # noqa: ANN003
        session = SimpleNamespace(booking_session_id="sess_rem_1")
        return SimpleNamespace(kind="ready", booking=self.booking, booking_session=session)

    async def start_patient_reschedule_session(self, **kwargs):  # noqa: ANN003
        session = SimpleNamespace(booking_session_id="sess_rsch_1")
        return SimpleNamespace(kind="ready", booking=self.booking, booking_session=session)

    async def get_booking_session(self, *, booking_session_id: str):
        return self.session if booking_session_id == self.session.booking_session_id else None

    async def get_availability_slot(self, *, slot_id: str):
        return self.slot if slot_id == self.slot.slot_id else None

    def list_services(self, *, clinic_id: str):
        return [SimpleNamespace(code="CONSULT", service_id="service_consult", title_key="service.cleaning")]

    async def list_slots_for_session(self, **kwargs):  # noqa: ANN003
        return [self.slot]

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

    async def request_reschedule(self, **kwargs):  # noqa: ANN003
        self.request_reschedule_calls += 1
        return OrchestrationSuccess(kind="success", entity=self.booking)


class _RepoUnique:
    async def find_patient_ids_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> list[str]:
        return ["pat_1"]


class _RepoUniqueWithPhone(_RepoUnique):
    async def find_primary_phone_by_patient(self, *, clinic_id: str, patient_id: str) -> str | None:
        return "+15550101099"


class _RepoUniqueWithoutPhone(_RepoUnique):
    async def find_primary_phone_by_patient(self, *, clinic_id: str, patient_id: str) -> str | None:
        return None


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
    text, keyboard = message.answers[-1]
    assert "share the same phone" in text
    assert isinstance(keyboard, ReplyKeyboardMarkup)
    rows = [[button.text for button in row] for row in keyboard.keyboard]
    assert rows[0] == ["Share contact"]
    assert rows[1] == ["🏠 Main menu"]
    assert "⬅️ Back" not in rows[1]


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


def test_my_booking_reschedule_moves_to_reschedule_start_panel() -> None:
    router, runtime, booking_flow, _ = _build_router(recommendation_repository=_RepoUnique())
    asyncio.run(_handler(router, "my_booking_entry")(_Message(text="/my_booking", user_id=1001)))
    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    assert active is not None
    callback = _Callback(data="mybk:reschedule:sess_known:b1", user_id=1001, message_id=active.message_id)

    asyncio.run(_handler(router, "request_reschedule", kind="callback")(callback))

    assert booking_flow.request_reschedule_calls == 1
    assert callback.bot.edits
    text = callback.bot.edits[-1]["text"]
    keyboard = callback.bot.edits[-1]["reply_markup"]
    assert "Reschedule mode started." in text
    assert keyboard is not None
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert labels == ["Select new time"]
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_session_id"] == "sess_rsch_1"
    assert state["booking_mode"] == "reschedule_booking_control"


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



def test_book_entry_uses_trusted_identity_and_phone_to_skip_contact_prompt() -> None:
    router, runtime, booking_flow, _ = _build_router(recommendation_repository=_RepoUniqueWithPhone())
    booking_flow.recent_prefill = RecentBookingPrefill(
        service_id="service_consult",
        doctor_id="doctor_1",
        branch_id="branch_1",
        service_label="Consultation",
        doctor_label="Dr One",
        branch_label="Main Branch",
    )

    message = _Message(text="/book", user_id=1001)
    asyncio.run(_handler(router, "book_entry")(message))

    assert booking_flow.start_or_resume_returning_calls == 1
    assert booking_flow.last_returning_kwargs is not None
    assert booking_flow.last_returning_kwargs.get("trusted_patient_id") == "pat_1"
    assert booking_flow.last_returning_kwargs.get("trusted_phone_snapshot") == "+15550101099"
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "new_booking_flow"
    assert state["quick_booking_prefill"]["service_id"] == "service_consult"
    assert message.answers
    assert "Quick booking suggestion based on your recent visit" in message.answers[-1][0]
    keyboard = message.answers[-1][1]
    assert keyboard is not None
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks == ["qbook:repeat:sess_1", "qbook:same_doctor:sess_1", "qbook:other:sess_1", "phome:home"]


def test_quick_book_repeat_prefills_session_and_opens_slot_selection() -> None:
    router, runtime, booking_flow, _ = _build_router(recommendation_repository=_RepoUniqueWithPhone())
    booking_flow.recent_prefill = RecentBookingPrefill(
        service_id="service_consult",
        doctor_id="doctor_1",
        branch_id="branch_1",
        service_label="Consultation",
        doctor_label="Dr One",
        branch_label="Main Branch",
    )
    message = _Message(text="/book", user_id=1001)
    asyncio.run(_handler(router, "book_entry")(message))

    callback = _Callback(data="qbook:repeat:sess_1", user_id=1001)
    asyncio.run(_handler(router, "quick_book_repeat", kind="callback")(callback))

    assert booking_flow.apply_prefill_calls == 1
    assert booking_flow.apply_same_doctor_prefill_calls == 0
    assert callback.bot.edits
    assert "Choose one of the nearest available slots" in callback.bot.edits[-1]["text"]
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["quick_booking_prefill"] == {}


def test_quick_book_other_falls_back_to_service_selection() -> None:
    router, runtime, booking_flow, _ = _build_router(recommendation_repository=_RepoUniqueWithPhone())
    booking_flow.recent_prefill = RecentBookingPrefill(
        service_id="service_consult",
        doctor_id="doctor_1",
        branch_id="branch_1",
        service_label="Consultation",
        doctor_label="Dr One",
        branch_label="Main Branch",
    )
    message = _Message(text="/book", user_id=1001)
    asyncio.run(_handler(router, "book_entry")(message))

    callback = _Callback(data="qbook:other:sess_1", user_id=1001)
    asyncio.run(_handler(router, "quick_book_other", kind="callback")(callback))

    assert callback.bot.edits
    assert "Choose a service" in callback.bot.edits[-1]["text"]
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["quick_booking_prefill"] == {}


def test_quick_book_same_doctor_prefills_doctor_and_branch_then_opens_service_selection() -> None:
    router, runtime, booking_flow, _ = _build_router(recommendation_repository=_RepoUniqueWithPhone())
    booking_flow.recent_prefill = RecentBookingPrefill(
        service_id="service_consult",
        doctor_id="doctor_1",
        branch_id="branch_1",
        service_label="Consultation",
        doctor_label="Dr One",
        branch_label="Main Branch",
    )
    message = _Message(text="/book", user_id=1001)
    asyncio.run(_handler(router, "book_entry")(message))

    callback = _Callback(data="qbook:same_doctor:sess_1", user_id=1001)
    asyncio.run(_handler(router, "quick_book_same_doctor", kind="callback")(callback))

    assert booking_flow.apply_same_doctor_prefill_calls == 1
    assert booking_flow.apply_prefill_calls == 0
    assert callback.bot.edits
    assert "Choose a service" in callback.bot.edits[-1]["text"]
    assert booking_flow.session.doctor_preference_type == "specific"
    assert booking_flow.session.doctor_id == "doctor_1"
    assert booking_flow.session.branch_id == "branch_1"
    assert booking_flow.session.service_id is None
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["quick_booking_prefill"] == {}


def test_quick_book_same_doctor_with_incomplete_prefill_falls_back_safely() -> None:
    router, runtime, booking_flow, _ = _build_router(recommendation_repository=_RepoUniqueWithPhone())
    booking_flow.recent_prefill = RecentBookingPrefill(
        service_id="service_consult",
        doctor_id="",
        branch_id="branch_1",
        service_label="Consultation",
        doctor_label="Dr One",
        branch_label="Main Branch",
    )
    message = _Message(text="/book", user_id=1001)
    asyncio.run(_handler(router, "book_entry")(message))

    callback = _Callback(data="qbook:same_doctor:sess_1", user_id=1001)
    asyncio.run(_handler(router, "quick_book_same_doctor", kind="callback")(callback))

    assert booking_flow.apply_same_doctor_prefill_calls == 0
    assert callback.bot.edits
    assert "Choose a service" in callback.bot.edits[-1]["text"]
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["quick_booking_prefill"] == {}


def test_quick_booking_panel_prefers_localized_service_title_when_available() -> None:
    router, _, booking_flow, _ = _build_router(recommendation_repository=_RepoUniqueWithPhone())
    booking_flow.recent_prefill = RecentBookingPrefill(
        service_id="service_cleaning",
        doctor_id="doctor_1",
        branch_id="branch_1",
        service_title_key="service.cleaning",
        service_code="CLEANING",
        service_label="",
        doctor_label="Dr One",
        branch_label="Main Branch",
    )

    message = _Message(text="/book", user_id=1001)
    asyncio.run(_handler(router, "book_entry")(message))

    assert message.answers
    panel_text = message.answers[-1][0]
    assert "Service: Teeth cleaning" in panel_text


def test_quick_book_manual_stale_callback_is_bounded() -> None:
    router, runtime, booking_flow, _ = _build_router(recommendation_repository=_RepoUniqueWithPhone())
    booking_flow.recent_prefill = RecentBookingPrefill(
        service_id="service_consult",
        doctor_id="doctor_1",
        branch_id="branch_1",
        service_label="Consultation",
        doctor_label="Dr One",
        branch_label="Main Branch",
    )
    message = _Message(text="/book", user_id=1001)
    asyncio.run(_handler(router, "book_entry")(message))

    callback = _Callback(data="qbook:same_doctor:sess_manual", user_id=1001)
    asyncio.run(_handler(router, "quick_book_same_doctor", kind="callback")(callback))

    assert booking_flow.apply_same_doctor_prefill_calls == 0
    assert callback.answers
    assert "This button is no longer active. Please use /book to continue." in callback.answers[-1]
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["quick_booking_prefill"]["service_id"] == "service_consult"


def test_book_entry_with_trusted_identity_without_phone_falls_back_to_contact_prompt() -> None:
    router, runtime, booking_flow, _ = _build_router(recommendation_repository=_RepoUniqueWithoutPhone())

    message = _Message(text="/book", user_id=1001)
    asyncio.run(_handler(router, "book_entry")(message))

    assert booking_flow.start_or_resume_returning_calls == 1
    assert booking_flow.last_returning_kwargs is not None
    assert booking_flow.last_returning_kwargs.get("trusted_patient_id") is None
    assert booking_flow.last_returning_kwargs.get("trusted_phone_snapshot") is None
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "new_booking_contact"
    assert message.answers
    assert "Contact for booking" in message.answers[-1][0]
    assert "+7 999 123-45-67" in message.answers[-1][0]


def test_phome_book_has_parity_with_book_for_trusted_identity_and_phone() -> None:
    router, runtime, booking_flow, _ = _build_router(recommendation_repository=_RepoUniqueWithPhone())
    booking_flow.recent_prefill = RecentBookingPrefill(
        service_id="service_consult",
        doctor_id="doctor_1",
        branch_id="branch_1",
        service_label="Consultation",
        doctor_label="Dr One",
        branch_label="Main Branch",
    )

    callback = _Callback(data="phome:book", user_id=1001)
    asyncio.run(_handler(router, "patient_home_book", kind="callback")(callback))

    assert booking_flow.start_or_resume_returning_calls == 1
    assert booking_flow.last_returning_kwargs is not None
    assert booking_flow.last_returning_kwargs.get("trusted_patient_id") == "pat_1"
    assert booking_flow.last_returning_kwargs.get("trusted_phone_snapshot") == "+15550101099"
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "new_booking_flow"
    assert callback.answers
    assert "Quick booking suggestion based on your recent visit" in callback.answers[-1]
    same_doctor_callback = _Callback(data="qbook:same_doctor:sess_1", user_id=1001)
    asyncio.run(_handler(router, "quick_book_same_doctor", kind="callback")(same_doctor_callback))
    assert booking_flow.apply_same_doctor_prefill_calls == 1
    assert same_doctor_callback.bot.edits
    assert "Choose a service" in same_doctor_callback.bot.edits[-1]["text"]


def test_book_entry_without_trusted_patient_falls_back_to_contact_prompt() -> None:
    router, runtime, booking_flow, _ = _build_router(recommendation_repository=None)

    message = _Message(text="/book", user_id=1001)
    asyncio.run(_handler(router, "book_entry")(message))

    assert booking_flow.start_or_resume_returning_calls == 1
    assert booking_flow.last_returning_kwargs is not None
    assert booking_flow.last_returning_kwargs.get("trusted_patient_id") is None
    assert booking_flow.last_returning_kwargs.get("trusted_phone_snapshot") is None
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "new_booking_contact"
    assert message.answers
    assert "Contact for booking" in message.answers[-1][0]
    assert "+7 999 123-45-67" in message.answers[-1][0]


def test_pat_a3_2_no_migration_directories_present() -> None:
    assert not Path("migrations").exists()
    assert not Path("alembic").exists()
