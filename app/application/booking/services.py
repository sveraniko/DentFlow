from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Protocol

from app.domain.booking import (
    BOOKING_FINAL_STATUSES,
    AdminEscalation,
    AvailabilitySlot,
    Booking,
    BookingSession,
    BookingStatusHistory,
    SessionEvent,
    SlotHold,
    WaitlistEntry,
)


class BookingRepository(Protocol):
    async def upsert_booking_session(self, item: BookingSession) -> None: ...
    async def get_booking_session(self, booking_session_id: str) -> BookingSession | None: ...
    async def append_session_event(self, event: SessionEvent) -> None: ...

    async def upsert_availability_slot(self, item: AvailabilitySlot) -> None: ...
    async def get_availability_slot(self, slot_id: str) -> AvailabilitySlot | None: ...
    async def list_availability_slots(self, *, doctor_id: str, start_at: datetime, end_at: datetime) -> list[AvailabilitySlot]: ...

    async def upsert_slot_hold(self, item: SlotHold) -> None: ...
    async def get_slot_hold(self, slot_hold_id: str) -> SlotHold | None: ...
    async def find_slot_hold(self, *, slot_id: str, booking_session_id: str) -> SlotHold | None: ...

    async def upsert_booking(self, item: Booking) -> None: ...
    async def get_booking(self, booking_id: str) -> Booking | None: ...
    async def append_booking_status_history(self, item: BookingStatusHistory) -> None: ...
    async def list_bookings_by_patient(self, *, patient_id: str) -> list[Booking]: ...
    async def list_bookings_by_doctor_time_window(self, *, doctor_id: str, start_at: datetime, end_at: datetime) -> list[Booking]: ...
    async def list_bookings_by_status_time_window(self, *, status: str, start_at: datetime, end_at: datetime) -> list[Booking]: ...

    async def upsert_waitlist_entry(self, item: WaitlistEntry) -> None: ...
    async def get_waitlist_entry(self, waitlist_entry_id: str) -> WaitlistEntry | None: ...

    async def upsert_admin_escalation(self, item: AdminEscalation) -> None: ...
    async def get_admin_escalation(self, admin_escalation_id: str) -> AdminEscalation | None: ...


@dataclass(slots=True)
class BookingSessionService:
    repository: BookingRepository

    async def create_session(self, session: BookingSession) -> BookingSession:
        await self.repository.upsert_booking_session(session)
        return session

    async def update_session(self, session: BookingSession) -> BookingSession:
        await self.repository.upsert_booking_session(session)
        return session

    async def load_session(self, booking_session_id: str) -> BookingSession | None:
        return await self.repository.get_booking_session(booking_session_id)

    async def expire_session(self, session: BookingSession) -> BookingSession:
        expired = BookingSession(**{**asdict(session), "status": "expired", "updated_at": datetime.now(timezone.utc)})
        await self.repository.upsert_booking_session(expired)
        return expired

    async def append_event(self, event: SessionEvent) -> None:
        await self.repository.append_session_event(event)


@dataclass(slots=True)
class AvailabilitySlotService:
    repository: BookingRepository

    async def create_slot(self, slot: AvailabilitySlot) -> AvailabilitySlot:
        await self.repository.upsert_availability_slot(slot)
        return slot

    async def update_slot(self, slot: AvailabilitySlot) -> AvailabilitySlot:
        await self.repository.upsert_availability_slot(slot)
        return slot

    async def load_slot(self, slot_id: str) -> AvailabilitySlot | None:
        return await self.repository.get_availability_slot(slot_id)

    async def list_slots_by_doctor_time_window(self, *, doctor_id: str, start_at: datetime, end_at: datetime) -> list[AvailabilitySlot]:
        return await self.repository.list_availability_slots(doctor_id=doctor_id, start_at=start_at, end_at=end_at)


@dataclass(slots=True)
class SlotHoldService:
    repository: BookingRepository

    async def create_hold(self, hold: SlotHold) -> SlotHold:
        await self.repository.upsert_slot_hold(hold)
        return hold

    async def update_hold_status(self, hold: SlotHold, status: str) -> SlotHold:
        updated = SlotHold(**{**asdict(hold), "status": status})
        await self.repository.upsert_slot_hold(updated)
        return updated

    async def load_hold(self, slot_hold_id: str) -> SlotHold | None:
        return await self.repository.get_slot_hold(slot_hold_id)

    async def find_by_slot_session(self, *, slot_id: str, booking_session_id: str) -> SlotHold | None:
        return await self.repository.find_slot_hold(slot_id=slot_id, booking_session_id=booking_session_id)


@dataclass(slots=True)
class BookingService:
    repository: BookingRepository

    async def create_booking(self, booking: Booking) -> Booking:
        self._validate_final_status(booking.status)
        await self.repository.upsert_booking(booking)
        return booking

    async def update_booking(self, booking: Booking) -> Booking:
        self._validate_final_status(booking.status)
        await self.repository.upsert_booking(booking)
        return booking

    async def load_booking(self, booking_id: str) -> Booking | None:
        return await self.repository.get_booking(booking_id)

    async def append_status_history(self, history: BookingStatusHistory) -> None:
        self._validate_final_status(history.new_status)
        if history.old_status:
            self._validate_final_status(history.old_status)
        await self.repository.append_booking_status_history(history)

    async def list_by_patient(self, *, patient_id: str) -> list[Booking]:
        return await self.repository.list_bookings_by_patient(patient_id=patient_id)

    async def list_by_doctor_time_window(self, *, doctor_id: str, start_at: datetime, end_at: datetime) -> list[Booking]:
        return await self.repository.list_bookings_by_doctor_time_window(doctor_id=doctor_id, start_at=start_at, end_at=end_at)

    async def list_by_status_time_window(self, *, status: str, start_at: datetime, end_at: datetime) -> list[Booking]:
        self._validate_final_status(status)
        return await self.repository.list_bookings_by_status_time_window(status=status, start_at=start_at, end_at=end_at)

    def _validate_final_status(self, status: str) -> None:
        if status not in BOOKING_FINAL_STATUSES:
            raise ValueError(f"Unsupported final booking status: {status}")


@dataclass(slots=True)
class WaitlistService:
    repository: BookingRepository

    async def create_or_update(self, item: WaitlistEntry) -> WaitlistEntry:
        await self.repository.upsert_waitlist_entry(item)
        return item

    async def load(self, waitlist_entry_id: str) -> WaitlistEntry | None:
        return await self.repository.get_waitlist_entry(waitlist_entry_id)


@dataclass(slots=True)
class AdminEscalationService:
    repository: BookingRepository

    async def create_or_update(self, item: AdminEscalation) -> AdminEscalation:
        await self.repository.upsert_admin_escalation(item)
        return item

    async def load(self, admin_escalation_id: str) -> AdminEscalation | None:
        return await self.repository.get_admin_escalation(admin_escalation_id)
