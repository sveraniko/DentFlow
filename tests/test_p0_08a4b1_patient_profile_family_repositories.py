from datetime import datetime, timezone
from pathlib import Path

from app.domain.patient_registry import PatientPreference, PatientProfileDetails, PatientRelationship
from app.infrastructure.db.patient_repository import (
    DbPatientRegistryRepository,
    _map_patient_preference,
    _map_patient_profile_details,
    _map_patient_relationship,
)

ROOT = Path(__file__).resolve().parents[1]


def test_repository_methods_exist() -> None:
    for name in [
        "get_profile_details",
        "upsert_profile_details",
        "get_profile_completion_state",
        "list_relationships",
        "list_linked_profiles_for_telegram",
        "upsert_relationship",
        "deactivate_relationship",
        "get_patient_preferences",
        "upsert_patient_preferences",
        "update_notification_preferences",
        "update_branch_preferences",
    ]:
        assert hasattr(DbPatientRegistryRepository, name)


def test_map_patient_profile_details() -> None:
    row = {
        "patient_id": "p1",
        "clinic_id": "c1",
        "profile_completion_state": "partial",
        "email": "a@b.com",
        "address_line1": "1",
        "address_line2": None,
        "city": "City",
        "postal_code": "12345",
        "country_code": "US",
        "emergency_contact_name": "EC",
        "emergency_contact_phone": "555",
        "profile_completed_at": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    mapped = _map_patient_profile_details(row)
    assert isinstance(mapped, PatientProfileDetails)
    assert mapped.city == "City"


def test_map_patient_relationship() -> None:
    row = {
        "relationship_id": "rel1",
        "clinic_id": "c1",
        "manager_patient_id": "p1",
        "related_patient_id": "p2",
        "relationship_type": "child",
        "consent_status": "active",
        "authority_scope": "booking",
        "is_default_for_booking": True,
        "is_default_notification_recipient": False,
        "starts_at": None,
        "expires_at": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    mapped = _map_patient_relationship(row)
    assert isinstance(mapped, PatientRelationship)
    assert mapped.relationship_type == "child"


def test_map_patient_preference_new_fields() -> None:
    row = {
        "patient_preference_id": "pp1",
        "patient_id": "p1",
        "preferred_language": "en",
        "preferred_reminder_channel": "telegram",
        "allow_sms": True,
        "allow_telegram": True,
        "allow_call": False,
        "allow_email": False,
        "marketing_opt_in": False,
        "contact_time_window": None,
        "notification_recipient_strategy": "manager",
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
        "quiet_hours_timezone": "UTC",
        "default_branch_id": "b1",
        "allow_any_branch": False,
    }
    mapped = _map_patient_preference(row)
    assert isinstance(mapped, PatientPreference)
    assert mapped.notification_recipient_strategy == "manager"
    assert mapped.quiet_hours_start == "22:00"
    assert mapped.quiet_hours_end == "08:00"
    assert mapped.quiet_hours_timezone == "UTC"
    assert mapped.default_branch_id == "b1"
    assert mapped.allow_any_branch is False


def test_no_alembic_versions_added() -> None:
    assert not (ROOT / "alembic/versions").exists()
