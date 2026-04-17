from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.application.patient.registry import PatientRegistryService


@dataclass(frozen=True)
class DoctorPatientSnapshot:
    patient_id: str
    display_name: str
    patient_number: str | None
    phone_raw: str | None
    has_photo: bool
    active_flags_summary: str | None


class DoctorPatientReader(Protocol):
    async def read_snapshot(self, *, patient_id: str) -> DoctorPatientSnapshot | None: ...


@dataclass(slots=True)
class RegistryDoctorPatientReader:
    patient_registry: PatientRegistryService

    async def read_snapshot(self, *, patient_id: str) -> DoctorPatientSnapshot | None:
        patient = self.patient_registry.get_patient(patient_id)
        if patient is None:
            return None
        primary_phone = next(
            (
                c
                for c in self.patient_registry.repository.contacts.values()
                if c.patient_id == patient_id and c.contact_type == "phone" and c.is_primary and c.is_active
            ),
            None,
        )
        has_photo = self.patient_registry.get_primary_photo(patient_id) is not None
        flags = self.patient_registry.active_flags(patient_id)
        return DoctorPatientSnapshot(
            patient_id=patient.patient_id,
            display_name=patient.display_name,
            patient_number=patient.patient_number,
            phone_raw=primary_phone.contact_value if primary_phone else None,
            has_photo=has_photo,
            active_flags_summary=", ".join(sorted({f.flag_type for f in flags})) if flags else None,
        )
