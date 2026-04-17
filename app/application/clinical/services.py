from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from app.domain.clinical import ClinicalEncounter, Diagnosis, EncounterNote, ImagingReference, OdontogramSnapshot, PatientChart, TreatmentPlan


@dataclass(frozen=True)
class ChartSummary:
    chart: PatientChart
    latest_diagnosis: Diagnosis | None
    latest_treatment_plan: TreatmentPlan | None
    latest_note: EncounterNote | None
    note_count: int
    imaging_count: int
    updated_at: datetime


class ClinicalRepository(Protocol):
    async def get_active_chart(self, *, patient_id: str, clinic_id: str) -> PatientChart | None: ...
    async def upsert_chart(self, item: PatientChart) -> None: ...
    async def get_chart(self, chart_id: str) -> PatientChart | None: ...
    async def get_open_encounter(self, *, chart_id: str, doctor_id: str, booking_id: str | None) -> ClinicalEncounter | None: ...
    async def get_encounter(self, encounter_id: str) -> ClinicalEncounter | None: ...
    async def upsert_encounter(self, item: ClinicalEncounter) -> None: ...
    async def add_encounter_note(self, item: EncounterNote) -> None: ...
    async def list_encounter_notes(self, *, encounter_id: str) -> list[EncounterNote]: ...
    async def upsert_diagnosis(self, item: Diagnosis) -> None: ...
    async def list_chart_diagnoses(self, *, chart_id: str) -> list[Diagnosis]: ...
    async def upsert_treatment_plan(self, item: TreatmentPlan) -> None: ...
    async def list_chart_treatment_plans(self, *, chart_id: str) -> list[TreatmentPlan]: ...
    async def upsert_imaging_reference(self, item: ImagingReference) -> None: ...
    async def list_imaging_references(self, *, chart_id: str) -> list[ImagingReference]: ...
    async def add_odontogram_snapshot(self, item: OdontogramSnapshot) -> None: ...
    async def get_latest_odontogram_snapshot(self, *, chart_id: str) -> OdontogramSnapshot | None: ...


@dataclass(slots=True)
class ClinicalChartService:
    repository: ClinicalRepository

    async def open_or_get_chart(self, *, patient_id: str, clinic_id: str, primary_doctor_id: str | None = None) -> PatientChart:
        existing = await self.repository.get_active_chart(patient_id=patient_id, clinic_id=clinic_id)
        if existing:
            return existing
        now = datetime.now(timezone.utc)
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
        await self.repository.upsert_chart(chart)
        return chart

    async def load_chart_summary(self, *, chart_id: str) -> ChartSummary | None:
        chart = await self.repository.get_chart(chart_id)
        if chart is None:
            return None
        diagnoses = await self.repository.list_chart_diagnoses(chart_id=chart_id)
        plans = await self.repository.list_chart_treatment_plans(chart_id=chart_id)
        imaging = await self.repository.list_imaging_references(chart_id=chart_id)
        latest_note = None
        note_count = 0
        encounter = await self.repository.get_open_encounter(chart_id=chart_id, doctor_id="", booking_id=None)
        if encounter:
            notes = await self.repository.list_encounter_notes(encounter_id=encounter.encounter_id)
            note_count = len(notes)
            latest_note = notes[-1] if notes else None
        timestamps = [chart.updated_at]
        if diagnoses:
            timestamps.append(diagnoses[-1].updated_at)
        if plans:
            timestamps.append(plans[-1].updated_at)
        if latest_note:
            timestamps.append(latest_note.updated_at)
        if imaging:
            timestamps.append(imaging[-1].updated_at)
        return ChartSummary(
            chart=chart,
            latest_diagnosis=diagnoses[-1] if diagnoses else None,
            latest_treatment_plan=plans[-1] if plans else None,
            latest_note=latest_note,
            note_count=note_count,
            imaging_count=len(imaging),
            updated_at=max(timestamps),
        )

    async def open_or_get_encounter(self, *, chart_id: str, doctor_id: str, booking_id: str | None = None) -> ClinicalEncounter:
        existing = await self.repository.get_open_encounter(chart_id=chart_id, doctor_id=doctor_id, booking_id=booking_id)
        if existing:
            return existing
        now = datetime.now(timezone.utc)
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
        await self.repository.upsert_encounter(encounter)
        return encounter

    async def close_encounter(self, encounter_id: str) -> ClinicalEncounter | None:
        encounter = await self.repository.get_encounter(encounter_id)
        if encounter is None:
            return None
        now = datetime.now(timezone.utc)
        updated = ClinicalEncounter(**{**asdict(encounter), "status": "closed", "closed_at": now, "updated_at": now})
        await self.repository.upsert_encounter(updated)
        return updated

    async def add_encounter_note(self, *, encounter_id: str, note_type: str, note_text: str, recorded_by_actor_id: str | None = None) -> EncounterNote:
        now = datetime.now(timezone.utc)
        note = EncounterNote(
            encounter_note_id=f"enote_{uuid4().hex[:12]}",
            encounter_id=encounter_id,
            note_type=note_type,
            note_text=note_text,
            recorded_by_actor_id=recorded_by_actor_id,
            recorded_at=now,
            created_at=now,
            updated_at=now,
        )
        await self.repository.add_encounter_note(note)
        return note

    async def set_diagnosis(self, *, chart_id: str, diagnosis_text: str, encounter_id: str | None = None, diagnosis_code: str | None = None, is_primary: bool = True, recorded_by_actor_id: str | None = None) -> Diagnosis:
        now = datetime.now(timezone.utc)
        diagnosis = Diagnosis(
            diagnosis_id=f"dx_{uuid4().hex[:12]}",
            chart_id=chart_id,
            encounter_id=encounter_id,
            diagnosis_code=diagnosis_code,
            diagnosis_text=diagnosis_text,
            is_primary=is_primary,
            status="active",
            recorded_by_actor_id=recorded_by_actor_id,
            recorded_at=now,
            created_at=now,
            updated_at=now,
        )
        await self.repository.upsert_diagnosis(diagnosis)
        return diagnosis

    async def set_treatment_plan(self, *, chart_id: str, title: str, plan_text: str, encounter_id: str | None = None, estimated_cost_amount: float | None = None, currency_code: str | None = None) -> TreatmentPlan:
        now = datetime.now(timezone.utc)
        plan = TreatmentPlan(
            treatment_plan_id=f"tp_{uuid4().hex[:12]}",
            chart_id=chart_id,
            encounter_id=encounter_id,
            title=title,
            plan_text=plan_text,
            status="active",
            estimated_cost_amount=estimated_cost_amount,
            currency_code=currency_code,
            approved_by_patient_at=None,
            created_at=now,
            updated_at=now,
        )
        await self.repository.upsert_treatment_plan(plan)
        return plan

    async def attach_imaging_reference(self, *, chart_id: str, imaging_type: str, media_asset_id: str | None = None, external_url: str | None = None, encounter_id: str | None = None, description: str | None = None, uploaded_by_actor_id: str | None = None, is_primary_for_case: bool = False) -> ImagingReference:
        if not media_asset_id and not external_url:
            raise ValueError("Either media_asset_id or external_url must be provided")
        if external_url and not (external_url.startswith("http://") or external_url.startswith("https://")):
            raise ValueError("External imaging URL must start with http:// or https://")
        now = datetime.now(timezone.utc)
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
        await self.repository.upsert_imaging_reference(ref)
        return ref

    async def save_odontogram_snapshot(self, *, chart_id: str, snapshot_payload_json: dict[str, object], encounter_id: str | None = None, recorded_by_actor_id: str | None = None) -> OdontogramSnapshot:
        now = datetime.now(timezone.utc)
        item = OdontogramSnapshot(
            odontogram_snapshot_id=f"odg_{uuid4().hex[:12]}",
            chart_id=chart_id,
            encounter_id=encounter_id,
            snapshot_payload_json=snapshot_payload_json,
            recorded_at=now,
            recorded_by_actor_id=recorded_by_actor_id,
            created_at=now,
        )
        await self.repository.add_odontogram_snapshot(item)
        return item

    async def load_latest_odontogram_snapshot(self, *, chart_id: str) -> OdontogramSnapshot | None:
        return await self.repository.get_latest_odontogram_snapshot(chart_id=chart_id)
