from __future__ import annotations

import json
from dataclasses import asdict

from sqlalchemy import text

from app.application.clinical import ClinicalRepository
from app.domain.clinical import ClinicalEncounter, Diagnosis, EncounterNote, ImagingReference, OdontogramSnapshot, PatientChart, TreatmentPlan
from app.infrastructure.db.engine import create_engine


class DbClinicalRepository(ClinicalRepository):
    def __init__(self, db_config) -> None:
        self._db_config = db_config

    async def get_active_chart(self, *, patient_id: str, clinic_id: str) -> PatientChart | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT chart_id, patient_id, clinic_id, chart_number, opened_at, status, primary_doctor_id, notes_summary, created_at, updated_at
            FROM clinical.patient_charts
            WHERE patient_id=:patient_id AND clinic_id=:clinic_id AND status='active'
            ORDER BY opened_at DESC
            LIMIT 1
            """,
            {"patient_id": patient_id, "clinic_id": clinic_id},
        )
        return PatientChart(**row) if row else None

    async def upsert_chart(self, item: PatientChart) -> None:
        await _exec(
            self._db_config,
            """
            INSERT INTO clinical.patient_charts (
              chart_id, patient_id, clinic_id, chart_number, opened_at, status, primary_doctor_id, notes_summary, created_at, updated_at
            ) VALUES (
              :chart_id, :patient_id, :clinic_id, :chart_number, :opened_at, :status, :primary_doctor_id, :notes_summary, :created_at, :updated_at
            )
            ON CONFLICT (chart_id) DO UPDATE SET
              chart_number=EXCLUDED.chart_number,
              status=EXCLUDED.status,
              primary_doctor_id=EXCLUDED.primary_doctor_id,
              notes_summary=EXCLUDED.notes_summary,
              updated_at=EXCLUDED.updated_at
            """,
            asdict(item),
        )

    async def get_chart(self, chart_id: str) -> PatientChart | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT chart_id, patient_id, clinic_id, chart_number, opened_at, status, primary_doctor_id, notes_summary, created_at, updated_at
            FROM clinical.patient_charts
            WHERE chart_id=:chart_id
            """,
            {"chart_id": chart_id},
        )
        return PatientChart(**row) if row else None

    async def get_open_encounter(self, *, chart_id: str, doctor_id: str, booking_id: str | None) -> ClinicalEncounter | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT encounter_id, chart_id, booking_id, doctor_id, opened_at, closed_at, status,
                   chief_complaint_snapshot, findings_summary, assessment_summary, plan_summary, created_at, updated_at
            FROM clinical.clinical_encounters
            WHERE chart_id=:chart_id
              AND status='open'
              AND (:doctor_id='' OR doctor_id=:doctor_id)
              AND (:booking_id IS NULL OR booking_id=:booking_id)
            ORDER BY opened_at DESC
            LIMIT 1
            """,
            {"chart_id": chart_id, "doctor_id": doctor_id, "booking_id": booking_id},
        )
        return ClinicalEncounter(**row) if row else None

    async def get_encounter(self, encounter_id: str) -> ClinicalEncounter | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT encounter_id, chart_id, booking_id, doctor_id, opened_at, closed_at, status,
                   chief_complaint_snapshot, findings_summary, assessment_summary, plan_summary, created_at, updated_at
            FROM clinical.clinical_encounters
            WHERE encounter_id=:encounter_id
            """,
            {"encounter_id": encounter_id},
        )
        return ClinicalEncounter(**row) if row else None

    async def upsert_encounter(self, item: ClinicalEncounter) -> None:
        await _exec(
            self._db_config,
            """
            INSERT INTO clinical.clinical_encounters (
              encounter_id, chart_id, booking_id, doctor_id, opened_at, closed_at, status,
              chief_complaint_snapshot, findings_summary, assessment_summary, plan_summary, created_at, updated_at
            ) VALUES (
              :encounter_id, :chart_id, :booking_id, :doctor_id, :opened_at, :closed_at, :status,
              :chief_complaint_snapshot, :findings_summary, :assessment_summary, :plan_summary, :created_at, :updated_at
            )
            ON CONFLICT (encounter_id) DO UPDATE SET
              closed_at=EXCLUDED.closed_at,
              status=EXCLUDED.status,
              chief_complaint_snapshot=EXCLUDED.chief_complaint_snapshot,
              findings_summary=EXCLUDED.findings_summary,
              assessment_summary=EXCLUDED.assessment_summary,
              plan_summary=EXCLUDED.plan_summary,
              updated_at=EXCLUDED.updated_at
            """,
            asdict(item),
        )

    async def add_encounter_note(self, item: EncounterNote) -> None:
        await _exec(
            self._db_config,
            """
            INSERT INTO clinical.encounter_notes (
              encounter_note_id, encounter_id, note_type, note_text, recorded_by_actor_id, recorded_at, created_at, updated_at
            ) VALUES (
              :encounter_note_id, :encounter_id, :note_type, :note_text, :recorded_by_actor_id, :recorded_at, :created_at, :updated_at
            )
            ON CONFLICT (encounter_note_id) DO UPDATE SET
              note_type=EXCLUDED.note_type,
              note_text=EXCLUDED.note_text,
              updated_at=EXCLUDED.updated_at
            """,
            asdict(item),
        )

    async def list_encounter_notes(self, *, encounter_id: str) -> list[EncounterNote]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT encounter_note_id, encounter_id, note_type, note_text, recorded_by_actor_id, recorded_at, created_at, updated_at
            FROM clinical.encounter_notes
            WHERE encounter_id=:encounter_id
            ORDER BY recorded_at ASC
            """,
            {"encounter_id": encounter_id},
        )
        return [EncounterNote(**row) for row in rows]

    async def upsert_diagnosis(self, item: Diagnosis) -> None:
        await _exec(
            self._db_config,
            """
            INSERT INTO clinical.diagnoses (
              diagnosis_id, chart_id, encounter_id, diagnosis_code, diagnosis_text, is_primary, status,
              recorded_by_actor_id, recorded_at, created_at, updated_at
            ) VALUES (
              :diagnosis_id, :chart_id, :encounter_id, :diagnosis_code, :diagnosis_text, :is_primary, :status,
              :recorded_by_actor_id, :recorded_at, :created_at, :updated_at
            )
            ON CONFLICT (diagnosis_id) DO UPDATE SET
              diagnosis_code=EXCLUDED.diagnosis_code,
              diagnosis_text=EXCLUDED.diagnosis_text,
              is_primary=EXCLUDED.is_primary,
              status=EXCLUDED.status,
              updated_at=EXCLUDED.updated_at
            """,
            asdict(item),
        )

    async def list_chart_diagnoses(self, *, chart_id: str) -> list[Diagnosis]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT diagnosis_id, chart_id, encounter_id, diagnosis_code, diagnosis_text, is_primary, status,
                   recorded_by_actor_id, recorded_at, created_at, updated_at
            FROM clinical.diagnoses
            WHERE chart_id=:chart_id
            ORDER BY recorded_at ASC
            """,
            {"chart_id": chart_id},
        )
        return [Diagnosis(**row) for row in rows]

    async def upsert_treatment_plan(self, item: TreatmentPlan) -> None:
        await _exec(
            self._db_config,
            """
            INSERT INTO clinical.treatment_plans (
              treatment_plan_id, chart_id, encounter_id, title, plan_text, status,
              estimated_cost_amount, currency_code, approved_by_patient_at, created_at, updated_at
            ) VALUES (
              :treatment_plan_id, :chart_id, :encounter_id, :title, :plan_text, :status,
              :estimated_cost_amount, :currency_code, :approved_by_patient_at, :created_at, :updated_at
            )
            ON CONFLICT (treatment_plan_id) DO UPDATE SET
              title=EXCLUDED.title,
              plan_text=EXCLUDED.plan_text,
              status=EXCLUDED.status,
              estimated_cost_amount=EXCLUDED.estimated_cost_amount,
              currency_code=EXCLUDED.currency_code,
              approved_by_patient_at=EXCLUDED.approved_by_patient_at,
              updated_at=EXCLUDED.updated_at
            """,
            asdict(item),
        )

    async def list_chart_treatment_plans(self, *, chart_id: str) -> list[TreatmentPlan]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT treatment_plan_id, chart_id, encounter_id, title, plan_text, status,
                   estimated_cost_amount, currency_code, approved_by_patient_at, created_at, updated_at
            FROM clinical.treatment_plans
            WHERE chart_id=:chart_id
            ORDER BY created_at ASC
            """,
            {"chart_id": chart_id},
        )
        return [TreatmentPlan(**row) for row in rows]

    async def upsert_imaging_reference(self, item: ImagingReference) -> None:
        await _exec(
            self._db_config,
            """
            INSERT INTO clinical.imaging_references (
              imaging_ref_id, chart_id, encounter_id, imaging_type, media_asset_id, external_url, description, taken_at,
              uploaded_at, uploaded_by_actor_id, is_primary_for_case, created_at, updated_at
            ) VALUES (
              :imaging_ref_id, :chart_id, :encounter_id, :imaging_type, :media_asset_id, :external_url, :description, :taken_at,
              :uploaded_at, :uploaded_by_actor_id, :is_primary_for_case, :created_at, :updated_at
            )
            ON CONFLICT (imaging_ref_id) DO UPDATE SET
              imaging_type=EXCLUDED.imaging_type,
              media_asset_id=EXCLUDED.media_asset_id,
              external_url=EXCLUDED.external_url,
              description=EXCLUDED.description,
              taken_at=EXCLUDED.taken_at,
              is_primary_for_case=EXCLUDED.is_primary_for_case,
              updated_at=EXCLUDED.updated_at
            """,
            asdict(item),
        )

    async def list_imaging_references(self, *, chart_id: str) -> list[ImagingReference]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT imaging_ref_id, chart_id, encounter_id, imaging_type, media_asset_id, external_url, description, taken_at,
                   uploaded_at, uploaded_by_actor_id, is_primary_for_case, created_at, updated_at
            FROM clinical.imaging_references
            WHERE chart_id=:chart_id
            ORDER BY uploaded_at ASC
            """,
            {"chart_id": chart_id},
        )
        return [ImagingReference(**row) for row in rows]

    async def add_odontogram_snapshot(self, item: OdontogramSnapshot) -> None:
        payload = asdict(item)
        payload["snapshot_payload_json"] = json.dumps(payload["snapshot_payload_json"])
        await _exec(
            self._db_config,
            """
            INSERT INTO clinical.odontogram_snapshots (
              odontogram_snapshot_id, chart_id, encounter_id, snapshot_payload_json, recorded_at, recorded_by_actor_id, created_at
            ) VALUES (
              :odontogram_snapshot_id, :chart_id, :encounter_id, CAST(:snapshot_payload_json AS JSONB), :recorded_at, :recorded_by_actor_id, :created_at
            )
            ON CONFLICT (odontogram_snapshot_id) DO UPDATE SET
              snapshot_payload_json=EXCLUDED.snapshot_payload_json,
              recorded_at=EXCLUDED.recorded_at,
              recorded_by_actor_id=EXCLUDED.recorded_by_actor_id
            """,
            payload,
        )

    async def get_latest_odontogram_snapshot(self, *, chart_id: str) -> OdontogramSnapshot | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT odontogram_snapshot_id, chart_id, encounter_id, snapshot_payload_json, recorded_at, recorded_by_actor_id, created_at
            FROM clinical.odontogram_snapshots
            WHERE chart_id=:chart_id
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
            {"chart_id": chart_id},
        )
        return OdontogramSnapshot(**row) if row else None


async def _fetch_one(db_config, sql: str, params: dict) -> dict | None:
    engine = create_engine(db_config)
    async with engine.connect() as conn:
        row = (await conn.execute(text(sql), params)).mappings().first()
    await engine.dispose()
    return dict(row) if row else None


async def _fetch_all(db_config, sql: str, params: dict) -> list[dict]:
    engine = create_engine(db_config)
    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql), params)).mappings().all()
    await engine.dispose()
    return [dict(row) for row in rows]


async def _exec(db_config, sql: str, params: dict) -> None:
    engine = create_engine(db_config)
    async with engine.begin() as conn:
        await conn.execute(text(sql), params)
    await engine.dispose()
