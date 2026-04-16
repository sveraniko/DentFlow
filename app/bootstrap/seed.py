from __future__ import annotations

import json
from pathlib import Path

from app.application.access import InMemoryAccessRepository
from app.application.clinic_reference import InMemoryClinicReferenceRepository
from app.application.policy import InMemoryPolicyRepository
from app.domain.access_identity.models import (
    ActorIdentity,
    ActorType,
    ClinicRoleAssignment,
    RoleCode,
    StaffMember,
    TelegramBinding,
)
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, DoctorAccessCode, RecordStatus, Service
from app.domain.policy_config.models import FeatureFlag, PolicySet, PolicyValue


class SeedBootstrap:
    def __init__(
        self,
        clinic_reference_repository: InMemoryClinicReferenceRepository,
        access_repository: InMemoryAccessRepository,
        policy_repository: InMemoryPolicyRepository,
    ) -> None:
        self.clinic_reference_repository = clinic_reference_repository
        self.access_repository = access_repository
        self.policy_repository = policy_repository

    def load_from_file(self, path: Path) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))

        for row in payload.get("clinics", []):
            self.clinic_reference_repository.upsert_clinic(Clinic(**row))
        for row in payload.get("branches", []):
            self.clinic_reference_repository.upsert_branch(Branch(**row))
        for row in payload.get("doctors", []):
            row["status"] = RecordStatus(row["status"])
            self.clinic_reference_repository.upsert_doctor(Doctor(**row))
        for row in payload.get("services", []):
            row["status"] = RecordStatus(row["status"])
            self.clinic_reference_repository.upsert_service(Service(**row))
        for row in payload.get("doctor_access_codes", []):
            row["status"] = RecordStatus(row["status"])
            self.clinic_reference_repository.upsert_doctor_access_code(DoctorAccessCode(**row))

        for row in payload.get("actor_identities", []):
            row["actor_type"] = ActorType(row["actor_type"])
            self.access_repository.upsert_actor_identity(ActorIdentity(**row))
        for row in payload.get("telegram_bindings", []):
            self.access_repository.upsert_telegram_binding(TelegramBinding(**row))
        for row in payload.get("staff_members", []):
            self.access_repository.upsert_staff_member(StaffMember(**row))
        for row in payload.get("clinic_role_assignments", []):
            row["role_code"] = RoleCode(row["role_code"])
            self.access_repository.upsert_role_assignment(ClinicRoleAssignment(**row))

        for row in payload.get("policy_sets", []):
            self.policy_repository.upsert_policy_set(PolicySet(**row))
        for row in payload.get("policy_values", []):
            self.policy_repository.add_policy_value(PolicyValue(**row))
        for row in payload.get("feature_flags", []):
            self.policy_repository.add_feature_flag(FeatureFlag(**row))
