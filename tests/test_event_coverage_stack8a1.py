from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone

from app.application.clinical import ClinicalChartService
from app.domain.clinical import ClinicalEncounter, Diagnosis, ImagingReference, PatientChart, TreatmentPlan
from app.domain.communication import ReminderJob
from app.infrastructure.db.communication_repository import DbReminderJobRepository


class _EventedClinicalRepo:
    def __init__(self) -> None:
        self.charts: dict[str, PatientChart] = {}
        self.encounters: dict[str, ClinicalEncounter] = {}
        self.diagnoses: dict[str, Diagnosis] = {}
        self.plans: dict[str, TreatmentPlan] = {}
        self.imaging: dict[str, ImagingReference] = {}
        self.events: list[dict[str, object]] = []
        self.transactions: list[dict[str, object]] = []
        self._tx_seq = 0

    def _start_tx(self, mutation: str) -> int:
        self._tx_seq += 1
        self.transactions.append({"tx": self._tx_seq, "mutation": mutation, "event": None})
        return self._tx_seq

    def _record_event(self, *, tx: int, event_name: str, payload: dict[str, object]) -> None:
        self.events.append({"tx": tx, "event_name": event_name, "payload": payload})
        self.transactions[-1]["event"] = event_name

    async def get_active_chart(self, *, patient_id: str, clinic_id: str):
        for chart in self.charts.values():
            if chart.patient_id == patient_id and chart.clinic_id == clinic_id and chart.status == "active":
                return chart
        return None

    async def open_or_get_chart_with_event(self, *, patient_id: str, clinic_id: str, primary_doctor_id: str | None = None) -> PatientChart:
        existing = await self.get_active_chart(patient_id=patient_id, clinic_id=clinic_id)
        if existing is not None:
            return existing
        tx = self._start_tx("chart")
        now = datetime.now(timezone.utc)
        chart = PatientChart(
            chart_id=f"chart_{len(self.charts) + 1}",
            patient_id=patient_id,
            clinic_id=clinic_id,
            opened_at=now,
            status="active",
            primary_doctor_id=primary_doctor_id,
            created_at=now,
            updated_at=now,
        )
        self.charts[chart.chart_id] = chart
        self._record_event(tx=tx, event_name="chart.opened", payload={"patient_id": patient_id})
        return chart

    async def upsert_chart(self, item: PatientChart) -> None:
        self.charts[item.chart_id] = item

    async def get_chart(self, chart_id: str):
        return self.charts.get(chart_id)

    async def get_open_encounter(self, *, chart_id: str, doctor_id: str, booking_id: str | None):
        rows = [e for e in self.encounters.values() if e.chart_id == chart_id and e.status == "open"]
        rows = [e for e in rows if e.doctor_id == doctor_id]
        if booking_id is not None:
            rows = [e for e in rows if e.booking_id == booking_id]
        rows.sort(key=lambda x: x.opened_at)
        return rows[-1] if rows else None

    async def open_or_get_encounter_with_event(self, *, chart_id: str, doctor_id: str, booking_id: str | None = None) -> ClinicalEncounter:
        existing = await self.get_open_encounter(chart_id=chart_id, doctor_id=doctor_id, booking_id=booking_id)
        if existing is not None:
            return existing
        tx = self._start_tx("encounter")
        now = datetime.now(timezone.utc)
        encounter = ClinicalEncounter(
            encounter_id=f"enc_{len(self.encounters) + 1}",
            chart_id=chart_id,
            booking_id=booking_id,
            doctor_id=doctor_id,
            opened_at=now,
            status="open",
            created_at=now,
            updated_at=now,
        )
        self.encounters[encounter.encounter_id] = encounter
        self._record_event(tx=tx, event_name="encounter.created", payload={"chart_id": chart_id})
        return encounter

    async def get_encounter(self, encounter_id: str):
        return self.encounters.get(encounter_id)

    async def upsert_encounter(self, item: ClinicalEncounter) -> None:
        self.encounters[item.encounter_id] = item

    async def add_encounter_note(self, item):
        return None

    async def list_encounter_notes(self, *, encounter_id: str):
        return []

    async def list_chart_notes(self, *, chart_id: str):
        return []

    async def get_current_primary_diagnosis(self, *, chart_id: str):
        rows = [d for d in self.diagnoses.values() if d.chart_id == chart_id and d.is_primary and d.is_current]
        rows.sort(key=lambda x: x.version_no)
        return rows[-1] if rows else None

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
        tx = self._start_tx("diagnosis")
        now = datetime.now(timezone.utc)
        current = await self.get_current_primary_diagnosis(chart_id=chart_id) if is_primary else None
        if current is not None:
            self.diagnoses[current.diagnosis_id] = Diagnosis(**{**asdict(current), "is_current": False, "status": "superseded", "superseded_at": now, "updated_at": now})
        diagnosis = Diagnosis(
            diagnosis_id=f"dx_{len(self.diagnoses) + 1}",
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
        self.diagnoses[diagnosis.diagnosis_id] = diagnosis
        self._record_event(tx=tx, event_name="diagnosis.recorded", payload={"chart_id": chart_id, "version_no": diagnosis.version_no})
        return diagnosis

    async def upsert_diagnosis(self, item: Diagnosis) -> None:
        self.diagnoses[item.diagnosis_id] = item

    async def list_chart_diagnoses(self, *, chart_id: str):
        return []

    async def get_current_treatment_plan(self, *, chart_id: str):
        rows = [p for p in self.plans.values() if p.chart_id == chart_id and p.is_current]
        rows.sort(key=lambda x: x.version_no)
        return rows[-1] if rows else None

    async def set_treatment_plan_with_event(self, *, chart_id: str, title: str, plan_text: str, encounter_id: str | None = None, estimated_cost_amount: float | None = None, currency_code: str | None = None) -> TreatmentPlan:
        tx = self._start_tx("treatment_plan")
        now = datetime.now(timezone.utc)
        current = await self.get_current_treatment_plan(chart_id=chart_id)
        if current is not None:
            self.plans[current.treatment_plan_id] = TreatmentPlan(**{**asdict(current), "is_current": False, "status": "superseded", "superseded_at": now, "updated_at": now})
        plan = TreatmentPlan(
            treatment_plan_id=f"tp_{len(self.plans) + 1}",
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
        self.plans[plan.treatment_plan_id] = plan
        self._record_event(tx=tx, event_name="treatment_plan.updated" if current else "treatment_plan.created", payload={"chart_id": chart_id, "version_no": plan.version_no})
        return plan

    async def upsert_treatment_plan(self, item: TreatmentPlan) -> None:
        self.plans[item.treatment_plan_id] = item

    async def list_chart_treatment_plans(self, *, chart_id: str):
        return []

    async def attach_imaging_reference_with_event(self, *, chart_id: str, imaging_type: str, media_asset_id: str | None = None, external_url: str | None = None, encounter_id: str | None = None, description: str | None = None, uploaded_by_actor_id: str | None = None, is_primary_for_case: bool = False) -> ImagingReference:
        tx = self._start_tx("imaging")
        now = datetime.now(timezone.utc)
        ref = ImagingReference(
            imaging_ref_id=f"img_{len(self.imaging) + 1}",
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
        self.imaging[ref.imaging_ref_id] = ref
        self._record_event(tx=tx, event_name="imaging_reference.added", payload={"chart_id": chart_id, "imaging_type": imaging_type})
        return ref

    async def upsert_imaging_reference(self, item: ImagingReference) -> None:
        self.imaging[item.imaging_ref_id] = item

    async def list_imaging_references(self, *, chart_id: str):
        return []

    async def add_odontogram_snapshot(self, item):
        return None

    async def get_latest_odontogram_snapshot(self, *, chart_id: str):
        return None


def test_clinical_event_coverage_and_no_duplicate_chart_opened() -> None:
    repo = _EventedClinicalRepo()
    service = ClinicalChartService(repository=repo)

    chart_first = asyncio.run(service.open_or_get_chart(patient_id="p1", clinic_id="c1", primary_doctor_id="d1"))
    chart_second = asyncio.run(service.open_or_get_chart(patient_id="p1", clinic_id="c1", primary_doctor_id="d1"))
    encounter = asyncio.run(service.open_or_get_encounter(chart_id=chart_first.chart_id, doctor_id="d1", booking_id="b1"))
    diagnosis = asyncio.run(service.set_diagnosis(chart_id=chart_first.chart_id, diagnosis_text="Caries", encounter_id=encounter.encounter_id))
    plan_1 = asyncio.run(service.set_treatment_plan(chart_id=chart_first.chart_id, title="Plan A", plan_text="Initial"))
    plan_2 = asyncio.run(service.set_treatment_plan(chart_id=chart_first.chart_id, title="Plan B", plan_text="Updated"))
    _ = asyncio.run(service.attach_imaging_reference(chart_id=chart_first.chart_id, imaging_type="xray", external_url="https://example.com/xray"))

    assert chart_first.chart_id == chart_second.chart_id
    emitted = [row["event_name"] for row in repo.events]
    assert emitted.count("chart.opened") == 1
    assert "encounter.created" in emitted
    assert "diagnosis.recorded" in emitted
    assert "treatment_plan.created" in emitted
    assert "treatment_plan.updated" in emitted
    assert "imaging_reference.added" in emitted
    assert diagnosis.version_no == 1
    assert plan_1.version_no == 1
    assert plan_2.version_no == 2

    for tx in repo.transactions:
        assert tx["event"] is not None


class _FakeResult:
    def __init__(self, row: dict[str, object] | None) -> None:
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _FakeConn:
    def __init__(self, row: dict[str, object] | None) -> None:
        self.row = row
        self.updated = False

    async def execute(self, *_args, **_kwargs):
        self.updated = True
        return _FakeResult(self.row)


class _FakeBegin:
    def __init__(self, conn: _FakeConn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, conn: _FakeConn) -> None:
        self.conn = conn

    def begin(self):
        return _FakeBegin(self.conn)

    async def dispose(self):
        return None


class _OutboxSpy:
    calls: list[tuple[object, object]] = []

    def __init__(self, _db_config) -> None:
        return None

    async def append_on_connection(self, conn, event):
        self.calls.append((conn, event))
        return 1


def _reminder_row(status: str) -> dict[str, object]:
    return {
        "reminder_id": "r1",
        "clinic_id": "c1",
        "booking_id": "b1",
        "reminder_type": "booking_previsit",
        "status": status,
    }


def test_mark_sent_and_failed_emit_delivery_events_transactionally(monkeypatch) -> None:
    import app.infrastructure.db.communication_repository as mod

    sent_conn = _FakeConn(_reminder_row("sent"))
    failed_conn = _FakeConn(_reminder_row("failed"))
    engines = [_FakeEngine(sent_conn), _FakeEngine(failed_conn)]

    def _fake_engine(_):
        return engines.pop(0)

    _OutboxSpy.calls.clear()
    monkeypatch.setattr(mod, "create_engine", _fake_engine)
    monkeypatch.setattr(mod, "OutboxRepository", _OutboxSpy)

    repo = DbReminderJobRepository(db_config=object())
    now = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)

    sent = asyncio.run(repo.mark_reminder_sent(reminder_id="r1", sent_at=now))
    failed = asyncio.run(repo.mark_reminder_failed(reminder_id="r1", failed_at=now, error_text="provider_timeout"))

    assert sent is True
    assert failed is True
    assert len(_OutboxSpy.calls) == 2
    assert _OutboxSpy.calls[0][0] is sent_conn
    assert _OutboxSpy.calls[1][0] is failed_conn
    assert _OutboxSpy.calls[0][1].event_name == "reminder.sent"
    assert _OutboxSpy.calls[1][1].event_name == "reminder.failed"
    assert _OutboxSpy.calls[1][1].payload["error_code"] == "provider_timeout"
    assert sent_conn.updated is True and failed_conn.updated is True
