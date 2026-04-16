from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import text

from app.application.patient import InMemoryPatientRegistryRepository, PatientRegistryService, normalize_contact_value
from app.domain.patient_registry.models import Patient
from app.infrastructure.db.engine import create_engine


class DbPatientRegistryRepository(InMemoryPatientRegistryRepository):
    def __init__(self, db_config) -> None:
        super().__init__()
        self._db_config = db_config

    async def persist_patient(self, patient: Patient) -> None:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
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
                asdict(patient),
            )
        await engine.dispose()

    async def persist_contact(self, contact) -> None:
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
                ON CONFLICT (patient_contact_id) DO UPDATE SET
                  contact_value=EXCLUDED.contact_value,
                  normalized_value=EXCLUDED.normalized_value,
                  is_primary=EXCLUDED.is_primary,
                  is_verified=EXCLUDED.is_verified,
                  is_active=EXCLUDED.is_active,
                  notes=EXCLUDED.notes,
                  updated_at=NOW()
                """
                ),
                asdict(contact),
            )
        await engine.dispose()


class DbPatientRegistryService(PatientRegistryService):
    repository: DbPatientRegistryRepository

    async def create_patient_db(self, **kwargs):
        patient = self.create_patient(**kwargs)
        await self.repository.persist_patient(patient)
        return patient

    async def update_patient_db(self, patient_id: str, **changes):
        patient = self.update_patient(patient_id, **changes)
        await self.repository.persist_patient(patient)
        return patient

    async def upsert_contact_db(self, *, patient_id: str, contact_type: str, contact_value: str, **kwargs):
        contact = self.upsert_contact(patient_id=patient_id, contact_type=contact_type, contact_value=contact_value, **kwargs)
        await self.repository.persist_contact(contact)
        return contact


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

    engine = create_engine(db_config)
    async with engine.begin() as conn:
        for row in payload.get("patient_preferences", []):
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
                ON CONFLICT (patient_preference_id) DO UPDATE SET
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
                row,
            )
        simple_tables = {
            "patient_flags": "patient_flag_id",
            "patient_photos": "patient_photo_id",
            "patient_medical_summaries": "patient_medical_summary_id",
            "patient_external_ids": "patient_external_id_id",
        }
        for table, pk in simple_tables.items():
            for row in payload.get(table, []):
                cols = ", ".join(row.keys())
                vals = ", ".join(f":{k}" for k in row.keys())
                updates = ", ".join(f"{k}=EXCLUDED.{k}" for k in row.keys() if k != pk)
                await conn.execute(
                    text(f"INSERT INTO core_patient.{table} ({cols}) VALUES ({vals}) ON CONFLICT ({pk}) DO UPDATE SET {updates}"),
                    row,
                )
    await engine.dispose()
    return {k: len(v) for k, v in payload.items() if isinstance(v, list)}


async def find_patient_by_exact_contact(db_config, *, contact_type: str, contact_value: str) -> dict | None:
    normalized = normalize_contact_value(contact_type, contact_value)
    engine = create_engine(db_config)
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                SELECT p.* FROM core_patient.patient_contacts c
                JOIN core_patient.patients p ON p.patient_id=c.patient_id
                WHERE c.contact_type=:contact_type AND c.normalized_value=:normalized AND c.is_active=TRUE
                LIMIT 1
                """
                ),
                {"contact_type": contact_type, "normalized": normalized},
            )
        ).mappings().first()
    await engine.dispose()
    return dict(row) if row else None


async def find_patient_by_external_id(db_config, *, external_system: str, external_id: str) -> dict | None:
    engine = create_engine(db_config)
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                SELECT p.* FROM core_patient.patient_external_ids x
                JOIN core_patient.patients p ON p.patient_id=x.patient_id
                WHERE x.external_system=:external_system AND x.external_id=:external_id
                LIMIT 1
                """
                ),
                {"external_system": external_system, "external_id": external_id},
            )
        ).mappings().first()
    await engine.dispose()
    return dict(row) if row else None
