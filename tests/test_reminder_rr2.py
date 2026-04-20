from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from app.application.communication.delivery import render_booking_reminder_message
from app.application.communication.recovery import ReminderRecoveryService
from app.application.communication.reminders import BookingReminderPlanner
from app.application.policy import InMemoryPolicyRepository, PolicyResolver
from app.domain.booking import Booking, BookingSession
from app.domain.communication import ReminderJob
from app.domain.policy_config.models import PolicySet, PolicyValue


def _booking(*, status: str = "pending_confirmation") -> Booking:
    now = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
    return Booking(
        booking_id="b1",
        clinic_id="clinic_main",
        branch_id="branch_1",
        patient_id="pat_1",
        doctor_id="doctor_1",
        service_id="svc_1",
        slot_id="slot_1",
        booking_mode="patient_bot",
        source_channel="telegram",
        scheduled_start_at=now + timedelta(days=1),
        scheduled_end_at=now + timedelta(days=1, minutes=30),
        status=status,
        confirmation_required=True,
        created_at=now,
        updated_at=now,
    )


def _reminder(*, reminder_type: str, sent_at: datetime | None = None) -> ReminderJob:
    now = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
    return ReminderJob(
        reminder_id="r1",
        clinic_id="clinic_main",
        patient_id="pat_1",
        booking_id="b1",
        care_order_id=None,
        recommendation_id=None,
        reminder_type=reminder_type,
        channel="telegram",
        status="sent" if sent_at else "scheduled",
        scheduled_for=now,
        payload_key="k",
        locale_at_send_time="en",
        planning_group="g1",
        supersedes_reminder_id=None,
        created_at=now,
        updated_at=now,
        sent_at=sent_at,
    )


def test_cadence_is_explicit_for_confirmation_day_before_and_same_day() -> None:
    now = datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc)
    planner = BookingReminderPlanner(PolicyResolver(InMemoryPolicyRepository()))
    plan = planner.build_plan(booking=_booking(), now=now)
    assert [item.reminder_type for item in plan] == ["booking_confirmation", "booking_previsit", "booking_day_of"]


def test_rendering_localized_copy_and_local_time() -> None:
    booking = _booking()

    class _TZ:
        def resolve_timezone(self, *, clinic_id: str, branch_id: str | None) -> str:
            return "Europe/Moscow"

    en = render_booking_reminder_message(reminder=_reminder(reminder_type="booking_no_response_followup"), booking=booking, timezone_resolver=_TZ())
    assert "DentFlow reminder" in en.text
    assert "MSK" in en.text
    assert "request a reschedule" in en.text.lower()

    ru_reminder = ReminderJob(**{**asdict(_reminder(reminder_type="booking_day_of")), "locale_at_send_time": "ru"})
    ru = render_booking_reminder_message(reminder=ru_reminder, booking=booking, timezone_resolver=_TZ())
    assert "Напоминание DentFlow" in ru.text
    assert "Сегодня ваш визит" in ru.text


class _RecoveryRepo:
    def __init__(self, reminder: ReminderJob) -> None:
        self.jobs = {reminder.reminder_id: reminder}

    async def list_stale_queued_reminders(self, *, queued_before: datetime, limit: int):
        return []

    async def reclaim_stale_queued_reminder(self, *, reminder_id: str, retry_at: datetime):
        return False

    async def mark_reminder_failed(self, *, reminder_id: str, failed_at: datetime, error_text: str):
        return False

    async def list_failed_booking_reminders(self, *, limit: int):
        return []

    async def list_confirmation_no_response_candidates(self, *, sent_before: datetime, limit: int):
        return [row for row in self.jobs.values() if row.reminder_type == "booking_confirmation"]

    async def create_reminder_job(self, item: ReminderJob) -> None:
        self.jobs[item.reminder_id] = item

    async def get_reminder(self, *, reminder_id: str) -> ReminderJob | None:
        return self.jobs.get(reminder_id)


class _RecoveryBookingRepo:
    async def get_booking(self, booking_id: str) -> Booking | None:
        return _booking(status="pending_confirmation")

    async def find_latest_session_for_patient(self, *, clinic_id: str, patient_id: str) -> BookingSession | None:
        now = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
        return BookingSession(
            booking_session_id="s1",
            clinic_id=clinic_id,
            telegram_user_id=123,
            resolved_patient_id=patient_id,
            status="review_ready",
            route_type="service_first",
            expires_at=now + timedelta(hours=1),
            created_at=now,
            updated_at=now,
        )

    async def upsert_admin_escalation(self, item):  # noqa: ANN001
        return None

    async def get_admin_escalation(self, admin_escalation_id: str):
        return None

    async def list_open_admin_escalations(self, *, clinic_id: str, limit: int):
        return []


def test_no_response_followup_is_scheduled_before_escalation() -> None:
    now = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
    policy_repo = InMemoryPolicyRepository()
    policy_set = PolicySet(policy_set_id="ps1", policy_family="booking", scope_type="clinic", scope_ref="clinic_main")
    policy_repo.upsert_policy_set(policy_set)
    policy_repo.add_policy_value(PolicyValue(policy_value_id="pv1", policy_set_id="ps1", policy_key="booking.non_response_escalation_enabled", value_type="bool", value_json=True))
    policy_repo.add_policy_value(PolicyValue(policy_value_id="pv2", policy_set_id="ps1", policy_key="booking.no_response_followup_enabled", value_type="bool", value_json=True))
    policy_repo.add_policy_value(PolicyValue(policy_value_id="pv3", policy_set_id="ps1", policy_key="booking.no_response_followup_delay_minutes", value_type="int", value_json=15))
    policy_repo.add_policy_value(PolicyValue(policy_value_id="pv4", policy_set_id="ps1", policy_key="booking.non_response_escalation_after_followup_minutes", value_type="int", value_json=30))

    base = _reminder(reminder_type="booking_confirmation", sent_at=now - timedelta(minutes=90))
    service = ReminderRecoveryService(_RecoveryRepo(base), _RecoveryBookingRepo(), PolicyResolver(policy_repo))
    stats = asyncio.run(service.detect_confirmation_no_response(now=now, limit=10))
    assert stats.no_response_escalated == 0
    assert "rem_nr_r1" in service.reminder_repository.jobs
