from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.application.booking import BookingPatientResolutionService, BookingService
from app.domain.booking import BOOKING_FINAL_STATUSES, Booking, BookingStatusHistory


class _Repo:
    def __init__(self) -> None:
        self.bookings: dict[str, Booking] = {}
        self.history: list[BookingStatusHistory] = []

    async def upsert_booking(self, item: Booking) -> None:
        self.bookings[item.booking_id] = item

    async def get_booking(self, booking_id: str):
        return self.bookings.get(booking_id)

    async def append_booking_status_history(self, item: BookingStatusHistory) -> None:
        self.history.append(item)

    async def list_bookings_by_patient(self, *, patient_id: str):
        return [b for b in self.bookings.values() if b.patient_id == patient_id]

    async def list_bookings_by_doctor_time_window(self, *, doctor_id: str, start_at: datetime, end_at: datetime):
        return [b for b in self.bookings.values() if b.doctor_id == doctor_id and start_at <= b.scheduled_start_at < end_at]

    async def list_bookings_by_status_time_window(self, *, status: str, start_at: datetime, end_at: datetime):
        return [b for b in self.bookings.values() if b.status == status and start_at <= b.scheduled_start_at < end_at]


def test_booking_service_enforces_canonical_statuses_and_history_append() -> None:
    repo = _Repo()
    service = BookingService(repo)  # type: ignore[arg-type]

    booking = Booking(
        booking_id="b1",
        clinic_id="clinic_main",
        branch_id="branch_central",
        patient_id="patient_sergey_ivanov",
        doctor_id="doctor_anna",
        service_id="service_consult",
        slot_id="slot_1",
        booking_mode="patient_bot",
        source_channel="telegram",
        scheduled_start_at=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
        scheduled_end_at=datetime(2026, 4, 20, 10, 30, tzinfo=timezone.utc),
        status="pending_confirmation",
        reason_for_visit_short=None,
        patient_note=None,
        confirmation_required=True,
        confirmed_at=None,
        canceled_at=None,
        checked_in_at=None,
        in_service_at=None,
        completed_at=None,
        no_show_at=None,
        created_at=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
    )
    asyncio.run(service.create_booking(booking))

    loaded = asyncio.run(service.load_booking("b1"))
    assert loaded and loaded.status in BOOKING_FINAL_STATUSES

    asyncio.run(
        service.append_status_history(
        BookingStatusHistory(
            booking_status_history_id="h1",
            booking_id="b1",
            old_status="pending_confirmation",
            new_status="confirmed",
            reason_code="patient_confirmed",
            actor_type="patient",
            actor_id="telegram:3001",
            occurred_at=datetime(2026, 4, 20, 9, 2, tzinfo=timezone.utc),
        )
    )
    )
    assert repo.history[0].new_status == "confirmed"

    with pytest.raises(ValueError):
        asyncio.run(service.update_booking(replace(booking, status="cancelled")))


class _Finder:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    async def find_patients_by_exact_contact(self, *, contact_type: str, contact_value: str) -> list[dict]:
        return self.rows

    async def find_patients_by_external_id(self, *, external_system: str, external_id: str) -> list[dict]:
        return self.rows


def test_booking_patient_resolution_typed_no_exact_ambiguous() -> None:
    no_match = BookingPatientResolutionService(_Finder([]))
    result = asyncio.run(no_match.resolve_by_exact_normalized_contact(contact_type="phone", contact_value="+1 555 1111"))
    assert result.resolution_kind == "no_match"

    exact = BookingPatientResolutionService(
        _Finder([{"patient_id": "p1", "clinic_id": "clinic_main", "display_name": "Sergey", "normalized_lookup_value": "15551111"}])
    )
    exact_result = asyncio.run(exact.resolve_by_exact_normalized_contact(contact_type="phone", contact_value="+1 555 1111"))
    assert exact_result.resolution_kind == "exact_match"
    assert exact_result.candidates[0].patient_id == "p1"

    ambiguous = BookingPatientResolutionService(
        _Finder(
            [
                {"patient_id": "p1", "clinic_id": "clinic_main", "display_name": "Parent", "normalized_lookup_value": "15551111"},
                {"patient_id": "p2", "clinic_id": "clinic_main", "display_name": "Child", "normalized_lookup_value": "15551111"},
            ]
        )
    )
    ambiguous_result = asyncio.run(
        ambiguous.resolve_by_exact_normalized_contact(contact_type="phone", contact_value="+1 555 1111")
    )
    assert ambiguous_result.resolution_kind == "ambiguous_match"
    assert [c.patient_id for c in ambiguous_result.candidates] == ["p1", "p2"]
