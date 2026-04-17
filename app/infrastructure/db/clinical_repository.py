from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text

from app.application.clinical import ClinicalRepository
from app.domain.clinical import ClinicalEncounter, Diagnosis, EncounterNote, ImagingReference, OdontogramSnapshot, PatientChart, TreatmentPlan
from app.domain.events import build_event
from app.infrastructure.db.engine import create_engine
from app.infrastructure.outbox.repository import OutboxRepository


class DbClinicalRepository(ClinicalRepository):
    def __init__(self, db_config) -> None:
        self._db_config = db_config

    async def _append_event_on_conn(self, conn, *, event_name: str, clinic_id: str, entity_type: str, entity_id: str, occurred_at, payload: dict[str, object]) -> None:
        await OutboxRepository(self._db_config).append_on_connection(
            conn,
            build_event(
                event_name=event_name,
                producer_context="clinical.chart",
                clinic_id=clinic_id,
                entity_type=entity_type,
                entity_id=entity_id,
                occurred_at=occurred_at,
                payload=payload,
            ),
        )

    async def open_or_get_chart_with_event(self, *, patient_id: str, clinic_id: str, primary_doctor_id: str | None = None) -> PatientChart:
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                existing = await _fetch_active_chart_on_conn(conn, patient_id=patient_id, clinic_id=clinic_id)
                if existing is not None:
                    return existing
                now = _now()
                chart = PatientChart(
                    chart_id=f"chart_{uuid4().hex[:12]}",
                    patient_id=patient_id,
                    clinic_id=clinic_id,
                    opened_at=now,
                    status="active",
                    primary_doctor_id=primary_doctor_id,
                    created_at=now,
                    updated_at=now,
                )
                await self._upsert_chart_on_conn(conn, chart)
                await self._append_event_on_conn(
                    conn,
                    event_name="chart.opened",
                    clinic_id=clinic_id,
                    entity_type="chart",
                    entity_id=chart.chart_id,
                    occurred_at=chart.opened_at,
                    payload={"patient_id": patient_id},
                )
                return chart
        finally:
            await engine.dispose()

    async def open_or_get_encounter_with_event(self, *, chart_id: str, doctor_id: str, booking_id: str | None = None) -> ClinicalEncounter:
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                existing = await _fetch_open_encounter_on_conn(conn, chart_id=chart_id, doctor_id=doctor_id, booking_id=booking_id)
                if existing is not None:
                    return existing
                row = (
                    await conn.execute(
                        text("SELECT clinic_id FROM clinical.patient_charts WHERE chart_id=:chart_id"),
                        {"chart_id": chart_id},
                    )
                ).mappings().first()
                if row is None:
                    raise ValueError(f"Chart not found: {chart_id}")
                now = _now()
                encounter = ClinicalEncounter(
                    encounter_id=f"enc_{uuid4().hex[:12]}",
                    chart_id=chart_id,
                    booking_id=booking_id,
                    doctor_id=doctor_id,
                    opened_at=now,
                    status="open",
                    created_at=now,
                    updated_at=now,
                )
                await self._upsert_encounter_on_conn(conn, encounter)
                await self._append_event_on_conn(
                    conn,
                    event_name="encounter.created",
                    clinic_id=row["clinic_id"],
                    entity_type="encounter",
                    entity_id=encounter.encounter_id,
                    occurred_at=encounter.opened_at,
                    payload={"chart_id": chart_id, "booking_id": booking_id, "doctor_id": doctor_id},
                )
                return encounter
        finally:
            await engine.dispose()

    async def set_diagnosis_with_event(
        self,
        *,
        chart_id: str,
        diagnosis_text: str,
        encounter_id: str | None = None,
        diagnosis_code: str | None = None,
        is_primary: bool = True,
        recorded_by_actor_id: str | None = None,
    ) -> Diagnosis:
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                chart_row = (
                    await conn.execute(
                        text("SELECT clinic_id FROM clinical.patient_charts WHERE chart_id=:chart_id"),
                        {"chart_id": chart_id},
                    )
                ).mappings().first()
                if chart_row is None:
                    raise ValueError(f"Chart not found: {chart_id}")
                now = _now()
                current = await _fetch_current_primary_diagnosis_on_conn(conn, chart_id=chart_id) if is_primary else None
                if current is not None:
                    superseded = Diagnosis(
                        **{
                            **asdict(current),
                            "is_current": False,
                            "status": "superseded",
                            "superseded_at": now,
                            "updated_at": now,
                        }
                    )
                    await self._upsert_diagnosis_on_conn(conn, superseded)
                diagnosis = Diagnosis(
                    diagnosis_id=f"dx_{uuid4().hex[:12]}",
                    chart_id=chart_id,
                    encounter_id=encounter_id,
                    diagnosis_code=diagnosis_code,
                    diagnosis_text=diagnosis_text,
                    is_primary=is_primary,
                    version_no=(current.version_no + 1) if current else 1,
                    is_current=True,
                    status="active",
                    supersedes_diagnosis_id=current.diagnosis_id if current else None,
                    superseded_at=None,
                    recorded_by_actor_id=recorded_by_actor_id,
                    recorded_at=now,
                    created_at=now,
                    updated_at=now,
                )
                await self._upsert_diagnosis_on_conn(conn, diagnosis)
                await self._append_event_on_conn(
                    conn,
                    event_name="diagnosis.recorded",
                    clinic_id=chart_row["clinic_id"],
                    entity_type="diagnosis",
                    entity_id=diagnosis.diagnosis_id,
                    occurred_at=now,
                    payload={"chart_id": chart_id, "encounter_id": encounter_id, "is_primary": is_primary, "version_no": diagnosis.version_no},
                )
                return diagnosis
        finally:
            await engine.dispose()

    async def set_treatment_plan_with_event(
        self,
        *,
        chart_id: str,
        title: str,
        plan_text: str,
        encounter_id: str | None = None,
        estimated_cost_amount: float | None = None,
        currency_code: str | None = None,
    ) -> TreatmentPlan:
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                chart_row = (
                    await conn.execute(
                        text("SELECT clinic_id FROM clinical.patient_charts WHERE chart_id=:chart_id"),
                        {"chart_id": chart_id},
                    )
                ).mappings().first()
                if chart_row is None:
                    raise ValueError(f"Chart not found: {chart_id}")
                now = _now()
                current = await _fetch_current_treatment_plan_on_conn(conn, chart_id=chart_id)
                if current is not None:
                    superseded = TreatmentPlan(
                        **{
                            **asdict(current),
                            "is_current": False,
                            "status": "superseded",
                            "superseded_at": now,
                            "updated_at": now,
                        }
                    )
                    await self._upsert_treatment_plan_on_conn(conn, superseded)
                plan = TreatmentPlan(
                    treatment_plan_id=f"tp_{uuid4().hex[:12]}",
                    chart_id=chart_id,
                    encounter_id=encounter_id,
                    title=title,
                    plan_text=plan_text,
                    version_no=(current.version_no + 1) if current else 1,
                    is_current=True,
                    status="active",
                    supersedes_treatment_plan_id=current.treatment_plan_id if current else None,
                    superseded_at=None,
                    estimated_cost_amount=estimated_cost_amount,
                    currency_code=currency_code,
                    approved_by_patient_at=None,
                    created_at=now,
                    updated_at=now,
                )
                await self._upsert_treatment_plan_on_conn(conn, plan)
                await self._append_event_on_conn(
                    conn,
                    event_name="treatment_plan.updated" if current else "treatment_plan.created",
                    clinic_id=chart_row["clinic_id"],
                    entity_type="treatment_plan",
                    entity_id=plan.treatment_plan_id,
                    occurred_at=now,
                    payload={"chart_id": chart_id, "encounter_id": encounter_id, "version_no": plan.version_no},
                )
                return plan
        finally:
            await engine.dispose()

    async def attach_imaging_reference_with_event(
        self,
        *,
        chart_id: str,
        imaging_type: str,
        media_asset_id: str | None = None,
        external_url: str | None = None,
        encounter_id: str | None = None,
        description: str | None = None,
        uploaded_by_actor_id: str | None = None,
        is_primary_for_case: bool = False,
    ) -> ImagingReference:
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                chart_row = (
                    await conn.execute(
                        text("SELECT clinic_id FROM clinical.patient_charts WHERE chart_id=:chart_id"),
                        {"chart_id": chart_id},
                    )
                ).mappings().first()
                if chart_row is None:
                    raise ValueError(f"Chart not found: {chart_id}")
                now = _now()
                ref = ImagingReference(
                    imaging_ref_id=f"img_{uuid4().hex[:12]}",
                    chart_id=chart_id,
                    encounter_id=encounter_id,
                    imaging_type=imaging_type,
                    media_asset_id=media_asset_id,
                    external_url=external_url,
                    description=description,
                    taken_at=None,
                    uploaded_at=now,
                    uploaded_by_actor_id=uploaded_by_actor_id,
                    is_primary_for_case=is_primary_for_case,
                    created_at=now,
                    updated_at=now,
                )
                await self._upsert_imaging_reference_on_conn(conn, ref)
                await self._append_event_on_conn(
                    conn,
                    event_name="imaging_reference.added",
                    clinic_id=chart_row["clinic_id"],
                    entity_type="imaging_reference",
                    entity_id=ref.imaging_ref_id,
                    occurred_at=now,
                    payload={"chart_id": chart_id, "encounter_id": encounter_id, "imaging_type": imaging_type},
                )
                return ref
        finally:
            await engine.dispose()

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

    async def _upsert_chart_on_conn(self, conn, item: PatientChart) -> None:
        await conn.execute(
            text(
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
                """
            ),
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

    async def _upsert_encounter_on_conn(self, conn, item: ClinicalEncounter) -> None:
        await conn.execute(
            text(
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
                """
            ),
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

    async def list_chart_notes(self, *, chart_id: str) -> list[EncounterNote]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT n.encounter_note_id, n.encounter_id, n.note_type, n.note_text, n.recorded_by_actor_id, n.recorded_at, n.created_at, n.updated_at
            FROM clinical.encounter_notes n
            JOIN clinical.clinical_encounters e ON e.encounter_id = n.encounter_id
            WHERE e.chart_id=:chart_id
            ORDER BY n.recorded_at ASC
            """,
            {"chart_id": chart_id},
        )
        return [EncounterNote(**row) for row in rows]

    async def get_current_primary_diagnosis(self, *, chart_id: str) -> Diagnosis | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT diagnosis_id, chart_id, encounter_id, diagnosis_code, diagnosis_text, is_primary, version_no, is_current, status,
                   supersedes_diagnosis_id, superseded_at, recorded_by_actor_id, recorded_at, created_at, updated_at
            FROM clinical.diagnoses
            WHERE chart_id=:chart_id
              AND is_primary=TRUE
              AND is_current=TRUE
            LIMIT 1
            """,
            {"chart_id": chart_id},
        )
        return Diagnosis(**row) if row else None

    async def upsert_diagnosis(self, item: Diagnosis) -> None:
        await _exec(
            self._db_config,
            """
            INSERT INTO clinical.diagnoses (
              diagnosis_id, chart_id, encounter_id, diagnosis_code, diagnosis_text, is_primary, version_no, is_current, status,
              supersedes_diagnosis_id, superseded_at, recorded_by_actor_id, recorded_at, created_at, updated_at
            ) VALUES (
              :diagnosis_id, :chart_id, :encounter_id, :diagnosis_code, :diagnosis_text, :is_primary, :version_no, :is_current, :status,
              :supersedes_diagnosis_id, :superseded_at, :recorded_by_actor_id, :recorded_at, :created_at, :updated_at
            )
            ON CONFLICT (diagnosis_id) DO UPDATE SET
              diagnosis_code=EXCLUDED.diagnosis_code,
              diagnosis_text=EXCLUDED.diagnosis_text,
              is_primary=EXCLUDED.is_primary,
              version_no=EXCLUDED.version_no,
              is_current=EXCLUDED.is_current,
              status=EXCLUDED.status,
              supersedes_diagnosis_id=EXCLUDED.supersedes_diagnosis_id,
              superseded_at=EXCLUDED.superseded_at,
              updated_at=EXCLUDED.updated_at
            """,
            asdict(item),
        )

    async def _upsert_diagnosis_on_conn(self, conn, item: Diagnosis) -> None:
        await conn.execute(
            text(
                """
                INSERT INTO clinical.diagnoses (
                  diagnosis_id, chart_id, encounter_id, diagnosis_code, diagnosis_text, is_primary, version_no, is_current, status,
                  supersedes_diagnosis_id, superseded_at, recorded_by_actor_id, recorded_at, created_at, updated_at
                ) VALUES (
                  :diagnosis_id, :chart_id, :encounter_id, :diagnosis_code, :diagnosis_text, :is_primary, :version_no, :is_current, :status,
                  :supersedes_diagnosis_id, :superseded_at, :recorded_by_actor_id, :recorded_at, :created_at, :updated_at
                )
                ON CONFLICT (diagnosis_id) DO UPDATE SET
                  diagnosis_code=EXCLUDED.diagnosis_code,
                  diagnosis_text=EXCLUDED.diagnosis_text,
                  is_primary=EXCLUDED.is_primary,
                  version_no=EXCLUDED.version_no,
                  is_current=EXCLUDED.is_current,
                  status=EXCLUDED.status,
                  supersedes_diagnosis_id=EXCLUDED.supersedes_diagnosis_id,
                  superseded_at=EXCLUDED.superseded_at,
                  updated_at=EXCLUDED.updated_at
                """
            ),
            asdict(item),
        )

    async def list_chart_diagnoses(self, *, chart_id: str) -> list[Diagnosis]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT diagnosis_id, chart_id, encounter_id, diagnosis_code, diagnosis_text, is_primary, version_no, is_current, status,
                   supersedes_diagnosis_id, superseded_at, recorded_by_actor_id, recorded_at, created_at, updated_at
            FROM clinical.diagnoses
            WHERE chart_id=:chart_id
            ORDER BY recorded_at ASC
            """,
            {"chart_id": chart_id},
        )
        return [Diagnosis(**row) for row in rows]

    async def get_current_treatment_plan(self, *, chart_id: str) -> TreatmentPlan | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT treatment_plan_id, chart_id, encounter_id, title, plan_text, version_no, is_current, status,
                   supersedes_treatment_plan_id, superseded_at,
                   estimated_cost_amount, currency_code, approved_by_patient_at, created_at, updated_at
            FROM clinical.treatment_plans
            WHERE chart_id=:chart_id
              AND is_current=TRUE
            LIMIT 1
            """,
            {"chart_id": chart_id},
        )
        return TreatmentPlan(**row) if row else None

    async def upsert_treatment_plan(self, item: TreatmentPlan) -> None:
        await _exec(
            self._db_config,
            """
            INSERT INTO clinical.treatment_plans (
              treatment_plan_id, chart_id, encounter_id, title, plan_text, version_no, is_current, status,
              supersedes_treatment_plan_id, superseded_at, estimated_cost_amount, currency_code, approved_by_patient_at, created_at, updated_at
            ) VALUES (
              :treatment_plan_id, :chart_id, :encounter_id, :title, :plan_text, :version_no, :is_current, :status,
              :supersedes_treatment_plan_id, :superseded_at, :estimated_cost_amount, :currency_code, :approved_by_patient_at, :created_at, :updated_at
            )
            ON CONFLICT (treatment_plan_id) DO UPDATE SET
              title=EXCLUDED.title,
              plan_text=EXCLUDED.plan_text,
              version_no=EXCLUDED.version_no,
              is_current=EXCLUDED.is_current,
              status=EXCLUDED.status,
              supersedes_treatment_plan_id=EXCLUDED.supersedes_treatment_plan_id,
              superseded_at=EXCLUDED.superseded_at,
              estimated_cost_amount=EXCLUDED.estimated_cost_amount,
              currency_code=EXCLUDED.currency_code,
              approved_by_patient_at=EXCLUDED.approved_by_patient_at,
              updated_at=EXCLUDED.updated_at
            """,
            asdict(item),
        )

    async def _upsert_treatment_plan_on_conn(self, conn, item: TreatmentPlan) -> None:
        await conn.execute(
            text(
                """
                INSERT INTO clinical.treatment_plans (
                  treatment_plan_id, chart_id, encounter_id, title, plan_text, version_no, is_current, status,
                  supersedes_treatment_plan_id, superseded_at, estimated_cost_amount, currency_code, approved_by_patient_at, created_at, updated_at
                ) VALUES (
                  :treatment_plan_id, :chart_id, :encounter_id, :title, :plan_text, :version_no, :is_current, :status,
                  :supersedes_treatment_plan_id, :superseded_at, :estimated_cost_amount, :currency_code, :approved_by_patient_at, :created_at, :updated_at
                )
                ON CONFLICT (treatment_plan_id) DO UPDATE SET
                  title=EXCLUDED.title,
                  plan_text=EXCLUDED.plan_text,
                  version_no=EXCLUDED.version_no,
                  is_current=EXCLUDED.is_current,
                  status=EXCLUDED.status,
                  supersedes_treatment_plan_id=EXCLUDED.supersedes_treatment_plan_id,
                  superseded_at=EXCLUDED.superseded_at,
                  estimated_cost_amount=EXCLUDED.estimated_cost_amount,
                  currency_code=EXCLUDED.currency_code,
                  approved_by_patient_at=EXCLUDED.approved_by_patient_at,
                  updated_at=EXCLUDED.updated_at
                """
            ),
            asdict(item),
        )

    async def list_chart_treatment_plans(self, *, chart_id: str) -> list[TreatmentPlan]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT treatment_plan_id, chart_id, encounter_id, title, plan_text, version_no, is_current, status,
                   supersedes_treatment_plan_id, superseded_at,
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

    async def _upsert_imaging_reference_on_conn(self, conn, item: ImagingReference) -> None:
        await conn.execute(
            text(
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
                """
            ),
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


def _now():
    return datetime.now(timezone.utc)


async def _fetch_active_chart_on_conn(conn, *, patient_id: str, clinic_id: str) -> PatientChart | None:
    row = (
        await conn.execute(
            text(
                """
                SELECT chart_id, patient_id, clinic_id, chart_number, opened_at, status, primary_doctor_id, notes_summary, created_at, updated_at
                FROM clinical.patient_charts
                WHERE patient_id=:patient_id AND clinic_id=:clinic_id AND status='active'
                ORDER BY opened_at DESC
                LIMIT 1
                """
            ),
            {"patient_id": patient_id, "clinic_id": clinic_id},
        )
    ).mappings().first()
    return PatientChart(**dict(row)) if row else None


async def _fetch_open_encounter_on_conn(conn, *, chart_id: str, doctor_id: str, booking_id: str | None) -> ClinicalEncounter | None:
    row = (
        await conn.execute(
            text(
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
                """
            ),
            {"chart_id": chart_id, "doctor_id": doctor_id, "booking_id": booking_id},
        )
    ).mappings().first()
    return ClinicalEncounter(**dict(row)) if row else None


async def _fetch_current_primary_diagnosis_on_conn(conn, *, chart_id: str) -> Diagnosis | None:
    row = (
        await conn.execute(
            text(
                """
                SELECT diagnosis_id, chart_id, encounter_id, diagnosis_code, diagnosis_text, is_primary, version_no, is_current, status,
                       supersedes_diagnosis_id, superseded_at, recorded_by_actor_id, recorded_at, created_at, updated_at
                FROM clinical.diagnoses
                WHERE chart_id=:chart_id
                  AND is_primary=TRUE
                  AND is_current=TRUE
                LIMIT 1
                """
            ),
            {"chart_id": chart_id},
        )
    ).mappings().first()
    return Diagnosis(**dict(row)) if row else None


async def _fetch_current_treatment_plan_on_conn(conn, *, chart_id: str) -> TreatmentPlan | None:
    row = (
        await conn.execute(
            text(
                """
                SELECT treatment_plan_id, chart_id, encounter_id, title, plan_text, version_no, is_current, status,
                       supersedes_treatment_plan_id, superseded_at,
                       estimated_cost_amount, currency_code, approved_by_patient_at, created_at, updated_at
                FROM clinical.treatment_plans
                WHERE chart_id=:chart_id
                  AND is_current=TRUE
                LIMIT 1
                """
            ),
            {"chart_id": chart_id},
        )
    ).mappings().first()
    return TreatmentPlan(**dict(row)) if row else None
