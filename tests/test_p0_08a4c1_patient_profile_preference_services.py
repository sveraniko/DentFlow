from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass

import pytest

from app.application.patient.profile import PatientPreferenceService, PatientProfileService
from app.domain.patient_registry.models import PatientPreference, PatientProfileDetails


def run(coro):
    return asyncio.run(coro)


@dataclass
class FakeProfileRepo:
    details: PatientProfileDetails | None = None

    async def get_profile_details(self, *, clinic_id: str, patient_id: str) -> PatientProfileDetails | None: return self.details
    async def upsert_profile_details(self, details: PatientProfileDetails) -> PatientProfileDetails: self.details = details; return details
    async def get_profile_completion_state(self, *, clinic_id: str, patient_id: str) -> str | None: return self.details.profile_completion_state if self.details else None
    async def get_patient_preferences(self, *, patient_id: str) -> PatientPreference | None: return None
    async def upsert_patient_preferences(self, preference: PatientPreference) -> PatientPreference: return preference


class FakePreferenceRepo:
    def __init__(self) -> None:
        self.preference = PatientPreference(patient_preference_id="pp_1", patient_id="pat_1")
        self.last_notification_changes = None
        self.last_branch_update = None

    async def get_patient_preferences(self, *, patient_id: str) -> PatientPreference | None: return self.preference
    async def update_notification_preferences(self, *, patient_id: str, **changes) -> PatientPreference:
        self.last_notification_changes = {"patient_id": patient_id, **changes}
        payload = asdict(self.preference)
        for key, value in changes.items():
            if value is not None:
                payload[key] = value
        self.preference = PatientPreference(**payload)
        return self.preference
    async def update_branch_preferences(self, *, patient_id: str, default_branch_id: str | None, allow_any_branch: bool) -> PatientPreference:
        self.last_branch_update = {"patient_id": patient_id, "default_branch_id": default_branch_id, "allow_any_branch": allow_any_branch}
        payload = asdict(self.preference); payload.update({"default_branch_id": default_branch_id, "allow_any_branch": allow_any_branch})
        self.preference = PatientPreference(**payload)
        return self.preference


class FakeReferenceService:
    def __init__(self, known_branch_ids: set[str]) -> None: self._known = known_branch_ids
    def get_branch(self, clinic_id: str, branch_id: str): return object() if branch_id in self._known else None


def test_profile_service_exists_and_methods_exist() -> None:
    service = PatientProfileService(FakeProfileRepo())
    assert hasattr(service, "get_profile_details") and hasattr(service, "save_profile_details")


def test_save_profile_details_delegates_and_normalizes() -> None:
    repo = FakeProfileRepo(); service = PatientProfileService(repo)
    details = run(service.save_profile_details(clinic_id="cl_1", patient_id="pat_1", email="a@b.com", country_code="us", city="NY"))
    assert details.email == "a@b.com" and details.country_code == "US" and details.profile_completion_state == "partial"


def test_completion_state_rules() -> None:
    service = PatientProfileService(FakeProfileRepo())
    assert service.compute_profile_completion_state(has_name=False, has_phone=True, details=None) == "missing"
    assert service.compute_profile_completion_state(has_name=True, has_phone=True, details=None) == "minimal"
    assert service.compute_profile_completion_state(has_name=True, has_phone=True, details=PatientProfileDetails(patient_id="p", clinic_id="c", city="A")) == "partial"
    assert service.compute_profile_completion_state(has_name=True, has_phone=True, details=PatientProfileDetails(patient_id="p", clinic_id="c", email="a@b", address_line1="x", city="A", country_code="US")) == "completed"


def test_invalid_email_rejected_but_empty_allowed() -> None:
    service = PatientProfileService(FakeProfileRepo())
    with pytest.raises(ValueError):
        run(service.save_profile_details(clinic_id="c", patient_id="p", email="bad-email"))
    run(service.save_profile_details(clinic_id="c", patient_id="p", email=""))
    run(service.save_profile_details(clinic_id="c", patient_id="p", email=None))


def test_preference_notification_update_validation_and_delegation() -> None:
    repo = FakePreferenceRepo(); service = PatientPreferenceService(repo)
    result = run(service.update_notification_settings(patient_id="pat_1", preferred_reminder_channel="telegram", allow_sms=None, allow_telegram=True, allow_call=False, allow_email=True, notification_recipient_strategy="guardian_or_self", quiet_hours_start="22:00", quiet_hours_end="07:30", quiet_hours_timezone="UTC"))
    assert result.preferred_reminder_channel == "telegram" and repo.last_notification_changes["allow_sms"] is None


def test_preference_invalid_notification_inputs() -> None:
    service = PatientPreferenceService(FakePreferenceRepo())
    with pytest.raises(ValueError): run(service.update_notification_settings(patient_id="pat_1", preferred_reminder_channel="fax"))
    with pytest.raises(ValueError): run(service.update_notification_settings(patient_id="pat_1", notification_recipient_strategy="unknown"))
    with pytest.raises(ValueError): run(service.update_notification_settings(patient_id="pat_1", quiet_hours_start="24:00"))
    with pytest.raises(ValueError): run(service.update_notification_settings(patient_id="pat_1", quiet_hours_timezone="Mars/Olympus"))


def test_branch_preference_validation_and_delegation() -> None:
    repo = FakePreferenceRepo(); service = PatientPreferenceService(repo, reference_service=FakeReferenceService({"b_1"}))
    assert run(service.update_branch_preference(clinic_id="cl_1", patient_id="pat_1", default_branch_id=None, allow_any_branch=True)).allow_any_branch
    with pytest.raises(ValueError): run(service.update_branch_preference(clinic_id="cl_1", patient_id="pat_1", default_branch_id=None, allow_any_branch=False))
    with pytest.raises(ValueError): run(service.update_branch_preference(clinic_id="cl_1", patient_id="pat_1", default_branch_id="missing", allow_any_branch=False))
    valid = run(service.update_branch_preference(clinic_id="cl_1", patient_id="pat_1", default_branch_id="b_1", allow_any_branch=False))
    assert valid.default_branch_id == "b_1" and repo.last_branch_update["default_branch_id"] == "b_1"


def test_no_migration_files_created() -> None:
    import pathlib
    migration_like = [p for p in pathlib.Path('.').rglob('*') if p.is_file() and 'alembic' in str(p).lower()]
    assert not migration_like
