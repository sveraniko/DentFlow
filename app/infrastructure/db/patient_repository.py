from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Any, Sequence
from uuid import uuid4

from sqlalchemy import text

from app.application.patient import InMemoryPatientRegistryRepository, PatientRegistryService, normalize_contact_value
from app.application.doctor.patient_read import DoctorPatientSnapshot
from app.application.booking.telegram_flow import CanonicalPatientCreator
from app.domain.events import build_event
from app.domain.patient_registry.models import (
    LinkedPatientProfile,
    Patient,
    PatientContact,
    PatientExternalId,
    PatientFlag,
    PatientMedicalSummary,
    PatientPhoto,
    PatientPreference,
    PatientProfileDetails,
    PatientRelationship,
    PreVisitQuestionnaire,
    PreVisitQuestionnaireAnswer,
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
                  allow_sms, allow_telegram, allow_call, allow_email, marketing_opt_in, contact_time_window,
                  notification_recipient_strategy, quiet_hours_start, quiet_hours_end, quiet_hours_timezone,
                  default_branch_id, allow_any_branch
                ) VALUES (
                  :patient_preference_id, :patient_id, :preferred_language, :preferred_reminder_channel,
                  :allow_sms, :allow_telegram, :allow_call, :allow_email, :marketing_opt_in, :contact_time_window,
                  :notification_recipient_strategy, :quiet_hours_start, :quiet_hours_end, :quiet_hours_timezone,
                  :default_branch_id, :allow_any_branch
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
                  notification_recipient_strategy=EXCLUDED.notification_recipient_strategy,
                  quiet_hours_start=EXCLUDED.quiet_hours_start,
                  quiet_hours_end=EXCLUDED.quiet_hours_end,
                  quiet_hours_timezone=EXCLUDED.quiet_hours_timezone,
                  default_branch_id=EXCLUDED.default_branch_id,
                  allow_any_branch=EXCLUDED.allow_any_branch,
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

    async def get_profile_details(self, *, clinic_id: str, patient_id: str) -> PatientProfileDetails | None:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT patient_id, clinic_id, profile_completion_state, email, address_line1, address_line2,
                               city, postal_code, country_code, emergency_contact_name, emergency_contact_phone,
                               profile_completed_at, created_at, updated_at
                        FROM core_patient.patient_profile_details
                        WHERE clinic_id=:clinic_id AND patient_id=:patient_id
                        """
                    ),
                    {"clinic_id": clinic_id, "patient_id": patient_id},
                )
            ).mappings().first()
        await engine.dispose()
        return _map_patient_profile_details(row) if row else None

    async def upsert_profile_details(self, details: PatientProfileDetails) -> PatientProfileDetails:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        INSERT INTO core_patient.patient_profile_details (
                          patient_id, clinic_id, profile_completion_state, email, address_line1, address_line2,
                          city, postal_code, country_code, emergency_contact_name, emergency_contact_phone, profile_completed_at
                        ) VALUES (
                          :patient_id, :clinic_id, :profile_completion_state, :email, :address_line1, :address_line2,
                          :city, :postal_code, :country_code, :emergency_contact_name, :emergency_contact_phone, :profile_completed_at
                        )
                        ON CONFLICT (patient_id) DO UPDATE SET
                          clinic_id=EXCLUDED.clinic_id,
                          profile_completion_state=EXCLUDED.profile_completion_state,
                          email=EXCLUDED.email,
                          address_line1=EXCLUDED.address_line1,
                          address_line2=EXCLUDED.address_line2,
                          city=EXCLUDED.city,
                          postal_code=EXCLUDED.postal_code,
                          country_code=EXCLUDED.country_code,
                          emergency_contact_name=EXCLUDED.emergency_contact_name,
                          emergency_contact_phone=EXCLUDED.emergency_contact_phone,
                          profile_completed_at=EXCLUDED.profile_completed_at,
                          updated_at=NOW()
                        RETURNING patient_id, clinic_id, profile_completion_state, email, address_line1, address_line2,
                                  city, postal_code, country_code, emergency_contact_name, emergency_contact_phone,
                                  profile_completed_at, created_at, updated_at
                        """
                    ),
                    asdict(details),
                )
            ).mappings().one()
        await engine.dispose()
        return _map_patient_profile_details(row)

    async def get_profile_completion_state(self, *, clinic_id: str, patient_id: str) -> str | None:
        row = await self.get_profile_details(clinic_id=clinic_id, patient_id=patient_id)
        return row.profile_completion_state if row else None

    async def list_relationships(
        self, *, clinic_id: str, manager_patient_id: str, include_inactive: bool = False
    ) -> list[PatientRelationship]:
        filters = ""
        if not include_inactive:
            filters = " AND consent_status='active' AND (expires_at IS NULL OR expires_at > NOW())"
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        f"""
                        SELECT relationship_id, clinic_id, manager_patient_id, related_patient_id, relationship_type,
                               consent_status, authority_scope, is_default_for_booking,
                               is_default_notification_recipient, starts_at, expires_at, created_at, updated_at
                        FROM core_patient.patient_relationships
                        WHERE clinic_id=:clinic_id AND manager_patient_id=:manager_patient_id{filters}
                        ORDER BY is_default_for_booking DESC, related_patient_id ASC
                        """
                    ),
                    {"clinic_id": clinic_id, "manager_patient_id": manager_patient_id},
                )
            ).mappings().all()
        await engine.dispose()
        return [_map_patient_relationship(row) for row in rows]

    async def upsert_relationship(self, relationship: PatientRelationship) -> PatientRelationship:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        INSERT INTO core_patient.patient_relationships (
                          relationship_id, clinic_id, manager_patient_id, related_patient_id, relationship_type,
                          consent_status, authority_scope, is_default_for_booking, is_default_notification_recipient,
                          starts_at, expires_at
                        ) VALUES (
                          :relationship_id, :clinic_id, :manager_patient_id, :related_patient_id, :relationship_type,
                          :consent_status, :authority_scope, :is_default_for_booking, :is_default_notification_recipient,
                          :starts_at, :expires_at
                        )
                        ON CONFLICT (relationship_id) DO UPDATE SET
                          clinic_id=EXCLUDED.clinic_id,
                          manager_patient_id=EXCLUDED.manager_patient_id,
                          related_patient_id=EXCLUDED.related_patient_id,
                          relationship_type=EXCLUDED.relationship_type,
                          consent_status=EXCLUDED.consent_status,
                          authority_scope=EXCLUDED.authority_scope,
                          is_default_for_booking=EXCLUDED.is_default_for_booking,
                          is_default_notification_recipient=EXCLUDED.is_default_notification_recipient,
                          starts_at=EXCLUDED.starts_at,
                          expires_at=EXCLUDED.expires_at,
                          updated_at=NOW()
                        RETURNING relationship_id, clinic_id, manager_patient_id, related_patient_id, relationship_type,
                                  consent_status, authority_scope, is_default_for_booking, is_default_notification_recipient,
                                  starts_at, expires_at, created_at, updated_at
                        """
                    ),
                    asdict(relationship),
                )
            ).mappings().one()
        await engine.dispose()
        return _map_patient_relationship(row)

    async def deactivate_relationship(self, *, clinic_id: str, relationship_id: str) -> PatientRelationship | None:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        UPDATE core_patient.patient_relationships
                        SET consent_status='revoked', updated_at=NOW()
                        WHERE clinic_id=:clinic_id AND relationship_id=:relationship_id
                        RETURNING relationship_id, clinic_id, manager_patient_id, related_patient_id, relationship_type,
                                  consent_status, authority_scope, is_default_for_booking, is_default_notification_recipient,
                                  starts_at, expires_at, created_at, updated_at
                        """
                    ),
                    {"clinic_id": clinic_id, "relationship_id": relationship_id},
                )
            ).mappings().first()
        await engine.dispose()
        return _map_patient_relationship(row) if row else None

    async def list_linked_profiles_for_telegram(
        self, *, clinic_id: str, telegram_user_id: int, include_inactive: bool = False
    ) -> list[LinkedPatientProfile]:
        rel_filter = ""
        patient_filter = ""
        if not include_inactive:
            rel_filter = "AND r.consent_status='active' AND (r.expires_at IS NULL OR r.expires_at > NOW())"
            patient_filter = "AND p.status='active'"
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        f"""
                        WITH managers AS (
                          SELECT DISTINCT p.patient_id AS manager_patient_id
                          FROM core_patient.patient_contacts c
                          JOIN core_patient.patients p ON p.patient_id = c.patient_id
                          WHERE p.clinic_id=:clinic_id
                            AND c.contact_type='telegram'
                            AND c.normalized_value=:normalized_value
                            AND c.is_active=TRUE
                        ),
                        self_pool AS (
                          SELECT
                            m.manager_patient_id AS patient_id,
                            'self'::TEXT AS relationship_type,
                            TRUE AS is_self,
                            FALSE AS is_default_for_booking,
                            FALSE AS is_default_notification_recipient
                          FROM managers m
                        ),
                        related_pool AS (
                          SELECT
                            r.related_patient_id AS patient_id,
                            r.relationship_type,
                            FALSE AS is_self,
                            r.is_default_for_booking,
                            r.is_default_notification_recipient
                          FROM core_patient.patient_relationships r
                          JOIN managers m ON m.manager_patient_id = r.manager_patient_id
                          WHERE r.clinic_id=:clinic_id {rel_filter}
                        ),
                        pool AS (
                          SELECT * FROM self_pool
                          UNION ALL
                          SELECT * FROM related_pool
                        ),
                        ranked AS (
                          SELECT
                            patient_id,
                            CASE WHEN BOOL_OR(is_self) THEN 'self' ELSE MIN(relationship_type) END AS relationship_type,
                            BOOL_OR(is_self) AS is_self,
                            BOOL_OR(is_default_for_booking) AS is_default_for_booking,
                            BOOL_OR(is_default_notification_recipient) AS is_default_notification_recipient
                          FROM pool
                          GROUP BY patient_id
                        ),
                        telegram_contacts AS (
                          SELECT DISTINCT ON (patient_id)
                            patient_id,
                            NULLIF(normalized_value, '')::BIGINT AS telegram_user_id
                          FROM core_patient.patient_contacts
                          WHERE contact_type='telegram' AND is_active=TRUE
                          ORDER BY patient_id, is_primary DESC, updated_at DESC NULLS LAST, created_at DESC NULLS LAST
                        ),
                        phone_contacts AS (
                          SELECT DISTINCT ON (patient_id)
                            patient_id,
                            contact_value AS phone
                          FROM core_patient.patient_contacts
                          WHERE contact_type='phone' AND is_active=TRUE
                          ORDER BY patient_id, is_primary DESC, updated_at DESC NULLS LAST, created_at DESC NULLS LAST
                        )
                        SELECT p.patient_id, p.clinic_id, p.patient_number, p.full_name_legal, p.first_name, p.last_name, p.middle_name,
                               p.display_name, p.birth_date, p.sex_marker, p.status, p.first_seen_at, p.last_seen_at,
                               ranked.relationship_type, ranked.is_self, ranked.is_default_for_booking,
                               ranked.is_default_notification_recipient, phone_contacts.phone, telegram_contacts.telegram_user_id
                        FROM ranked
                        JOIN core_patient.patients p ON p.patient_id=ranked.patient_id
                        LEFT JOIN phone_contacts ON phone_contacts.patient_id = p.patient_id
                        LEFT JOIN telegram_contacts ON telegram_contacts.patient_id = p.patient_id
                        WHERE p.clinic_id=:clinic_id {patient_filter}
                        ORDER BY ranked.is_self DESC, ranked.is_default_for_booking DESC, p.display_name ASC
                        """
                    ),
                    {"clinic_id": clinic_id, "normalized_value": str(telegram_user_id)},
                )
            ).mappings().all()
        await engine.dispose()
        return [
            LinkedPatientProfile(
                patient_id=row["patient_id"],
                clinic_id=row["clinic_id"],
                display_name=row["display_name"],
                relationship_type=row["relationship_type"],
                is_self=row["is_self"],
                is_default_for_booking=row["is_default_for_booking"],
                is_default_notification_recipient=row["is_default_notification_recipient"],
                phone=row["phone"],
                telegram_user_id=row["telegram_user_id"],
                status=row["status"],
            )
            for row in rows
        ]

    async def get_patient_preferences(self, *, patient_id: str) -> PatientPreference | None:
        row = await _fetch_preference_row(self._db_config, patient_id=patient_id)
        return _map_patient_preference(row) if row else None

    async def upsert_patient_preferences(self, preference: PatientPreference) -> PatientPreference:
        await self.persist_preferences(preference)
        row = await _fetch_preference_row(self._db_config, patient_id=preference.patient_id)
        assert row is not None
        return _map_patient_preference(row)

    async def update_notification_preferences(self, *, patient_id: str, **changes) -> PatientPreference:
        current = await self.get_patient_preferences(patient_id=patient_id)
        if current is None:
            current = PatientPreference(patient_preference_id=f"pp_{uuid4().hex}", patient_id=patient_id)
        merged = asdict(current)
        for key, value in changes.items():
            if value is not None:
                merged[key] = value
        return await self.upsert_patient_preferences(PatientPreference(**merged))

    async def update_branch_preferences(
        self, *, patient_id: str, default_branch_id: str | None, allow_any_branch: bool
    ) -> PatientPreference:
        current = await self.get_patient_preferences(patient_id=patient_id)
        if current is None:
            current = PatientPreference(patient_preference_id=f"pp_{uuid4().hex}", patient_id=patient_id)
        merged = asdict(current)
        merged["default_branch_id"] = default_branch_id
        merged["allow_any_branch"] = allow_any_branch
        return await self.upsert_patient_preferences(PatientPreference(**merged))

    async def get_pre_visit_questionnaire(
        self, *, clinic_id: str, questionnaire_id: str
    ) -> PreVisitQuestionnaire | None:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT questionnaire_id, clinic_id, patient_id, booking_id, questionnaire_type, status,
                               version, completed_at, created_at, updated_at
                        FROM core_patient.pre_visit_questionnaires
                        WHERE clinic_id=:clinic_id AND questionnaire_id=:questionnaire_id
                        """
                    ),
                    {"clinic_id": clinic_id, "questionnaire_id": questionnaire_id},
                )
            ).mappings().first()
        await engine.dispose()
        return _map_pre_visit_questionnaire(row) if row else None

    async def list_pre_visit_questionnaires(
        self, *, clinic_id: str, patient_id: str, booking_id: str | None = None, status: str | None = None
    ) -> list[PreVisitQuestionnaire]:
        engine = create_engine(self._db_config)
        clauses = ["clinic_id=:clinic_id", "patient_id=:patient_id"]
        params: dict[str, Any] = {"clinic_id": clinic_id, "patient_id": patient_id}
        if booking_id is not None:
            clauses.append("booking_id=:booking_id")
            params["booking_id"] = booking_id
        if status is not None:
            clauses.append("status=:status")
            params["status"] = status
        where_sql = " AND ".join(clauses)
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        f"""
                        SELECT questionnaire_id, clinic_id, patient_id, booking_id, questionnaire_type, status,
                               version, completed_at, created_at, updated_at
                        FROM core_patient.pre_visit_questionnaires
                        WHERE {where_sql}
                        ORDER BY completed_at DESC NULLS LAST, updated_at DESC, created_at DESC
                        """
                    ),
                    params,
                )
            ).mappings().all()
        await engine.dispose()
        return [_map_pre_visit_questionnaire(row) for row in rows]

    async def upsert_pre_visit_questionnaire(self, questionnaire: PreVisitQuestionnaire) -> PreVisitQuestionnaire:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        INSERT INTO core_patient.pre_visit_questionnaires (
                          questionnaire_id, clinic_id, patient_id, booking_id, questionnaire_type, status,
                          version, completed_at, created_at, updated_at
                        ) VALUES (
                          :questionnaire_id, :clinic_id, :patient_id, :booking_id, :questionnaire_type, :status,
                          :version, :completed_at, COALESCE(:created_at, NOW()), COALESCE(:updated_at, NOW())
                        )
                        ON CONFLICT (questionnaire_id) DO UPDATE SET
                          clinic_id=EXCLUDED.clinic_id,
                          patient_id=EXCLUDED.patient_id,
                          booking_id=EXCLUDED.booking_id,
                          questionnaire_type=EXCLUDED.questionnaire_type,
                          status=EXCLUDED.status,
                          version=EXCLUDED.version,
                          completed_at=EXCLUDED.completed_at,
                          created_at=core_patient.pre_visit_questionnaires.created_at,
                          updated_at=NOW()
                        RETURNING questionnaire_id, clinic_id, patient_id, booking_id, questionnaire_type, status,
                                  version, completed_at, created_at, updated_at
                        """
                    ),
                    asdict(questionnaire),
                )
            ).mappings().one()
        await engine.dispose()
        return _map_pre_visit_questionnaire(row)

    async def complete_pre_visit_questionnaire(
        self, *, clinic_id: str, questionnaire_id: str, completed_at: datetime | None = None
    ) -> PreVisitQuestionnaire | None:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        UPDATE core_patient.pre_visit_questionnaires
                        SET status='completed',
                            completed_at=COALESCE(:completed_at, NOW()),
                            updated_at=NOW()
                        WHERE clinic_id=:clinic_id AND questionnaire_id=:questionnaire_id
                        RETURNING questionnaire_id, clinic_id, patient_id, booking_id, questionnaire_type, status,
                                  version, completed_at, created_at, updated_at
                        """
                    ),
                    {"clinic_id": clinic_id, "questionnaire_id": questionnaire_id, "completed_at": completed_at},
                )
            ).mappings().first()
        await engine.dispose()
        return _map_pre_visit_questionnaire(row) if row else None

    async def list_pre_visit_questionnaire_answers(
        self, *, questionnaire_id: str
    ) -> list[PreVisitQuestionnaireAnswer]:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        """
                        SELECT answer_id, questionnaire_id, question_key, answer_value, answer_type, visibility,
                               created_at, updated_at
                        FROM core_patient.pre_visit_questionnaire_answers
                        WHERE questionnaire_id=:questionnaire_id
                        ORDER BY question_key ASC
                        """
                    ),
                    {"questionnaire_id": questionnaire_id},
                )
            ).mappings().all()
        await engine.dispose()
        return [_map_pre_visit_questionnaire_answer(row) for row in rows]

    async def upsert_pre_visit_questionnaire_answer(self, answer: PreVisitQuestionnaireAnswer) -> PreVisitQuestionnaireAnswer:
        engine = create_engine(self._db_config)
        params = asdict(answer)
        if not isinstance(params.get("answer_value"), (dict, list, str, int, float, bool, type(None))):
            params["answer_value"] = str(params["answer_value"])
        params["answer_value"] = json.dumps(params["answer_value"])
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        INSERT INTO core_patient.pre_visit_questionnaire_answers (
                          answer_id, questionnaire_id, question_key, answer_value, answer_type, visibility,
                          created_at, updated_at
                        ) VALUES (
                          :answer_id, :questionnaire_id, :question_key, CAST(:answer_value AS JSONB), :answer_type, :visibility,
                          COALESCE(:created_at, NOW()), COALESCE(:updated_at, NOW())
                        )
                        ON CONFLICT (answer_id) DO UPDATE SET
                          questionnaire_id=EXCLUDED.questionnaire_id,
                          question_key=EXCLUDED.question_key,
                          answer_value=EXCLUDED.answer_value,
                          answer_type=EXCLUDED.answer_type,
                          visibility=EXCLUDED.visibility,
                          created_at=core_patient.pre_visit_questionnaire_answers.created_at,
                          updated_at=NOW()
                        RETURNING answer_id, questionnaire_id, question_key, answer_value, answer_type, visibility,
                                  created_at, updated_at
                        """
                    ),
                    params,
                )
            ).mappings().one()
        await engine.dispose()
        return _map_pre_visit_questionnaire_answer(row)

    async def upsert_pre_visit_questionnaire_answers(
        self, answers: Sequence[PreVisitQuestionnaireAnswer]
    ) -> list[PreVisitQuestionnaireAnswer]:
        persisted: list[PreVisitQuestionnaireAnswer] = []
        for answer in answers:
            persisted.append(await self.upsert_pre_visit_questionnaire_answer(answer))
        return persisted

    async def delete_pre_visit_questionnaire_answer(self, *, questionnaire_id: str, question_key: str) -> bool:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            deleted = await conn.execute(
                text(
                    """
                    DELETE FROM core_patient.pre_visit_questionnaire_answers
                    WHERE questionnaire_id=:questionnaire_id AND question_key=:question_key
                    """
                ),
                {"questionnaire_id": questionnaire_id, "question_key": question_key},
            )
        await engine.dispose()
        return deleted.rowcount > 0

    async def get_latest_pre_visit_questionnaire_for_booking(
        self, *, clinic_id: str, booking_id: str, questionnaire_type: str | None = None
    ) -> PreVisitQuestionnaire | None:
        return await self._get_latest_pre_visit_questionnaire(
            clinic_id=clinic_id, filters={"booking_id": booking_id}, questionnaire_type=questionnaire_type
        )

    async def get_latest_pre_visit_questionnaire_for_patient(
        self, *, clinic_id: str, patient_id: str, questionnaire_type: str | None = None
    ) -> PreVisitQuestionnaire | None:
        return await self._get_latest_pre_visit_questionnaire(
            clinic_id=clinic_id, filters={"patient_id": patient_id}, questionnaire_type=questionnaire_type
        )

    async def _get_latest_pre_visit_questionnaire(
        self, *, clinic_id: str, filters: dict[str, str], questionnaire_type: str | None
    ) -> PreVisitQuestionnaire | None:
        clauses = ["clinic_id=:clinic_id"]
        params: dict[str, Any] = {"clinic_id": clinic_id}
        for key, value in filters.items():
            clauses.append(f"{key}=:{key}")
            params[key] = value
        if questionnaire_type is not None:
            clauses.append("questionnaire_type=:questionnaire_type")
            params["questionnaire_type"] = questionnaire_type
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        f"""
                        SELECT questionnaire_id, clinic_id, patient_id, booking_id, questionnaire_type, status,
                               version, completed_at, created_at, updated_at
                        FROM core_patient.pre_visit_questionnaires
                        WHERE {" AND ".join(clauses)}
                        ORDER BY completed_at DESC NULLS LAST, updated_at DESC, created_at DESC
                        LIMIT 1
                        """
                    ),
                    params,
                )
            ).mappings().first()
        await engine.dispose()
        return _map_pre_visit_questionnaire(row) if row else None

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
        return _map_patient_preference(row) if row else None


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
                           allow_sms, allow_telegram, allow_call, allow_email, marketing_opt_in, contact_time_window,
                           notification_recipient_strategy, quiet_hours_start, quiet_hours_end, quiet_hours_timezone,
                           default_branch_id, allow_any_branch
                    FROM core_patient.patient_preferences
                    WHERE patient_id=:patient_id
                    """
                ),
                {"patient_id": patient_id},
            )
        ).mappings().first()
    await engine.dispose()
    return dict(row) if row else None


def _map_patient_profile_details(row) -> PatientProfileDetails:
    return PatientProfileDetails(**dict(row))


def _map_patient_relationship(row) -> PatientRelationship:
    return PatientRelationship(**dict(row))


def _map_patient_preference(row) -> PatientPreference:
    return PatientPreference(**dict(row))


def _map_pre_visit_questionnaire(row) -> PreVisitQuestionnaire:
    return PreVisitQuestionnaire(**dict(row))


def _map_pre_visit_questionnaire_answer(row) -> PreVisitQuestionnaireAnswer:
    return PreVisitQuestionnaireAnswer(**dict(row))
