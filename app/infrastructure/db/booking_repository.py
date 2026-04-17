from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.application.booking.services import BookingRepository
from app.domain.booking import AdminEscalation, AvailabilitySlot, Booking, BookingSession, BookingStatusHistory, SessionEvent, SlotHold, WaitlistEntry
from app.domain.communication import ReminderJob
from app.domain.events import build_event
from app.infrastructure.db.engine import create_engine
from app.infrastructure.outbox.repository import OutboxRepository


class DbBookingRepository(BookingRepository):
    def __init__(self, db_config) -> None:
        self._db_config = db_config

    def _engine(self):
        return create_engine(self._db_config)

    def transaction(self):
        return DbBookingUnitOfWork(self._engine(), self._db_config)

    async def _upsert_booking_session_on_conn(self, conn: Any, item: BookingSession) -> None:
        payload = asdict(item)
        await conn.execute(
            text(
                """
                INSERT INTO booking.booking_sessions (
                  booking_session_id, clinic_id, branch_id, telegram_user_id, resolved_patient_id, status, route_type, service_id,
                  urgency_type, requested_date_type, requested_date, time_window, doctor_preference_type, doctor_id, doctor_code_raw,
                  selected_slot_id, selected_hold_id, contact_phone_snapshot, notes, expires_at, created_at, updated_at
                ) VALUES (
                  :booking_session_id, :clinic_id, :branch_id, :telegram_user_id, :resolved_patient_id, :status, :route_type, :service_id,
                  :urgency_type, :requested_date_type, :requested_date, :time_window, :doctor_preference_type, :doctor_id, :doctor_code_raw,
                  :selected_slot_id, :selected_hold_id, :contact_phone_snapshot, :notes, :expires_at, :created_at, :updated_at
                )
                ON CONFLICT (booking_session_id) DO UPDATE SET
                  branch_id=EXCLUDED.branch_id,
                  resolved_patient_id=EXCLUDED.resolved_patient_id,
                  status=EXCLUDED.status,
                  route_type=EXCLUDED.route_type,
                  service_id=EXCLUDED.service_id,
                  urgency_type=EXCLUDED.urgency_type,
                  requested_date_type=EXCLUDED.requested_date_type,
                  requested_date=EXCLUDED.requested_date,
                  time_window=EXCLUDED.time_window,
                  doctor_preference_type=EXCLUDED.doctor_preference_type,
                  doctor_id=EXCLUDED.doctor_id,
                  doctor_code_raw=EXCLUDED.doctor_code_raw,
                  selected_slot_id=EXCLUDED.selected_slot_id,
                  selected_hold_id=EXCLUDED.selected_hold_id,
                  contact_phone_snapshot=EXCLUDED.contact_phone_snapshot,
                  notes=EXCLUDED.notes,
                  expires_at=EXCLUDED.expires_at,
                  updated_at=EXCLUDED.updated_at
                """
            ),
            payload,
        )

    async def upsert_booking_session(self, item: BookingSession) -> None:
        engine = self._engine()
        async with engine.begin() as conn:
            await self._upsert_booking_session_on_conn(conn, item)
        await engine.dispose()

    async def get_booking_session(self, booking_session_id: str) -> BookingSession | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT booking_session_id, clinic_id, branch_id, telegram_user_id, resolved_patient_id, status, route_type, service_id,
                   urgency_type, requested_date_type, requested_date, time_window, doctor_preference_type, doctor_id, doctor_code_raw,
                   selected_slot_id, selected_hold_id, contact_phone_snapshot, notes, expires_at, created_at, updated_at
            FROM booking.booking_sessions
            WHERE booking_session_id=:booking_session_id
            """,
            {"booking_session_id": booking_session_id},
        )
        return BookingSession(**row) if row else None

    async def list_active_sessions_for_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> list[BookingSession]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT booking_session_id, clinic_id, branch_id, telegram_user_id, resolved_patient_id, status, route_type, service_id,
                   urgency_type, requested_date_type, requested_date, time_window, doctor_preference_type, doctor_id, doctor_code_raw,
                   selected_slot_id, selected_hold_id, contact_phone_snapshot, notes, expires_at, created_at, updated_at
            FROM booking.booking_sessions
            WHERE clinic_id=:clinic_id
              AND telegram_user_id=:telegram_user_id
              AND status IN ('initiated', 'in_progress', 'awaiting_slot_selection', 'awaiting_contact_confirmation', 'review_ready')
            ORDER BY updated_at DESC
            """,
            {"clinic_id": clinic_id, "telegram_user_id": telegram_user_id},
        )
        return [BookingSession(**row) for row in rows]

    async def find_latest_session_for_patient(self, *, clinic_id: str, patient_id: str) -> BookingSession | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT booking_session_id, clinic_id, branch_id, telegram_user_id, resolved_patient_id, status, route_type, service_id,
                   urgency_type, requested_date_type, requested_date, time_window, doctor_preference_type, doctor_id, doctor_code_raw,
                   selected_slot_id, selected_hold_id, contact_phone_snapshot, notes, expires_at, created_at, updated_at
            FROM booking.booking_sessions
            WHERE clinic_id=:clinic_id
              AND resolved_patient_id=:patient_id
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            {"clinic_id": clinic_id, "patient_id": patient_id},
        )
        return BookingSession(**row) if row else None

    async def get_booking_session_for_update(self, booking_session_id: str) -> BookingSession | None:
        async with self.transaction() as tx:
            return await tx.get_booking_session_for_update(booking_session_id)

    async def _append_session_event_on_conn(self, conn: Any, event: SessionEvent) -> None:
        payload = asdict(event)
        payload["payload_json"] = json.dumps(payload["payload_json"]) if payload["payload_json"] is not None else None
        await conn.execute(
            text(
                """
                INSERT INTO booking.session_events (
                  session_event_id, booking_session_id, event_name, payload_json, actor_type, actor_id, occurred_at
                ) VALUES (
                  :session_event_id, :booking_session_id, :event_name, CAST(:payload_json AS JSONB), :actor_type, :actor_id, :occurred_at
                )
                ON CONFLICT (session_event_id) DO NOTHING
                """
            ),
            payload,
        )

    async def append_session_event(self, event: SessionEvent) -> None:
        engine = self._engine()
        async with engine.begin() as conn:
            await self._append_session_event_on_conn(conn, event)
        await engine.dispose()

    async def upsert_availability_slot(self, item: AvailabilitySlot) -> None:
        payload = asdict(item)
        engine = self._engine()
        async with engine.begin() as conn:
            payload["service_scope"] = json.dumps(payload["service_scope"]) if payload["service_scope"] is not None else None
            await conn.execute(
                text(
                    """
                    INSERT INTO booking.availability_slots (
                      slot_id, clinic_id, branch_id, doctor_id, start_at, end_at, status, visibility_policy, service_scope, source_ref, updated_at
                    ) VALUES (
                      :slot_id, :clinic_id, :branch_id, :doctor_id, :start_at, :end_at, :status, :visibility_policy,
                      CAST(:service_scope AS JSONB), :source_ref, :updated_at
                    )
                    ON CONFLICT (slot_id) DO UPDATE SET
                      branch_id=EXCLUDED.branch_id,
                      doctor_id=EXCLUDED.doctor_id,
                      start_at=EXCLUDED.start_at,
                      end_at=EXCLUDED.end_at,
                      status=EXCLUDED.status,
                      visibility_policy=EXCLUDED.visibility_policy,
                      service_scope=EXCLUDED.service_scope,
                      source_ref=EXCLUDED.source_ref,
                      updated_at=EXCLUDED.updated_at
                    """
                ),
                payload,
            )
        await engine.dispose()

    async def get_availability_slot(self, slot_id: str) -> AvailabilitySlot | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT slot_id, clinic_id, branch_id, doctor_id, start_at, end_at, status, visibility_policy, service_scope, source_ref, updated_at
            FROM booking.availability_slots
            WHERE slot_id=:slot_id
            """,
            {"slot_id": slot_id},
        )
        return AvailabilitySlot(**row) if row else None

    async def get_availability_slot_for_update(self, slot_id: str) -> AvailabilitySlot | None:
        async with self.transaction() as tx:
            return await tx.get_availability_slot_for_update(slot_id)

    async def list_availability_slots(self, *, doctor_id: str, start_at: datetime, end_at: datetime) -> list[AvailabilitySlot]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT slot_id, clinic_id, branch_id, doctor_id, start_at, end_at, status, visibility_policy, service_scope, source_ref, updated_at
            FROM booking.availability_slots
            WHERE doctor_id=:doctor_id AND start_at >= :start_at AND start_at < :end_at
            ORDER BY start_at ASC
            """,
            {"doctor_id": doctor_id, "start_at": start_at, "end_at": end_at},
        )
        return [AvailabilitySlot(**row) for row in rows]

    async def list_open_slots(
        self,
        *,
        clinic_id: str,
        start_at: datetime,
        end_at: datetime,
        doctor_id: str | None,
        branch_id: str | None,
        limit: int,
    ) -> list[AvailabilitySlot]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT slot_id, clinic_id, branch_id, doctor_id, start_at, end_at, status, visibility_policy, service_scope, source_ref, updated_at
            FROM booking.availability_slots
            WHERE clinic_id=:clinic_id
              AND status='open'
              AND start_at >= :start_at
              AND start_at < :end_at
              AND (:doctor_id IS NULL OR doctor_id=:doctor_id)
              AND (:branch_id IS NULL OR branch_id=:branch_id)
            ORDER BY start_at ASC, slot_id ASC
            LIMIT :limit
            """,
            {
                "clinic_id": clinic_id,
                "start_at": start_at,
                "end_at": end_at,
                "doctor_id": doctor_id,
                "branch_id": branch_id,
                "limit": limit,
            },
        )
        return [AvailabilitySlot(**row) for row in rows]

    async def _upsert_slot_hold_on_conn(self, conn: Any, item: SlotHold) -> None:
        payload = asdict(item)
        await conn.execute(
            text(
                """
                INSERT INTO booking.slot_holds (
                  slot_hold_id, clinic_id, slot_id, booking_session_id, telegram_user_id, status, expires_at, created_at
                ) VALUES (
                  :slot_hold_id, :clinic_id, :slot_id, :booking_session_id, :telegram_user_id, :status, :expires_at, :created_at
                )
                ON CONFLICT (slot_hold_id) DO UPDATE SET
                  status=EXCLUDED.status,
                  expires_at=EXCLUDED.expires_at
                """
            ),
            payload,
        )

    async def upsert_slot_hold(self, item: SlotHold) -> None:
        engine = self._engine()
        async with engine.begin() as conn:
            await self._upsert_slot_hold_on_conn(conn, item)
        await engine.dispose()

    async def get_slot_hold(self, slot_hold_id: str) -> SlotHold | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT slot_hold_id, clinic_id, slot_id, booking_session_id, telegram_user_id, status, expires_at, created_at
            FROM booking.slot_holds WHERE slot_hold_id=:slot_hold_id
            """,
            {"slot_hold_id": slot_hold_id},
        )
        return SlotHold(**row) if row else None

    async def get_slot_hold_for_update(self, slot_hold_id: str) -> SlotHold | None:
        async with self.transaction() as tx:
            return await tx.get_slot_hold_for_update(slot_hold_id)

    async def find_slot_hold(self, *, slot_id: str, booking_session_id: str) -> SlotHold | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT slot_hold_id, clinic_id, slot_id, booking_session_id, telegram_user_id, status, expires_at, created_at
            FROM booking.slot_holds
            WHERE slot_id=:slot_id AND booking_session_id=:booking_session_id
            ORDER BY created_at DESC
            LIMIT 1
            """,
            {"slot_id": slot_id, "booking_session_id": booking_session_id},
        )
        return SlotHold(**row) if row else None

    async def _upsert_booking_on_conn(self, conn: Any, item: Booking) -> None:
        payload = asdict(item)
        await conn.execute(
            text(
                """
                INSERT INTO booking.bookings (
                  booking_id, clinic_id, branch_id, patient_id, doctor_id, service_id, slot_id, booking_mode, source_channel,
                  scheduled_start_at, scheduled_end_at, status, reason_for_visit_short, patient_note, confirmation_required,
                  confirmed_at, canceled_at, checked_in_at, in_service_at, completed_at, no_show_at, created_at, updated_at
                ) VALUES (
                  :booking_id, :clinic_id, :branch_id, :patient_id, :doctor_id, :service_id, :slot_id, :booking_mode, :source_channel,
                  :scheduled_start_at, :scheduled_end_at, :status, :reason_for_visit_short, :patient_note, :confirmation_required,
                  :confirmed_at, :canceled_at, :checked_in_at, :in_service_at, :completed_at, :no_show_at, :created_at, :updated_at
                )
                ON CONFLICT (booking_id) DO UPDATE SET
                  branch_id=EXCLUDED.branch_id,
                  patient_id=EXCLUDED.patient_id,
                  doctor_id=EXCLUDED.doctor_id,
                  service_id=EXCLUDED.service_id,
                  slot_id=EXCLUDED.slot_id,
                  booking_mode=EXCLUDED.booking_mode,
                  source_channel=EXCLUDED.source_channel,
                  scheduled_start_at=EXCLUDED.scheduled_start_at,
                  scheduled_end_at=EXCLUDED.scheduled_end_at,
                  status=EXCLUDED.status,
                  reason_for_visit_short=EXCLUDED.reason_for_visit_short,
                  patient_note=EXCLUDED.patient_note,
                  confirmation_required=EXCLUDED.confirmation_required,
                  confirmed_at=EXCLUDED.confirmed_at,
                  canceled_at=EXCLUDED.canceled_at,
                  checked_in_at=EXCLUDED.checked_in_at,
                  in_service_at=EXCLUDED.in_service_at,
                  completed_at=EXCLUDED.completed_at,
                  no_show_at=EXCLUDED.no_show_at,
                  updated_at=EXCLUDED.updated_at
                """
            ),
            payload,
        )

    async def upsert_booking(self, item: Booking) -> None:
        engine = self._engine()
        async with engine.begin() as conn:
            await self._upsert_booking_on_conn(conn, item)
        await engine.dispose()

    async def get_booking(self, booking_id: str) -> Booking | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT booking_id, clinic_id, branch_id, patient_id, doctor_id, service_id, slot_id, booking_mode, source_channel,
                   scheduled_start_at, scheduled_end_at, status, reason_for_visit_short, patient_note, confirmation_required,
                   confirmed_at, canceled_at, checked_in_at, in_service_at, completed_at, no_show_at, created_at, updated_at
            FROM booking.bookings
            WHERE booking_id=:booking_id
            """,
            {"booking_id": booking_id},
        )
        return Booking(**row) if row else None

    async def get_booking_for_update(self, booking_id: str) -> Booking | None:
        async with self.transaction() as tx:
            return await tx.get_booking_for_update(booking_id)

    async def _append_booking_status_history_on_conn(self, conn: Any, item: BookingStatusHistory) -> None:
        payload = asdict(item)
        await conn.execute(
            text(
                """
                INSERT INTO booking.booking_status_history (
                  booking_status_history_id, booking_id, old_status, new_status, reason_code, actor_type, actor_id, occurred_at
                ) VALUES (
                  :booking_status_history_id, :booking_id, :old_status, :new_status, :reason_code, :actor_type, :actor_id, :occurred_at
                )
                ON CONFLICT (booking_status_history_id) DO NOTHING
                """
            ),
            payload,
        )

    async def append_booking_status_history(self, item: BookingStatusHistory) -> None:
        engine = self._engine()
        async with engine.begin() as conn:
            await self._append_booking_status_history_on_conn(conn, item)
        await engine.dispose()

    async def list_bookings_by_patient(self, *, patient_id: str) -> list[Booking]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT booking_id, clinic_id, branch_id, patient_id, doctor_id, service_id, slot_id, booking_mode, source_channel,
                   scheduled_start_at, scheduled_end_at, status, reason_for_visit_short, patient_note, confirmation_required,
                   confirmed_at, canceled_at, checked_in_at, in_service_at, completed_at, no_show_at, created_at, updated_at
            FROM booking.bookings
            WHERE patient_id=:patient_id
            ORDER BY scheduled_start_at DESC
            """,
            {"patient_id": patient_id},
        )
        return [Booking(**row) for row in rows]

    async def list_bookings_by_doctor_time_window(self, *, doctor_id: str, start_at: datetime, end_at: datetime) -> list[Booking]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT booking_id, clinic_id, branch_id, patient_id, doctor_id, service_id, slot_id, booking_mode, source_channel,
                   scheduled_start_at, scheduled_end_at, status, reason_for_visit_short, patient_note, confirmation_required,
                   confirmed_at, canceled_at, checked_in_at, in_service_at, completed_at, no_show_at, created_at, updated_at
            FROM booking.bookings
            WHERE doctor_id=:doctor_id AND scheduled_start_at >= :start_at AND scheduled_start_at < :end_at
            ORDER BY scheduled_start_at ASC
            """,
            {"doctor_id": doctor_id, "start_at": start_at, "end_at": end_at},
        )
        return [Booking(**row) for row in rows]

    async def list_bookings_by_status_time_window(self, *, status: str, start_at: datetime, end_at: datetime) -> list[Booking]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT booking_id, clinic_id, branch_id, patient_id, doctor_id, service_id, slot_id, booking_mode, source_channel,
                   scheduled_start_at, scheduled_end_at, status, reason_for_visit_short, patient_note, confirmation_required,
                   confirmed_at, canceled_at, checked_in_at, in_service_at, completed_at, no_show_at, created_at, updated_at
            FROM booking.bookings
            WHERE status=:status AND scheduled_start_at >= :start_at AND scheduled_start_at < :end_at
            ORDER BY scheduled_start_at ASC
            """,
            {"status": status, "start_at": start_at, "end_at": end_at},
        )
        return [Booking(**row) for row in rows]

    async def _upsert_waitlist_entry_on_conn(self, conn: Any, item: WaitlistEntry) -> None:
        payload = asdict(item)
        payload["date_window"] = json.dumps(payload["date_window"]) if payload["date_window"] is not None else None
        await conn.execute(
            text(
                """
                INSERT INTO booking.waitlist_entries (
                  waitlist_entry_id, clinic_id, branch_id, patient_id, telegram_user_id, service_id, doctor_id, date_window,
                  time_window, priority, status, source_session_id, notes, created_at, updated_at
                ) VALUES (
                  :waitlist_entry_id, :clinic_id, :branch_id, :patient_id, :telegram_user_id, :service_id, :doctor_id,
                  CAST(:date_window AS JSONB), :time_window, :priority, :status, :source_session_id, :notes, :created_at, :updated_at
                )
                ON CONFLICT (waitlist_entry_id) DO UPDATE SET
                  branch_id=EXCLUDED.branch_id,
                  patient_id=EXCLUDED.patient_id,
                  telegram_user_id=EXCLUDED.telegram_user_id,
                  service_id=EXCLUDED.service_id,
                  doctor_id=EXCLUDED.doctor_id,
                  date_window=EXCLUDED.date_window,
                  time_window=EXCLUDED.time_window,
                  priority=EXCLUDED.priority,
                  status=EXCLUDED.status,
                  source_session_id=EXCLUDED.source_session_id,
                  notes=EXCLUDED.notes,
                  updated_at=EXCLUDED.updated_at
                """
            ),
            payload,
        )

    async def upsert_waitlist_entry(self, item: WaitlistEntry) -> None:
        engine = self._engine()
        async with engine.begin() as conn:
            await self._upsert_waitlist_entry_on_conn(conn, item)
        await engine.dispose()

    async def get_waitlist_entry(self, waitlist_entry_id: str) -> WaitlistEntry | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT waitlist_entry_id, clinic_id, branch_id, patient_id, telegram_user_id, service_id, doctor_id, date_window,
                   time_window, priority, status, source_session_id, notes, created_at, updated_at
            FROM booking.waitlist_entries
            WHERE waitlist_entry_id=:waitlist_entry_id
            """,
            {"waitlist_entry_id": waitlist_entry_id},
        )
        return WaitlistEntry(**row) if row else None

    async def get_waitlist_entry_for_update(self, waitlist_entry_id: str) -> WaitlistEntry | None:
        async with self.transaction() as tx:
            return await tx.get_waitlist_entry_for_update(waitlist_entry_id)

    async def list_active_holds_for_slot(self, *, slot_id: str) -> list[SlotHold]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT slot_hold_id, clinic_id, slot_id, booking_session_id, telegram_user_id, status, expires_at, created_at
            FROM booking.slot_holds
            WHERE slot_id=:slot_id AND status='active'
            ORDER BY created_at DESC
            """,
            {"slot_id": slot_id},
        )
        return [SlotHold(**row) for row in rows]

    async def list_live_bookings_for_slot(self, *, slot_id: str) -> list[Booking]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT booking_id, clinic_id, branch_id, patient_id, doctor_id, service_id, slot_id, booking_mode, source_channel,
                   scheduled_start_at, scheduled_end_at, status, reason_for_visit_short, patient_note, confirmation_required,
                   confirmed_at, canceled_at, checked_in_at, in_service_at, completed_at, no_show_at, created_at, updated_at
            FROM booking.bookings
            WHERE slot_id=:slot_id
              AND status IN ('pending_confirmation', 'confirmed', 'reschedule_requested', 'checked_in', 'in_service')
            ORDER BY scheduled_start_at DESC
            """,
            {"slot_id": slot_id},
        )
        return [Booking(**row) for row in rows]

    async def upsert_admin_escalation(self, item: AdminEscalation) -> None:
        payload = asdict(item)
        payload["payload_summary"] = json.dumps(payload["payload_summary"]) if payload["payload_summary"] is not None else None
        engine = self._engine()
        async with engine.begin() as conn:
            await self._upsert_admin_escalation_on_conn(conn, item)
        await engine.dispose()

    async def get_admin_escalation(self, admin_escalation_id: str) -> AdminEscalation | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT admin_escalation_id, clinic_id, booking_session_id, patient_id, reason_code, priority, status,
                   assigned_to_actor_id, payload_summary, created_at, updated_at
            FROM booking.admin_escalations
            WHERE admin_escalation_id=:admin_escalation_id
            """,
            {"admin_escalation_id": admin_escalation_id},
        )
        return AdminEscalation(**row) if row else None

    async def list_open_admin_escalations(self, *, clinic_id: str, limit: int) -> list[AdminEscalation]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT admin_escalation_id, clinic_id, booking_session_id, patient_id, reason_code, priority, status,
                   assigned_to_actor_id, payload_summary, created_at, updated_at
            FROM booking.admin_escalations
            WHERE clinic_id=:clinic_id AND status='open'
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            {"clinic_id": clinic_id, "limit": limit},
        )
        return [AdminEscalation(**row) for row in rows]

    async def list_recent_bookings_by_statuses(self, *, clinic_id: str, statuses: tuple[str, ...], limit: int) -> list[Booking]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT booking_id, clinic_id, branch_id, patient_id, doctor_id, service_id, slot_id, booking_mode, source_channel,
                   scheduled_start_at, scheduled_end_at, status, reason_for_visit_short, patient_note, confirmation_required,
                   confirmed_at, canceled_at, checked_in_at, in_service_at, completed_at, no_show_at, created_at, updated_at
            FROM booking.bookings
            WHERE clinic_id=:clinic_id
              AND status = ANY(:statuses)
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            {"clinic_id": clinic_id, "statuses": list(statuses), "limit": limit},
        )
        return [Booking(**row) for row in rows]

    async def _upsert_admin_escalation_on_conn(self, conn: Any, item: AdminEscalation) -> None:
        payload = asdict(item)
        payload["payload_summary"] = json.dumps(payload["payload_summary"]) if payload["payload_summary"] is not None else None
        await conn.execute(
            text(
                """
                INSERT INTO booking.admin_escalations (
                  admin_escalation_id, clinic_id, booking_session_id, patient_id, reason_code, priority, status,
                  assigned_to_actor_id, payload_summary, created_at, updated_at
                ) VALUES (
                  :admin_escalation_id, :clinic_id, :booking_session_id, :patient_id, :reason_code, :priority, :status,
                  :assigned_to_actor_id, CAST(:payload_summary AS JSONB), :created_at, :updated_at
                )
                ON CONFLICT (admin_escalation_id) DO UPDATE SET
                  patient_id=EXCLUDED.patient_id,
                  reason_code=EXCLUDED.reason_code,
                  priority=EXCLUDED.priority,
                  status=EXCLUDED.status,
                  assigned_to_actor_id=EXCLUDED.assigned_to_actor_id,
                  payload_summary=EXCLUDED.payload_summary,
                  updated_at=EXCLUDED.updated_at
                """
            ),
            payload,
        )


class DbBookingUnitOfWork:
    def __init__(self, engine, db_config) -> None:
        self._engine = engine
        self._db_config = db_config
        self._tx_ctx = None
        self._conn = None
        self._repo = None
        self._outbox = None

    async def __aenter__(self):
        self._repo = DbBookingRepository.__new__(DbBookingRepository)
        self._repo._db_config = self._db_config
        self._repo._engine = lambda: self._engine
        self._tx_ctx = self._engine.begin()
        self._outbox = OutboxRepository(self._repo._db_config)
        self._conn = await self._tx_ctx.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        assert self._tx_ctx is not None
        try:
            return await self._tx_ctx.__aexit__(exc_type, exc, tb)
        finally:
            await self._engine.dispose()

    async def upsert_booking_session(self, item: BookingSession) -> None:
        assert self._repo is not None and self._conn is not None
        await self._repo._upsert_booking_session_on_conn(self._conn, item)

    async def append_session_event(self, event: SessionEvent) -> None:
        assert self._repo is not None and self._conn is not None
        await self._repo._append_session_event_on_conn(self._conn, event)

    async def upsert_slot_hold(self, item: SlotHold) -> None:
        assert self._repo is not None and self._conn is not None
        await self._repo._upsert_slot_hold_on_conn(self._conn, item)

    async def upsert_booking(self, item: Booking) -> None:
        assert self._repo is not None and self._conn is not None
        await self._repo._upsert_booking_on_conn(self._conn, item)

    async def append_booking_status_history(self, item: BookingStatusHistory) -> None:
        assert self._repo is not None and self._conn is not None
        await self._repo._append_booking_status_history_on_conn(self._conn, item)

    async def upsert_waitlist_entry(self, item: WaitlistEntry) -> None:
        assert self._repo is not None and self._conn is not None
        await self._repo._upsert_waitlist_entry_on_conn(self._conn, item)

    async def upsert_admin_escalation(self, item: AdminEscalation) -> None:
        assert self._repo is not None and self._conn is not None
        await self._repo._upsert_admin_escalation_on_conn(self._conn, item)

    async def get_booking_session_for_update(self, booking_session_id: str) -> BookingSession | None:
        assert self._conn is not None
        row = (
            await self._conn.execute(
                text(
                    """
                    SELECT booking_session_id, clinic_id, branch_id, telegram_user_id, resolved_patient_id, status, route_type, service_id,
                           urgency_type, requested_date_type, requested_date, time_window, doctor_preference_type, doctor_id, doctor_code_raw,
                           selected_slot_id, selected_hold_id, contact_phone_snapshot, notes, expires_at, created_at, updated_at
                    FROM booking.booking_sessions
                    WHERE booking_session_id=:booking_session_id
                    FOR UPDATE
                    """
                ),
                {"booking_session_id": booking_session_id},
            )
        ).mappings().first()
        return BookingSession(**dict(row)) if row else None

    async def get_slot_hold_for_update(self, slot_hold_id: str) -> SlotHold | None:
        assert self._conn is not None
        row = (
            await self._conn.execute(
                text(
                    """
                    SELECT slot_hold_id, clinic_id, slot_id, booking_session_id, telegram_user_id, status, expires_at, created_at
                    FROM booking.slot_holds
                    WHERE slot_hold_id=:slot_hold_id
                    FOR UPDATE
                    """
                ),
                {"slot_hold_id": slot_hold_id},
            )
        ).mappings().first()
        return SlotHold(**dict(row)) if row else None

    async def find_slot_hold_for_update(self, *, slot_id: str, booking_session_id: str) -> SlotHold | None:
        assert self._conn is not None
        row = (
            await self._conn.execute(
                text(
                    """
                    SELECT slot_hold_id, clinic_id, slot_id, booking_session_id, telegram_user_id, status, expires_at, created_at
                    FROM booking.slot_holds
                    WHERE slot_id=:slot_id AND booking_session_id=:booking_session_id
                    ORDER BY created_at DESC
                    LIMIT 1
                    FOR UPDATE
                    """
                ),
                {"slot_id": slot_id, "booking_session_id": booking_session_id},
            )
        ).mappings().first()
        return SlotHold(**dict(row)) if row else None

    async def get_booking_for_update(self, booking_id: str) -> Booking | None:
        assert self._conn is not None
        row = (
            await self._conn.execute(
                text(
                    """
                    SELECT booking_id, clinic_id, branch_id, patient_id, doctor_id, service_id, slot_id, booking_mode, source_channel,
                           scheduled_start_at, scheduled_end_at, status, reason_for_visit_short, patient_note, confirmation_required,
                           confirmed_at, canceled_at, checked_in_at, in_service_at, completed_at, no_show_at, created_at, updated_at
                    FROM booking.bookings
                    WHERE booking_id=:booking_id
                    FOR UPDATE
                    """
                ),
                {"booking_id": booking_id},
            )
        ).mappings().first()
        return Booking(**dict(row)) if row else None

    async def get_availability_slot_for_update(self, slot_id: str) -> AvailabilitySlot | None:
        assert self._conn is not None
        row = (
            await self._conn.execute(
                text(
                    """
                    SELECT slot_id, clinic_id, branch_id, doctor_id, start_at, end_at, status, visibility_policy, service_scope, source_ref, updated_at
                    FROM booking.availability_slots
                    WHERE slot_id=:slot_id
                    FOR UPDATE
                    """
                ),
                {"slot_id": slot_id},
            )
        ).mappings().first()
        return AvailabilitySlot(**dict(row)) if row else None

    async def get_waitlist_entry_for_update(self, waitlist_entry_id: str) -> WaitlistEntry | None:
        assert self._conn is not None
        row = (
            await self._conn.execute(
                text(
                    """
                    SELECT waitlist_entry_id, clinic_id, branch_id, patient_id, telegram_user_id, service_id, doctor_id, date_window,
                           time_window, priority, status, source_session_id, notes, created_at, updated_at
                    FROM booking.waitlist_entries
                    WHERE waitlist_entry_id=:waitlist_entry_id
                    FOR UPDATE
                    """
                ),
                {"waitlist_entry_id": waitlist_entry_id},
            )
        ).mappings().first()
        return WaitlistEntry(**dict(row)) if row else None

    async def list_active_holds_for_slot_for_update(self, *, slot_id: str) -> list[SlotHold]:
        assert self._conn is not None
        rows = list(
            (
                await self._conn.execute(
                    text(
                        """
                        SELECT slot_hold_id, clinic_id, slot_id, booking_session_id, telegram_user_id, status, expires_at, created_at
                        FROM booking.slot_holds
                        WHERE slot_id=:slot_id AND status='active'
                        FOR UPDATE
                        """
                    ),
                    {"slot_id": slot_id},
                )
            ).mappings()
        )
        return [SlotHold(**dict(row)) for row in rows]

    async def list_active_holds_for_session_for_update(self, *, booking_session_id: str) -> list[SlotHold]:
        assert self._conn is not None
        rows = list(
            (
                await self._conn.execute(
                    text(
                        """
                        SELECT slot_hold_id, clinic_id, slot_id, booking_session_id, telegram_user_id, status, expires_at, created_at
                        FROM booking.slot_holds
                        WHERE booking_session_id=:booking_session_id AND status='active'
                        FOR UPDATE
                        """
                    ),
                    {"booking_session_id": booking_session_id},
                )
            ).mappings()
        )
        return [SlotHold(**dict(row)) for row in rows]

    async def list_live_bookings_for_slot_for_update(self, *, slot_id: str) -> list[Booking]:
        assert self._conn is not None
        rows = list(
            (
                await self._conn.execute(
                    text(
                        """
                        SELECT booking_id, clinic_id, branch_id, patient_id, doctor_id, service_id, slot_id, booking_mode, source_channel,
                               scheduled_start_at, scheduled_end_at, status, reason_for_visit_short, patient_note, confirmation_required,
                               confirmed_at, canceled_at, checked_in_at, in_service_at, completed_at, no_show_at, created_at, updated_at
                        FROM booking.bookings
                        WHERE slot_id=:slot_id
                          AND status IN ('pending_confirmation', 'confirmed', 'reschedule_requested', 'checked_in', 'in_service')
                        FOR UPDATE
                        """
                    ),
                    {"slot_id": slot_id},
                )
            ).mappings()
        )
        return [Booking(**dict(row)) for row in rows]

    async def create_reminder_job_in_transaction(self, item: ReminderJob) -> None:
        assert self._conn is not None
        payload = asdict(item)
        await self._conn.execute(
            text(
                """
                INSERT INTO communication.reminder_jobs (
                  reminder_id, clinic_id, patient_id, booking_id, care_order_id, recommendation_id,
                  reminder_type, channel, status, scheduled_for, payload_key, locale_at_send_time,
                  planning_group, supersedes_reminder_id, created_at, updated_at, queued_at,
                  delivery_attempts_count, last_error_code, last_error_text, last_failed_at, sent_at, acknowledged_at,
                  canceled_at, cancel_reason_code
                ) VALUES (
                  :reminder_id, :clinic_id, :patient_id, :booking_id, :care_order_id, :recommendation_id,
                  :reminder_type, :channel, :status, :scheduled_for, :payload_key, :locale_at_send_time,
                  :planning_group, :supersedes_reminder_id, :created_at, :updated_at, :queued_at,
                  :delivery_attempts_count, :last_error_code, :last_error_text, :last_failed_at, :sent_at, :acknowledged_at,
                  :canceled_at, :cancel_reason_code
                )
                ON CONFLICT (reminder_id) DO UPDATE SET
                  status=EXCLUDED.status,
                  channel=EXCLUDED.channel,
                  scheduled_for=EXCLUDED.scheduled_for,
                  payload_key=EXCLUDED.payload_key,
                  locale_at_send_time=EXCLUDED.locale_at_send_time,
                  planning_group=EXCLUDED.planning_group,
                  supersedes_reminder_id=EXCLUDED.supersedes_reminder_id,
                  updated_at=EXCLUDED.updated_at,
                  queued_at=EXCLUDED.queued_at,
                  delivery_attempts_count=EXCLUDED.delivery_attempts_count,
                  last_error_code=EXCLUDED.last_error_code,
                  last_error_text=EXCLUDED.last_error_text,
                  last_failed_at=EXCLUDED.last_failed_at,
                  sent_at=EXCLUDED.sent_at,
                  acknowledged_at=EXCLUDED.acknowledged_at,
                  canceled_at=EXCLUDED.canceled_at,
                  cancel_reason_code=EXCLUDED.cancel_reason_code
                """
            ),
            payload,
        )

        await self.append_outbox_event(
            build_event(
                event_name="reminder.scheduled",
                producer_context="communication.reminder_plan",
                clinic_id=item.clinic_id,
                entity_type="reminder",
                entity_id=item.reminder_id,
                occurred_at=item.created_at,
                payload={"booking_id": item.booking_id, "status": item.status, "reminder_type": item.reminder_type},
            )
        )

    async def cancel_scheduled_reminders_for_booking_in_transaction(
        self, *, booking_id: str, canceled_at: datetime, reason_code: str
    ) -> int:
        assert self._conn is not None
        result = await self._conn.execute(
            text(
                """
                UPDATE communication.reminder_jobs
                SET status='canceled', canceled_at=:canceled_at, cancel_reason_code=:reason_code, updated_at=:canceled_at
                WHERE booking_id=:booking_id
                  AND status='scheduled'
                RETURNING reminder_id, clinic_id
                """
            ),
            {"booking_id": booking_id, "canceled_at": canceled_at, "reason_code": reason_code},
        )
        rows = result.mappings().all()
        for row in rows:
            await self.append_outbox_event(
                build_event(
                    event_name="reminder.canceled",
                    producer_context="communication.reminder_plan",
                    clinic_id=row["clinic_id"],
                    entity_type="reminder",
                    entity_id=row["reminder_id"],
                    occurred_at=canceled_at,
                    payload={"booking_id": booking_id, "reason_code": reason_code},
                )
            )
        return len(rows)

    async def get_reminder_for_update_in_transaction(self, *, reminder_id: str) -> ReminderJob | None:
        assert self._conn is not None
        row = (
            await self._conn.execute(
                text(
                    """
                    SELECT reminder_id, clinic_id, patient_id, booking_id, care_order_id, recommendation_id,
                           reminder_type, channel, status, scheduled_for, payload_key, locale_at_send_time,
                           planning_group, supersedes_reminder_id, created_at, updated_at, queued_at,
                           delivery_attempts_count, last_error_code, last_error_text, last_failed_at, sent_at,
                           acknowledged_at, canceled_at, cancel_reason_code
                    FROM communication.reminder_jobs
                    WHERE reminder_id=:reminder_id
                    FOR UPDATE
                    """
                ),
                {"reminder_id": reminder_id},
            )
        ).mappings().first()
        return ReminderJob(**dict(row)) if row is not None else None

    async def mark_reminder_acknowledged_in_transaction(self, *, reminder_id: str, acknowledged_at: datetime) -> bool:
        assert self._conn is not None
        result = await self._conn.execute(
            text(
                """
                UPDATE communication.reminder_jobs
                SET status='acknowledged', acknowledged_at=:acknowledged_at, updated_at=:acknowledged_at
                WHERE reminder_id=:reminder_id
                  AND status='sent'
                RETURNING clinic_id, reminder_id, booking_id
                """
            ),
            {"reminder_id": reminder_id, "acknowledged_at": acknowledged_at},
        )
        row = result.mappings().first()
        if row:
            await self.append_outbox_event(
                build_event(
                    event_name="reminder.acknowledged",
                    producer_context="communication.actions",
                    clinic_id=row["clinic_id"],
                    entity_type="reminder",
                    entity_id=row["reminder_id"],
                    occurred_at=acknowledged_at,
                    payload={"booking_id": row["booking_id"]},
                )
            )
        return bool(row)


    async def append_outbox_event(self, event) -> None:
        assert self._outbox is not None and self._conn is not None
        await self._outbox.append_on_connection(self._conn, event)

    async def has_sent_delivery_for_provider_message_in_transaction(self, *, reminder_id: str, provider_message_id: str) -> bool:
        assert self._conn is not None
        count = (
            await self._conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS c
                    FROM communication.message_deliveries
                    WHERE reminder_id=:reminder_id
                      AND provider_message_id=:provider_message_id
                      AND delivery_status='sent'
                    """
                ),
                {"reminder_id": reminder_id, "provider_message_id": provider_message_id},
            )
        ).scalar_one()
        return int(count) > 0


async def _fetch_one(db_config, sql: str, params: dict) -> dict | None:
    engine = create_engine(db_config)
    async with engine.connect() as conn:
        row = (await conn.execute(text(sql), params)).mappings().first()
    await engine.dispose()
    return dict(row) if row else None


async def _fetch_all(db_config, sql: str, params: dict) -> list[dict]:
    engine = create_engine(db_config)
    async with engine.connect() as conn:
        rows = list((await conn.execute(text(sql), params)).mappings())
    await engine.dispose()
    return [dict(row) for row in rows]


async def seed_stack3_booking(db_config, path: Path) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    engine = create_engine(db_config)
    async with engine.begin() as conn:
        await _seed_rows(conn, payload)
    await engine.dispose()
    return {key: len(payload.get(key, [])) for key in payload}


async def _seed_rows(conn, payload: dict) -> None:
    statements = {
        "booking_sessions": (
            "booking.booking_sessions",
            [
                "booking_session_id",
                "clinic_id",
                "branch_id",
                "telegram_user_id",
                "resolved_patient_id",
                "status",
                "route_type",
                "service_id",
                "urgency_type",
                "requested_date_type",
                "requested_date",
                "time_window",
                "doctor_preference_type",
                "doctor_id",
                "doctor_code_raw",
                "selected_slot_id",
                "selected_hold_id",
                "contact_phone_snapshot",
                "notes",
                "expires_at",
                "created_at",
                "updated_at",
            ],
        ),
        "session_events": (
            "booking.session_events",
            ["session_event_id", "booking_session_id", "event_name", "payload_json", "actor_type", "actor_id", "occurred_at"],
        ),
        "availability_slots": (
            "booking.availability_slots",
            ["slot_id", "clinic_id", "branch_id", "doctor_id", "start_at", "end_at", "status", "visibility_policy", "service_scope", "source_ref", "updated_at"],
        ),
        "slot_holds": (
            "booking.slot_holds",
            ["slot_hold_id", "clinic_id", "slot_id", "booking_session_id", "telegram_user_id", "status", "expires_at", "created_at"],
        ),
        "bookings": (
            "booking.bookings",
            [
                "booking_id",
                "clinic_id",
                "branch_id",
                "patient_id",
                "doctor_id",
                "service_id",
                "slot_id",
                "booking_mode",
                "source_channel",
                "scheduled_start_at",
                "scheduled_end_at",
                "status",
                "reason_for_visit_short",
                "patient_note",
                "confirmation_required",
                "confirmed_at",
                "canceled_at",
                "checked_in_at",
                "in_service_at",
                "completed_at",
                "no_show_at",
                "created_at",
                "updated_at",
            ],
        ),
        "booking_status_history": (
            "booking.booking_status_history",
            ["booking_status_history_id", "booking_id", "old_status", "new_status", "reason_code", "actor_type", "actor_id", "occurred_at"],
        ),
        "waitlist_entries": (
            "booking.waitlist_entries",
            [
                "waitlist_entry_id",
                "clinic_id",
                "branch_id",
                "patient_id",
                "telegram_user_id",
                "service_id",
                "doctor_id",
                "date_window",
                "time_window",
                "priority",
                "status",
                "source_session_id",
                "notes",
                "created_at",
                "updated_at",
            ],
        ),
        "admin_escalations": (
            "booking.admin_escalations",
            [
                "admin_escalation_id",
                "clinic_id",
                "booking_session_id",
                "patient_id",
                "reason_code",
                "priority",
                "status",
                "assigned_to_actor_id",
                "payload_summary",
                "created_at",
                "updated_at",
            ],
        ),
    }

    for key, (table, columns) in statements.items():
        for row in payload.get(key, []):
            serialized = {name: row.get(name) for name in columns}
            for json_key in ("payload_json", "service_scope", "date_window", "payload_summary"):
                if json_key in serialized and serialized[json_key] is not None:
                    serialized[json_key] = json.dumps(serialized[json_key])
            col_csv = ", ".join(columns)
            values = ", ".join(f":{name}" for name in columns)
            updates = ", ".join(f"{name}=EXCLUDED.{name}" for name in columns if name != columns[0])
            await conn.execute(
                text(f"INSERT INTO {table} ({col_csv}) VALUES ({values}) ON CONFLICT ({columns[0]}) DO UPDATE SET {updates}"),
                serialized,
            )
