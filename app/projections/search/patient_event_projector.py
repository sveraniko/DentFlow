from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from app.domain.events import EventEnvelope
from app.infrastructure.db.engine import create_engine

_PATIENT_EVENTS = {
    "patient.created",
    "patient.updated",
    "patient.contact_added",
    "patient.contact_updated",
    "patient.preference_updated",
    "patient.flag_set",
    "patient.flag_cleared",
    "patient.photo_updated",
}


@dataclass(slots=True)
class PatientSearchProjector:
    db_config: Any
    name: str = "search.patient_projection"

    async def handle(self, event: EventEnvelope, outbox_event_id: int) -> bool:
        if event.event_name not in _PATIENT_EVENTS:
            return False
        patient_id = event.entity_id
        engine = create_engine(self.db_config)
        try:
            async with engine.begin() as conn:
                row = (
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
                              ORDER BY e.is_primary DESC, e.patient_external_id_id DESC
                              LIMIT 1
                            ) ext ON TRUE
                            LEFT JOIN LATERAL (
                              SELECT COALESCE(ph.external_ref, ph.media_asset_id) AS primary_photo_ref
                              FROM core_patient.patient_photos ph
                              WHERE ph.patient_id = p.patient_id
                              ORDER BY ph.is_primary DESC, ph.patient_photo_id DESC
                              LIMIT 1
                            ) photo ON TRUE
                            LEFT JOIN LATERAL (
                              SELECT string_agg(DISTINCT pf.flag_type, ', ' ORDER BY pf.flag_type) AS active_flags_summary
                              FROM core_patient.patient_flags pf
                              WHERE pf.patient_id = p.patient_id AND pf.is_active = TRUE
                            ) flags ON TRUE
                            WHERE p.patient_id=:patient_id
                            """
                        ),
                        {"patient_id": patient_id},
                    )
                ).mappings().first()
                if row is None:
                    return False
                name_normalized = _normalize_text(str(row["display_name"] or row["full_name_legal"] or ""))
                await conn.execute(
                    text(
                        """
                        INSERT INTO search.patient_search_projection (
                          patient_id, clinic_id, patient_number, display_name, full_name_legal,
                          first_name, last_name, middle_name, name_normalized, name_tokens_normalized,
                          translit_tokens, external_id_normalized, primary_phone_normalized,
                          preferred_language, primary_photo_ref, active_flags_summary, status, updated_at
                        ) VALUES (
                          :patient_id, :clinic_id, :patient_number, :display_name, :full_name_legal,
                          :first_name, :last_name, :middle_name, :name_normalized, :name_tokens_normalized,
                          :translit_tokens, :external_id_normalized, :primary_phone_normalized,
                          :preferred_language, :primary_photo_ref, :active_flags_summary, :status, :updated_at
                        )
                        ON CONFLICT (patient_id) DO UPDATE SET
                          patient_number=EXCLUDED.patient_number,
                          display_name=EXCLUDED.display_name,
                          full_name_legal=EXCLUDED.full_name_legal,
                          first_name=EXCLUDED.first_name,
                          last_name=EXCLUDED.last_name,
                          middle_name=EXCLUDED.middle_name,
                          name_normalized=EXCLUDED.name_normalized,
                          name_tokens_normalized=EXCLUDED.name_tokens_normalized,
                          translit_tokens=EXCLUDED.translit_tokens,
                          external_id_normalized=EXCLUDED.external_id_normalized,
                          primary_phone_normalized=EXCLUDED.primary_phone_normalized,
                          preferred_language=EXCLUDED.preferred_language,
                          primary_photo_ref=EXCLUDED.primary_photo_ref,
                          active_flags_summary=EXCLUDED.active_flags_summary,
                          status=EXCLUDED.status,
                          updated_at=EXCLUDED.updated_at
                        """
                    ),
                    {
                        **dict(row),
                        "name_normalized": name_normalized,
                        "name_tokens_normalized": name_normalized,
                        "translit_tokens": name_normalized,
                    },
                )
        finally:
            await engine.dispose()
        return True


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\sа-яё]", " ", value.lower(), flags=re.IGNORECASE), flags=re.IGNORECASE).strip()
