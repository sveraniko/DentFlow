from __future__ import annotations

from sqlalchemy import text

from app.application.search.models import DoctorProjectionRow, PatientProjectionRow, ServiceProjectionRow
from app.infrastructure.db.engine import create_engine


class ProjectionSearchReader:
    def __init__(self, db_config) -> None:
        self._db_config = db_config

    async def load_patient_projection_rows(self) -> list[PatientProjectionRow]:
        statement = text(
            """
            SELECT patient_id, clinic_id, display_name, patient_number, name_tokens_normalized, translit_tokens,
                   primary_phone_normalized, preferred_language, primary_photo_ref, active_flags_summary, status, updated_at
            FROM search.patient_search_projection
            """
        )
        engine = create_engine(self._db_config)
        try:
            async with engine.connect() as conn:
                rows = (await conn.execute(statement)).mappings().all()
        finally:
            await engine.dispose()
        return [PatientProjectionRow(**row) for row in rows]

    async def load_doctor_projection_rows(self) -> list[DoctorProjectionRow]:
        statement = text(
            """
            SELECT doctor_id, clinic_id, branch_id, display_name, name_tokens_normalized, translit_tokens,
                   specialty_code, specialty_label, public_booking_enabled, status, updated_at
            FROM search.doctor_search_projection
            """
        )
        engine = create_engine(self._db_config)
        try:
            async with engine.connect() as conn:
                rows = (await conn.execute(statement)).mappings().all()
        finally:
            await engine.dispose()
        return [DoctorProjectionRow(**row) for row in rows]

    async def load_service_projection_rows(self) -> list[ServiceProjectionRow]:
        statement = text(
            """
            SELECT service_id, clinic_id, code, title_key, localized_search_text_ru, localized_search_text_en,
                   specialty_required, status, updated_at
            FROM search.service_search_projection
            """
        )
        engine = create_engine(self._db_config)
        try:
            async with engine.connect() as conn:
                rows = (await conn.execute(statement)).mappings().all()
        finally:
            await engine.dispose()
        return [ServiceProjectionRow(**row) for row in rows]
