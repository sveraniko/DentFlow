from __future__ import annotations

import json
import re
from pathlib import Path

from sqlalchemy import text

from app.infrastructure.db.engine import create_engine

_CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y",
    "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


class SearchProjectionRebuilder:
    def __init__(self, *, db_config, locales_path: Path) -> None:
        self._db_config = db_config
        self._locales_path = locales_path

    async def rebuild_all(self) -> dict[str, int]:
        return {
            "patients": await self.rebuild_patients(),
            "doctors": await self.rebuild_doctors(),
            "services": await self.rebuild_services(),
        }

    async def rebuild_patients(self) -> int:
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT
                              p.patient_id,
                              p.clinic_id,
                              p.patient_number,
                              p.display_name,
                              p.full_name_legal,
                              p.first_name,
                              p.last_name,
                              p.middle_name,
                              p.status,
                              p.updated_at,
                              pref.preferred_language,
                              contacts.primary_phone_normalized,
                              ext.external_id_normalized,
                              photo.primary_photo_ref,
                              flags.active_flags_summary
                            FROM core_patient.patients p
                            LEFT JOIN core_patient.patient_preferences pref ON pref.patient_id = p.patient_id
                            LEFT JOIN LATERAL (
                              SELECT c.normalized_value AS primary_phone_normalized
                              FROM core_patient.patient_contacts c
                              WHERE c.patient_id = p.patient_id
                                AND c.contact_type = 'phone'
                                AND c.is_active = TRUE
                              ORDER BY c.is_primary DESC, c.updated_at DESC
                              LIMIT 1
                            ) contacts ON TRUE
                            LEFT JOIN LATERAL (
                              SELECT lower(trim(e.external_id)) AS external_id_normalized
                              FROM core_patient.patient_external_ids e
                              WHERE e.patient_id = p.patient_id
                              ORDER BY e.is_primary DESC, e.created_at DESC
                              LIMIT 1
                            ) ext ON TRUE
                            LEFT JOIN LATERAL (
                              SELECT COALESCE(ph.external_ref, ph.media_asset_id) AS primary_photo_ref
                              FROM core_patient.patient_photos ph
                              WHERE ph.patient_id = p.patient_id
                              ORDER BY ph.is_primary DESC, ph.created_at DESC
                              LIMIT 1
                            ) photo ON TRUE
                            LEFT JOIN LATERAL (
                              SELECT string_agg(DISTINCT pf.flag_type, ', ' ORDER BY pf.flag_type) AS active_flags_summary
                              FROM core_patient.patient_flags pf
                              WHERE pf.patient_id = p.patient_id
                                AND pf.is_active = TRUE
                            ) flags ON TRUE
                            """
                        )
                    )
                ).mappings().all()
                payload: list[dict[str, object]] = []
                for row in rows:
                    name_source = row["display_name"] or row["full_name_legal"] or ""
                    name_normalized = _normalize_text(str(name_source))
                    payload.append(
                        {
                            "patient_id": row["patient_id"],
                            "clinic_id": row["clinic_id"],
                            "patient_number": row["patient_number"],
                            "display_name": row["display_name"],
                            "full_name_legal": row["full_name_legal"],
                            "first_name": row["first_name"],
                            "last_name": row["last_name"],
                            "middle_name": row["middle_name"],
                            "name_normalized": name_normalized,
                            "name_tokens_normalized": name_normalized,
                            "translit_tokens": _transliterate(name_normalized),
                            "external_id_normalized": row["external_id_normalized"],
                            "primary_phone_normalized": _normalize_phone(str(row["primary_phone_normalized"] or "")) or None,
                            "preferred_language": row["preferred_language"],
                            "primary_photo_ref": row["primary_photo_ref"],
                            "active_flags_summary": row["active_flags_summary"],
                            "status": row["status"],
                            "updated_at": row["updated_at"],
                        }
                    )

                await conn.execute(text("TRUNCATE TABLE search.patient_search_projection"))
                if payload:
                    await conn.execute(
                        text(
                            """
                            INSERT INTO search.patient_search_projection (
                              patient_id, clinic_id, patient_number, display_name, full_name_legal,
                              first_name, last_name, middle_name, name_normalized, name_tokens_normalized,
                              translit_tokens, external_id_normalized, primary_phone_normalized, preferred_language,
                              primary_photo_ref, active_flags_summary, status, updated_at
                            ) VALUES (
                              :patient_id, :clinic_id, :patient_number, :display_name, :full_name_legal,
                              :first_name, :last_name, :middle_name, :name_normalized, :name_tokens_normalized,
                              :translit_tokens, :external_id_normalized, :primary_phone_normalized, :preferred_language,
                              :primary_photo_ref, :active_flags_summary, :status, :updated_at
                            )
                            """
                        ),
                        payload,
                    )
                return len(payload)
        finally:
            await engine.dispose()

    async def rebuild_doctors(self) -> int:
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT
                              doctor_id,
                              clinic_id,
                              branch_id,
                              display_name,
                              specialty_code,
                              specialty_code AS specialty_label,
                              public_booking_enabled,
                              status,
                              updated_at
                            FROM core_reference.doctors
                            """
                        )
                    )
                ).mappings().all()
                payload: list[dict[str, object]] = []
                for row in rows:
                    name_normalized = _normalize_text(str(row["display_name"] or ""))
                    payload.append(
                        {
                            "doctor_id": row["doctor_id"],
                            "clinic_id": row["clinic_id"],
                            "branch_id": row["branch_id"],
                            "display_name": row["display_name"],
                            "name_normalized": name_normalized,
                            "name_tokens_normalized": name_normalized,
                            "translit_tokens": _transliterate(name_normalized),
                            "specialty_code": row["specialty_code"],
                            "specialty_label": row["specialty_label"],
                            "public_booking_enabled": bool(row["public_booking_enabled"]),
                            "status": row["status"],
                            "updated_at": row["updated_at"],
                        }
                    )
                await conn.execute(text("TRUNCATE TABLE search.doctor_search_projection"))
                if payload:
                    await conn.execute(
                        text(
                            """
                            INSERT INTO search.doctor_search_projection (
                              doctor_id, clinic_id, branch_id, display_name,
                              name_normalized, name_tokens_normalized, translit_tokens,
                              specialty_code, specialty_label, public_booking_enabled, status, updated_at
                            ) VALUES (
                              :doctor_id, :clinic_id, :branch_id, :display_name,
                              :name_normalized, :name_tokens_normalized, :translit_tokens,
                              :specialty_code, :specialty_label, :public_booking_enabled, :status, :updated_at
                            )
                            """
                        ),
                        payload,
                    )
                return len(payload)
        finally:
            await engine.dispose()

    async def rebuild_services(self) -> int:
        catalogs = {
            "ru": json.loads((self._locales_path / "ru.json").read_text(encoding="utf-8")),
            "en": json.loads((self._locales_path / "en.json").read_text(encoding="utf-8")),
        }
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT service_id, clinic_id, code, title_key, specialty_required, status, updated_at
                            FROM core_reference.services
                            """
                        )
                    )
                ).mappings().all()
                payload = [
                    {
                        "service_id": row["service_id"],
                        "clinic_id": row["clinic_id"],
                        "code": row["code"],
                        "title_key": row["title_key"],
                        "localized_search_text_ru": catalogs["ru"].get(row["title_key"], row["title_key"]),
                        "localized_search_text_en": catalogs["en"].get(row["title_key"], row["title_key"]),
                        "specialty_required": bool(row["specialty_required"]),
                        "status": row["status"],
                        "updated_at": row["updated_at"],
                    }
                    for row in rows
                ]
                await conn.execute(text("TRUNCATE TABLE search.service_search_projection"))
                if payload:
                    await conn.execute(
                        text(
                            """
                            INSERT INTO search.service_search_projection (
                              service_id, clinic_id, code, title_key,
                              localized_search_text_ru, localized_search_text_en,
                              specialty_required, status, updated_at
                            ) VALUES (
                              :service_id, :clinic_id, :code, :title_key,
                              :localized_search_text_ru, :localized_search_text_en,
                              :specialty_required, :status, :updated_at
                            )
                            """
                        ),
                        payload,
                    )
                return len(payload)
        finally:
            await engine.dispose()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\sа-яё]", " ", value.lower(), flags=re.IGNORECASE), flags=re.IGNORECASE).strip()


def _transliterate(value: str) -> str:
    return " ".join("".join(_CYR_TO_LAT.get(ch, ch) for ch in token) for token in value.split())


def _normalize_phone(value: str) -> str:
    return re.sub(r"\D+", "", value)
