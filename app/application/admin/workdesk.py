from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text

from app.infrastructure.db.engine import create_engine


@dataclass(slots=True)
class TodayScheduleRow:
    clinic_id: str
    branch_id: str | None
    booking_id: str
    patient_id: str
    doctor_id: str
    service_id: str
    local_service_date: date
    local_service_time: str
    scheduled_start_at_utc: datetime
    scheduled_end_at_utc: datetime | None
    booking_status: str
    confirmation_state: str
    checkin_state: str
    no_show_flag: bool
    reschedule_requested_flag: bool
    waitlist_linked_flag: bool | None
    recommendation_linked_flag: bool | None
    care_order_linked_flag: bool | None
    patient_display_name: str
    doctor_display_name: str
    service_label: str
    branch_label: str
    compact_flags_summary: str | None
    updated_at: datetime


@dataclass(slots=True)
class ConfirmationQueueRow:
    clinic_id: str
    branch_id: str | None
    booking_id: str
    patient_id: str
    doctor_id: str
    local_service_date: date
    local_service_time: str
    booking_status: str
    confirmation_signal: str
    reminder_state_summary: str | None
    no_response_flag: bool
    patient_display_name: str
    doctor_display_name: str
    service_label: str
    branch_label: str
    updated_at: datetime


@dataclass(slots=True)
class RescheduleQueueRow:
    clinic_id: str
    branch_id: str | None
    booking_id: str
    patient_id: str
    doctor_id: str
    local_service_date: date
    local_service_time: str
    booking_status: str
    reschedule_context: str | None
    patient_display_name: str
    doctor_display_name: str
    service_label: str
    branch_label: str
    updated_at: datetime


@dataclass(slots=True)
class WaitlistQueueRow:
    clinic_id: str
    branch_id: str | None
    waitlist_entry_id: str
    patient_id: str | None
    preferred_doctor_id: str | None
    preferred_service_id: str | None
    preferred_time_window_summary: str | None
    status: str
    patient_display_name: str
    doctor_display_name: str | None
    service_label: str | None
    updated_at: datetime


@dataclass(slots=True)
class CarePickupQueueRow:
    clinic_id: str
    branch_id: str | None
    care_order_id: str
    patient_id: str
    pickup_status: str
    local_ready_date: date | None
    local_ready_time: str | None
    patient_display_name: str
    branch_label: str
    compact_item_summary: str
    updated_at: datetime


@dataclass(slots=True)
class OpsIssueQueueRow:
    clinic_id: str
    branch_id: str | None
    issue_type: str
    issue_ref_id: str
    issue_status: str
    severity: str
    patient_id: str | None
    booking_id: str | None
    care_order_id: str | None
    local_related_date: date | None
    local_related_time: str | None
    summary_text: str
    patient_display_name: str | None
    updated_at: datetime


@dataclass(slots=True)
class AdminWorkdeskReadService:
    db_config: object
    app_default_timezone: str = "UTC"

    async def get_today_schedule(
        self,
        *,
        clinic_id: str,
        branch_id: str | None = None,
        doctor_id: str | None = None,
        local_day: date | None = None,
        now: datetime | None = None,
        statuses: tuple[str, ...] | None = None,
        limit: int = 200,
    ) -> list[TodayScheduleRow]:
        target_date = await self._resolve_local_day(clinic_id=clinic_id, branch_id=branch_id, local_day=local_day, now=now)
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT clinic_id, branch_id, booking_id, patient_id, doctor_id, service_id,
                                   local_service_date, local_service_time, scheduled_start_at_utc,
                                   scheduled_end_at_utc, booking_status, confirmation_state, checkin_state,
                                   no_show_flag, reschedule_requested_flag, waitlist_linked_flag,
                                   recommendation_linked_flag, care_order_linked_flag, patient_display_name,
                                   doctor_display_name, service_label, branch_label, compact_flags_summary,
                                   updated_at
                            FROM admin_views.today_schedule
                            WHERE clinic_id=:clinic_id
                              AND local_service_date=:target_date
                              AND (:branch_id IS NULL OR branch_id=:branch_id)
                              AND (:doctor_id IS NULL OR doctor_id=:doctor_id)
                              AND (:statuses_is_null OR booking_status = ANY(:statuses))
                            ORDER BY scheduled_start_at_utc ASC, booking_id ASC
                            LIMIT :limit
                            """
                        ),
                        {
                            "clinic_id": clinic_id,
                            "target_date": target_date,
                            "branch_id": branch_id,
                            "doctor_id": doctor_id,
                            "statuses": list(statuses or []),
                            "statuses_is_null": statuses is None,
                            "limit": max(limit, 1),
                        },
                    )
                ).mappings().all()
        finally:
            await engine.dispose()
        return [TodayScheduleRow(**dict(row)) for row in rows]

    async def get_confirmation_queue(
        self,
        *,
        clinic_id: str,
        branch_id: str | None = None,
        doctor_id: str | None = None,
        local_day: date | None = None,
        now: datetime | None = None,
        statuses: tuple[str, ...] | None = None,
        only_no_response: bool = False,
        limit: int = 200,
    ) -> list[ConfirmationQueueRow]:
        target_date = await self._resolve_local_day(clinic_id=clinic_id, branch_id=branch_id, local_day=local_day, now=now)
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT clinic_id, branch_id, booking_id, patient_id, doctor_id, local_service_date,
                                   local_service_time, booking_status, confirmation_signal,
                                   reminder_state_summary, no_response_flag, patient_display_name,
                                   doctor_display_name, service_label, branch_label, updated_at
                            FROM admin_views.confirmation_queue
                            WHERE clinic_id=:clinic_id
                              AND local_service_date=:target_date
                              AND (:branch_id IS NULL OR branch_id=:branch_id)
                              AND (:doctor_id IS NULL OR doctor_id=:doctor_id)
                              AND (:statuses_is_null OR booking_status = ANY(:statuses))
                              AND (:only_no_response = FALSE OR no_response_flag = TRUE)
                            ORDER BY no_response_flag DESC, local_service_time ASC, booking_id ASC
                            LIMIT :limit
                            """
                        ),
                        {
                            "clinic_id": clinic_id,
                            "target_date": target_date,
                            "branch_id": branch_id,
                            "doctor_id": doctor_id,
                            "statuses": list(statuses or []),
                            "statuses_is_null": statuses is None,
                            "only_no_response": only_no_response,
                            "limit": max(limit, 1),
                        },
                    )
                ).mappings().all()
        finally:
            await engine.dispose()
        return [ConfirmationQueueRow(**dict(row)) for row in rows]

    async def get_reschedule_queue(
        self,
        *,
        clinic_id: str,
        branch_id: str | None = None,
        doctor_id: str | None = None,
        local_day: date | None = None,
        now: datetime | None = None,
        statuses: tuple[str, ...] | None = None,
        limit: int = 200,
    ) -> list[RescheduleQueueRow]:
        target_date = await self._resolve_local_day(clinic_id=clinic_id, branch_id=branch_id, local_day=local_day, now=now)
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT clinic_id, branch_id, booking_id, patient_id, doctor_id, local_service_date,
                                   local_service_time, booking_status, reschedule_context,
                                   patient_display_name, doctor_display_name, service_label,
                                   branch_label, updated_at
                            FROM admin_views.reschedule_queue
                            WHERE clinic_id=:clinic_id
                              AND local_service_date=:target_date
                              AND (:branch_id IS NULL OR branch_id=:branch_id)
                              AND (:doctor_id IS NULL OR doctor_id=:doctor_id)
                              AND (:statuses_is_null OR booking_status = ANY(:statuses))
                            ORDER BY local_service_time ASC, booking_id ASC
                            LIMIT :limit
                            """
                        ),
                        {
                            "clinic_id": clinic_id,
                            "target_date": target_date,
                            "branch_id": branch_id,
                            "doctor_id": doctor_id,
                            "statuses": list(statuses or []),
                            "statuses_is_null": statuses is None,
                            "limit": max(limit, 1),
                        },
                    )
                ).mappings().all()
        finally:
            await engine.dispose()
        return [RescheduleQueueRow(**dict(row)) for row in rows]

    async def get_waitlist_queue(
        self,
        *,
        clinic_id: str,
        branch_id: str | None = None,
        doctor_id: str | None = None,
        statuses: tuple[str, ...] | None = None,
        limit: int = 200,
    ) -> list[WaitlistQueueRow]:
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT clinic_id, branch_id, waitlist_entry_id, patient_id, preferred_doctor_id,
                                   preferred_service_id, preferred_time_window_summary, status,
                                   patient_display_name, doctor_display_name, service_label, updated_at
                            FROM admin_views.waitlist_queue
                            WHERE clinic_id=:clinic_id
                              AND (:branch_id IS NULL OR branch_id=:branch_id)
                              AND (:doctor_id IS NULL OR preferred_doctor_id=:doctor_id)
                              AND (:statuses_is_null OR status = ANY(:statuses))
                            ORDER BY priority_rank DESC, updated_at DESC, waitlist_entry_id ASC
                            LIMIT :limit
                            """
                        ),
                        {
                            "clinic_id": clinic_id,
                            "branch_id": branch_id,
                            "doctor_id": doctor_id,
                            "statuses": list(statuses or []),
                            "statuses_is_null": statuses is None,
                            "limit": max(limit, 1),
                        },
                    )
                ).mappings().all()
        finally:
            await engine.dispose()
        return [WaitlistQueueRow(**dict(row)) for row in rows]

    async def get_care_pickup_queue(
        self,
        *,
        clinic_id: str,
        branch_id: str | None = None,
        statuses: tuple[str, ...] | None = None,
        local_day: date | None = None,
        now: datetime | None = None,
        limit: int = 200,
    ) -> list[CarePickupQueueRow]:
        target_date = await self._resolve_local_day(clinic_id=clinic_id, branch_id=branch_id, local_day=local_day, now=now)
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT clinic_id, branch_id, care_order_id, patient_id, pickup_status,
                                   local_ready_date, local_ready_time, patient_display_name,
                                   branch_label, compact_item_summary, updated_at
                            FROM admin_views.care_pickup_queue
                            WHERE clinic_id=:clinic_id
                              AND (:branch_id IS NULL OR branch_id=:branch_id)
                              AND (:statuses_is_null OR pickup_status = ANY(:statuses))
                              AND (:target_date IS NULL OR local_ready_date IS NULL OR local_ready_date=:target_date)
                            ORDER BY COALESCE(local_ready_time, '00:00') ASC, updated_at DESC
                            LIMIT :limit
                            """
                        ),
                        {
                            "clinic_id": clinic_id,
                            "branch_id": branch_id,
                            "statuses": list(statuses or []),
                            "statuses_is_null": statuses is None,
                            "target_date": target_date,
                            "limit": max(limit, 1),
                        },
                    )
                ).mappings().all()
        finally:
            await engine.dispose()
        return [CarePickupQueueRow(**dict(row)) for row in rows]

    async def get_ops_issue_queue(
        self,
        *,
        clinic_id: str,
        branch_id: str | None = None,
        statuses: tuple[str, ...] | None = None,
        issue_types: tuple[str, ...] | None = None,
        local_day: date | None = None,
        now: datetime | None = None,
        limit: int = 200,
    ) -> list[OpsIssueQueueRow]:
        target_date = await self._resolve_local_day(clinic_id=clinic_id, branch_id=branch_id, local_day=local_day, now=now)
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT clinic_id, branch_id, issue_type, issue_ref_id, issue_status,
                                   severity, patient_id, booking_id, care_order_id,
                                   local_related_date, local_related_time, summary_text,
                                   patient_display_name, updated_at
                            FROM admin_views.ops_issue_queue
                            WHERE clinic_id=:clinic_id
                              AND (:branch_id IS NULL OR branch_id=:branch_id)
                              AND (:statuses_is_null OR issue_status = ANY(:statuses))
                              AND (:types_is_null OR issue_type = ANY(:issue_types))
                              AND (:target_date IS NULL OR local_related_date IS NULL OR local_related_date=:target_date)
                            ORDER BY severity_rank DESC, updated_at DESC
                            LIMIT :limit
                            """
                        ),
                        {
                            "clinic_id": clinic_id,
                            "branch_id": branch_id,
                            "statuses": list(statuses or []),
                            "statuses_is_null": statuses is None,
                            "issue_types": list(issue_types or []),
                            "types_is_null": issue_types is None,
                            "target_date": target_date,
                            "limit": max(limit, 1),
                        },
                    )
                ).mappings().all()
        finally:
            await engine.dispose()
        return [OpsIssueQueueRow(**dict(row)) for row in rows]

    async def _resolve_local_day(
        self,
        *,
        clinic_id: str,
        branch_id: str | None,
        local_day: date | None,
        now: datetime | None,
    ) -> date:
        if local_day is not None:
            return local_day
        point = now or datetime.now(timezone.utc)
        tz_name = await self._resolve_timezone(clinic_id=clinic_id, branch_id=branch_id)
        zone = _zone_or_utc(tz_name)
        return point.astimezone(zone).date()

    async def _resolve_timezone(self, *, clinic_id: str, branch_id: str | None) -> str:
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                return await _resolve_timezone_from_conn(
                    conn,
                    clinic_id=clinic_id,
                    branch_id=branch_id,
                    app_default_timezone=self.app_default_timezone,
                )
        finally:
            await engine.dispose()


async def _resolve_timezone_from_conn(conn, *, clinic_id: str, branch_id: str | None, app_default_timezone: str) -> str:
    if branch_id:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT b.timezone AS branch_timezone, c.timezone AS clinic_timezone
                    FROM core_reference.branches b
                    JOIN core_reference.clinics c ON c.clinic_id=b.clinic_id
                    WHERE b.branch_id=:branch_id AND c.clinic_id=:clinic_id
                    """
                ),
                {"branch_id": branch_id, "clinic_id": clinic_id},
            )
        ).mappings().first()
        if row:
            if row.get("branch_timezone"):
                return str(row["branch_timezone"])
            if row.get("clinic_timezone"):
                return str(row["clinic_timezone"])

    clinic = (
        await conn.execute(
            text("SELECT timezone FROM core_reference.clinics WHERE clinic_id=:clinic_id"),
            {"clinic_id": clinic_id},
        )
    ).mappings().first()
    if clinic and clinic.get("timezone"):
        return str(clinic["timezone"])
    return app_default_timezone


def _zone_or_utc(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def no_response_threshold(*, now: datetime | None = None) -> datetime:
    point = now or datetime.now(timezone.utc)
    return point - timedelta(hours=2)
