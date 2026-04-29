from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from app.domain.patient_registry.models import LinkedPatientProfile, PatientRelationship

_ALLOWED_RELATIONSHIP_TYPES = {"self", "spouse", "child", "parent", "other"}
_ALLOWED_CONSENT_STATUSES = {"active", "revoked", "expired"}


@dataclass(frozen=True)
class LinkedPatientOption:
    patient_id: str
    display_name: str
    relationship_type: str
    is_self: bool = False
    is_default_for_booking: bool = False
    is_default_notification_recipient: bool = False
    phone: str | None = None
    telegram_user_id: int | None = None


@dataclass(frozen=True)
class BookingPatientSelectionResult:
    mode: str
    selected_patient_id: str | None = None
    options: tuple[LinkedPatientOption, ...] = ()
    phone: str | None = None
    reason: str | None = None


class PatientFamilyRepositoryProtocol(Protocol):
    async def list_relationships(self, *, clinic_id: str, manager_patient_id: str, include_inactive: bool = False) -> list[PatientRelationship]: ...
    async def list_linked_profiles_for_telegram(
        self, *, clinic_id: str, telegram_user_id: int, include_inactive: bool = False
    ) -> list[LinkedPatientProfile]: ...
    async def upsert_relationship(self, relationship: PatientRelationship) -> PatientRelationship: ...
    async def deactivate_relationship(self, *, clinic_id: str, relationship_id: str) -> PatientRelationship | None: ...
    async def get_patient_preferences(self, *, patient_id: str): ...


class PatientFamilyService:
    def __init__(self, repository: PatientFamilyRepositoryProtocol, *, clock=None) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def list_linked_profiles_for_telegram(self, *, clinic_id: str, telegram_user_id: int) -> tuple[LinkedPatientOption, ...]:
        patients = await self._repository.list_linked_profiles_for_telegram(clinic_id=clinic_id, telegram_user_id=telegram_user_id)
        options: list[LinkedPatientOption] = []
        for patient in patients:
            relationship_type = str(
                getattr(patient, "relationship_type", "self" if bool(getattr(patient, "is_manager", False)) else "other")
            )
            is_self = bool(getattr(patient, "is_self", relationship_type == "self"))
            options.append(
                LinkedPatientOption(
                    patient_id=patient.patient_id,
                    display_name=patient.display_name,
                    relationship_type=relationship_type,
                    is_self=is_self,
                    is_default_for_booking=bool(getattr(patient, "is_default_for_booking", False)),
                    is_default_notification_recipient=bool(getattr(patient, "is_default_notification_recipient", False)),
                    phone=getattr(patient, "phone", None),
                    telegram_user_id=getattr(patient, "telegram_user_id", None),
                )
            )
        options.sort(key=lambda item: (not item.is_self, not item.is_default_for_booking, item.display_name.lower()))
        return tuple(options)

    async def list_relationships(self, *, clinic_id: str, manager_patient_id: str, include_inactive: bool = False) -> tuple[PatientRelationship, ...]:
        rows = await self._repository.list_relationships(clinic_id=clinic_id, manager_patient_id=manager_patient_id, include_inactive=include_inactive)
        return tuple(rows)

    async def add_relationship(self, relationship: PatientRelationship) -> PatientRelationship:
        self._validate_relationship(relationship)
        return await self._repository.upsert_relationship(relationship)

    async def deactivate_relationship(self, *, clinic_id: str, relationship_id: str) -> PatientRelationship | None:
        return await self._repository.deactivate_relationship(clinic_id=clinic_id, relationship_id=relationship_id)

    def _validate_relationship(self, relationship: PatientRelationship) -> None:
        if relationship.relationship_type not in _ALLOWED_RELATIONSHIP_TYPES:
            raise ValueError("Invalid relationship_type")
        if relationship.consent_status not in _ALLOWED_CONSENT_STATUSES:
            raise ValueError("Invalid consent_status")
        if relationship.manager_patient_id == relationship.related_patient_id and relationship.relationship_type != "self":
            raise ValueError("manager_patient_id and related_patient_id must differ unless relationship_type='self'")
        if relationship.starts_at and relationship.expires_at and relationship.expires_at <= relationship.starts_at:
            raise ValueError("expires_at must be after starts_at")


class BookingPatientSelectorService:
    def __init__(self, family_service: PatientFamilyService, patient_registry_service=None, *, clock=None) -> None:
        self._family_service = family_service
        self._patient_registry_service = patient_registry_service
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def resolve_for_telegram(self, *, clinic_id: str, telegram_user_id: int) -> BookingPatientSelectionResult:
        options = await self._family_service.list_linked_profiles_for_telegram(clinic_id=clinic_id, telegram_user_id=telegram_user_id)
        if len(options) == 0:
            return BookingPatientSelectionResult(mode="phone_required")
        if len(options) == 1:
            return BookingPatientSelectionResult(mode="single_match", selected_patient_id=options[0].patient_id, options=options)
        return BookingPatientSelectionResult(mode="multiple_profiles", options=options)

    async def resolve_for_phone(self, *, clinic_id: str, phone: str) -> BookingPatientSelectionResult:
        if self._patient_registry_service is None:
            return BookingPatientSelectionResult(mode="minimal_name_required", phone=phone, reason="registry_unavailable")
        patients = await self._patient_registry_service.find_by_phone(clinic_id=clinic_id, phone=phone)
        if len(patients) == 0:
            return BookingPatientSelectionResult(mode="minimal_name_required", phone=phone)
        if len(patients) == 1:
            return BookingPatientSelectionResult(mode="single_match", selected_patient_id=patients[0]["patient_id"], phone=phone)
        options = tuple(LinkedPatientOption(patient_id=p["patient_id"], display_name=p.get("display_name", p["patient_id"]), relationship_type="other") for p in patients)
        return BookingPatientSelectionResult(mode="multiple_profiles", options=options, phone=phone)

    async def select_patient(self, *, clinic_id: str, telegram_user_id: int, patient_id: str) -> BookingPatientSelectionResult:
        options = await self._family_service.list_linked_profiles_for_telegram(clinic_id=clinic_id, telegram_user_id=telegram_user_id)
        if any(opt.patient_id == patient_id for opt in options):
            return BookingPatientSelectionResult(mode="single_match", selected_patient_id=patient_id, options=options)
        return BookingPatientSelectionResult(mode="no_match", reason="patient_not_linked")
