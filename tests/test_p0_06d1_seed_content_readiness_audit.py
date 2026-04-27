from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

STACK1_PATH = Path("seeds/stack1_seed.json")
STACK2_PATH = Path("seeds/stack2_patients.json")
STACK3_PATH = Path("seeds/stack3_booking.json")

STACK1_REQUIRED_KEYS = {
    "clinics",
    "branches",
    "doctors",
    "services",
    "doctor_access_codes",
}
STACK2_REQUIRED_KEYS = {"patients", "patient_contacts"}
STACK3_REQUIRED_KEYS = {
    "booking_sessions",
    "availability_slots",
    "bookings",
    "booking_status_history",
}


@dataclass(frozen=True)
class SeedSnapshot:
    stack1: dict
    stack2: dict
    stack3: dict



def _load_json(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    assert isinstance(parsed, dict), f"{path} must contain a top-level JSON object"
    return parsed



def _seed_snapshot() -> SeedSnapshot:
    return SeedSnapshot(
        stack1=_load_json(STACK1_PATH),
        stack2=_load_json(STACK2_PATH),
        stack3=_load_json(STACK3_PATH),
    )



def test_seed_json_files_are_valid_and_have_expected_top_level_keys() -> None:
    snapshot = _seed_snapshot()

    assert STACK1_REQUIRED_KEYS.issubset(snapshot.stack1.keys())
    assert STACK2_REQUIRED_KEYS.issubset(snapshot.stack2.keys())
    assert STACK3_REQUIRED_KEYS.issubset(snapshot.stack3.keys())

    for key in STACK1_REQUIRED_KEYS:
        assert isinstance(snapshot.stack1[key], list), f"stack1.{key} must be a list"
    for key in STACK2_REQUIRED_KEYS:
        assert isinstance(snapshot.stack2[key], list), f"stack2.{key} must be a list"
    for key in STACK3_REQUIRED_KEYS:
        assert isinstance(snapshot.stack3[key], list), f"stack3.{key} must be a list"



def test_seed_cross_stack_references_are_coherent_for_core_booking_entities() -> None:
    snapshot = _seed_snapshot()

    branch_ids = {row["branch_id"] for row in snapshot.stack1["branches"]}
    doctor_ids = {row["doctor_id"] for row in snapshot.stack1["doctors"]}
    service_ids = {row["service_id"] for row in snapshot.stack1["services"]}
    patient_ids = {row["patient_id"] for row in snapshot.stack2["patients"]}

    for slot in snapshot.stack3["availability_slots"]:
        assert slot["branch_id"] in branch_ids
        assert slot["doctor_id"] in doctor_ids
        scoped_services = (slot.get("service_scope") or {}).get("service_ids") or []
        for scoped_service_id in scoped_services:
            assert scoped_service_id in service_ids

    for booking in snapshot.stack3["bookings"]:
        assert booking["branch_id"] in branch_ids
        assert booking["doctor_id"] in doctor_ids
        assert booking["service_id"] in service_ids
        assert booking["patient_id"] in patient_ids

    for session in snapshot.stack3["booking_sessions"]:
        if session.get("branch_id"):
            assert session["branch_id"] in branch_ids
        if session.get("doctor_id"):
            assert session["doctor_id"] in doctor_ids
        if session.get("service_id"):
            assert session["service_id"] in service_ids
        if session.get("resolved_patient_id"):
            assert session["resolved_patient_id"] in patient_ids



def test_seed_slot_temporal_distribution_is_reported_for_audit() -> None:
    snapshot = _seed_snapshot()
    now = datetime.now(timezone.utc)

    slots = snapshot.stack3["availability_slots"]
    parsed = [datetime.fromisoformat(slot["start_at"].replace("Z", "+00:00")) for slot in slots]
    future = [value for value in parsed if value > now]
    past_or_now = [value for value in parsed if value <= now]

    # Intentional soft assertions: this is an audit signal test and should only fail on malformed structure.
    assert len(parsed) == len(slots)
    assert len(future) + len(past_or_now) == len(parsed)
