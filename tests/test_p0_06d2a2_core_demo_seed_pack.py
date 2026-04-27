from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("sqlalchemy")

from app.infrastructure.db import booking_repository

STACK1_PATH = Path("seeds/stack1_seed.json")
STACK2_PATH = Path("seeds/stack2_patients.json")
STACK3_PATH = Path("seeds/stack3_booking.json")
EN_PATH = Path("locales/en.json")
RU_PATH = Path("locales/ru.json")


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_stack1_core_counts() -> None:
    stack1 = _load_json(STACK1_PATH)

    doctors = stack1["doctors"]
    public_doctors = [row for row in doctors if row.get("public_booking_enabled")]

    assert len(stack1["clinics"]) >= 1
    assert len(stack1["branches"]) >= 1
    assert len(doctors) >= 3
    assert len(public_doctors) >= 2
    assert len(stack1["services"]) >= 4
    assert len(stack1["doctor_access_codes"]) >= 3


def test_stack1_service_locale_keys() -> None:
    stack1 = _load_json(STACK1_PATH)
    en = _load_json(EN_PATH)
    ru = _load_json(RU_PATH)

    for service in stack1["services"]:
        title_key = service["title_key"]
        assert title_key in en
        assert title_key in ru


def test_stack1_doctor_access_code_references() -> None:
    stack1 = _load_json(STACK1_PATH)
    doctor_ids = {row["doctor_id"] for row in stack1["doctors"]}
    service_ids = {row["service_id"] for row in stack1["services"]}
    branch_ids = {row["branch_id"] for row in stack1["branches"]}

    for code in stack1["doctor_access_codes"]:
        assert code["doctor_id"] in doctor_ids
        for service_id in code.get("service_scope") or []:
            assert service_id in service_ids
        for branch_id in code.get("branch_scope") or []:
            assert branch_id in branch_ids


def test_stack2_patient_readiness() -> None:
    stack2 = _load_json(STACK2_PATH)
    patients = stack2["patients"]
    contacts = stack2["patient_contacts"]
    preferences = stack2["patient_preferences"]

    assert len(patients) >= 4

    phone_contacts = [row for row in contacts if row.get("contact_type") == "phone"]
    telegram_contacts = [row for row in contacts if row.get("contact_type") == "telegram"]
    assert len(phone_contacts) >= 2
    assert len(telegram_contacts) >= 2

    tg_3001 = [
        row for row in telegram_contacts if row.get("contact_value") == "3001" and row.get("patient_id") == "patient_sergey_ivanov"
    ]
    assert tg_3001

    phones_by_patient = {}
    telegram_by_patient = {}
    for row in phone_contacts:
        phones_by_patient.setdefault(row["patient_id"], 0)
        phones_by_patient[row["patient_id"]] += 1
    for row in telegram_contacts:
        telegram_by_patient.setdefault(row["patient_id"], 0)
        telegram_by_patient[row["patient_id"]] += 1

    phone_only = [pid for pid in phones_by_patient if pid not in telegram_by_patient]
    assert phone_only

    pref_by_patient = {row["patient_id"]: row for row in preferences}
    for patient_id in {
        "patient_sergey_ivanov",
        "patient_elena_ivanova",
        "patient_giorgi_beridze",
        "patient_maria_petrova",
    }:
        pref = pref_by_patient.get(patient_id)
        assert pref is not None
        assert pref.get("preferred_language")
        assert pref.get("preferred_reminder_channel")
        assert "allow_telegram" in pref
        assert "allow_sms" in pref
        assert pref.get("contact_time_window")


def test_stack3_reference_integrity() -> None:
    stack1 = _load_json(STACK1_PATH)
    stack2 = _load_json(STACK2_PATH)
    stack3 = _load_json(STACK3_PATH)

    patient_ids = {row["patient_id"] for row in stack2["patients"]}
    doctor_ids = {row["doctor_id"] for row in stack1["doctors"]}
    service_ids = {row["service_id"] for row in stack1["services"]}
    branch_ids = {row["branch_id"] for row in stack1["branches"]}
    slot_ids = {row["slot_id"] for row in stack3["availability_slots"]}
    session_ids = {row["booking_session_id"] for row in stack3["booking_sessions"]}

    for booking in stack3["bookings"]:
        assert booking["patient_id"] in patient_ids
        assert booking["doctor_id"] in doctor_ids
        assert booking["service_id"] in service_ids
        assert booking["branch_id"] in branch_ids
        if booking.get("slot_id"):
            assert booking["slot_id"] in slot_ids

    for slot in stack3["availability_slots"]:
        assert slot["doctor_id"] in doctor_ids
        for service_id in (slot.get("service_scope") or {}).get("service_ids") or []:
            assert service_id in service_ids

    for hold in stack3["slot_holds"]:
        assert hold["slot_id"] in slot_ids
        assert hold["booking_session_id"] in session_ids

    for waitlist in stack3["waitlist_entries"]:
        assert waitlist["patient_id"] in patient_ids
        assert waitlist["service_id"] in service_ids
        assert waitlist["doctor_id"] in doctor_ids
        assert waitlist["branch_id"] in branch_ids


def test_stack3_booking_slot_readiness_static() -> None:
    stack2 = _load_json(STACK2_PATH)
    stack3 = _load_json(STACK3_PATH)

    assert len(stack3["availability_slots"]) >= 12

    statuses = {row["status"] for row in stack3["bookings"]}
    assert {"pending_confirmation", "confirmed", "reschedule_requested", "canceled"}.issubset(statuses)

    assert len(stack3["waitlist_entries"]) >= 1

    tz = ZoneInfo("Europe/Moscow")
    local_hours = {
        datetime.fromisoformat(slot["start_at"].replace("Z", "+00:00")).astimezone(tz).hour
        for slot in stack3["availability_slots"]
    }
    assert 10 in local_hours
    assert 14 in local_hours
    assert 18 in local_hours

    active_statuses = {"pending_confirmation", "confirmed", "reschedule_requested"}
    sergey_active = [
        row
        for row in stack3["bookings"]
        if row["patient_id"] == "patient_sergey_ivanov" and row["status"] in active_statuses
    ]
    assert sergey_active

    patient_by_id = {row["patient_id"]: row for row in stack2["patients"]}
    assert patient_by_id.get("patient_sergey_ivanov") is not None
    assert any(
        row["patient_id"] == "patient_sergey_ivanov" and row["status"] == "confirmed"
        for row in stack3["bookings"]
    )


def test_stack3_relative_date_readiness() -> None:
    stack3 = _load_json(STACK3_PATH)
    shifted = booking_repository._shift_stack3_seed_dates(
        stack3,
        now=datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc),
        start_offset_days=1,
    )

    now = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
    shifted_slot_times = [datetime.fromisoformat(row["start_at"].replace("Z", "+00:00")) for row in shifted["availability_slots"]]
    future_slots = [value for value in shifted_slot_times if value > now]
    assert len(future_slots) >= 8

    shifted_bookings = shifted["bookings"]
    active_shifted = [
        row
        for row in shifted_bookings
        if row["status"] in {"pending_confirmation", "confirmed", "reschedule_requested"}
        and datetime.fromisoformat(row["scheduled_start_at"].replace("Z", "+00:00")) > now
    ]
    assert active_shifted

    original_slots = {row["slot_id"]: row for row in stack3["availability_slots"]}
    for shifted_slot in shifted["availability_slots"]:
        original_slot = original_slots[shifted_slot["slot_id"]]
        shifted_start = datetime.fromisoformat(shifted_slot["start_at"].replace("Z", "+00:00"))
        shifted_end = datetime.fromisoformat(shifted_slot["end_at"].replace("Z", "+00:00"))
        original_start = datetime.fromisoformat(original_slot["start_at"].replace("Z", "+00:00"))
        original_end = datetime.fromisoformat(original_slot["end_at"].replace("Z", "+00:00"))

        assert (shifted_end - shifted_start) == (original_end - original_start)
        assert shifted_slot["slot_id"] == original_slot["slot_id"]

    original_window = stack3["waitlist_entries"][0]["date_window"]
    shifted_window = shifted["waitlist_entries"][0]["date_window"]
    assert shifted_window["from"] != original_window["from"]
    assert shifted_window["to"] != original_window["to"]
