from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text

from app.application.integration.google_calendar_projection import CalendarEventMapping, CalendarProjectionBooking
from app.infrastructure.db.engine import create_engine


@dataclass(slots=True)
class DbGoogleCalendarProjectionRepository:
    db_config: object
    app_default_timezone: str = "UTC"

    async def get_booking_projection(self, *, booking_id: str) -> CalendarProjectionBooking | None:
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                row = (
                    await conn.execute(
                        text(
                            """
                            SELECT
                              b.booking_id,
                              b.clinic_id,
                              b.doctor_id,
                              b.service_id,
                              b.patient_id,
                              b.status,
                              b.scheduled_start_at,
                              b.scheduled_end_at,
                              COALESCE(br.timezone, c.timezone, :app_default_timezone) AS timezone,
                              COALESCE(igd.calendar_external_id, 'doctor_' || b.doctor_id) AS doctor_calendar_id,
                              p.display_name AS patient_display_name,
                              d.display_name AS doctor_display_name,
                              s.title_key AS service_label,
                              COALESCE(br.display_name, 'Main Branch') AS branch_label
                            FROM booking.bookings b
                            JOIN core_reference.clinics c ON c.clinic_id=b.clinic_id
                            LEFT JOIN core_reference.branches br ON br.branch_id=b.branch_id
                            JOIN core_reference.doctors d ON d.doctor_id=b.doctor_id
                            JOIN core_reference.services s ON s.service_id=b.service_id
                            JOIN core_patient.patients p ON p.patient_id=b.patient_id
                            LEFT JOIN integration.google_calendar_doctor_calendars igd
                              ON igd.clinic_id=b.clinic_id AND igd.doctor_id=b.doctor_id AND igd.is_active=TRUE
                            WHERE b.booking_id=:booking_id
                            """
                        ),
                        {"booking_id": booking_id, "app_default_timezone": self.app_default_timezone},
                    )
                ).mappings().first()
                return CalendarProjectionBooking(**dict(row)) if row else None
        finally:
            await engine.dispose()

    async def get_event_mapping(self, *, booking_id: str) -> CalendarEventMapping | None:
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                row = (
                    await conn.execute(
                        text(
                            """
                            SELECT booking_id, clinic_id, calendar_provider, target_calendar_id, external_event_id,
                                   sync_status, sync_attempts, last_synced_at, last_error_text, payload_hash
                            FROM integration.google_calendar_booking_event_map
                            WHERE booking_id=:booking_id
                            """
                        ),
                        {"booking_id": booking_id},
                    )
                ).mappings().first()
                return CalendarEventMapping(**dict(row)) if row else None
        finally:
            await engine.dispose()

    async def upsert_event_mapping(
        self,
        *,
        booking_id: str,
        clinic_id: str,
        target_calendar_id: str,
        external_event_id: str | None,
        sync_status: str,
        payload_hash: str | None,
        last_error_text: str | None,
    ) -> None:
        engine = create_engine(self.db_config)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        INSERT INTO integration.google_calendar_booking_event_map (
                          booking_id, clinic_id, calendar_provider, target_calendar_id, external_event_id,
                          sync_status, sync_attempts, payload_hash, last_error_text, last_synced_at, updated_at
                        ) VALUES (
                          :booking_id, :clinic_id, 'google_calendar', :target_calendar_id, :external_event_id,
                          :sync_status, 1, :payload_hash, :last_error_text, :last_synced_at, :updated_at
                        )
                        ON CONFLICT (booking_id) DO UPDATE SET
                          target_calendar_id=EXCLUDED.target_calendar_id,
                          external_event_id=EXCLUDED.external_event_id,
                          sync_status=EXCLUDED.sync_status,
                          sync_attempts=integration.google_calendar_booking_event_map.sync_attempts + 1,
                          payload_hash=EXCLUDED.payload_hash,
                          last_error_text=EXCLUDED.last_error_text,
                          last_synced_at=EXCLUDED.last_synced_at,
                          updated_at=EXCLUDED.updated_at
                        """
                    ),
                    {
                        "booking_id": booking_id,
                        "clinic_id": clinic_id,
                        "target_calendar_id": target_calendar_id,
                        "external_event_id": external_event_id,
                        "sync_status": sync_status,
                        "payload_hash": payload_hash,
                        "last_error_text": (last_error_text or "")[:1000] or None,
                        "last_synced_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    },
                )
        finally:
            await engine.dispose()

    async def retry_failed(self, *, limit: int = 100) -> list[str]:
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT booking_id
                            FROM integration.google_calendar_booking_event_map
                            WHERE sync_status IN ('failed', 'cancel_failed')
                            ORDER BY updated_at ASC
                            LIMIT :limit
                            """
                        ),
                        {"limit": limit},
                    )
                ).scalars().all()
                return [str(x) for x in rows]
        finally:
            await engine.dispose()
