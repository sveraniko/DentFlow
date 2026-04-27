from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application.booking.orchestration_outcomes import OrchestrationSuccess
from app.application.booking.orchestration_outcomes import SlotUnavailableOutcome
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.common.i18n import I18nService
from app.domain.booking import AvailabilitySlot
from app.domain.booking import Booking
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, Service
from app.interfaces.bots.patient.router import make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore
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
        return SimpleNamespace(chat=self.chat, message_id=800 + len(self.answers))


class _CallbackMessage:
    def __init__(self, message_id: int = 701) -> None:
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
    def __init__(self, data: str, *, user_id: int = 1001, message_id: int = 701) -> None:
        self.data = data
        self.bot = _Bot()
        self.chat = SimpleNamespace(id=9001)
        self.from_user = SimpleNamespace(id=user_id)
        self.message = _CallbackMessage(message_id=message_id)
        self.answered: list[tuple[str, bool]] = []

    async def answer(self, text: str = "", show_alert: bool = False, reply_markup=None) -> None:  # noqa: ARG002
        self.answered.append((text, show_alert))
        return SimpleNamespace(chat=self.chat, message_id=self.message.message_id)


class _ReminderActions:
    def __init__(self, *, outcome_kind: str = "accepted", outcome_reason: str = "booking_confirmed", booking_id: str = "b1") -> None:
        self.outcome_kind = outcome_kind
        self.outcome_reason = outcome_reason
        self.booking_id = booking_id

    async def handle_action(self, **kwargs):  # noqa: ANN003
        return SimpleNamespace(kind=self.outcome_kind, reason=self.outcome_reason, booking_id=self.booking_id)


class _BookingFlowStub:
    def __init__(self) -> None:
        now = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
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
        self.request_reschedule_calls = 0
        self.start_patient_reschedule_calls = 0
        self.start_existing_booking_calls = 0
        self.start_or_resume_session_calls = 0
        self.start_or_resume_returning_calls = 0
        self.start_or_resume_existing_booking_calls = 0
        self.allowed_route_type_checks: list[frozenset[str] | None] = []
        self.reschedule_validation_ok = True
        self.selected_slot_id: str | None = None
        self.complete_patient_reschedule_calls = 0
        self.complete_patient_reschedule_outcome: object | None = None

    async def request_reschedule(self, **kwargs):  # noqa: ANN003
        self.request_reschedule_calls += 1
        return OrchestrationSuccess(kind="success", entity=self.booking)

    async def start_patient_reschedule_session(self, **kwargs):  # noqa: ANN003
        self.start_patient_reschedule_calls += 1
        session = SimpleNamespace(booking_session_id="sess_rsch_1")
        return SimpleNamespace(kind="ready", booking=self.booking, booking_session=session)

    async def start_existing_booking_control_for_booking(self, **kwargs):  # noqa: ANN003
        self.start_existing_booking_calls += 1
        session = SimpleNamespace(booking_session_id="sess_existing_1")
        return SimpleNamespace(kind="ready", booking=self.booking, booking_session=session)

    async def validate_active_session_callback(self, **kwargs):  # noqa: ANN003
        self.allowed_route_type_checks.append(kwargs.get("allowed_route_types"))
        return self.reschedule_validation_ok

    async def start_or_resume_session(self, **kwargs):  # noqa: ANN003
        self.start_or_resume_session_calls += 1
        return SimpleNamespace(booking_session_id="sess_new_booking_1")

    async def start_or_resume_returning_patient_booking(self, **kwargs):  # noqa: ANN003
        self.start_or_resume_returning_calls += 1
        session = await self.start_or_resume_session(**kwargs)
        from types import SimpleNamespace

        return SimpleNamespace(booking_session=session, trusted_shortcut_applied=False)


    async def start_or_resume_existing_booking_session(self, **kwargs):  # noqa: ANN003
        self.start_or_resume_existing_booking_calls += 1
        return SimpleNamespace(booking_session_id="sess_existing_lookup_1")

    async def determine_resume_panel(self, **kwargs):  # noqa: ANN003
        return SimpleNamespace(panel_key="service_selection", booking_session=SimpleNamespace(clinic_id="clinic_main", branch_id="branch_1"))

    async def list_services(self, **kwargs):  # noqa: ANN003
        return []

    async def list_slots_for_session(self, **kwargs):  # noqa: ANN003
        now = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
        return [
            AvailabilitySlot(
                slot_id="slot_new_1",
                clinic_id="clinic_main",
                doctor_id="doctor_1",
                start_at=datetime(2026, 4, 24, 10, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 4, 24, 10, 30, tzinfo=timezone.utc),
                status="open",
                visibility_policy="public",
                updated_at=now,
                branch_id="branch_1",
                service_scope={"service_ids": ["service_consult"]},
            )
        ]

    async def get_booking_session(self, **kwargs):  # noqa: ANN003
        return SimpleNamespace(
            booking_session_id="sess_rsch_1",
            clinic_id="clinic_main",
            telegram_user_id=1001,
            route_type="reschedule_booking_control",
            selected_slot_id=self.selected_slot_id,
            resolved_patient_id="pat_1",
            service_id="service_consult",
            doctor_id="doctor_1",
            branch_id="branch_1",
        )

    async def select_slot(self, **kwargs):  # noqa: ANN003
        self.selected_slot_id = kwargs.get("slot_id")
        return OrchestrationSuccess(kind="success", entity=SimpleNamespace())

    async def get_booking(self, **kwargs):  # noqa: ANN003
        return self.booking

    async def complete_patient_reschedule(self, **kwargs):  # noqa: ANN003
        self.complete_patient_reschedule_calls += 1
        if self.complete_patient_reschedule_outcome is not None:
            return self.complete_patient_reschedule_outcome
        now = datetime(2026, 4, 24, 10, 0, tzinfo=timezone.utc)
        self.booking = Booking(
            **{
                **asdict(self.booking),
                "slot_id": "slot_new_1",
                "scheduled_start_at": now,
                "scheduled_end_at": datetime(2026, 4, 24, 10, 30, tzinfo=timezone.utc),
                "status": "confirmed",
                "updated_at": now,
            }
        )
        return OrchestrationSuccess(kind="success", entity=self.booking)

    async def get_availability_slot(self, **kwargs):  # noqa: ANN003
        now = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
        return AvailabilitySlot(
            slot_id="slot_new_1",
            clinic_id="clinic_main",
            doctor_id="doctor_1",
            start_at=datetime(2026, 4, 24, 10, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 4, 24, 10, 30, tzinfo=timezone.utc),
            status="open",
            visibility_policy="public",
            updated_at=now,
            branch_id="branch_1",
            service_scope={"service_ids": ["service_consult"]},
        )

    def build_booking_snapshot(self, **kwargs):  # noqa: ANN003
        from app.interfaces.cards import BookingRuntimeSnapshot

        token = kwargs.get("state_token", "sess_existing_1")
        return BookingRuntimeSnapshot(
            booking_id="b1",
            state_token=token,
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


class _RepoNone:
    async def find_patient_ids_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> list[str]:
        return []


def _reference() -> ClinicReferenceService:
    repo = InMemoryClinicReferenceRepository()
    repo.upsert_clinic(Clinic(clinic_id="clinic_main", code="MAIN", display_name="Main", timezone="UTC", default_locale="en"))
    repo.upsert_branch(Branch(branch_id="branch_1", clinic_id="clinic_main", display_name="Main Branch", address_text="-", timezone="UTC"))
    repo.upsert_service(Service(service_id="service_consult", clinic_id="clinic_main", code="CONSULT", title_key="service.consult", duration_minutes=30))
    repo.upsert_doctor(Doctor(doctor_id="doctor_1", clinic_id="clinic_main", display_name="Dr One", specialty_code="dent", branch_id="branch_1"))
    return ClinicReferenceService(repo)


def _handler(router, name: str, *, kind: str = "callback"):
    handlers = router.callback_query.handlers if kind == "callback" else router.message.handlers
    for h in handlers:
        if h.callback.__name__ == name:
            return h.callback
    raise AssertionError(name)


def _build_router(*, reminder_actions: _ReminderActions | None = None, booking_flow: _BookingFlowStub | None = None):
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    flow = booking_flow or _BookingFlowStub()
    reminders = reminder_actions or _ReminderActions()
    router = make_router(
        i18n=i18n,
        booking_flow=flow,
        reference=_reference(),
        reminder_actions=reminders,
        recommendation_service=None,
        care_commerce_service=None,
        recommendation_repository=_RepoNone(),
        default_locale="en",
        card_runtime=runtime,
        card_callback_codec=codec,
    )
    return router, runtime, flow


def _last_callback_text(callback: _Callback) -> str:
    for text, _ in reversed(callback.answered):
        if text:
            return text
    if callback.message.answers:
        return callback.message.answers[-1][0]
    if callback.bot.edits:
        return callback.bot.edits[-1]["text"]
    return ""


def test_my_booking_reschedule_lands_in_canonical_reschedule_start_panel() -> None:
    router, runtime, flow = _build_router()
    asyncio.run(runtime.bind_actor_session_state(scope="patient_flow", actor_id=1001, payload={"booking_session_id": "sess_existing_1", "booking_mode": "existing_booking_control"}))
    callback = _Callback("mybk:reschedule:sess_existing_1:b1", user_id=1001)

    asyncio.run(_handler(router, "request_reschedule")(callback))

    assert flow.request_reschedule_calls == 1
    assert flow.start_patient_reschedule_calls == 1
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "reschedule_booking_control"
    assert state["booking_session_id"] == "sess_rsch_1"
    assert state["reschedule_booking_id"] == "b1"


def test_reminder_reschedule_accepted_lands_in_same_canonical_reschedule_start_panel() -> None:
    router, runtime, flow = _build_router(reminder_actions=_ReminderActions(outcome_kind="accepted", outcome_reason="reschedule_requested", booking_id="b1"))
    callback = _Callback("rem:reschedule:rem_1", user_id=1001)

    asyncio.run(_handler(router, "reminder_action_callback")(callback))

    assert flow.start_patient_reschedule_calls == 1
    sent_text, sent_keyboard = callback.message.answers[-1]
    assert "Reschedule mode started." in sent_text
    assert sent_keyboard is not None
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "reschedule_booking_control"
    assert state["booking_session_id"] == "sess_rsch_1"
    assert state["reschedule_booking_id"] == "b1"


def test_non_reschedule_reminder_actions_keep_existing_handoff_behavior() -> None:
    router, runtime, flow = _build_router(reminder_actions=_ReminderActions(outcome_kind="accepted", outcome_reason="booking_confirmed", booking_id="b1"))
    callback = _Callback("rem:confirm:rem_1", user_id=1001)

    asyncio.run(_handler(router, "reminder_action_callback")(callback))

    assert flow.start_existing_booking_calls == 1
    assert flow.start_patient_reschedule_calls == 0
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "existing_booking_control"
    assert state["booking_session_id"] == "sess_existing_1"


def test_active_reschedule_session_resume_from_book_returns_to_reschedule_panel() -> None:
    router, runtime, flow = _build_router()
    asyncio.run(runtime.bind_actor_session_state(scope="patient_flow", actor_id=1001, payload={"booking_session_id": "sess_rsch_1", "booking_mode": "reschedule_booking_control"}))
    message = _Message("/book", user_id=1001)

    asyncio.run(_handler(router, "book_entry", kind="message")(message))

    assert flow.start_or_resume_session_calls == 0
    assert flow.start_or_resume_returning_calls == 0
    assert message.answers
    assert "Reschedule mode started." in message.answers[-1][0]


def test_active_reschedule_with_selected_slot_resumes_to_review_from_book() -> None:
    router, runtime, flow = _build_router()
    flow.selected_slot_id = "slot_new_1"
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_rsch_1", "booking_mode": "reschedule_booking_control", "reschedule_booking_id": "b1"},
        )
    )
    message = _Message("/book", user_id=1001)

    asyncio.run(_handler(router, "book_entry", kind="message")(message))

    assert "Review your reschedule before confirming:" in message.answers[-1][0]


def test_my_booking_respects_active_reschedule_context_and_does_not_collapse() -> None:
    router, runtime, flow = _build_router()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_rsch_1", "booking_mode": "reschedule_booking_control", "reschedule_booking_id": "b1"},
        )
    )
    message = _Message("/my_booking", user_id=1001)

    asyncio.run(_handler(router, "my_booking_entry", kind="message")(message))

    assert flow.start_or_resume_session_calls == 0
    assert "Reschedule mode started." in message.answers[-1][0]


def test_phome_my_booking_has_parity_with_my_booking_for_active_reschedule() -> None:
    router, runtime, flow = _build_router()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_rsch_1", "booking_mode": "reschedule_booking_control", "reschedule_booking_id": "b1"},
        )
    )
    callback = _Callback("phome:my_booking", user_id=1001)

    asyncio.run(_handler(router, "patient_home_my_booking")(callback))

    assert flow.start_or_resume_session_calls == 0
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "reschedule_booking_control"
    assert state["booking_session_id"] == "sess_rsch_1"


def test_stale_reschedule_context_from_my_booking_is_bounded_and_normalized() -> None:
    router, runtime, flow = _build_router()
    flow.reschedule_validation_ok = False
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_rsch_1", "booking_mode": "reschedule_booking_control", "reschedule_booking_id": "b1"},
        )
    )
    message = _Message("/my_booking", user_id=1001)

    asyncio.run(_handler(router, "my_booking_entry", kind="message")(message))

    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] != "reschedule_booking_control"
    assert state["reschedule_booking_id"] == ""
    assert flow.start_or_resume_existing_booking_calls == 1
    assert "cannot open reschedule right now" in message.answers[0][0]


def test_stale_reschedule_start_callback_is_safely_rejected() -> None:
    router, runtime, flow = _build_router()
    flow.reschedule_validation_ok = False
    asyncio.run(runtime.bind_actor_session_state(scope="patient_flow", actor_id=1001, payload={"booking_session_id": "sess_rsch_1", "booking_mode": "reschedule_booking_control"}))
    callback = _Callback("rsch:start:sess_rsch_1", user_id=1001)

    asyncio.run(_handler(router, "reschedule_start_continue")(callback))

    assert callback.answered[-1] == ("This button is no longer active. Please use /book to continue.", True)


def test_reschedule_start_opens_real_slot_selection_panel() -> None:
    router, runtime, _ = _build_router()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={
                "booking_session_id": "sess_rsch_1",
                "booking_mode": "reschedule_booking_control",
                "reschedule_booking_id": "b1",
            },
        )
    )
    callback = _Callback("rsch:start:sess_rsch_1", user_id=1001)

    asyncio.run(_handler(router, "reschedule_start_continue")(callback))

    text = _last_callback_text(callback)
    assert "slots" in text.lower()


def test_reschedule_slot_selection_skips_contact_and_renders_review_panel() -> None:
    router, runtime, _ = _build_router()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={
                "booking_session_id": "sess_rsch_1",
                "booking_mode": "reschedule_booking_control",
                "reschedule_booking_id": "b1",
            },
        )
    )
    callback = _Callback("book:slot:sess_rsch_1:slot_new_1", user_id=1001)

    asyncio.run(_handler(router, "select_slot")(callback))

    text = _last_callback_text(callback)
    assert "Review your reschedule before confirming:" in text
    assert "Share your phone contact or type the number in chat." not in text
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "reschedule_booking_control"


def test_contact_input_in_reschedule_mode_is_bounded_and_not_interpreted() -> None:
    router, runtime, _ = _build_router()
    asyncio.run(runtime.bind_actor_session_state(scope="patient_flow", actor_id=1001, payload={"booking_session_id": "sess_rsch_1", "booking_mode": "reschedule_booking_control"}))
    contact = _Message("+15550000000", user_id=1001)

    asyncio.run(_handler(router, "on_contact_text", kind="message")(contact))

    assert contact.answers == []
    assert contact.bot.edits == []


def test_reschedule_confirm_happy_path_handoffs_to_canonical_booking_panel() -> None:
    router, runtime, flow = _build_router()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={
                "booking_session_id": "sess_rsch_1",
                "booking_mode": "reschedule_booking_control",
                "reschedule_booking_id": "b1",
            },
        )
    )
    callback = _Callback("rsch:confirm:sess_rsch_1", user_id=1001)

    asyncio.run(_handler(router, "reschedule_confirm")(callback))

    assert flow.complete_patient_reschedule_calls == 1
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "existing_booking_control"
    assert state["reschedule_booking_id"] == ""
    text = _last_callback_text(callback)
    assert "Your booking was rescheduled successfully." in text


def test_reminder_and_my_booking_reschedule_paths_reach_same_completed_semantics() -> None:
    router, runtime, flow = _build_router(reminder_actions=_ReminderActions(outcome_kind="accepted", outcome_reason="reschedule_requested", booking_id="b1"))
    reminder_callback = _Callback("rem:reschedule:rem_1", user_id=1001)
    asyncio.run(_handler(router, "reminder_action_callback")(reminder_callback))
    reminder_state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert reminder_state["booking_mode"] == "reschedule_booking_control"
    assert reminder_state["reschedule_booking_id"] == "b1"
    asyncio.run(_handler(router, "reschedule_confirm")(_Callback("rsch:confirm:sess_rsch_1", user_id=1001)))
    reminder_done_state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert reminder_done_state["booking_mode"] == "existing_booking_control"
    assert reminder_done_state["reschedule_booking_id"] == ""

    router2, runtime2, flow2 = _build_router()
    asyncio.run(runtime2.bind_actor_session_state(scope="patient_flow", actor_id=1001, payload={"booking_session_id": "sess_existing_1", "booking_mode": "existing_booking_control"}))
    asyncio.run(_handler(router2, "request_reschedule")(_Callback("mybk:reschedule:sess_existing_1:b1", user_id=1001)))
    my_state = asyncio.run(runtime2.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert my_state["booking_mode"] == "reschedule_booking_control"
    assert my_state["reschedule_booking_id"] == "b1"
    asyncio.run(_handler(router2, "reschedule_confirm")(_Callback("rsch:confirm:sess_rsch_1", user_id=1001)))
    my_done_state = asyncio.run(runtime2.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert my_done_state["booking_mode"] == "existing_booking_control"
    assert my_done_state["reschedule_booking_id"] == ""
    assert flow.complete_patient_reschedule_calls >= 1
    assert flow2.complete_patient_reschedule_calls >= 1


def test_reschedule_confirm_slot_unavailable_is_bounded_and_returns_to_slot_selection() -> None:
    flow = _BookingFlowStub()
    flow.complete_patient_reschedule_outcome = SlotUnavailableOutcome(kind="slot_unavailable", reason="selected slot is unavailable")
    router, runtime, _ = _build_router(booking_flow=flow)
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={
                "booking_session_id": "sess_rsch_1",
                "booking_mode": "reschedule_booking_control",
                "reschedule_booking_id": "b1",
            },
        )
    )
    callback = _Callback("rsch:confirm:sess_rsch_1", user_id=1001)

    asyncio.run(_handler(router, "reschedule_confirm")(callback))

    assert all(show_alert is False for _, show_alert in callback.answered)
    text = _last_callback_text(callback)
    assert "This slot is no longer available" in text
    assert "slots" in text.lower()


def test_pat_a4_2c_no_migration_directories_present() -> None:
    assert not Path("migrations").exists()
    assert not Path("alembic").exists()
