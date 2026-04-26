from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.clinic_reference.models import Branch, Clinic, Doctor, DoctorAccessCode, RecordStatus, Service


class InMemoryClinicReferenceRepository:
    def __init__(self) -> None:
        self.clinics: dict[str, Clinic] = {}
        self.branches: dict[str, Branch] = {}
        self.doctors: dict[str, Doctor] = {}
        self.services: dict[str, Service] = {}
        self.doctor_access_codes: dict[str, DoctorAccessCode] = {}

    def upsert_clinic(self, clinic: Clinic) -> None:
        self.clinics[clinic.clinic_id] = clinic

    def upsert_branch(self, branch: Branch) -> None:
        self.branches[branch.branch_id] = branch

    def upsert_doctor(self, doctor: Doctor) -> None:
        self.doctors[doctor.doctor_id] = doctor

    def upsert_service(self, service: Service) -> None:
        self.services[service.service_id] = service

    def upsert_doctor_access_code(self, access_code: DoctorAccessCode) -> None:
        self.doctor_access_codes[access_code.doctor_access_code_id] = access_code


@dataclass(slots=True)
class ClinicReferenceService:
    repository: InMemoryClinicReferenceRepository

    def get_clinic(self, clinic_id: str) -> Clinic | None:
        return self.repository.clinics.get(clinic_id)

    def list_clinics(self) -> list[Clinic]:
        return list(self.repository.clinics.values())

    def get_doctor(self, clinic_id: str, doctor_id: str) -> Doctor | None:
        doctor = self.repository.doctors.get(doctor_id)
        if doctor is None or doctor.clinic_id != clinic_id:
            return None
        return doctor

    def list_branches(self, clinic_id: str) -> list[Branch]:
        return [b for b in self.repository.branches.values() if b.clinic_id == clinic_id]

    def get_branch(self, clinic_id: str, branch_id: str) -> Branch | None:
        branch = self.repository.branches.get(branch_id)
        if branch is None or branch.clinic_id != clinic_id:
            return None
        return branch

    def list_doctors(self, clinic_id: str, branch_id: str | None = None) -> list[Doctor]:
        doctors = [d for d in self.repository.doctors.values() if d.clinic_id == clinic_id]
        if branch_id is not None:
            doctors = [d for d in doctors if d.branch_id in (None, branch_id)]
        return doctors

    def get_service(self, clinic_id: str, service_id: str) -> Service | None:
        service = self.repository.services.get(service_id)
        if service is None or service.clinic_id != clinic_id:
            return None
        return service

    def list_services(self, clinic_id: str) -> list[Service]:
        return [s for s in self.repository.services.values() if s.clinic_id == clinic_id]

    def resolve_doctor_access_code(
        self,
        *,
        clinic_id: str,
        code: str,
        service_id: str | None = None,
        branch_id: str | None = None,
        now: datetime | None = None,
    ) -> DoctorAccessCode | None:
        normalized = (code or "").strip().upper()
        if not normalized:
            return None
        check_time = now or datetime.now(timezone.utc)
        for access in self.repository.doctor_access_codes.values():
            if access.clinic_id != clinic_id:
                continue
            if access.status != RecordStatus.ACTIVE:
                continue
            if access.code.strip().upper() != normalized:
                continue
            if access.expires_at is not None and access.expires_at <= check_time:
                continue
            if access.service_scope and (service_id is None or service_id not in set(access.service_scope)):
                continue
            if access.branch_scope and (branch_id is None or branch_id not in set(access.branch_scope)):
                continue
            doctor = self.get_doctor(clinic_id, access.doctor_id)
            if doctor is None or not doctor.public_booking_enabled:
                continue
            return access
        return None
