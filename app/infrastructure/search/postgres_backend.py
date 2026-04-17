from __future__ import annotations

import re

from sqlalchemy import text

from app.application.search.models import (
    DoctorSearchResult,
    PatientSearchResult,
    SearchQuery,
    SearchResultOrigin,
    ServiceSearchResult,
)
from app.infrastructure.db.engine import create_engine


class PostgresSearchBackend:
    def __init__(self, db_config) -> None:
        self._db_config = db_config

    async def search_patients_strict(self, query: SearchQuery) -> list[PatientSearchResult]:
        normalized_phone = _normalize_phone(query.query)
        normalized_query = query.query.strip().lower()
        statement = text(
            """
            SELECT patient_id, clinic_id, display_name, patient_number, primary_phone_normalized, active_flags_summary, status
            FROM search.patient_search_projection
            WHERE clinic_id = :clinic_id
              AND (
                patient_number = :exact_query
                OR primary_phone_normalized = :normalized_phone
                OR external_id_normalized = :exact_query
                OR lower(name_normalized) = :normalized_query
              )
            ORDER BY updated_at DESC
            LIMIT :limit
            """
        )
        engine = create_engine(self._db_config)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        statement,
                        {
                            "clinic_id": query.clinic_id,
                            "exact_query": query.query.strip(),
                            "normalized_phone": normalized_phone,
                            "normalized_query": normalized_query,
                            "limit": query.limit,
                        },
                    )
                ).mappings().all()
        finally:
            await engine.dispose()
        return [
            PatientSearchResult(
                patient_id=row["patient_id"],
                clinic_id=row["clinic_id"],
                display_name=row.get("display_name") or "",
                patient_number=row.get("patient_number"),
                primary_phone_normalized=row.get("primary_phone_normalized"),
                active_flags_summary=row.get("active_flags_summary"),
                status=row.get("status"),
                origin=SearchResultOrigin.POSTGRES_STRICT,
            )
            for row in rows
        ]

    async def search_patients(self, query: SearchQuery) -> list[PatientSearchResult]:
        statement = text(
            """
            SELECT patient_id, clinic_id, display_name, patient_number, primary_phone_normalized, active_flags_summary, status
            FROM search.patient_search_projection
            WHERE clinic_id = :clinic_id
              AND (
                lower(display_name) LIKE :q
                OR coalesce(name_normalized, '') LIKE :q
                OR coalesce(name_tokens_normalized, '') LIKE :q
                OR coalesce(translit_tokens, '') LIKE :q
              )
            ORDER BY updated_at DESC
            LIMIT :limit
            """
        )
        return await self._load_patients(statement=statement, query=query)

    async def search_doctors(self, query: SearchQuery) -> list[DoctorSearchResult]:
        statement = text(
            """
            SELECT doctor_id, clinic_id, branch_id, display_name, specialty_code, specialty_label,
                   public_booking_enabled, status
            FROM search.doctor_search_projection
            WHERE clinic_id = :clinic_id
              AND (
                lower(display_name) LIKE :q
                OR coalesce(name_normalized, '') LIKE :q
                OR coalesce(name_tokens_normalized, '') LIKE :q
                OR coalesce(translit_tokens, '') LIKE :q
                OR coalesce(specialty_label, '') LIKE :q
                OR coalesce(specialty_code, '') LIKE :q
              )
            ORDER BY updated_at DESC
            LIMIT :limit
            """
        )
        engine = create_engine(self._db_config)
        try:
            async with engine.connect() as conn:
                rows = (await conn.execute(statement, _q_params(query))).mappings().all()
        finally:
            await engine.dispose()
        return [
            DoctorSearchResult(
                doctor_id=row["doctor_id"],
                clinic_id=row["clinic_id"],
                branch_id=row.get("branch_id"),
                display_name=row.get("display_name") or "",
                specialty_code=row.get("specialty_code"),
                specialty_label=row.get("specialty_label"),
                public_booking_enabled=bool(row.get("public_booking_enabled", False)),
                status=row.get("status"),
                origin=SearchResultOrigin.POSTGRES_FALLBACK,
            )
            for row in rows
        ]

    async def search_services(self, query: SearchQuery) -> list[ServiceSearchResult]:
        statement = text(
            """
            SELECT service_id, clinic_id, code, title_key, localized_search_text_ru, localized_search_text_en,
                   specialty_required, status
            FROM search.service_search_projection
            WHERE clinic_id = :clinic_id
              AND (
                coalesce(code, '') LIKE :q
                OR coalesce(title_key, '') LIKE :q
                OR coalesce(localized_search_text_ru, '') LIKE :q
                OR coalesce(localized_search_text_en, '') LIKE :q
              )
            ORDER BY updated_at DESC
            LIMIT :limit
            """
        )
        engine = create_engine(self._db_config)
        try:
            async with engine.connect() as conn:
                rows = (await conn.execute(statement, _q_params(query))).mappings().all()
        finally:
            await engine.dispose()
        return [
            ServiceSearchResult(
                service_id=row["service_id"],
                clinic_id=row["clinic_id"],
                code=row.get("code"),
                title_key=row.get("title_key"),
                localized_search_text_ru=row.get("localized_search_text_ru"),
                localized_search_text_en=row.get("localized_search_text_en"),
                specialty_required=bool(row.get("specialty_required", False)),
                status=row.get("status"),
                origin=SearchResultOrigin.POSTGRES_FALLBACK,
            )
            for row in rows
        ]

    async def _load_patients(self, *, statement, query: SearchQuery) -> list[PatientSearchResult]:
        engine = create_engine(self._db_config)
        try:
            async with engine.connect() as conn:
                rows = (await conn.execute(statement, _q_params(query))).mappings().all()
        finally:
            await engine.dispose()
        return [
            PatientSearchResult(
                patient_id=row["patient_id"],
                clinic_id=row["clinic_id"],
                display_name=row.get("display_name") or "",
                patient_number=row.get("patient_number"),
                primary_phone_normalized=row.get("primary_phone_normalized"),
                active_flags_summary=row.get("active_flags_summary"),
                status=row.get("status"),
                origin=SearchResultOrigin.POSTGRES_FALLBACK,
            )
            for row in rows
        ]


def _q_params(query: SearchQuery) -> dict:
    return {
        "clinic_id": query.clinic_id,
        "q": f"%{query.query.strip().lower()}%",
        "limit": query.limit,
    }


def _normalize_phone(value: str) -> str:
    return re.sub(r"\D+", "", value)
