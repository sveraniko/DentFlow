from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text

from app.application.admin.workdesk import no_response_threshold
from app.domain.events import EventEnvelope
from app.infrastructure.db.engine import create_engine


@dataclass(slots=True)
class AdminWorkdeskProjectionStore:
    db_config: object
    app_default_timezone: str = "UTC"

    async def rebuild_all(self) -> dict[str, int]:
        engine = create_engine(self.db_config)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("TRUNCATE TABLE admin_views.today_schedule"))
                await conn.execute(text("TRUNCATE TABLE admin_views.confirmation_queue"))
                await conn.execute(text("TRUNCATE TABLE admin_views.reschedule_queue"))
                await conn.execute(text("TRUNCATE TABLE admin_views.waitlist_queue"))
                await conn.execute(text("TRUNCATE TABLE admin_views.care_pickup_queue"))
                await conn.execute(text("TRUNCATE TABLE admin_views.ops_issue_queue"))

                await self.refresh_all_bookings_on_conn(conn)
                await self.refresh_all_waitlist_on_conn(conn)
                await self.refresh_all_care_orders_on_conn(conn)
                await self.refresh_ops_issues_on_conn(conn)

                return {
                    "today_schedule": await _count(conn, "admin_views.today_schedule"),
                    "confirmation_queue": await _count(conn, "admin_views.confirmation_queue"),
                    "reschedule_queue": await _count(conn, "admin_views.reschedule_queue"),
                    "waitlist_queue": await _count(conn, "admin_views.waitlist_queue"),
                    "care_pickup_queue": await _count(conn, "admin_views.care_pickup_queue"),
                    "ops_issue_queue": await _count(conn, "admin_views.ops_issue_queue"),
                }
        finally:
            await engine.dispose()

    async def refresh_booking(self, *, booking_id: str) -> None:
        engine = create_engine(self.db_config)
        try:
            async with engine.begin() as conn:
                await self.refresh_booking_on_conn(conn, booking_id=booking_id)
                await self.refresh_ops_issues_on_conn(conn)
        finally:
            await engine.dispose()

    async def refresh_waitlist_entry(self, *, waitlist_entry_id: str) -> None:
        engine = create_engine(self.db_config)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("DELETE FROM admin_views.waitlist_queue WHERE waitlist_entry_id=:id"), {"id": waitlist_entry_id})
                await conn.execute(text(_WAITLIST_INSERT + " AND w.waitlist_entry_id=:id"), self._params | {"id": waitlist_entry_id})
        finally:
            await engine.dispose()

    async def refresh_care_order(self, *, care_order_id: str) -> None:
        engine = create_engine(self.db_config)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("DELETE FROM admin_views.care_pickup_queue WHERE care_order_id=:id"), {"id": care_order_id})
                await conn.execute(text(_CARE_PICKUP_INSERT + " AND o.care_order_id=:id"), self._params | {"id": care_order_id})
        finally:
            await engine.dispose()

    @property
    def _params(self) -> dict[str, object]:
        return {
            "app_default_timezone": self.app_default_timezone,
            "no_response_threshold": no_response_threshold(now=datetime.now(timezone.utc)),
        }

    async def refresh_all_bookings_on_conn(self, conn) -> None:
        await conn.execute(text(_TODAY_SCHEDULE_INSERT), self._params)
        await conn.execute(text(_CONFIRMATION_QUEUE_INSERT), self._params)
        await conn.execute(text(_RESCHEDULE_QUEUE_INSERT), self._params)

    async def refresh_all_waitlist_on_conn(self, conn) -> None:
        await conn.execute(text(_WAITLIST_INSERT), self._params)

    async def refresh_all_care_orders_on_conn(self, conn) -> None:
        await conn.execute(text(_CARE_PICKUP_INSERT), self._params)

    async def refresh_booking_on_conn(self, conn, *, booking_id: str) -> None:
        params = self._params | {"booking_id": booking_id}
        await conn.execute(text("DELETE FROM admin_views.today_schedule WHERE booking_id=:booking_id"), params)
        await conn.execute(text("DELETE FROM admin_views.confirmation_queue WHERE booking_id=:booking_id"), params)
        await conn.execute(text("DELETE FROM admin_views.reschedule_queue WHERE booking_id=:booking_id"), params)

        await conn.execute(text(_TODAY_SCHEDULE_INSERT + " AND b.booking_id=:booking_id"), params)
        await conn.execute(text(_CONFIRMATION_QUEUE_INSERT + " AND b.booking_id=:booking_id"), params)
        await conn.execute(text(_RESCHEDULE_QUEUE_INSERT + " AND b.booking_id=:booking_id"), params)

    async def refresh_ops_issues_on_conn(self, conn) -> None:
        await conn.execute(text("TRUNCATE TABLE admin_views.ops_issue_queue"))
        await conn.execute(text(_OPS_ISSUES_INSERT), self._params)


@dataclass(slots=True)
class AdminWorkdeskProjector:
    db_config: object
    app_default_timezone: str = "UTC"
    name: str = "admin.workdesk"

    async def handle(self, event: EventEnvelope, outbox_event_id: int) -> bool:
        if not event.clinic_id:
            return False

        store = AdminWorkdeskProjectionStore(self.db_config, app_default_timezone=self.app_default_timezone)
        event_name = event.event_name

        if event_name.startswith("booking."):
            await store.refresh_booking(booking_id=event.entity_id)
            return True
        if event_name.startswith("waitlist."):
            await store.refresh_waitlist_entry(waitlist_entry_id=event.entity_id)
            return True
        if event_name.startswith("care_order."):
            await store.refresh_care_order(care_order_id=event.entity_id)
            return True
        if event_name.startswith("reminder."):
            booking_id = str(event.payload.get("booking_id") or "").strip() if event.payload else ""
            if booking_id:
                await store.refresh_booking(booking_id=booking_id)
                return True
        return False


async def _count(conn, table_name: str) -> int:
    return int((await conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))).scalar_one())


_BOOKING_BASE_CTE = """
WITH booking_base AS (
  SELECT
    b.clinic_id,
    b.branch_id,
    b.booking_id,
    b.patient_id,
    b.doctor_id,
    b.service_id,
    b.scheduled_start_at,
    b.scheduled_end_at,
    b.status,
    p.display_name AS patient_display_name,
    d.display_name AS doctor_display_name,
    s.title_key AS service_label,
    COALESCE(br.display_name, 'Main Branch') AS branch_label,
    COALESCE(br.timezone, c.timezone, :app_default_timezone) AS effective_timezone,
    EXISTS(SELECT 1 FROM booking.waitlist_entries w WHERE w.patient_id=b.patient_id AND w.status IN ('active', 'open', 'pending')) AS waitlist_linked,
    EXISTS(SELECT 1 FROM recommendation.recommendations r WHERE r.booking_id=b.booking_id) AS recommendation_linked,
    EXISTS(SELECT 1 FROM care_commerce.care_orders co WHERE co.booking_id=b.booking_id AND co.status NOT IN ('canceled', 'fulfilled', 'expired')) AS care_order_linked,
    EXISTS(
      SELECT 1
      FROM communication.reminder_jobs rj
      WHERE rj.booking_id=b.booking_id
        AND rj.reminder_type='booking_confirmation'
        AND rj.status='sent'
        AND rj.acknowledged_at IS NULL
        AND rj.sent_at IS NOT NULL
        AND rj.sent_at <= :no_response_threshold
    ) AS no_response_flag,
    (
      SELECT STRING_AGG(status || ':' || cnt, ',')
      FROM (
        SELECT rj.status, COUNT(*) AS cnt
        FROM communication.reminder_jobs rj
        WHERE rj.booking_id=b.booking_id AND rj.reminder_type='booking_confirmation'
        GROUP BY rj.status
      ) t
    ) AS reminder_state_summary,
    b.updated_at
  FROM booking.bookings b
  JOIN core_reference.clinics c ON c.clinic_id=b.clinic_id
  LEFT JOIN core_reference.branches br ON br.branch_id=b.branch_id
  JOIN core_patient.patients p ON p.patient_id=b.patient_id
  JOIN core_reference.doctors d ON d.doctor_id=b.doctor_id
  JOIN core_reference.services s ON s.service_id=b.service_id
)
"""

_TODAY_SCHEDULE_INSERT = (
    _BOOKING_BASE_CTE
    + """
INSERT INTO admin_views.today_schedule (
  clinic_id, branch_id, booking_id, patient_id, doctor_id, service_id,
  local_service_date, local_service_time, scheduled_start_at_utc, scheduled_end_at_utc,
  booking_status, confirmation_state, checkin_state, no_show_flag, reschedule_requested_flag,
  waitlist_linked_flag, recommendation_linked_flag, care_order_linked_flag,
  patient_display_name, doctor_display_name, service_label, branch_label, compact_flags_summary, updated_at
)
SELECT
  clinic_id,
  branch_id,
  booking_id,
  patient_id,
  doctor_id,
  service_id,
  (scheduled_start_at AT TIME ZONE effective_timezone)::date AS local_service_date,
  TO_CHAR((scheduled_start_at AT TIME ZONE effective_timezone), 'HH24:MI') AS local_service_time,
  scheduled_start_at AS scheduled_start_at_utc,
  scheduled_end_at AS scheduled_end_at_utc,
  status AS booking_status,
  CASE
    WHEN status='confirmed' THEN 'confirmed'
    WHEN no_response_flag THEN 'no_response'
    WHEN status='pending_confirmation' THEN 'pending'
    ELSE 'not_required'
  END AS confirmation_state,
  CASE
    WHEN status='checked_in' THEN 'checked_in'
    WHEN status='in_service' THEN 'in_service'
    WHEN status='completed' THEN 'completed'
    ELSE 'not_arrived'
  END AS checkin_state,
  (status='no_show') AS no_show_flag,
  (status='reschedule_requested') AS reschedule_requested_flag,
  waitlist_linked,
  recommendation_linked,
  care_order_linked,
  patient_display_name,
  doctor_display_name,
  service_label,
  branch_label,
  CONCAT_WS(',',
    CASE WHEN status='pending_confirmation' THEN 'needs_confirmation' END,
    CASE WHEN status='reschedule_requested' THEN 'reschedule' END,
    CASE WHEN waitlist_linked THEN 'waitlist' END,
    CASE WHEN care_order_linked THEN 'care' END,
    CASE WHEN no_response_flag THEN 'no_response' END
  ) AS compact_flags_summary,
  updated_at
FROM booking_base b
WHERE b.status IN ('pending_confirmation', 'confirmed', 'reschedule_requested', 'checked_in', 'in_service', 'completed', 'no_show')
"""
)

_CONFIRMATION_QUEUE_INSERT = (
    _BOOKING_BASE_CTE
    + """
INSERT INTO admin_views.confirmation_queue (
  clinic_id, branch_id, booking_id, patient_id, doctor_id,
  local_service_date, local_service_time, booking_status,
  confirmation_signal, reminder_state_summary, no_response_flag,
  patient_display_name, doctor_display_name, service_label, branch_label, updated_at
)
SELECT
  clinic_id,
  branch_id,
  booking_id,
  patient_id,
  doctor_id,
  (scheduled_start_at AT TIME ZONE effective_timezone)::date AS local_service_date,
  TO_CHAR((scheduled_start_at AT TIME ZONE effective_timezone), 'HH24:MI') AS local_service_time,
  status AS booking_status,
  CASE WHEN no_response_flag THEN 'no_response' ELSE 'pending_confirmation' END AS confirmation_signal,
  reminder_state_summary,
  no_response_flag,
  patient_display_name,
  doctor_display_name,
  service_label,
  branch_label,
  updated_at
FROM booking_base b
WHERE b.status='pending_confirmation' OR b.no_response_flag
"""
)

_RESCHEDULE_QUEUE_INSERT = (
    _BOOKING_BASE_CTE
    + """
INSERT INTO admin_views.reschedule_queue (
  clinic_id, branch_id, booking_id, patient_id, doctor_id,
  local_service_date, local_service_time, booking_status,
  reschedule_context, patient_display_name, doctor_display_name,
  service_label, branch_label, updated_at
)
SELECT
  clinic_id,
  branch_id,
  booking_id,
  patient_id,
  doctor_id,
  (scheduled_start_at AT TIME ZONE effective_timezone)::date AS local_service_date,
  TO_CHAR((scheduled_start_at AT TIME ZONE effective_timezone), 'HH24:MI') AS local_service_time,
  status AS booking_status,
  'patient_or_clinic_requested' AS reschedule_context,
  patient_display_name,
  doctor_display_name,
  service_label,
  branch_label,
  updated_at
FROM booking_base b
WHERE b.status='reschedule_requested'
"""
)

_WAITLIST_INSERT = """
INSERT INTO admin_views.waitlist_queue (
  clinic_id, branch_id, waitlist_entry_id, patient_id, preferred_doctor_id,
  preferred_service_id, preferred_time_window_summary, status,
  patient_display_name, doctor_display_name, service_label, priority_rank, updated_at
)
SELECT
  w.clinic_id,
  w.branch_id,
  w.waitlist_entry_id,
  w.patient_id,
  w.doctor_id AS preferred_doctor_id,
  w.service_id AS preferred_service_id,
  COALESCE(w.time_window, CAST(w.date_window AS TEXT)) AS preferred_time_window_summary,
  w.status,
  COALESCE(p.display_name, 'Unknown patient') AS patient_display_name,
  d.display_name AS doctor_display_name,
  s.title_key AS service_label,
  w.priority AS priority_rank,
  w.updated_at
FROM booking.waitlist_entries w
LEFT JOIN core_patient.patients p ON p.patient_id=w.patient_id
LEFT JOIN core_reference.doctors d ON d.doctor_id=w.doctor_id
LEFT JOIN core_reference.services s ON s.service_id=w.service_id
WHERE w.status IN ('active', 'open', 'pending')
"""

_CARE_PICKUP_INSERT = """
INSERT INTO admin_views.care_pickup_queue (
  clinic_id, branch_id, care_order_id, patient_id, pickup_status,
  local_ready_date, local_ready_time, patient_display_name,
  branch_label, compact_item_summary, updated_at
)
SELECT
  o.clinic_id,
  o.pickup_branch_id AS branch_id,
  o.care_order_id,
  o.patient_id,
  o.status AS pickup_status,
  CASE WHEN o.ready_for_pickup_at IS NULL THEN NULL ELSE (o.ready_for_pickup_at AT TIME ZONE COALESCE(br.timezone, c.timezone, :app_default_timezone))::date END AS local_ready_date,
  CASE WHEN o.ready_for_pickup_at IS NULL THEN NULL ELSE TO_CHAR((o.ready_for_pickup_at AT TIME ZONE COALESCE(br.timezone, c.timezone, :app_default_timezone)), 'HH24:MI') END AS local_ready_time,
  p.display_name AS patient_display_name,
  COALESCE(br.display_name, 'Main Branch') AS branch_label,
  COALESCE((
    SELECT STRING_AGG(pr.title_key || ' x' || i.quantity, ', ' ORDER BY i.created_at)
    FROM care_commerce.care_order_items i
    JOIN care_commerce.products pr ON pr.care_product_id=i.care_product_id
    WHERE i.care_order_id=o.care_order_id
  ), 'No items') AS compact_item_summary,
  o.updated_at
FROM care_commerce.care_orders o
JOIN core_reference.clinics c ON c.clinic_id=o.clinic_id
LEFT JOIN core_reference.branches br ON br.branch_id=o.pickup_branch_id
JOIN core_patient.patients p ON p.patient_id=o.patient_id
WHERE o.status IN ('confirmed', 'awaiting_payment', 'paid', 'ready_for_pickup', 'issued')
"""

_OPS_ISSUES_INSERT = """
INSERT INTO admin_views.ops_issue_queue (
  clinic_id, branch_id, issue_type, issue_ref_id, issue_status, severity,
  patient_id, booking_id, care_order_id, local_related_date, local_related_time,
  summary_text, patient_display_name, severity_rank, updated_at
)
SELECT
  b.clinic_id,
  b.branch_id,
  'confirmation_no_response' AS issue_type,
  b.booking_id AS issue_ref_id,
  'open' AS issue_status,
  'medium' AS severity,
  b.patient_id,
  b.booking_id,
  NULL AS care_order_id,
  (b.scheduled_start_at AT TIME ZONE COALESCE(br.timezone, c.timezone, :app_default_timezone))::date AS local_related_date,
  TO_CHAR((b.scheduled_start_at AT TIME ZONE COALESCE(br.timezone, c.timezone, :app_default_timezone)), 'HH24:MI') AS local_related_time,
  'Confirmation reminder sent but no patient response yet' AS summary_text,
  p.display_name AS patient_display_name,
  2 AS severity_rank,
  GREATEST(b.updated_at, COALESCE(mx.latest_sent_at, b.updated_at)) AS updated_at
FROM booking.bookings b
JOIN core_reference.clinics c ON c.clinic_id=b.clinic_id
LEFT JOIN core_reference.branches br ON br.branch_id=b.branch_id
JOIN core_patient.patients p ON p.patient_id=b.patient_id
JOIN (
  SELECT booking_id, MAX(sent_at) AS latest_sent_at
  FROM communication.reminder_jobs
  WHERE reminder_type='booking_confirmation'
    AND status='sent'
    AND acknowledged_at IS NULL
    AND sent_at <= :no_response_threshold
  GROUP BY booking_id
) mx ON mx.booking_id=b.booking_id
WHERE b.status='pending_confirmation'
UNION ALL
SELECT
  b.clinic_id,
  b.branch_id,
  'reminder_failed' AS issue_type,
  r.reminder_id AS issue_ref_id,
  'open' AS issue_status,
  'high' AS severity,
  b.patient_id,
  b.booking_id,
  NULL AS care_order_id,
  (b.scheduled_start_at AT TIME ZONE COALESCE(br.timezone, c.timezone, :app_default_timezone))::date AS local_related_date,
  TO_CHAR((b.scheduled_start_at AT TIME ZONE COALESCE(br.timezone, c.timezone, :app_default_timezone)), 'HH24:MI') AS local_related_time,
  'Reminder delivery failed; manual outreach needed' AS summary_text,
  p.display_name AS patient_display_name,
  3 AS severity_rank,
  r.updated_at
FROM communication.reminder_jobs r
JOIN booking.bookings b ON b.booking_id=r.booking_id
JOIN core_reference.clinics c ON c.clinic_id=b.clinic_id
LEFT JOIN core_reference.branches br ON br.branch_id=b.branch_id
JOIN core_patient.patients p ON p.patient_id=b.patient_id
WHERE r.status='failed'
  AND r.booking_id IS NOT NULL
"""
