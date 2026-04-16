from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.patient_registry.models import (
    Patient,
    PatientContact,
    PatientExternalId,
    PatientFlag,
    PatientMedicalSummary,
    PatientPhoto,
    PatientPreference,
)


def normalize_contact_value(contact_type: str, contact_value: str) -> str:
    if contact_type in {"phone", "telegram"}:
        return "".join(ch for ch in contact_value if ch.isdigit())
    return contact_value.strip().lower()


class InMemoryPatientRegistryRepository:
    def __init__(self) -> None:
        self.patients: dict[str, Patient] = {}
        self.contacts: dict[str, PatientContact] = {}
        self.preferences: dict[str, PatientPreference] = {}
        self.flags: dict[str, PatientFlag] = {}
        self.photos: dict[str, PatientPhoto] = {}
        self.medical_summaries: dict[str, PatientMedicalSummary] = {}
        self.external_ids: dict[str, PatientExternalId] = {}


@dataclass(slots=True)
class PatientRegistryService:
    repository: InMemoryPatientRegistryRepository

    def create_patient(
        self,
        *,
        clinic_id: str,
        patient_id: str | None = None,
        first_name: str,
        last_name: str,
        full_name_legal: str,
        display_name: str,
        patient_number: str | None = None,
        middle_name: str | None = None,
        birth_date=None,
        sex_marker: str | None = None,
        first_seen_at: datetime | None = None,
        last_seen_at: datetime | None = None,
    ) -> Patient:
        patient = Patient(
            patient_id=patient_id or f"pat_{uuid4().hex}",
            clinic_id=clinic_id,
            first_name=first_name,
            last_name=last_name,
            full_name_legal=full_name_legal,
            display_name=display_name,
            patient_number=patient_number,
            middle_name=middle_name,
            birth_date=birth_date,
            sex_marker=sex_marker,
            first_seen_at=first_seen_at,
            last_seen_at=last_seen_at,
        )
        self.repository.patients[patient.patient_id] = patient
        return patient

    def update_patient(self, patient_id: str, **changes) -> Patient:
        current = self.repository.patients[patient_id]
        updated = Patient(**({**asdict(current), **changes}))
        self.repository.patients[patient_id] = updated
        return updated

    def upsert_contact(self, *, patient_id: str, contact_type: str, contact_value: str, **kwargs) -> PatientContact:
        normalized = normalize_contact_value(contact_type, contact_value)
        existing = next(
            (
                c
                for c in self.repository.contacts.values()
                if c.patient_id == patient_id and c.contact_type == contact_type and c.normalized_value == normalized
            ),
            None,
        )
        payload = {
            "patient_contact_id": existing.patient_contact_id if existing else f"pc_{uuid4().hex}",
            "patient_id": patient_id,
            "contact_type": contact_type,
            "contact_value": contact_value,
            "normalized_value": normalized,
            **kwargs,
        }
        contact = PatientContact(**payload)
        self.repository.contacts[contact.patient_contact_id] = contact
        if contact.is_primary:
            for item_id, item in list(self.repository.contacts.items()):
                if item.patient_id == patient_id and item.contact_type == contact_type and item_id != contact.patient_contact_id:
                    self.repository.contacts[item_id] = PatientContact(**{**asdict(item), "is_primary": False})
        return contact

    def get_patient(self, patient_id: str) -> Patient | None:
        return self.repository.patients.get(patient_id)

    def find_by_exact_contact(self, *, contact_type: str, contact_value: str) -> Patient | None:
        normalized = normalize_contact_value(contact_type, contact_value)
        for contact in self.repository.contacts.values():
            if contact.contact_type == contact_type and contact.normalized_value == normalized and contact.is_active:
                return self.repository.patients.get(contact.patient_id)
        return None

    def upsert_preferences(self, *, patient_id: str, **changes) -> PatientPreference:
        current = next((p for p in self.repository.preferences.values() if p.patient_id == patient_id), None)
        payload = {
            "patient_preference_id": current.patient_preference_id if current else f"pp_{uuid4().hex}",
            "patient_id": patient_id,
            **(asdict(current) if current else {}),
            **changes,
        }
        preference = PatientPreference(**payload)
        self.repository.preferences[preference.patient_preference_id] = preference
        return preference

    def get_preferences(self, patient_id: str) -> PatientPreference | None:
        return next((p for p in self.repository.preferences.values() if p.patient_id == patient_id), None)

    def add_flag(self, *, patient_id: str, flag_type: str, flag_severity: str, **kwargs) -> PatientFlag:
        flag = PatientFlag(
            patient_flag_id=f"pf_{uuid4().hex}",
            patient_id=patient_id,
            flag_type=flag_type,
            flag_severity=flag_severity,
            set_at=kwargs.pop("set_at", datetime.now(timezone.utc)),
            **kwargs,
        )
        self.repository.flags[flag.patient_flag_id] = flag
        return flag

    def deactivate_flag(self, patient_flag_id: str) -> PatientFlag:
        current = self.repository.flags[patient_flag_id]
        updated = PatientFlag(**{**asdict(current), "is_active": False})
        self.repository.flags[patient_flag_id] = updated
        return updated

    def active_flags(self, patient_id: str) -> list[PatientFlag]:
        return [f for f in self.repository.flags.values() if f.patient_id == patient_id and f.is_active]

    def add_photo(self, *, patient_id: str, source_type: str, **kwargs) -> PatientPhoto:
        photo = PatientPhoto(patient_photo_id=f"pho_{uuid4().hex}", patient_id=patient_id, source_type=source_type, **kwargs)
        self.repository.photos[photo.patient_photo_id] = photo
        if photo.is_primary:
            self.set_primary_photo(photo.patient_photo_id)
        return photo

    def set_primary_photo(self, patient_photo_id: str) -> None:
        target = self.repository.photos.get(patient_photo_id)
        if target is None:
            return
        for photo_id, photo in list(self.repository.photos.items()):
            if photo.patient_id == target.patient_id:
                self.repository.photos[photo_id] = PatientPhoto(**{**asdict(photo), "is_primary": photo_id == patient_photo_id})

    def get_primary_photo(self, patient_id: str) -> PatientPhoto | None:
        return next((p for p in self.repository.photos.values() if p.patient_id == patient_id and p.is_primary), None)

    def upsert_medical_summary(self, *, patient_id: str, **changes) -> PatientMedicalSummary:
        now = datetime.now(timezone.utc)
        current = next((m for m in self.repository.medical_summaries.values() if m.patient_id == patient_id), None)
        payload = {
            "patient_medical_summary_id": current.patient_medical_summary_id if current else f"pms_{uuid4().hex}",
            "patient_id": patient_id,
            **(asdict(current) if current else {"created_at": now}),
            **changes,
            "created_at": current.created_at if current else now,
            "last_updated_at": now,
        }
        summary = PatientMedicalSummary(**payload)
        self.repository.medical_summaries[summary.patient_medical_summary_id] = summary
        return summary

    def get_medical_summary(self, patient_id: str) -> PatientMedicalSummary | None:
        return next((m for m in self.repository.medical_summaries.values() if m.patient_id == patient_id), None)

    def upsert_external_id(self, *, patient_id: str, external_system: str, external_id: str, **kwargs) -> PatientExternalId:
        current = next(
            (
                x
                for x in self.repository.external_ids.values()
                if x.patient_id == patient_id and x.external_system == external_system
            ),
            None,
        )
        payload = {
            "patient_external_id_id": current.patient_external_id_id if current else f"pex_{uuid4().hex}",
            "patient_id": patient_id,
            "external_system": external_system,
            **(asdict(current) if current else {}),
            **kwargs,
            "external_id": external_id,
        }
        ext = PatientExternalId(**payload)
        self.repository.external_ids[ext.patient_external_id_id] = ext
        return ext

    def list_external_ids(self, patient_id: str) -> list[PatientExternalId]:
        return [item for item in self.repository.external_ids.values() if item.patient_id == patient_id]

    def find_by_external_id(self, *, external_system: str, external_id: str) -> Patient | None:
        for item in self.repository.external_ids.values():
            if item.external_system == external_system and item.external_id == external_id:
                return self.repository.patients.get(item.patient_id)
        return None
