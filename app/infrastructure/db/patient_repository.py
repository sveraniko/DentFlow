from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime, timezone

from sqlalchemy import text

from app.application.patient import InMemoryPatientRegistryRepository, PatientRegistryService, normalize_contact_value
from app.application.doctor.patient_read import DoctorPatientSnapshot
from app.application.booking.telegram_flow import CanonicalPatientCreator
from app.domain.events import build_event
from app.domain.patient_registry.models import (
    Patient,
    PatientContact,
    PatientExternalId,
    PatientFlag,
    PatientMedicalSummary,
    PatientPhoto,
    PatientPreference,
)
from app.infrastructure.db.engine import create_engine
from app.infrastructure.outbox.repository import OutboxRepository

DEFAULT_SEED_TIMESTAMP = datetime(2024, 1, 1, tzinfo=timezone.utc)


class DbPatientRegistryRepository(InMemoryPatientRegistryRepository):
    def __init__(self, db_config) -> None:
        super().__init__()
        self._db_config = db_config

    @classmethod
    async def load(cls, db_config) -> "DbPatientRegistryRepository":
        repo = cls(db_config)
        engine = create_engine(db_config)
        async with engine.connect() as conn:
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT patient_id, clinic_id, patient_number, full_name_legal, first_name, last_name, middle_name,
                               display_name, birth_date, sex_marker, status, first_seen_at, last_seen_at
                        FROM core_patient.patients
                        """
                    )
                )
            ).mappings():
                repo.patients[row["patient_id"]] = Patient(
                    patient_id=row["patient_id"],
                    clinic_id=row["clinic_id"],
                    patient_number=row["patient_number"],
                    full_name_legal=row["full_name_legal"],
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    middle_name=row["middle_name"],
                    display_name=row["display_name"],
                    birth_date=row["birth_date"],
                    sex_marker=row["sex_marker"],
                    status=row["status"],
                    first_seen_at=row["first_seen_at"],
                    last_seen_at=row["last_seen_at"],
                )
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT patient_contact_id, patient_id, contact_type, contact_value, normalized_value,
                               is_primary, is_verified, is_active, notes
                        FROM core_patient.patient_contacts
                        """
                    )
                )
            ).mappings():
                repo.contacts[row["patient_contact_id"]] = PatientContact(
                    patient_contact_id=row["patient_contact_id"],
                    patient_id=row["patient_id"],
                    contact_type=row["contact_type"],
                    contact_value=row["contact_value"],
                    normalized_value=row["normalized_value"],
                    is_primary=row["is_primary"],
                    is_verified=row["is_verified"],
                    is_active=row["is_active"],
                    notes=row["notes"],
                )
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT patient_preference_id, patient_id, preferred_language, preferred_reminder_channel,
                               allow_sms, allow_telegram, allow_call, allow_email, marketing_opt_in, contact_time_window,
                               notification_recipient_strategy, quiet_hours_start, quiet_hours_end,
                               quiet_hours_timezone, default_branch_id, allow_any_branch
                        FROM core_patient.patient_preferences
                        """
                    )
                )
            ).mappings():
                repo.preferences[row["patient_preference_id"]] = PatientPreference(
                    patient_preference_id=row["patient_preference_id"],
                    patient_id=row["patient_id"],
                    preferred_language=row["preferred_language"],
                    preferred_reminder_channel=row["preferred_reminder_channel"],
                    allow_sms=row["allow_sms"],
                    allow_telegram=row["allow_telegram"],
                    allow_call=row["allow_call"],
                    allow_email=row["allow_email"],
                    marketing_opt_in=row["marketing_opt_in"],
                    contact_time_window=row["contact_time_window"],
                    notification_recipient_strategy=row.get("notification_recipient_strategy"),
                    quiet_hours_start=row.get("quiet_hours_start"),
                    quiet_hours_end=row.get("quiet_hours_end"),
                    quiet_hours_timezone=row.get("quiet_hours_timezone"),
                    default_branch_id=row.get("default_branch_id"),
                    allow_any_branch=row.get("allow_any_branch", True),
                )
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT patient_flag_id, patient_id, flag_type, flag_severity, is_active, set_by_actor_id, set_at, expires_at, note
                        FROM core_patient.patient_flags
                        """
                    )
                )
            ).mappings():
                repo.flags[row["patient_flag_id"]] = PatientFlag(
                    patient_flag_id=row["patient_flag_id"],
                    patient_id=row["patient_id"],
                    flag_type=row["flag_type"],
                    flag_severity=row["flag_severity"],
                    is_active=row["is_active"],
                    set_by_actor_id=row["set_by_actor_id"],
                    set_at=row["set_at"],
                    expires_at=row["expires_at"],
                    note=row["note"],
                )
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT patient_photo_id, patient_id, media_asset_id, external_ref, is_primary, captured_at, source_type
                        FROM core_patient.patient_photos
                        """
                    )
                )
            ).mappings():
                repo.photos[row["patient_photo_id"]] = PatientPhoto(
                    patient_photo_id=row["patient_photo_id"],
                    patient_id=row["patient_id"],
                    media_asset_id=row["media_asset_id"],
                    external_ref=row["external_ref"],
                    is_primary=row["is_primary"],
                    captured_at=row["captured_at"],
                    source_type=row["source_type"],
                )
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT patient_medical_summary_id, patient_id, allergy_summary, chronic_conditions_summary,
                               contraindication_summary, current_primary_dental_issue_summary, important_history_summary,
                               last_updated_by_actor_id, last_updated_at, created_at
                        FROM core_patient.patient_medical_summaries
                        """
                    )
                )
            ).mappings():
                repo.medical_summaries[row["patient_medical_summary_id"]] = PatientMedicalSummary(
                    patient_medical_summary_id=row["patient_medical_summary_id"],
                    patient_id=row["patient_id"],
                    allergy_summary=row["allergy_summary"],
                    chronic_conditions_summary=row["chronic_conditions_summary"],
                    contraindication_summary=row["contraindication_summary"],
                    current_primary_dental_issue_summary=row["current_primary_dental_issue_summary"],
                    important_history_summary=row["important_history_summary"],
                    last_updated_by_actor_id=row["last_updated_by_actor_id"],
                    last_updated_at=row["last_updated_at"],
                    created_at=row["created_at"],
                )
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT patient_external_id_id, patient_id, external_system, external_id, is_primary, last_synced_at
                        FROM core_patient.patient_external_ids
                        """
                    )
                )
            ).mappings():
                repo.external_ids[row["patient_external_id_id"]] = PatientExternalId(
                    patient_external_id_id=row["patient_external_id_id"],
                    patient_id=row["patient_id"],
                    external_system=row["external_system"],
                    external_id=row["external_id"],
                    is_primary=row["is_primary"],
                    last_synced_at=row["last_synced_at"],
                )
        await engine.dispose()
        return repo

    async def _append_event_on_conn(self, conn, event_name: str, patient_id: str, clinic_id: str, payload: dict[str, object]) -> None:
        await OutboxRepository(self._db_config).append_on_connection(
            conn,
            build_event(
                event_name=event_name,
                producer_context="patient.registry",
                clinic_id=clinic_id,
                entity_type="patient",
                entity_id=patient_id,
                payload=payload,
            ),
        )

    async def persist_patient(self, patient: Patient, *, event_name: str | None = None) -> None:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            params = asdict(patient)
            if isinstance(params.get("birth_date"), str):
                params["birth_date"] = date.fromisoformat(params["birth_date"])
            await conn.execute(
                text(
                    """
                INSERT INTO core_patient.patients (
                  patient_id, clinic_id, patient_number, full_name_legal, first_name, last_name, middle_name,
                  display_name, birth_date, sex_marker, status, first_seen_at, last_seen_at
                )
                VALUES (
                  :patient_id, :clinic_id, :patient_number, :full_name_legal, :first_name, :last_name, :middle_name,
                  :display_name, :birth_date, :sex_marker, :status, :first_seen_at, :last_seen_at
                )
                ON CONFLICT (patient_id) DO UPDATE SET
                  patient_number=EXCLUDED.patient_number,
                  full_name_legal=EXCLUDED.full_name_legal,
                  first_name=EXCLUDED.first_name,
                  last_name=EXCLUDED.last_name,
                  middle_name=EXCLUDED.middle_name,
                  display_name=EXCLUDED.display_name,
                  birth_date=EXCLUDED.birth_date,
                  sex_marker=EXCLUDED.sex_marker,
                  status=EXCLUDED.status,
                  first_seen_at=EXCLUDED.first_seen_at,
                  last_seen_at=EXCLUDED.last_seen_at,
                  updated_at=NOW()
                """
                ),
                params,
            )
            if event_name is not None:
                await self._append_event_on_conn(
                    conn,
                    event_name=event_name,
                    patient_id=patient.patient_id,
                    clinic_id=patient.clinic_id,
                    payload={"display_name": patient.display_name},
                )
        await engine.dispose()

    async def persist_contact(self, contact, *, event_name: str = "patient.contact_updated") -> None:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            if contact.is_primary:
                await conn.execute(
                    text("UPDATE core_patient.patient_contacts SET is_primary=FALSE, updated_at=NOW() WHERE patient_id=:patient_id AND contact_type=:contact_type"),
                    {"patient_id": contact.patient_id, "contact_type": contact.contact_type},
                )
            await conn.execute(
                text(
                    """
                INSERT INTO core_patient.patient_contacts (
                  patient_contact_id, patient_id, contact_type, contact_value, normalized_value,
                  is_primary, is_verified, is_active, notes
                ) VALUES (
                  :patient_contact_id, :patient_id, :contact_type, :contact_value, :normalized_value,
                  :is_primary, :is_verified, :is_active, :notes
                )
                ON CONFLICT (patient_id, contact_type, normalized_value) DO UPDATE SET
                  patient_contact_id=EXCLUDED.patient_contact_id,
                  contact_value=EXCLUDED.contact_value,
                  is_primary=EXCLUDED.is_primary,
                  is_verified=EXCLUDED.is_verified,
                  is_active=EXCLUDED.is_active,
                  notes=EXCLUDED.notes,
                  updated_at=NOW()
                """
                ),
                asdict(contact),
            )
            patient = self.patients.get(contact.patient_id)
            if patient is not None:
                await self._append_event_on_conn(
                    conn,
                    event_name=event_name,
                    patient_id=contact.patient_id,
                    clinic_id=patient.clinic_id,
                    payload={"contact_type": contact.contact_type, "is_primary": contact.is_primary},
                )
        await engine.dispose()

    async def persist_preferences(self, preference: PatientPreference) -> None:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            params = asdict(preference)
            if isinstance(params.get("contact_time_window"), (dict, list)):
                params["contact_time_window"] = json.dumps(params["contact_time_window"])
            await conn.execute(
                text(
                    """
                INSERT INTO core_patient.patient_preferences (
                  patient_preference_id, patient_id, preferred_language, preferred_reminder_channel,
                  allow_sms, allow_telegram, allow_call, allow_email, marketing_opt_in, contact_time_window
                ) VALUES (
                  :patient_preference_id, :patient_id, :preferred_language, :preferred_reminder_channel,
                  :allow_sms, :allow_telegram, :allow_call, :allow_email, :marketing_opt_in, :contact_time_window
                )
                ON CONFLICT (patient_id) DO UPDATE SET
                  patient_preference_id=EXCLUDED.patient_preference_id,
                  preferred_language=EXCLUDED.preferred_language,
                  preferred_reminder_channel=EXCLUDED.preferred_reminder_channel,
                  allow_sms=EXCLUDED.allow_sms,
                  allow_telegram=EXCLUDED.allow_telegram,
                  allow_call=EXCLUDED.allow_call,
                  allow_email=EXCLUDED.allow_email,
                  marketing_opt_in=EXCLUDED.marketing_opt_in,
                  contact_time_window=EXCLUDED.contact_time_window,
                  updated_at=NOW()
                """
                ),
                params,
            )
            patient = self.patients.get(preference.patient_id)
            if patient is not None:
                await self._append_event_on_conn(
                    conn,
                    event_name="patient.preference_updated",
                    patient_id=preference.patient_id,
                    clinic_id=patient.clinic_id,
                    payload={"preferred_language": preference.preferred_language},
                )
        await engine.dispose()

    async def persist_flag(self, flag: PatientFlag, *, event_name: str) -> None:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                INSERT INTO core_patient.patient_flags (
                  patient_flag_id, patient_id, flag_type, flag_severity, is_active, set_by_actor_id, set_at, expires_at, note
                ) VALUES (
                  :patient_flag_id, :patient_id, :flag_type, :flag_severity, :is_active, :set_by_actor_id, :set_at, :expires_at, :note
                )
                ON CONFLICT (patient_flag_id) DO UPDATE SET
                  flag_type=EXCLUDED.flag_type,
                  flag_severity=EXCLUDED.flag_severity,
                  is_active=EXCLUDED.is_active,
                  set_by_actor_id=EXCLUDED.set_by_actor_id,
                  set_at=EXCLUDED.set_at,
                  expires_at=EXCLUDED.expires_at,
                  note=EXCLUDED.note
                """
                ),
                asdict(flag),
            )
            patient = self.patients.get(flag.patient_id)
            if patient is not None:
                await self._append_event_on_conn(
                    conn,
                    event_name=event_name,
                    patient_id=flag.patient_id,
                    clinic_id=patient.clinic_id,
                    payload={"flag_type": flag.flag_type, "is_active": flag.is_active},
                )
        await engine.dispose()

    async def persist_photo(self, photo: PatientPhoto) -> None:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            if photo.is_primary:
                await conn.execute(
                    text("UPDATE core_patient.patient_photos SET is_primary=FALSE WHERE patient_id=:patient_id"),
                    {"patient_id": photo.patient_id},
                )
            await conn.execute(
                text(
                    """
                INSERT INTO core_patient.patient_photos (
                  patient_photo_id, patient_id, media_asset_id, external_ref, is_primary, captured_at, source_type
                ) VALUES (
                  :patient_photo_id, :patient_id, :media_asset_id, :external_ref, :is_primary, :captured_at, :source_type
                )
                ON CONFLICT (patient_photo_id) DO UPDATE SET
                  media_asset_id=EXCLUDED.media_asset_id,
                  external_ref=EXCLUDED.external_ref,
                  is_primary=EXCLUDED.is_primary,
                  captured_at=EXCLUDED.captured_at,
                  source_type=EXCLUDED.source_type
                """
                ),
                asdict(photo),
            )
            patient = self.patients.get(photo.patient_id)
            if patient is not None:
                await self._append_event_on_conn(
                    conn,
                    event_name="patient.photo_updated",
                    patient_id=photo.patient_id,
                    clinic_id=patient.clinic_id,
                    payload={"is_primary": photo.is_primary},
                )
        await engine.dispose()

    async def persist_medical_summary(self, summary: PatientMedicalSummary) -> None:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                INSERT INTO core_patient.patient_medical_summaries (
                  patient_medical_summary_id, patient_id, allergy_summary, chronic_conditions_summary, contraindication_summary,
                  current_primary_dental_issue_summary, important_history_summary, last_updated_by_actor_id, last_updated_at, created_at
                ) VALUES (
                  :patient_medical_summary_id, :patient_id, :allergy_summary, :chronic_conditions_summary, :contraindication_summary,
                  :current_primary_dental_issue_summary, :important_history_summary, :last_updated_by_actor_id, :last_updated_at, :created_at
                )
                ON CONFLICT (patient_id) DO UPDATE SET
                  patient_medical_summary_id=EXCLUDED.patient_medical_summary_id,
                  allergy_summary=EXCLUDED.allergy_summary,
                  chronic_conditions_summary=EXCLUDED.chronic_conditions_summary,
                  contraindication_summary=EXCLUDED.contraindication_summary,
                  current_primary_dental_issue_summary=EXCLUDED.current_primary_dental_issue_summary,
                  important_history_summary=EXCLUDED.important_history_summary,
                  last_updated_by_actor_id=EXCLUDED.last_updated_by_actor_id,
                  last_updated_at=EXCLUDED.last_updated_at,
                  created_at=core_patient.patient_medical_summaries.created_at
                """
                ),
                asdict(summary),
            )
        await engine.dispose()

    async def persist_external_id(self, external_id: PatientExternalId) -> None:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                INSERT INTO core_patient.patient_external_ids (
                  patient_external_id_id, patient_id, external_system, external_id, is_primary, last_synced_at
                ) VALUES (
                  :patient_external_id_id, :patient_id, :external_system, :external_id, :is_primary, :last_synced_at
                )
                ON CONFLICT (patient_id, external_system) DO UPDATE SET
                  patient_external_id_id=EXCLUDED.patient_external_id_id,
                  external_id=EXCLUDED.external_id,
                  is_primary=EXCLUDED.is_primary,
                  last_synced_at=EXCLUDED.last_synced_at
                """
                ),
                asdict(external_id),
            )
        await engine.dispose()


class DbPatientRegistryService(PatientRegistryService):
    repository: DbPatientRegistryRepository

    async def create_patient_db(self, **kwargs):
        patient = self.create_patient(**kwargs)
        await self.repository.persist_patient(patient, event_name="patient.created")
        return patient

    async def update_patient_db(self, patient_id: str, **changes):
        patient = self.update_patient(patient_id, **changes)
        await self.repository.persist_patient(patient, event_name="patient.updated")
        return patient

    async def upsert_contact_db(self, *, patient_id: str, contact_type: str, contact_value: str, **kwargs):
        contact = self.upsert_contact(patient_id=patient_id, contact_type=contact_type, contact_value=contact_value, **kwargs)
        await self.repository.persist_contact(contact, event_name="patient.contact_added")
        return contact

    async def upsert_preferences_db(self, *, patient_id: str, **changes):
        preference = self.upsert_preferences(patient_id=patient_id, **changes)
        await self.repository.persist_preferences(preference)
        return preference

    async def add_flag_db(self, *, patient_id: str, flag_type: str, flag_severity: str, **kwargs):
        flag = self.add_flag(patient_id=patient_id, flag_type=flag_type, flag_severity=flag_severity, **kwargs)
        await self.repository.persist_flag(flag, event_name="patient.flag_set")
        return flag

    async def deactivate_flag_db(self, patient_flag_id: str):
        flag = self.deactivate_flag(patient_flag_id)
        await self.repository.persist_flag(flag, event_name="patient.flag_cleared")
        return flag

    async def add_photo_db(self, *, patient_id: str, source_type: str, **kwargs):
        photo = self.add_photo(patient_id=patient_id, source_type=source_type, **kwargs)
        await self.repository.persist_photo(photo)
        return photo

    async def set_primary_photo_db(self, patient_photo_id: str):
        self.set_primary_photo(patient_photo_id)
        photo = self.repository.photos.get(patient_photo_id)
        if photo is not None:
            await self.repository.persist_photo(photo)

    async def upsert_medical_summary_db(self, *, patient_id: str, **changes):
        summary = self.upsert_medical_summary(patient_id=patient_id, **changes)
        await self.repository.persist_medical_summary(summary)
        return summary

    async def upsert_external_id_db(self, *, patient_id: str, external_system: str, external_id: str, **kwargs):
        ext = self.upsert_external_id(patient_id=patient_id, external_system=external_system, external_id=external_id, **kwargs)
        await self.repository.persist_external_id(ext)
        return ext


class DbCanonicalPatientCreator(CanonicalPatientCreator):
    def __init__(self, db_config) -> None:
        self._db_config = db_config

    async def create_minimal_patient(self, *, clinic_id: str, display_name: str, phone: str) -> str:
        repository = await DbPatientRegistryRepository.load(self._db_config)
        service = DbPatientRegistryService(repository)
        trimmed = (display_name or "").strip() or "Patient"
        parts = trimmed.split(maxsplit=1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else "-"
        patient = await service.create_patient_db(
            clinic_id=clinic_id,
            first_name=first_name,
            last_name=last_name,
            full_name_legal=trimmed,
            display_name=trimmed,
        )
        await service.upsert_contact_db(
            patient_id=patient.patient_id,
            contact_type="phone",
            contact_value=phone,
            is_primary=True,
            is_verified=False,
            is_active=True,
        )
        return patient.patient_id

    async def upsert_telegram_contact(self, *, patient_id: str, telegram_user_id: int) -> None:
        repository = await DbPatientRegistryRepository.load(self._db_config)
        service = DbPatientRegistryService(repository)
        await service.upsert_contact_db(
            patient_id=patient_id,
            contact_type="telegram",
            contact_value=str(telegram_user_id),
            is_primary=True,
            is_verified=True,
            is_active=True,
        )


async def seed_stack2_patients(db_config, payload: dict) -> dict[str, int]:
    repo = DbPatientRegistryRepository(db_config)
    service = DbPatientRegistryService(repo)
    for patient in payload.get("patients", []):
        model = service.create_patient(**patient)
        await repo.persist_patient(model)

    for row in payload.get("patient_contacts", []):
        await service.upsert_contact_db(
            patient_id=row["patient_id"],
            contact_type=row["contact_type"],
            contact_value=row["contact_value"],
            is_primary=row.get("is_primary", False),
            is_verified=row.get("is_verified", False),
            is_active=row.get("is_active", True),
            notes=row.get("notes"),
        )

    for row in payload.get("patient_preferences", []):
        await repo.persist_preferences(
            PatientPreference(
                patient_preference_id=row["patient_preference_id"],
                patient_id=row["patient_id"],
                preferred_language=row.get("preferred_language"),
                preferred_reminder_channel=row.get("preferred_reminder_channel"),
                allow_sms=row.get("allow_sms", True),
                allow_telegram=row.get("allow_telegram", True),
                allow_call=row.get("allow_call", False),
                allow_email=row.get("allow_email", False),
                marketing_opt_in=row.get("marketing_opt_in", False),
                contact_time_window=row.get("contact_time_window"),
            )
        )
    for row in payload.get("patient_flags", []):
        await repo.persist_flag(
            PatientFlag(
                patient_flag_id=row["patient_flag_id"],
                patient_id=row["patient_id"],
                flag_type=row["flag_type"],
                flag_severity=row["flag_severity"],
                is_active=row.get("is_active", True),
                set_by_actor_id=row.get("set_by_actor_id"),
                set_at=row.get("set_at", DEFAULT_SEED_TIMESTAMP),
                expires_at=row.get("expires_at"),
                note=row.get("note"),
            ),
            event_name="patient.flag_set",
        )
    for row in payload.get("patient_photos", []):
        await repo.persist_photo(
            PatientPhoto(
                patient_photo_id=row["patient_photo_id"],
                patient_id=row["patient_id"],
                source_type=row["source_type"],
                media_asset_id=row.get("media_asset_id"),
                external_ref=row.get("external_ref"),
                is_primary=row.get("is_primary", False),
                captured_at=row.get("captured_at"),
            )
        )
    for row in payload.get("patient_medical_summaries", []):
        await repo.persist_medical_summary(
            PatientMedicalSummary(
                patient_medical_summary_id=row["patient_medical_summary_id"],
                patient_id=row["patient_id"],
                allergy_summary=row.get("allergy_summary"),
                chronic_conditions_summary=row.get("chronic_conditions_summary"),
                contraindication_summary=row.get("contraindication_summary"),
                current_primary_dental_issue_summary=row.get("current_primary_dental_issue_summary"),
                important_history_summary=row.get("important_history_summary"),
                last_updated_by_actor_id=row.get("last_updated_by_actor_id"),
                last_updated_at=row.get("last_updated_at", row.get("created_at", DEFAULT_SEED_TIMESTAMP)),
                created_at=row.get("created_at", DEFAULT_SEED_TIMESTAMP),
            )
        )
    for row in payload.get("patient_external_ids", []):
        await repo.persist_external_id(
            PatientExternalId(
                patient_external_id_id=row["patient_external_id_id"],
                patient_id=row["patient_id"],
                external_system=row["external_system"],
                external_id=row["external_id"],
                is_primary=row.get("is_primary", False),
                last_synced_at=row.get("last_synced_at"),
            )
        )
    return {k: len(v) for k, v in payload.items() if isinstance(v, list)}


async def find_patient_by_exact_contact(db_config, *, contact_type: str, contact_value: str) -> dict | None:
    rows = await find_patients_by_exact_contact(db_config, contact_type=contact_type, contact_value=contact_value)
    return rows[0] if rows else None


async def find_patient_by_external_id(db_config, *, external_system: str, external_id: str) -> dict | None:
    rows = await find_patients_by_external_id(db_config, external_system=external_system, external_id=external_id)
    return rows[0] if rows else None


async def find_patients_by_exact_contact(db_config, *, contact_type: str, contact_value: str) -> list[dict]:
    normalized = normalize_contact_value(contact_type, contact_value)
    engine = create_engine(db_config)
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
            SELECT p.patient_id, p.clinic_id, p.display_name, c.normalized_value AS normalized_lookup_value
            FROM core_patient.patient_contacts c
            JOIN core_patient.patients p ON p.patient_id=c.patient_id
            WHERE c.contact_type=:contact_type AND c.normalized_value=:normalized AND c.is_active=TRUE
            ORDER BY c.is_primary DESC, p.patient_id ASC
            """
            ),
            {"contact_type": contact_type, "normalized": normalized},
        )
        rows = list(result.mappings())
    await engine.dispose()
    return [dict(row) for row in rows]


async def find_patients_by_external_id(db_config, *, external_system: str, external_id: str) -> list[dict]:
    engine = create_engine(db_config)
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
            SELECT p.patient_id, p.clinic_id, p.display_name
            FROM core_patient.patient_external_ids x
            JOIN core_patient.patients p ON p.patient_id=x.patient_id
            WHERE x.external_system=:external_system AND x.external_id=:external_id
            ORDER BY p.patient_id ASC
            """
            ),
            {"external_system": external_system, "external_id": external_id},
        )
        rows = list(result.mappings())
    await engine.dispose()
    return [dict(row) for row in rows]


class DbPatientPreferenceReader:
    def __init__(self, db_config) -> None:
        self._db_config = db_config

    async def get_preferences(self, patient_id: str) -> PatientPreference | None:
        row = await _fetch_preference_row(self._db_config, patient_id=patient_id)
        if row is None:
            return None
        return PatientPreference(
            patient_preference_id=row["patient_preference_id"],
            patient_id=row["patient_id"],
            preferred_language=row["preferred_language"],
            preferred_reminder_channel=row["preferred_reminder_channel"],
            allow_sms=row["allow_sms"],
            allow_telegram=row["allow_telegram"],
            allow_call=row["allow_call"],
            allow_email=row["allow_email"],
            marketing_opt_in=row["marketing_opt_in"],
            contact_time_window=row["contact_time_window"],
        )


class DbDoctorPatientReader:
    def __init__(self, db_config) -> None:
        self._db_config = db_config

    async def read_snapshot(self, *, patient_id: str) -> DoctorPatientSnapshot | None:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            patient_row = (
                await conn.execute(
                    text(
                        """
                        SELECT patient_id, display_name, patient_number
                        FROM core_patient.patients
                        WHERE patient_id=:patient_id
                        """
                    ),
                    {"patient_id": patient_id},
                )
            ).mappings().first()
            if patient_row is None:
                result = None
            else:
                phone_row = (
                    await conn.execute(
                        text(
                            """
                            SELECT contact_value
                            FROM core_patient.patient_contacts
                            WHERE patient_id=:patient_id
                              AND contact_type='phone'
                              AND is_primary=TRUE
                              AND is_active=TRUE
                            LIMIT 1
                            """
                        ),
                        {"patient_id": patient_id},
                    )
                ).mappings().first()
                flags_rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT DISTINCT flag_type
                            FROM core_patient.patient_flags
                            WHERE patient_id=:patient_id AND is_active=TRUE
                            ORDER BY flag_type ASC
                            """
                        ),
                        {"patient_id": patient_id},
                    )
                ).mappings().all()
                has_photo = (
                    await conn.execute(
                        text(
                            """
                            SELECT 1
                            FROM core_patient.patient_photos
                            WHERE patient_id=:patient_id AND is_primary=TRUE
                            LIMIT 1
                            """
                        ),
                        {"patient_id": patient_id},
                    )
                ).scalar_one_or_none() is not None
                result = DoctorPatientSnapshot(
                    patient_id=patient_row["patient_id"],
                    display_name=patient_row["display_name"],
                    patient_number=patient_row["patient_number"],
                    phone_raw=phone_row["contact_value"] if phone_row else None,
                    has_photo=has_photo,
                    active_flags_summary=", ".join(row["flag_type"] for row in flags_rows) if flags_rows else None,
                )
        await engine.dispose()
        return result


async def _fetch_preference_row(db_config, *, patient_id: str) -> dict | None:
    engine = create_engine(db_config)
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT patient_preference_id, patient_id, preferred_language, preferred_reminder_channel,
                           allow_sms, allow_telegram, allow_call, allow_email, marketing_opt_in, contact_time_window
                    FROM core_patient.patient_preferences
                    WHERE patient_id=:patient_id
                    """
                ),
                {"patient_id": patient_id},
            )
        ).mappings().first()
    await engine.dispose()
    return dict(row) if row else None
