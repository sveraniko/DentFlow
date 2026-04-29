from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

from app.domain.patient_registry.models import PatientPreference, PatientProfileDetails

_ALLOWED_PROFILE_STATES = {"missing", "minimal", "partial", "completed"}
_ALLOWED_CHANNELS = {"telegram", "sms", "call", "email", "none"}
_ALLOWED_RECIPIENT_STRATEGIES = {"self", "guardian", "guardian_or_self", "clinic_manual"}


class PatientProfileRepositoryProtocol(Protocol):
    async def get_profile_details(self, *, clinic_id: str, patient_id: str) -> PatientProfileDetails | None: ...

    async def upsert_profile_details(self, details: PatientProfileDetails) -> PatientProfileDetails: ...

    async def get_profile_completion_state(self, *, clinic_id: str, patient_id: str) -> str | None: ...

    async def get_patient_preferences(self, *, patient_id: str) -> PatientPreference | None: ...

    async def upsert_patient_preferences(self, preference: PatientPreference) -> PatientPreference: ...


class PatientPreferenceRepositoryProtocol(Protocol):
    async def get_patient_preferences(self, *, patient_id: str) -> PatientPreference | None: ...

    async def update_notification_preferences(self, *, patient_id: str, **changes) -> PatientPreference: ...

    async def update_branch_preferences(
        self, *, patient_id: str, default_branch_id: str | None, allow_any_branch: bool
    ) -> PatientPreference: ...


class PatientProfileService:
    def __init__(self, repository: PatientProfileRepositoryProtocol, *, clock=None) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def get_profile_details(self, *, clinic_id: str, patient_id: str) -> PatientProfileDetails | None:
        return await self._repository.get_profile_details(clinic_id=clinic_id, patient_id=patient_id)

    async def save_profile_details(
        self,
        *,
        clinic_id: str,
        patient_id: str,
        email: str | None = None,
        address_line1: str | None = None,
        address_line2: str | None = None,
        city: str | None = None,
        postal_code: str | None = None,
        country_code: str | None = None,
        emergency_contact_name: str | None = None,
        emergency_contact_phone: str | None = None,
        profile_completion_state: str | None = None,
    ) -> PatientProfileDetails:
        existing = await self._repository.get_profile_details(clinic_id=clinic_id, patient_id=patient_id)
        normalized_email = self._validate_email(email) if email is not None else None
        normalized_country_code = country_code.strip().upper() if country_code else None

        merged = asdict(existing) if existing else {"patient_id": patient_id, "clinic_id": clinic_id}
        merged.update({"clinic_id": clinic_id, "patient_id": patient_id})

        field_updates = {
            "email": normalized_email,
            "address_line1": address_line1,
            "address_line2": address_line2,
            "city": city,
            "postal_code": postal_code,
            "country_code": normalized_country_code,
            "emergency_contact_name": emergency_contact_name,
            "emergency_contact_phone": emergency_contact_phone,
        }
        for field_name, field_value in field_updates.items():
            if field_value is not None:
                merged[field_name] = field_value

        if profile_completion_state is not None:
            if profile_completion_state not in _ALLOWED_PROFILE_STATES:
                raise ValueError("Invalid profile_completion_state")
            merged["profile_completion_state"] = profile_completion_state
        else:
            inferred = self.compute_profile_completion_state(
                has_name=True,
                has_phone=True,
                details=PatientProfileDetails(**merged),
            )
            merged["profile_completion_state"] = inferred

        if merged["profile_completion_state"] == "completed":
            merged["profile_completed_at"] = merged.get("profile_completed_at") or self._clock()

        return await self._repository.upsert_profile_details(PatientProfileDetails(**merged))

    async def get_profile_completion_state(self, *, clinic_id: str, patient_id: str) -> str:
        state = await self._repository.get_profile_completion_state(clinic_id=clinic_id, patient_id=patient_id)
        return state or "missing"

    def compute_profile_completion_state(
        self,
        *,
        has_name: bool,
        has_phone: bool,
        details: PatientProfileDetails | None,
    ) -> str:
        if details and details.profile_completion_state == "completed":
            return "completed"
        if not has_name or not has_phone:
            return "missing"
        if details is None:
            return "minimal"

        required = [details.email, details.address_line1, details.city, details.country_code]
        present = [v for v in required if v]
        if len(present) == len(required):
            return "completed"

        optional = [details.address_line2, details.postal_code, details.emergency_contact_name, details.emergency_contact_phone]
        if any(required) or any(optional):
            return "partial"
        return "minimal"

    def _validate_email(self, email: str | None) -> str | None:
        if email is None:
            return None
        normalized = email.strip()
        if not normalized:
            return None
        if "@" not in normalized:
            raise ValueError("Invalid email")
        return normalized


class PatientPreferenceService:
    def __init__(self, repository: PatientPreferenceRepositoryProtocol, reference_service=None, *, clock=None) -> None:
        self._repository = repository
        self._reference_service = reference_service
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def get_preferences(self, *, patient_id: str) -> PatientPreference | None:
        return await self._repository.get_patient_preferences(patient_id=patient_id)

    async def update_notification_settings(
        self,
        *,
        patient_id: str,
        preferred_reminder_channel: str | None = None,
        allow_sms: bool | None = None,
        allow_telegram: bool | None = None,
        allow_call: bool | None = None,
        allow_email: bool | None = None,
        notification_recipient_strategy: str | None = None,
        quiet_hours_start: str | None = None,
        quiet_hours_end: str | None = None,
        quiet_hours_timezone: str | None = None,
    ) -> PatientPreference:
        if preferred_reminder_channel is not None and preferred_reminder_channel not in _ALLOWED_CHANNELS:
            raise ValueError("Invalid preferred_reminder_channel")
        self.validate_notification_recipient_strategy(notification_recipient_strategy)
        self.validate_quiet_hours(start=quiet_hours_start, end=quiet_hours_end)
        if quiet_hours_timezone is not None:
            try:
                ZoneInfo(quiet_hours_timezone)
            except Exception as exc:  # noqa: BLE001
                raise ValueError("Invalid quiet_hours_timezone") from exc

        return await self._repository.update_notification_preferences(
            patient_id=patient_id,
            preferred_reminder_channel=preferred_reminder_channel,
            allow_sms=allow_sms,
            allow_telegram=allow_telegram,
            allow_call=allow_call,
            allow_email=allow_email,
            notification_recipient_strategy=notification_recipient_strategy,
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
            quiet_hours_timezone=quiet_hours_timezone,
        )

    async def update_branch_preference(
        self,
        *,
        clinic_id: str,
        patient_id: str,
        default_branch_id: str | None,
        allow_any_branch: bool,
    ) -> PatientPreference:
        if not allow_any_branch and default_branch_id is None:
            raise ValueError("default_branch_id is required when allow_any_branch is False")
        if default_branch_id is not None and self._reference_service is not None:
            branch = self._reference_service.get_branch(clinic_id, default_branch_id)
            if branch is None:
                raise ValueError("Unknown branch for clinic")
        return await self._repository.update_branch_preferences(
            patient_id=patient_id,
            default_branch_id=default_branch_id,
            allow_any_branch=allow_any_branch,
        )

    def validate_quiet_hours(self, *, start: str | None, end: str | None) -> None:
        def _valid(value: str) -> bool:
            if len(value) != 5 or value[2] != ":":
                return False
            hh, mm = value.split(":", 1)
            return hh.isdigit() and mm.isdigit() and 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59

        if start is not None and not _valid(start):
            raise ValueError("Invalid quiet_hours_start")
        if end is not None and not _valid(end):
            raise ValueError("Invalid quiet_hours_end")

    def validate_notification_recipient_strategy(self, strategy: str | None) -> None:
        if strategy is not None and strategy not in _ALLOWED_RECIPIENT_STRATEGIES:
            raise ValueError("Invalid notification_recipient_strategy")
