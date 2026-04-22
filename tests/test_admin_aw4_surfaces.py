from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application.access import AccessResolver, InMemoryAccessRepository
from app.application.admin.workdesk import CarePickupQueueRow, OpsIssueQueueRow, WaitlistQueueRow
from app.application.booking.orchestration_outcomes import OrchestrationSuccess
from app.application.search.models import PatientSearchResponse, PatientSearchResult, SearchResultOrigin
from app.common.i18n import I18nService
from app.domain.access_identity.models import (
    ActorIdentity,
    ActorStatus,
    ActorType,
    ClinicRoleAssignment,
    RoleCode,
    StaffMember,
    StaffStatus,
    TelegramBinding,
)
from app.interfaces.bots.admin.router import make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore
from app.interfaces.cards.models import SourceContext
from app.interfaces.cards.runtime_state import InMemoryRedis


class _Message:
    def __init__(self, text: str, user_id: int = 501) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.answers: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append((text, reply_markup))


class _CallbackMessage:
    def __init__(self) -> None:
        self.edits: list[tuple[str, object | None]] = []

    async def edit_text(self, text: str, reply_markup=None) -> None:
        self.edits.append((text, reply_markup))


class _Callback:
    def __init__(self, data: str, user_id: int = 501) -> None:
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.message = _CallbackMessage()
        self.answers: list[str] = []

    async def answer(self, text: str, show_alert: bool = False) -> None:
        self.answers.append(text)


class _Reference:
    def get_clinic(self, clinic_id: str):
        return SimpleNamespace(default_locale="en")

    def get_service(self, clinic_id: str, service_id: str):
        return None

    def get_branch(self, clinic_id: str, branch_id: str):
        return SimpleNamespace(display_name="Main")


class _Search:
    async def search_patients(self, query):
        row = PatientSearchResult(
            patient_id="p1",
            clinic_id=query.clinic_id,
            display_name="Jane Roe",
            patient_number="1001",
            primary_phone_normalized="+15551234567",
            active_flags_summary="vip",
            status="active",
            origin=SearchResultOrigin.POSTGRES_STRICT,
        )
        return PatientSearchResponse(exact_matches=[row], suggestions=[])


class _BookingFlow:
    def __init__(self) -> None:
        self._sessions: dict[str, SimpleNamespace] = {}
        self.reads = self
        self.orchestration = SimpleNamespace(
            confirm_booking=self._ok,
            request_booking_reschedule=self._ok,
            cancel_booking=self._ok,
            booking_state_service=SimpleNamespace(transition_booking=self._ok),
        )

    async def _ok(self, **kwargs):
        return SimpleNamespace(kind="success", entity=self._booking())

    async def get_booking(self, booking_id: str):
        return self._booking(booking_id=booking_id)

    async def start_admin_reschedule_session(self, *, clinic_id: str, telegram_user_id: int, booking_id: str):
        session_id = f"sess_{booking_id}"
        self._sessions[session_id] = SimpleNamespace(
            booking_session_id=session_id,
            clinic_id=clinic_id,
            telegram_user_id=telegram_user_id,
            route_type="reschedule_booking_control",
            selected_slot_id=None,
        )
        return SimpleNamespace(kind="ready", booking_session=self._sessions[session_id])

    async def validate_active_session_callback(self, **kwargs):
        return kwargs.get("callback_session_id") in self._sessions

    async def list_slots_for_session(self, *, booking_session_id: str):
        return [SimpleNamespace(slot_id="slot_ok", start_at=datetime(2026, 4, 21, 11, 0, tzinfo=timezone.utc))]

    async def select_slot(self, *, booking_session_id: str, slot_id: str):
        self._sessions[booking_session_id].selected_slot_id = slot_id
        return OrchestrationSuccess(kind="success", entity=self._sessions[booking_session_id])

    async def get_booking_session(self, *, booking_session_id: str):
        return self._sessions.get(booking_session_id)

    async def get_availability_slot(self, *, slot_id: str):
        return SimpleNamespace(slot_id=slot_id, start_at=datetime(2026, 4, 21, 11, 0, tzinfo=timezone.utc))

    async def complete_admin_reschedule_from_session(self, **kwargs):
        return OrchestrationSuccess(kind="success", entity=self._booking(status="confirmed"))

    def build_booking_snapshot(self, **kwargs):
        booking = kwargs["booking"]
        return SimpleNamespace(
            doctor_label="Dr A",
            service_label="Consultation",
            branch_label="Main",
            next_step_note_key="patient.booking.card.next.default",
            booking_id=booking.booking_id,
            state_token=booking.booking_id,
            role_variant="admin",
            scheduled_start_at=datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc),
            timezone_name="UTC",
            patient_label="Jane Roe",
            status=booking.status,
            source_channel="telegram",
            patient_contact=None,
            compact_flags=(),
            reminder_summary=None,
            reschedule_summary=None,
            recommendation_summary=None,
            care_order_summary=None,
            chart_summary_entry=None,
        )

    def _booking(self, booking_id: str = "b1", status: str = "pending_confirmation"):
        return SimpleNamespace(
            booking_id=booking_id,
            patient_id="p1",
            doctor_id="d1",
            service_id="s1",
            clinic_id="c1",
            branch_id="br1",
            status=status,
            source_channel="telegram",
            scheduled_start_at=datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc),
        )


class _Workdesk:
    async def get_today_schedule(self, **kwargs):
        return []

    async def get_waitlist_queue(self, **kwargs):
        return [
            WaitlistQueueRow(
                clinic_id="c1",
                branch_id="br1",
                waitlist_entry_id="w1",
                patient_id="p1",
                preferred_doctor_id="d1",
                preferred_service_id="s1",
                preferred_time_window_summary="morning",
                status="active",
                patient_display_name="Jane Roe",
                doctor_display_name="Dr A",
                service_label="admin.today.title",
                updated_at=datetime.now(timezone.utc),
            )
        ]

    async def get_care_pickup_queue(self, **kwargs):
        return [
            CarePickupQueueRow(
                clinic_id="c1",
                branch_id="br1",
                care_order_id="co1",
                patient_id="p1",
                pickup_status="ready_for_pickup",
                local_ready_date=date(2026, 4, 19),
                local_ready_time="14:00",
                patient_display_name="Jane Roe",
                branch_label="Main",
                compact_item_summary="Kit",
                updated_at=datetime.now(timezone.utc),
            )
        ]

    async def get_ops_issue_queue(self, **kwargs):
        return [
            OpsIssueQueueRow(
                clinic_id="c1",
                branch_id="br1",
                issue_type="confirmation_no_response",
                issue_ref_id="b1",
                issue_status="open",
                severity="high",
                patient_id="p1",
                booking_id="b1",
                care_order_id=None,
                local_related_date=date(2026, 4, 19),
                local_related_time="08:00",
                summary_text="raw",
                patient_display_name="Jane Roe",
                updated_at=datetime.now(timezone.utc),
            ),
            OpsIssueQueueRow(
                clinic_id="c1",
                branch_id="br1",
                issue_type="reminder_failed",
                issue_ref_id="r_fail_1",
                issue_status="open",
                severity="medium",
                patient_id="p1",
                booking_id="b1",
                care_order_id=None,
                local_related_date=date(2026, 4, 19),
                local_related_time="10:00",
                summary_text="raw",
                patient_display_name="Jane Roe",
                updated_at=datetime.now(timezone.utc),
            ),
            OpsIssueQueueRow(
                clinic_id="c1",
                branch_id="br1",
                issue_type="reminder_failed",
                issue_ref_id="r_fail_2",
                issue_status="open",
                severity="medium",
                patient_id="p1",
                booking_id=None,
                care_order_id=None,
                local_related_date=date(2026, 4, 19),
                local_related_time="10:00",
                summary_text="raw",
                patient_display_name="Jane Roe",
                updated_at=datetime.now(timezone.utc),
            ),
        ]


class _CareService:
    async def get_order(self, care_order_id: str):
        return SimpleNamespace(care_order_id=care_order_id, patient_id="p1", status="ready_for_pickup", pickup_branch_id="br1")

    async def apply_admin_order_action(self, *, care_order_id: str, action: str, **kwargs):
        return SimpleNamespace(care_order_id=care_order_id, status="fulfilled")


class _ReminderRecovery:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._seen: set[str] = set()

    async def retry_failed_reminder(self, *, reminder_id: str, now):  # noqa: ANN001
        self.calls.append(reminder_id)
        if reminder_id in self._seen:
            return SimpleNamespace(outcome="already_pending", reminder_id=f"rem_mr_{reminder_id}")
        self._seen.add(reminder_id)
        return SimpleNamespace(outcome="scheduled", reminder_id=f"rem_mr_{reminder_id}")


def _access() -> AccessResolver:
    repo = InMemoryAccessRepository()
    now = datetime(2026, 4, 17, tzinfo=timezone.utc)
    repo.upsert_actor_identity(ActorIdentity(actor_id="a1", actor_type=ActorType.STAFF, display_name="Admin", status=ActorStatus.ACTIVE, locale="en"))
    repo.upsert_telegram_binding(TelegramBinding(telegram_binding_id="t1", actor_id="a1", telegram_user_id=501))
    repo.upsert_staff_member(StaffMember(staff_id="s1", actor_id="a1", clinic_id="c1", full_name="Admin", display_name="Admin", staff_status=StaffStatus.ACTIVE))
    repo.upsert_role_assignment(ClinicRoleAssignment(role_assignment_id="r1", staff_id="s1", clinic_id="c1", role_code=RoleCode.ADMIN, granted_at=now))
    return AccessResolver(repo)


def _router():
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    recovery = _ReminderRecovery()
    return make_router(
        i18n,
        _access(),
        _Reference(),
        _BookingFlow(),
        search_service=_Search(),
        stt_service=SimpleNamespace(),
        voice_mode_store=SimpleNamespace(),
        care_commerce_service=_CareService(),
        admin_workdesk=_Workdesk(),
        reminder_recovery=recovery,
        default_locale="en",
        max_voice_duration_sec=60,
        max_voice_file_size_bytes=1024,
        voice_mode_ttl_sec=30,
        card_runtime=runtime,
        card_callback_codec=codec,
    ), codec, recovery


def _handler(router, name: str, kind: str = "message"):
    handlers = router.message.handlers if kind == "message" else router.callback_query.handlers
    for h in handlers:
        if h.callback.__name__ == name:
            return h.callback
    raise AssertionError(name)


def test_admin_patients_search_and_open_card() -> None:
    router, codec, _ = _router()
    msg = _Message("/admin_patients jane")
    asyncio.run(_handler(router, "admin_patients")(msg))
    text, keyboard = msg.answers[-1]
    assert "Patients" in text
    cb = keyboard.inline_keyboard[0][0].callback_data
    decoded = asyncio.run(codec.decode(cb))
    assert decoded.source_context == SourceContext.ADMIN_PATIENTS

    callback = _Callback(cb)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(callback))
    assert any("Jane Roe" in row[0] for row in callback.message.edits)


def test_admin_care_pickups_queue_and_action() -> None:
    router, _, _ = _router()
    msg = _Message("/admin_care_pickups")
    asyncio.run(_handler(router, "admin_care_pickups")(msg))
    text, keyboard = msg.answers[-1]
    assert "Care Pickups Queue" in text

    action_cb = keyboard.inline_keyboard[2][0].callback_data
    callback = _Callback(action_cb)
    asyncio.run(_handler(router, "admin_care_pickups_callback", kind="callback")(callback))
    assert any("Care Pickups Queue" in row[0] for row in callback.message.edits)


def test_admin_care_pickups_detail_has_back_to_queue() -> None:
    router, _, _ = _router()
    msg = _Message("/admin_care_pickups")
    asyncio.run(_handler(router, "admin_care_pickups")(msg))
    _, keyboard = msg.answers[-1]
    open_cb = keyboard.inline_keyboard[1][0].callback_data
    callback = _Callback(open_cb)
    asyncio.run(_handler(router, "admin_care_pickups_callback", kind="callback")(callback))
    _, detail_markup = callback.message.edits[-1]
    assert detail_markup is not None
    back_cb = detail_markup.inline_keyboard[0][0].callback_data
    back = _Callback(back_cb)
    asyncio.run(_handler(router, "admin_care_pickups_callback", kind="callback")(back))
    assert any("Care Pickups Queue" in row[0] for row in back.message.edits)


def test_admin_issues_localized_and_booking_open() -> None:
    router, codec, _ = _router()
    msg = _Message("/admin_issues")
    asyncio.run(_handler(router, "admin_issues")(msg))
    text, keyboard = msg.answers[-1]
    assert "did not respond" in text

    cb = keyboard.inline_keyboard[1][0].callback_data
    decoded = asyncio.run(codec.decode(cb))
    assert decoded.source_context == SourceContext.ADMIN_ISSUES


def test_admin_issues_patient_linked_open_has_back_to_queue() -> None:
    router, _, _ = _router()
    msg = _Message("/admin_issues")
    asyncio.run(_handler(router, "admin_issues")(msg))
    _, keyboard = msg.answers[-1]
    patient_cb = keyboard.inline_keyboard[4][0].callback_data
    callback = _Callback(patient_cb)
    asyncio.run(_handler(router, "admin_issues_object_callback", kind="callback")(callback))
    panel_text, panel_markup = callback.message.edits[-1]
    assert "Jane Roe" in panel_text
    assert panel_markup is not None
    back_cb = panel_markup.inline_keyboard[0][0].callback_data
    back = _Callback(back_cb)
    asyncio.run(_handler(router, "admin_issues_object_callback", kind="callback")(back))
    assert any("Issues Queue" in row[0] for row in back.message.edits)


def test_waitlist_detail_uses_localized_service_label() -> None:
    router, _, _ = _router()
    msg = _Message("/admin_waitlist")
    asyncio.run(_handler(router, "admin_waitlist")(msg))
    _, keyboard = msg.answers[-1]
    open_cb = keyboard.inline_keyboard[1][0].callback_data
    callback = _Callback(open_cb)
    asyncio.run(_handler(router, "admin_waitlist_callback", kind="callback")(callback))
    assert any("Today Workdesk" in row[0] for row in callback.message.edits)


def test_admin_issues_retry_action_is_visible_and_bounded() -> None:
    router, _, recovery = _router()
    msg = _Message("/admin_issues")
    asyncio.run(_handler(router, "admin_issues")(msg))
    _, keyboard = msg.answers[-1]
    retry_cb = keyboard.inline_keyboard[3][0].callback_data

    first = _Callback(retry_cb)
    asyncio.run(_handler(router, "admin_issues_object_callback", kind="callback")(first))
    assert "Retry scheduled." in first.answers[-1]

    second = _Callback(retry_cb)
    asyncio.run(_handler(router, "admin_issues_object_callback", kind="callback")(second))
    assert "Retry already scheduled." in second.answers[-1]
    assert recovery.calls.count("r_fail_1") == 2
