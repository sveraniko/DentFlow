from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.application.patient.family import (
    BookingPatientSelectionResult,
    BookingPatientSelectorService,
    LinkedPatientOption,
    PatientFamilyService,
)
from app.domain.patient_registry.models import PatientRelationship


def run(coro):
    return asyncio.run(coro)


@dataclass
class FakeFamilyRepo:
    relationships: list[PatientRelationship]
    linked: list[Patient]
    deactivated: PatientRelationship | None = None
    upserted: PatientRelationship | None = None

    async def list_relationships(self, *, clinic_id: str, manager_patient_id: str, include_inactive: bool = False) -> list[PatientRelationship]: return self.relationships
    async def list_linked_profiles_for_telegram(self, *, clinic_id: str, telegram_user_id: int, include_inactive: bool = False) -> list[Patient]: return self.linked
    async def upsert_relationship(self, relationship: PatientRelationship) -> PatientRelationship: self.upserted = relationship; return relationship
    async def deactivate_relationship(self, *, clinic_id: str, relationship_id: str) -> PatientRelationship | None: return self.deactivated
    async def get_patient_preferences(self, *, patient_id: str): return None


class FakeRegistryService:
    def __init__(self, rows: list[dict]) -> None: self.rows = rows
    async def find_by_phone(self, *, clinic_id: str, phone: str) -> list[dict]: return self.rows


def rel(**changes) -> PatientRelationship:
    payload = {
        "relationship_id": "rel_1", "clinic_id": "cl_1", "manager_patient_id": "pat_self", "related_patient_id": "pat_child",
        "relationship_type": "child", "consent_status": "active", "starts_at": datetime(2026, 1, 1, tzinfo=timezone.utc), "expires_at": None,
    }
    payload.update(changes)
    return PatientRelationship(**payload)


@dataclass
class FakeLinkedPatient:
    patient_id: str
    display_name: str
    is_manager: bool = False
    is_default_for_booking: bool = False
    phone: str | None = "+15550001"


def pat(patient_id: str, display_name: str, *, is_manager: bool = False, is_default_for_booking: bool = False) -> FakeLinkedPatient:
    return FakeLinkedPatient(patient_id=patient_id, display_name=display_name, is_manager=is_manager, is_default_for_booking=is_default_for_booking)


def test_family_service_validation_rules() -> None:
    service = PatientFamilyService(FakeFamilyRepo([], []))
    run(service.add_relationship(rel(relationship_type="spouse")))
    with pytest.raises(ValueError): run(service.add_relationship(rel(relationship_type="bad")))
    with pytest.raises(ValueError): run(service.add_relationship(rel(consent_status="bad")))
    with pytest.raises(ValueError): run(service.add_relationship(rel(manager_patient_id="same", related_patient_id="same", relationship_type="child")))
    with pytest.raises(ValueError): run(service.add_relationship(rel(expires_at=datetime(2025, 1, 1, tzinfo=timezone.utc))))


def test_list_linked_profiles_maps_and_sorts() -> None:
    repo = FakeFamilyRepo([], [pat("pat_child", "Child", is_default_for_booking=True), pat("pat_self", "Self", is_manager=True)])
    service = PatientFamilyService(repo)
    options = run(service.list_linked_profiles_for_telegram(clinic_id="cl_1", telegram_user_id=1))
    assert isinstance(options[0], LinkedPatientOption)
    assert options[0].patient_id == "pat_self" and options[0].is_self and options[0].phone == "+15550001"


def test_add_and_deactivate_delegate() -> None:
    relationship = rel()
    repo = FakeFamilyRepo([], [], deactivated=relationship)
    service = PatientFamilyService(repo)
    assert run(service.add_relationship(relationship)).relationship_id == "rel_1" and repo.upserted is not None
    assert run(service.deactivate_relationship(clinic_id="cl_1", relationship_id="rel_1")) == relationship


def test_booking_selector_resolve_for_telegram_modes() -> None:
    selector0 = BookingPatientSelectorService(PatientFamilyService(FakeFamilyRepo([], [])))
    assert run(selector0.resolve_for_telegram(clinic_id="cl_1", telegram_user_id=1)).mode == "phone_required"
    selector1 = BookingPatientSelectorService(PatientFamilyService(FakeFamilyRepo([], [pat("p1", "One", is_manager=True)])))
    assert run(selector1.resolve_for_telegram(clinic_id="cl_1", telegram_user_id=1)).mode == "single_match"
    selector2 = BookingPatientSelectorService(PatientFamilyService(FakeFamilyRepo([], [pat("p1", "One", is_manager=True), pat("p2", "Two")])))
    assert run(selector2.resolve_for_telegram(clinic_id="cl_1", telegram_user_id=1)).mode == "multiple_profiles"


def test_select_patient_modes() -> None:
    selector = BookingPatientSelectorService(PatientFamilyService(FakeFamilyRepo([], [pat("p1", "One", is_manager=True)])))
    assert run(selector.select_patient(clinic_id="cl_1", telegram_user_id=1, patient_id="p1")).mode == "single_match"
    assert run(selector.select_patient(clinic_id="cl_1", telegram_user_id=1, patient_id="p9")).mode == "no_match"


def test_resolve_for_phone_modes() -> None:
    selector_single = BookingPatientSelectorService(PatientFamilyService(FakeFamilyRepo([], [])), FakeRegistryService([{"patient_id": "p1", "display_name": "One"}]))
    assert run(selector_single.resolve_for_phone(clinic_id="cl_1", phone="+1")).mode == "single_match"
    selector_none = BookingPatientSelectorService(PatientFamilyService(FakeFamilyRepo([], [])), FakeRegistryService([]))
    assert run(selector_none.resolve_for_phone(clinic_id="cl_1", phone="+1")).mode == "minimal_name_required"
    selector_multi = BookingPatientSelectorService(PatientFamilyService(FakeFamilyRepo([], [])), FakeRegistryService([{"patient_id": "p1", "display_name": "One"}, {"patient_id": "p2", "display_name": "Two"}]))
    assert run(selector_multi.resolve_for_phone(clinic_id="cl_1", phone="+1")).mode == "multiple_profiles"


def test_dataclasses_exist() -> None:
    assert BookingPatientSelectionResult(mode="no_match").mode == "no_match"
