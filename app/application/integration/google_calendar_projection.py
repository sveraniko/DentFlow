from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from app.domain.events import EventEnvelope

VISIBLE_BOOKING_STATUSES: frozenset[str] = frozenset(
    {
        "pending_confirmation",
        "confirmed",
        "reschedule_requested",
        "checked_in",
        "in_service",
        "completed",
        "no_show",
    }
)


@dataclass(frozen=True, slots=True)
class CalendarProjectionBooking:
    booking_id: str
    clinic_id: str
    doctor_id: str
    service_id: str
    patient_id: str
    status: str
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    timezone: str
    doctor_calendar_id: str
    patient_display_name: str
    doctor_display_name: str
    service_label: str
    service_locale: str
    branch_label: str


@dataclass(frozen=True, slots=True)
class CalendarEventMapping:
    booking_id: str
    clinic_id: str
    calendar_provider: str
    target_calendar_id: str
    external_event_id: str | None
    sync_status: str
    sync_attempts: int
    last_synced_at: datetime | None
    last_error_text: str | None
    payload_hash: str | None


@dataclass(frozen=True, slots=True)
class CalendarEventPayload:
    title: str
    description: str
    starts_at_local: datetime
    ends_at_local: datetime
    timezone: str
    status: str


class CalendarProjectionRepository(Protocol):
    async def get_booking_projection(self, *, booking_id: str) -> CalendarProjectionBooking | None: ...

    async def get_event_mapping(self, *, booking_id: str) -> CalendarEventMapping | None: ...

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
    ) -> None: ...


class GoogleCalendarGateway(Protocol):
    async def upsert_event(
        self,
        *,
        calendar_id: str,
        event: CalendarEventPayload,
        external_event_id: str | None,
    ) -> str: ...

    async def cancel_event(self, *, calendar_id: str, external_event_id: str) -> None: ...


@dataclass(slots=True)
class GoogleCalendarProjectionService:
    repository: CalendarProjectionRepository
    gateway: GoogleCalendarGateway
    dentflow_base_url: str = "https://dentflow.local"

    async def handle_event(self, event: EventEnvelope) -> bool:
        if not event.event_name.startswith("booking."):
            return False
        await self.sync_booking(booking_id=event.entity_id)
        return True

    async def sync_booking(self, *, booking_id: str) -> None:
        booking = await self.repository.get_booking_projection(booking_id=booking_id)
        if booking is None:
            return

        mapping = await self.repository.get_event_mapping(booking_id=booking_id)
        if booking.status == "canceled":
            await self._cancel_projection(booking=booking, mapping=mapping)
            return

        if booking.status not in VISIBLE_BOOKING_STATUSES:
            return

        event_payload = render_calendar_event(booking=booking, dentflow_base_url=self.dentflow_base_url)
        payload_hash = hash_payload(event_payload)
        if mapping and mapping.payload_hash == payload_hash and mapping.sync_status == "synced":
            return

        try:
            external_event_id = await self.gateway.upsert_event(
                calendar_id=booking.doctor_calendar_id,
                event=event_payload,
                external_event_id=mapping.external_event_id if mapping else None,
            )
            await self.repository.upsert_event_mapping(
                booking_id=booking.booking_id,
                clinic_id=booking.clinic_id,
                target_calendar_id=booking.doctor_calendar_id,
                external_event_id=external_event_id,
                sync_status="synced",
                payload_hash=payload_hash,
                last_error_text=None,
            )
        except Exception as exc:  # noqa: BLE001
            await self.repository.upsert_event_mapping(
                booking_id=booking.booking_id,
                clinic_id=booking.clinic_id,
                target_calendar_id=booking.doctor_calendar_id,
                external_event_id=mapping.external_event_id if mapping else None,
                sync_status="failed",
                payload_hash=payload_hash,
                last_error_text=str(exc),
            )

    async def _cancel_projection(self, *, booking: CalendarProjectionBooking, mapping: CalendarEventMapping | None) -> None:
        if mapping and mapping.external_event_id:
            try:
                await self.gateway.cancel_event(
                    calendar_id=mapping.target_calendar_id,
                    external_event_id=mapping.external_event_id,
                )
            except Exception as exc:  # noqa: BLE001
                await self.repository.upsert_event_mapping(
                    booking_id=booking.booking_id,
                    clinic_id=booking.clinic_id,
                    target_calendar_id=mapping.target_calendar_id,
                    external_event_id=mapping.external_event_id,
                    sync_status="cancel_failed",
                    payload_hash=mapping.payload_hash,
                    last_error_text=str(exc),
                )
                return

        await self.repository.upsert_event_mapping(
            booking_id=booking.booking_id,
            clinic_id=booking.clinic_id,
            target_calendar_id=mapping.target_calendar_id if mapping else booking.doctor_calendar_id,
            external_event_id=None,
            sync_status="canceled",
            payload_hash=None,
            last_error_text=None,
        )


def render_calendar_event(*, booking: CalendarProjectionBooking, dentflow_base_url: str) -> CalendarEventPayload:
    tz = ZoneInfo(booking.timezone)
    local_start = booking.scheduled_start_at.astimezone(tz)
    local_end = booking.scheduled_end_at.astimezone(tz)
    service_label = render_service_label(booking.service_label, booking.service_locale)
    title = f"{local_start:%H:%M} • {mask_patient_name(booking.patient_display_name)} • {service_label}"
    description = "\n".join(
        [
            f"DentFlow booking: {booking.booking_id}",
            f"Status: {booking.status}",
            f"Doctor: {booking.doctor_display_name}",
            f"Branch: {booking.branch_label}",
            f"Open in DentFlow: {dentflow_base_url}/admin/booking/{booking.booking_id}",
        ]
    )
    return CalendarEventPayload(
        title=title,
        description=description,
        starts_at_local=local_start,
        ends_at_local=local_end,
        timezone=booking.timezone,
        status=booking.status,
    )


def mask_patient_name(value: str) -> str:
    chunks = [c for c in value.strip().split(" ") if c]
    if not chunks:
        return "Patient"
    if len(chunks) == 1:
        return chunks[0]
    return f"{chunks[0]} {chunks[1][0]}."


def render_service_label(service_label: str, preferred_locale: str) -> str:
    localized = _lookup_localized_service_label(service_label, preferred_locale=preferred_locale)
    if localized:
        return localized
    return _humanize_service_label(service_label)


def _lookup_localized_service_label(service_label: str, *, preferred_locale: str) -> str | None:
    locales = _service_locale_catalog()
    candidates = [preferred_locale, "ru", "en"]
    for locale in candidates:
        if not locale:
            continue
        value = locales.get(locale, {}).get(service_label)
        if value:
            return value
    return None


@lru_cache(maxsize=1)
def _service_locale_catalog() -> dict[str, dict[str, str]]:
    base = Path("locales")
    catalogs: dict[str, dict[str, str]] = {}
    for locale in ("ru", "en"):
        locale_file = base / f"{locale}.json"
        if locale_file.exists():
            catalogs[locale] = json.loads(locale_file.read_text(encoding="utf-8"))
    return catalogs


def _humanize_service_label(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        return "Service"
    if "." in candidate:
        candidate = candidate.rsplit(".", 1)[-1]
    candidate = candidate.replace("_", " ").replace("-", " ").strip()
    if not candidate:
        return "Service"
    return candidate[:1].upper() + candidate[1:]


def hash_payload(payload: CalendarEventPayload) -> str:
    raw = "|".join(
        [
            payload.title,
            payload.description,
            payload.starts_at_local.isoformat(),
            payload.ends_at_local.isoformat(),
            payload.timezone,
            payload.status,
        ]
    )
    return sha256(raw.encode("utf-8")).hexdigest()
