from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from app.application.booking.telegram_flow import BookingPatientFlowService
from app.application.communication import ReminderRecoveryService
from app.application.policy import InMemoryPolicyRepository, PolicyResolver
from app.domain.booking import AdminEscalation, Booking, BookingSession
from app.domain.policy_config.models import PolicySet, PolicyValue
from app.domain.communication import ReminderJob


class _ReminderRepo:
    def __init__(self, jobs: list[ReminderJob]) -> None:
        self.jobs = {j.reminder_id: j for j in jobs}

    async def list_stale_queued_reminders(self, *, queued_before: datetime, limit: int) -> list[ReminderJob]:
        rows = [j for j in self.jobs.values() if j.status == "queued" and j.queued_at is not None and j.queued_at <= queued_before]
        return sorted(rows, key=lambda x: x.queued_at or x.updated_at)[:limit]

    async def reclaim_stale_queued_reminder(self, *, reminder_id: str, retry_at: datetime) -> bool:
        row = self.jobs[reminder_id]
        if row.status != "queued":
            return False
        self.jobs[reminder_id] = ReminderJob(**{**asdict(row), "status": "scheduled", "scheduled_for": retry_at, "queued_at": None, "updated_at": retry_at})
        return True

    async def mark_reminder_failed(self, *, reminder_id: str, failed_at: datetime, error_text: str) -> bool:
        row = self.jobs[reminder_id]
        if row.status != "queued":
            return False
        self.jobs[reminder_id] = ReminderJob(
            **{
                **asdict(row),
                "status": "failed",
                "updated_at": failed_at,
                "queued_at": None,
                "delivery_attempts_count": row.delivery_attempts_count + 1,
                "last_error_code": error_text,
                "last_error_text": error_text,
                "last_failed_at": failed_at,
            }
        )
        return True

    async def list_failed_booking_reminders(self, *, limit: int) -> list[ReminderJob]:
        rows = [j for j in self.jobs.values() if j.status == "failed" and j.booking_id is not None]
        return rows[:limit]

    async def list_confirmation_no_response_candidates(self, *, sent_before: datetime, limit: int) -> list[ReminderJob]:
        rows = [
            j
            for j in self.jobs.values()
            if j.status == "sent" and j.reminder_type == "booking_confirmation" and j.sent_at is not None and j.sent_at <= sent_before and j.acknowledged_at is None
        ]
        return rows[:limit]

    async def create_reminder_job(self, item: ReminderJob) -> None:
        self.jobs[item.reminder_id] = item

    async def get_reminder(self, *, reminder_id: str) -> ReminderJob | None:
        return self.jobs.get(reminder_id)


class _BookingRepo:
    def __init__(self, bookings: list[Booking], sessions: list[BookingSession]) -> None:
        self.bookings = {b.booking_id: b for b in bookings}
        self.sessions = sessions
        self.escalations: dict[str, AdminEscalation] = {}

    async def get_booking(self, booking_id: str) -> Booking | None:
        return self.bookings.get(booking_id)

    async def find_latest_session_for_patient(self, *, clinic_id: str, patient_id: str) -> BookingSession | None:
        for row in sorted(self.sessions, key=lambda x: x.updated_at, reverse=True):
            if row.clinic_id == clinic_id and row.resolved_patient_id == patient_id:
                return row
        return None

    async def upsert_admin_escalation(self, item: AdminEscalation) -> None:
        self.escalations[item.admin_escalation_id] = item

    async def get_admin_escalation(self, admin_escalation_id: str) -> AdminEscalation | None:
        return self.escalations.get(admin_escalation_id)

    async def list_open_admin_escalations(self, *, clinic_id: str, limit: int) -> list[AdminEscalation]:
        rows = [e for e in self.escalations.values() if e.clinic_id == clinic_id and e.status == "open"]
        return rows[:limit]


def _booking(*, status: str = "pending_confirmation") -> Booking:
    now = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
    return Booking(
        booking_id="b1",
        clinic_id="clinic_main",
        patient_id="pat_1",
        doctor_id="doctor_1",
        service_id="svc",
        booking_mode="patient_bot",
        source_channel="telegram",
        scheduled_start_at=now + timedelta(days=1),
        scheduled_end_at=now + timedelta(days=1, minutes=30),
        status=status,
        confirmation_required=True,
        created_at=now,
        updated_at=now,
        branch_id=None,
        slot_id=None,
    )


def _session() -> BookingSession:
    now = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
    return BookingSession(
        booking_session_id="s1",
        clinic_id="clinic_main",
        telegram_user_id=123,
        resolved_patient_id="pat_1",
        status="review_ready",
        route_type="service_first",
        expires_at=now + timedelta(hours=2),
        created_at=now,
        updated_at=now,
    )


def _reminder(*, status: str, reminder_type: str = "booking_previsit", queued_delta_min: int = 30, sent_delta_min: int = 45, attempts: int = 0) -> ReminderJob:
    now = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
    return ReminderJob(
        reminder_id="r1",
        clinic_id="clinic_main",
        patient_id="pat_1",
        booking_id="b1",
        care_order_id=None,
        recommendation_id=None,
        reminder_type=reminder_type,
        channel="telegram",
        status=status,
        scheduled_for=now - timedelta(minutes=60),
        payload_key="k",
        locale_at_send_time="en",
        planning_group="g1",
        supersedes_reminder_id=None,
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(minutes=queued_delta_min),
        queued_at=(now - timedelta(minutes=queued_delta_min)) if status == "queued" else None,
        delivery_attempts_count=attempts,
        sent_at=(now - timedelta(minutes=sent_delta_min)) if status == "sent" else None,
    )


def _policy_set(repo: InMemoryPolicyRepository, *, scope_ref: str) -> str:
    policy_set_id = f"ps_{scope_ref}"
    repo.upsert_policy_set(PolicySet(policy_set_id=policy_set_id, policy_family="booking", scope_type="clinic", scope_ref=scope_ref))
    return policy_set_id


def test_stale_queued_recovery_requeues_and_is_idempotent() -> None:
    now = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
    reminder_repo = _ReminderRepo([_reminder(status="queued", queued_delta_min=40, attempts=0)])
    booking_repo = _BookingRepo([_booking()], [_session()])
    service = ReminderRecoveryService(reminder_repo, booking_repo, PolicyResolver(InMemoryPolicyRepository()))

    first = asyncio.run(service.recover_stale_queued_reminders(now=now, limit=10))
    second = asyncio.run(service.recover_stale_queued_reminders(now=now, limit=10))

    assert first.stale_requeued == 1
    assert reminder_repo.jobs["r1"].status == "scheduled"
    assert second.stale_requeued == 0


def test_stale_queued_exhausted_marks_failed_and_escalates() -> None:
    now = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
    reminder_repo = _ReminderRepo([_reminder(status="queued", queued_delta_min=60, attempts=3)])
    booking_repo = _BookingRepo([_booking()], [_session()])
    service = ReminderRecoveryService(reminder_repo, booking_repo, PolicyResolver(InMemoryPolicyRepository()))

    stats = asyncio.run(service.recover_stale_queued_reminders(now=now, limit=10))

    assert stats.stale_failed == 1
    assert reminder_repo.jobs["r1"].status == "failed"
    assert any(e.reason_code == "reminder_delivery_stale_queued" for e in booking_repo.escalations.values())


def test_failed_delivery_escalation_for_non_retryable_failure() -> None:
    now = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
    reminder = _reminder(status="failed")
    reminder = ReminderJob(**{**asdict(reminder), "last_error_code": "target_missing", "last_error_text": "telegram_target_missing"})
    reminder_repo = _ReminderRepo([reminder])
    booking_repo = _BookingRepo([_booking()], [_session()])
    service = ReminderRecoveryService(reminder_repo, booking_repo, PolicyResolver(InMemoryPolicyRepository()))

    stats = asyncio.run(service.escalate_failed_delivery_reminders(now=now, limit=10))

    assert stats.failed_escalated == 1
    assert any(e.reason_code == "reminder_target_missing" for e in booking_repo.escalations.values())


def test_no_response_escalation_single_upsert_and_terminal_skip() -> None:
    now = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
    policy_repo = InMemoryPolicyRepository()
    policy_set_id = _policy_set(policy_repo, scope_ref="clinic_main")
    policy_repo.add_policy_value(PolicyValue(policy_value_id="pv1", policy_set_id=policy_set_id, policy_key="booking.non_response_escalation_enabled", value_type="bool", value_json=True))
    policy_repo.add_policy_value(PolicyValue(policy_value_id="pv2", policy_set_id=policy_set_id, policy_key="booking.non_response_escalation_after_minutes", value_type="int", value_json=30))
    policy_repo.add_policy_value(PolicyValue(policy_value_id="pv3", policy_set_id=policy_set_id, policy_key="booking.no_response_followup_enabled", value_type="bool", value_json=False))

    reminder_repo = _ReminderRepo([_reminder(status="sent", reminder_type="booking_confirmation", sent_delta_min=90)])
    booking_repo = _BookingRepo([_booking(status="pending_confirmation")], [_session()])
    service = ReminderRecoveryService(reminder_repo, booking_repo, PolicyResolver(policy_repo))

    first = asyncio.run(service.detect_confirmation_no_response(now=now, limit=10))
    second = asyncio.run(service.detect_confirmation_no_response(now=now, limit=10))

    assert first.no_response_escalated == 1
    assert second.no_response_escalated == 0

    booking_repo_terminal = _BookingRepo([_booking(status="confirmed")], [_session()])
    service_terminal = ReminderRecoveryService(reminder_repo, booking_repo_terminal, PolicyResolver(policy_repo))
    terminal_stats = asyncio.run(service_terminal.detect_confirmation_no_response(now=now, limit=10))
    assert terminal_stats.no_response_escalated == 0


def test_no_response_escalation_respects_per_clinic_policy_scope() -> None:
    now = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
    policy_repo = InMemoryPolicyRepository()
    enabled_set = _policy_set(policy_repo, scope_ref="clinic_enabled")
    disabled_set = _policy_set(policy_repo, scope_ref="clinic_disabled")
    policy_repo.add_policy_value(
        PolicyValue(
            policy_value_id="pv_enabled_1",
            policy_set_id=enabled_set,
            policy_key="booking.non_response_escalation_enabled",
            value_type="bool",
            value_json=True,
        )
    )
    policy_repo.add_policy_value(
        PolicyValue(
            policy_value_id="pv_enabled_2",
            policy_set_id=enabled_set,
            policy_key="booking.non_response_escalation_after_minutes",
            value_type="int",
            value_json=20,
        )
    )
    policy_repo.add_policy_value(
        PolicyValue(
            policy_value_id="pv_enabled_3",
            policy_set_id=enabled_set,
            policy_key="booking.no_response_followup_enabled",
            value_type="bool",
            value_json=False,
        )
    )
    policy_repo.add_policy_value(
        PolicyValue(
            policy_value_id="pv_disabled_1",
            policy_set_id=disabled_set,
            policy_key="booking.non_response_escalation_enabled",
            value_type="bool",
            value_json=False,
        )
    )

    enabled_booking = Booking(**{**asdict(_booking()), "booking_id": "b_enabled", "clinic_id": "clinic_enabled"})
    disabled_booking = Booking(**{**asdict(_booking()), "booking_id": "b_disabled", "clinic_id": "clinic_disabled"})
    session_enabled = BookingSession(**{**asdict(_session()), "booking_session_id": "s_enabled", "clinic_id": "clinic_enabled"})
    session_disabled = BookingSession(**{**asdict(_session()), "booking_session_id": "s_disabled", "clinic_id": "clinic_disabled"})

    reminder_enabled = ReminderJob(**{**asdict(_reminder(status="sent", reminder_type="booking_confirmation", sent_delta_min=30)), "reminder_id": "r_enabled", "clinic_id": "clinic_enabled", "booking_id": "b_enabled"})
    reminder_disabled = ReminderJob(**{**asdict(_reminder(status="sent", reminder_type="booking_confirmation", sent_delta_min=30)), "reminder_id": "r_disabled", "clinic_id": "clinic_disabled", "booking_id": "b_disabled"})

    service = ReminderRecoveryService(
        _ReminderRepo([reminder_enabled, reminder_disabled]),
        _BookingRepo([enabled_booking, disabled_booking], [session_enabled, session_disabled]),
        PolicyResolver(policy_repo),
    )
    stats = asyncio.run(service.detect_confirmation_no_response(now=now, limit=10))

    assert stats.no_response_escalated == 1


def test_stale_recovery_uses_clinic_specific_stale_and_retry_policies() -> None:
    now = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
    policy_repo = InMemoryPolicyRepository()
    strict_set = _policy_set(policy_repo, scope_ref="clinic_strict")
    relaxed_set = _policy_set(policy_repo, scope_ref="clinic_relaxed")
    policy_repo.add_policy_value(PolicyValue(policy_value_id="pv_s1", policy_set_id=strict_set, policy_key="communication.reminder_stale_queued_after_minutes", value_type="int", value_json=10))
    policy_repo.add_policy_value(PolicyValue(policy_value_id="pv_s2", policy_set_id=strict_set, policy_key="communication.reminder_retry_max_attempts", value_type="int", value_json=1))
    policy_repo.add_policy_value(PolicyValue(policy_value_id="pv_r1", policy_set_id=relaxed_set, policy_key="communication.reminder_stale_queued_after_minutes", value_type="int", value_json=45))
    policy_repo.add_policy_value(PolicyValue(policy_value_id="pv_r2", policy_set_id=relaxed_set, policy_key="communication.reminder_retry_max_attempts", value_type="int", value_json=5))

    strict_reminder = ReminderJob(**{**asdict(_reminder(status="queued", queued_delta_min=20, attempts=1)), "reminder_id": "r_strict", "clinic_id": "clinic_strict", "booking_id": "b_strict"})
    relaxed_reminder = ReminderJob(**{**asdict(_reminder(status="queued", queued_delta_min=20, attempts=1)), "reminder_id": "r_relaxed", "clinic_id": "clinic_relaxed", "booking_id": "b_relaxed"})
    strict_booking = Booking(**{**asdict(_booking()), "booking_id": "b_strict", "clinic_id": "clinic_strict"})
    relaxed_booking = Booking(**{**asdict(_booking()), "booking_id": "b_relaxed", "clinic_id": "clinic_relaxed"})
    strict_session = BookingSession(**{**asdict(_session()), "booking_session_id": "s_strict", "clinic_id": "clinic_strict"})
    relaxed_session = BookingSession(**{**asdict(_session()), "booking_session_id": "s_relaxed", "clinic_id": "clinic_relaxed"})

    reminder_repo = _ReminderRepo([strict_reminder, relaxed_reminder])
    booking_repo = _BookingRepo([strict_booking, relaxed_booking], [strict_session, relaxed_session])
    service = ReminderRecoveryService(reminder_repo, booking_repo, PolicyResolver(policy_repo))

    stats = asyncio.run(service.recover_stale_queued_reminders(now=now, limit=10))

    assert stats.stale_failed == 1
    assert reminder_repo.jobs["r_strict"].status == "failed"
    assert reminder_repo.jobs["r_relaxed"].status == "queued"


def test_admin_recovery_actions_take_and_resolve() -> None:
    now = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
    esc = AdminEscalation(
        admin_escalation_id="e1",
        clinic_id="clinic_main",
        booking_session_id="s1",
        patient_id="pat_1",
        reason_code="reminder_delivery_failed",
        priority="high",
        status="open",
        created_at=now,
        updated_at=now,
        payload_summary={"booking_id": "b1"},
    )

    class _FlowRepo(_BookingRepo):
        async def list_active_sessions_for_telegram_user(self, *, clinic_id: str, telegram_user_id: int):
            return []

        async def list_open_slots(self, **kwargs):  # noqa: ANN003
            return []

        async def list_recent_bookings_by_statuses(self, *, clinic_id: str, statuses: tuple[str, ...], limit: int):
            return []

        async def list_bookings_by_patient(self, *, patient_id: str):
            return []

        async def get_booking_session(self, booking_session_id: str):
            return None

    repo = _FlowRepo([_booking()], [_session()])
    repo.escalations[esc.admin_escalation_id] = esc
    flow = BookingPatientFlowService(
        orchestration=type("O", (), {"repository": repo})(),  # type: ignore[arg-type]
        reads=repo,  # type: ignore[arg-type]
        reference=type("R", (), {})(),  # type: ignore[arg-type]
        patient_creator=type("P", (), {})(),  # type: ignore[arg-type]
    )

    taken = asyncio.run(flow.take_admin_escalation(clinic_id="clinic_main", escalation_id="e1", actor_id="adm_1"))
    resolved = asyncio.run(flow.resolve_admin_escalation(clinic_id="clinic_main", escalation_id="e1", actor_id="adm_1"))

    assert taken is not None and taken.status == "in_progress"
    assert resolved is not None and resolved.status == "resolved"


def test_manual_retry_failed_reminder_is_bounded_and_idempotent() -> None:
    now = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
    failed = ReminderJob(
        **{
            **asdict(_reminder(status="failed", reminder_type="booking_confirmation", attempts=1)),
            "status": "failed",
            "last_error_code": "telegram_send_error",
            "last_error_text": "timeout",
        }
    )
    reminder_repo = _ReminderRepo([failed])
    booking_repo = _BookingRepo([_booking(status="pending_confirmation")], [_session()])
    service = ReminderRecoveryService(reminder_repo, booking_repo, PolicyResolver(InMemoryPolicyRepository()))

    first = asyncio.run(service.retry_failed_reminder(reminder_id="r1", now=now))
    second = asyncio.run(service.retry_failed_reminder(reminder_id="r1", now=now))

    assert first.outcome == "scheduled"
    assert first.reminder_id == "rem_mr_r1"
    assert reminder_repo.jobs["rem_mr_r1"].status == "scheduled"
    assert second.outcome == "already_pending"


def test_manual_retry_respects_explicit_policy_toggle() -> None:
    now = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
    failed = ReminderJob(
        **{
            **asdict(_reminder(status="failed", reminder_type="booking_confirmation", attempts=1)),
            "status": "failed",
            "last_error_code": "telegram_send_error",
            "last_error_text": "timeout",
        }
    )
    reminder_repo = _ReminderRepo([failed])
    booking_repo = _BookingRepo([_booking(status="pending_confirmation")], [_session()])
    policy_repo = InMemoryPolicyRepository()
    policy_set = PolicySet(policy_set_id="ps_manual", policy_family="communication", scope_type="clinic", scope_ref="clinic_main")
    policy_repo.upsert_policy_set(policy_set)
    policy_repo.add_policy_value(
        PolicyValue(
            policy_value_id="pv_manual",
            policy_set_id="ps_manual",
            policy_key="communication.manual_retry_enabled",
            value_type="bool",
            value_json=False,
        )
    )
    service = ReminderRecoveryService(reminder_repo, booking_repo, PolicyResolver(policy_repo))

    result = asyncio.run(service.retry_failed_reminder(reminder_id="r1", now=now))
    assert result.outcome == "manual_retry_disabled"
    assert "rem_mr_r1" not in reminder_repo.jobs
