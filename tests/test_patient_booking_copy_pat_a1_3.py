from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.application.booking.orchestration_outcomes import OrchestrationSuccess
from app.application.booking.telegram_flow import BookingCardView, BookingResumePanel, PatientResolutionFlowResult
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.common.i18n import I18nService
from app.domain.booking import AvailabilitySlot, Booking, BookingSession
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
        return SimpleNamespace(chat=self.chat, message_id=500 + len(self.answers))


class _CallbackMessage:
    def __init__(self, message_id: int) -> None:
        self.chat = SimpleNamespace(id=9001)
        self.message_id = message_id


class _Callback:
    def __init__(self, data: str, *, user_id: int, message_id: int) -> None:
        self.data = data
        self.bot = _Bot()
        self.chat = SimpleNamespace(id=9001)
        self.from_user = SimpleNamespace(id=user_id)
        self.message = _CallbackMessage(message_id=message_id)
        self.answers: list[str] = []

    async def answer(self, text: str = "", show_alert: bool = False, reply_markup=None) -> None:
        if text:
            self.answers.append(text)
        return SimpleNamespace(chat=self.chat, message_id=self.message.message_id)


class _ReminderActions:
    async def handle_action(self, **kwargs):  # noqa: ANN003
        return SimpleNamespace(kind="invalid")


class _BookingFlowStub:
    def __init__(self, *, booking_status: str = "pending_confirmation") -> None:
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
            doctor_preference_type="specific",
            doctor_id="doctor_1",
            doctor_code_raw=None,
            selected_slot_id="slot_1",
            selected_hold_id="hold_1",
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
        self.finalize_calls = 0
        self.booking_status = booking_status

    async def start_or_resume_session(self, **kwargs):  # noqa: ANN003
        return self.session

    async def start_or_resume_returning_patient_booking(self, **kwargs):  # noqa: ANN003
        session = await self.start_or_resume_session(**kwargs)
        from types import SimpleNamespace

        return SimpleNamespace(booking_session=session, trusted_shortcut_applied=False)


    async def determine_resume_panel(self, **kwargs):  # noqa: ANN003
        return BookingResumePanel(panel_key="contact_collection", booking_session=self.session)

    async def validate_active_session_callback(self, **kwargs):  # noqa: ANN003
        return True

    def list_services(self, *, clinic_id: str):
        return []

    def list_doctors(self, *, clinic_id: str, branch_id: str | None = None):
        return []

    async def list_slots_for_session(self, **kwargs):  # noqa: ANN003
        return [self.slot]

    async def select_slot(self, **kwargs):  # noqa: ANN003
        return OrchestrationSuccess(kind="success", entity=self.session)

    async def set_contact_phone(self, *, booking_session_id: str, phone: str):
        self.session = BookingSession(**{**asdict(self.session), "contact_phone_snapshot": phone})
        return self.session

    async def resolve_patient_from_contact(self, **kwargs):  # noqa: ANN003
        return PatientResolutionFlowResult(kind="exact_match", booking_session=self.session)

    async def mark_review_ready(self, **kwargs):  # noqa: ANN003
        self.session = BookingSession(**{**asdict(self.session), "status": "review_ready"})
        return OrchestrationSuccess(kind="success", entity=self.session)

    async def get_booking_session(self, *, booking_session_id: str):
        return self.session if booking_session_id == self.session.booking_session_id else None

    async def get_availability_slot(self, *, slot_id: str):
        return self.slot if slot_id == self.slot.slot_id else None

    async def finalize(self, **kwargs):  # noqa: ANN003
        self.finalize_calls += 1
        booking = Booking(
            booking_id="bk_1",
            clinic_id="clinic_main",
            patient_id="pat_1",
            doctor_id=self.session.doctor_id,
            service_id=self.session.service_id or "service_consult",
            booking_mode="service_first",
            source_channel="telegram",
            scheduled_start_at=self.slot.start_at,
            scheduled_end_at=self.slot.end_at,
            status=self.booking_status,
            confirmation_required=True,
            created_at=self.slot.start_at,
            updated_at=self.slot.start_at,
            branch_id=self.session.branch_id,
            slot_id=self.slot.slot_id,
        )
        return OrchestrationSuccess(kind="success", entity=booking)

    def build_booking_card(self, *, booking: Booking) -> BookingCardView:
        return BookingCardView(
            booking_id=booking.booking_id,
            doctor_label=booking.doctor_id or "-",
            service_label=booking.service_id,
            datetime_label=booking.scheduled_start_at.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M %Z"),
            branch_label=booking.branch_id or "-",
            status_label=f"booking.status.{booking.status}",
            next_step_key="patient.booking.card.next.pending_confirmation",
        )


def _reference(*, clinic_tz: str = "Europe/Berlin", include_refs: bool = True, service_title_key: str = "service.cleaning") -> ClinicReferenceService:
    repo = InMemoryClinicReferenceRepository()
    repo.upsert_clinic(Clinic(clinic_id="clinic_main", code="MAIN", display_name="Main", timezone=clinic_tz, default_locale="en"))
    if include_refs:
        repo.upsert_branch(Branch(branch_id="branch_1", clinic_id="clinic_main", display_name="Main Branch", address_text="-", timezone=clinic_tz))
        repo.upsert_doctor(Doctor(doctor_id="doctor_1", clinic_id="clinic_main", display_name="Dr One", specialty_code="dent", branch_id="branch_1"))
    repo.upsert_service(Service(service_id="service_consult", clinic_id="clinic_main", code="CONSULT", title_key=service_title_key, duration_minutes=30))
    return ClinicReferenceService(repo)


def _handler(router, name: str, *, kind: str = "message"):
    handlers = router.message.handlers if kind == "message" else router.callback_query.handlers
    for h in handlers:
        if h.callback.__name__ == name:
            return h.callback
    raise AssertionError(name)


def _build(*, clinic_tz: str = "Europe/Berlin", include_refs: bool = True, service_title_key: str = "service.cleaning", booking_status: str = "pending_confirmation"):
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    booking_flow = _BookingFlowStub(booking_status=booking_status)
    router = make_router(
        i18n=i18n,
        booking_flow=booking_flow,
        reference=_reference(clinic_tz=clinic_tz, include_refs=include_refs, service_title_key=service_title_key),
        reminder_actions=_ReminderActions(),
        default_locale="en",
        card_runtime=runtime,
        card_callback_codec=codec,
    )
    return router, booking_flow, runtime


def _prepare_review(router, runtime, booking_flow) -> str:
    asyncio.run(runtime.bind_actor_session_state(scope="patient_flow", actor_id=1001, payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_contact", "care": {}}))
    msg = _Message(text="+1 555 123 1234", user_id=1001)
    asyncio.run(_handler(router, "on_contact_text")(msg))
    return msg.answers[-1][0]


def _finalize_and_get_text(router) -> str:
    callback = _Callback(data="book:confirm:sess_1", user_id=1001, message_id=500)
    asyncio.run(_handler(router, "confirm_new_booking", kind="callback")(callback))
    return callback.bot.edits[-1]["text"]


def test_review_uses_localized_human_service_label() -> None:
    router, booking_flow, runtime = _build()
    review_text = _prepare_review(router, runtime, booking_flow)
    assert "Service: Teeth cleaning" in review_text


def test_success_uses_human_labels_and_localized_status_in_normal_path() -> None:
    router, booking_flow, runtime = _build()
    _prepare_review(router, runtime, booking_flow)
    success_text = _finalize_and_get_text(router)
    assert "Doctor: Dr One" in success_text
    assert "Service: Teeth cleaning" in success_text
    assert "Branch: Main Branch" in success_text
    assert "Status: pending clinic confirmation" in success_text
    assert "doctor_1" not in success_text
    assert "service_consult" not in success_text
    assert "branch_1" not in success_text


def test_review_fallback_is_safe_when_slot_and_reference_rows_are_missing() -> None:
    router, booking_flow, runtime = _build(include_refs=False)
    booking_flow.session = BookingSession(**{**asdict(booking_flow.session), "selected_slot_id": "slot_missing"})
    review_text = _prepare_review(router, runtime, booking_flow)
    assert "Doctor: -" in review_text
    assert "Branch: not selected" in review_text
    assert "Time: -" in review_text


def test_invalid_timezone_falls_back_to_utc_without_crash() -> None:
    router, booking_flow, runtime = _build(clinic_tz="Mars/Phobos")
    review_text = _prepare_review(router, runtime, booking_flow)
    assert "Date: 22 Apr 2026" in review_text
    assert "Time: 10:00" in review_text
    assert "UTC" not in review_text


def test_title_key_does_not_leak_when_service_localization_is_missing() -> None:
    router, booking_flow, runtime = _build(service_title_key="service.unknown_untranslated")
    review_text = _prepare_review(router, runtime, booking_flow)
    success_text = _finalize_and_get_text(router)
    assert "service.unknown_untranslated" not in review_text
    assert "service.unknown_untranslated" not in success_text
    assert "Service: CONSULT" in review_text
    assert "Service: CONSULT" in success_text
