import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.application.clinical import ClinicalChartService
from app.application.doctor.operations import DoctorOperationsService
from app.application.access import AccessResolver, InMemoryAccessRepository
from app.application.booking import BookingOrchestrationService, BookingService, BookingStateService
from app.application.booking.orchestration_outcomes import InvalidStateOutcome
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.application.doctor.patient_read import DoctorPatientSnapshot
from app.domain.access_identity.models import ActorIdentity, ActorStatus, ActorType, ClinicRoleAssignment, DoctorProfile, RoleCode, StaffMember, StaffStatus, TelegramBinding
from app.domain.booking import Booking
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, RecordStatus, Service
from app.domain.clinical import ClinicalEncounter, Diagnosis, EncounterNote, ImagingReference, OdontogramSnapshot, PatientChart, TreatmentPlan


class _ClinicalRepo:
    def __init__(self):
        self.charts = {}
        self.encounters = {}
        self.notes = {}
        self.diagnoses = {}
        self.plans = {}
        self.imaging = {}
        self.odont = {}

    async def get_active_chart(self, *, patient_id: str, clinic_id: str):
        for c in self.charts.values():
            if c.patient_id == patient_id and c.clinic_id == clinic_id and c.status == "active":
                return c
        return None

    async def upsert_chart(self, item: PatientChart) -> None:
        self.charts[item.chart_id] = item

    async def get_chart(self, chart_id: str):
        return self.charts.get(chart_id)

    async def get_open_encounter(self, *, chart_id: str, doctor_id: str, booking_id: str | None):
        rows = [e for e in self.encounters.values() if e.chart_id == chart_id and e.status == "open"]
        if doctor_id:
            rows = [e for e in rows if e.doctor_id == doctor_id]
        if booking_id is not None:
            rows = [e for e in rows if e.booking_id == booking_id]
        rows.sort(key=lambda x: x.opened_at)
        return rows[-1] if rows else None

    async def get_encounter(self, encounter_id: str):
        return self.encounters.get(encounter_id)

    async def upsert_encounter(self, item: ClinicalEncounter) -> None:
        self.encounters[item.encounter_id] = item

    async def add_encounter_note(self, item: EncounterNote) -> None:
        self.notes[item.encounter_note_id] = item

    async def list_encounter_notes(self, *, encounter_id: str):
        return sorted([n for n in self.notes.values() if n.encounter_id == encounter_id], key=lambda x: x.recorded_at)

    async def list_chart_notes(self, *, chart_id: str):
        encounter_ids = {e.encounter_id for e in self.encounters.values() if e.chart_id == chart_id}
        return sorted([n for n in self.notes.values() if n.encounter_id in encounter_ids], key=lambda x: x.recorded_at)

    async def get_current_primary_diagnosis(self, *, chart_id: str):
        rows = [d for d in self.diagnoses.values() if d.chart_id == chart_id and d.is_primary and d.is_current]
        rows.sort(key=lambda x: x.version_no)
        return rows[-1] if rows else None

    async def upsert_diagnosis(self, item: Diagnosis) -> None:
        self.diagnoses[item.diagnosis_id] = item

    async def list_chart_diagnoses(self, *, chart_id: str):
        return sorted([d for d in self.diagnoses.values() if d.chart_id == chart_id], key=lambda x: x.recorded_at)

    async def upsert_treatment_plan(self, item: TreatmentPlan) -> None:
        self.plans[item.treatment_plan_id] = item

    async def get_current_treatment_plan(self, *, chart_id: str):
        rows = [p for p in self.plans.values() if p.chart_id == chart_id and p.is_current]
        rows.sort(key=lambda x: x.version_no)
        return rows[-1] if rows else None

    async def list_chart_treatment_plans(self, *, chart_id: str):
        return sorted([p for p in self.plans.values() if p.chart_id == chart_id], key=lambda x: x.created_at)

    async def upsert_imaging_reference(self, item: ImagingReference) -> None:
        self.imaging[item.imaging_ref_id] = item

    async def list_imaging_references(self, *, chart_id: str):
        return sorted([i for i in self.imaging.values() if i.chart_id == chart_id], key=lambda x: x.uploaded_at)

    async def add_odontogram_snapshot(self, item: OdontogramSnapshot) -> None:
        self.odont[item.odontogram_snapshot_id] = item

    async def get_latest_odontogram_snapshot(self, *, chart_id: str):
        rows = [o for o in self.odont.values() if o.chart_id == chart_id]
        rows.sort(key=lambda x: x.recorded_at)
        return rows[-1] if rows else None


class _BookingRepo:
    def __init__(self, booking):
        self.booking = booking

    async def get_booking(self, booking_id):
        return self.booking if self.booking and self.booking.booking_id == booking_id else None

    async def list_bookings_by_patient(self, *, patient_id):
        if self.booking and self.booking.patient_id == patient_id:
            return [self.booking]
        return []

    async def list_bookings_by_doctor_time_window(self, *, doctor_id, start_at, end_at):
        if self.booking and self.booking.doctor_id == doctor_id and start_at <= self.booking.scheduled_start_at < end_at:
            return [self.booking]
        return []


class _Reader:
    async def read_snapshot(self, *, patient_id: str):
        return DoctorPatientSnapshot(patient_id=patient_id, display_name="P", patient_number="N1", phone_raw="12345", has_photo=False, active_flags_summary=None)


def _ops() -> DoctorOperationsService:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)
    booking = Booking(
        booking_id="b1",
        clinic_id="c1",
        patient_id="p1",
        doctor_id="d1",
        service_id="s1",
        booking_mode="manual",
        source_channel="admin",
        scheduled_start_at=now,
        scheduled_end_at=now + timedelta(minutes=30),
        status="confirmed",
        confirmation_required=False,
        created_at=now,
        updated_at=now,
    )
    access_repo = InMemoryAccessRepository()
    access_repo.upsert_actor_identity(ActorIdentity(actor_id="a1", actor_type=ActorType.STAFF, display_name="D", status=ActorStatus.ACTIVE, locale="en"))
    access_repo.upsert_telegram_binding(TelegramBinding(telegram_binding_id="t1", actor_id="a1", telegram_user_id=1, telegram_username=None, first_seen_at=None, last_seen_at=None, is_primary=True, is_active=True))
    access_repo.upsert_staff_member(StaffMember(staff_id="s1", actor_id="a1", clinic_id="c1", full_name="Doc", display_name="Doc", staff_status=StaffStatus.ACTIVE))
    access_repo.upsert_role_assignment(ClinicRoleAssignment(role_assignment_id="r1", staff_id="s1", clinic_id="c1", role_code=RoleCode.DOCTOR, branch_id=None, scope_type="clinic", scope_ref=None, granted_by_actor_id=None, granted_at=now, revoked_at=None, is_active=True))
    access_repo.upsert_doctor_profile(DoctorProfile(doctor_profile_id="dp1", doctor_id="d1", staff_id="s1", clinic_id="c1"))

    ref_repo = InMemoryClinicReferenceRepository()
    ref_repo.upsert_clinic(Clinic(clinic_id="c1", code="c1", display_name="Clinic", timezone="UTC", default_locale="en", status=RecordStatus.ACTIVE))
    ref_repo.upsert_doctor(Doctor(doctor_id="d1", clinic_id="c1", branch_id=None, display_name="Doc", specialty_code="gen", public_booking_enabled=True, status=RecordStatus.ACTIVE))
    ref_repo.upsert_service(Service(service_id="s1", clinic_id="c1", code="CONS", title_key="consult", duration_minutes=30, specialty_required=None, status=RecordStatus.ACTIVE))

    repo = _BookingRepo(booking)
    clinical = ClinicalChartService(_ClinicalRepo())
    return DoctorOperationsService(
        access_resolver=AccessResolver(access_repo),
        booking_service=BookingService(repo),
        booking_state_service=BookingStateService(repo),
        booking_orchestration=BookingOrchestrationService(repo, None, None, None, None, None, None, None),
        reference_service=ClinicReferenceService(ref_repo),
        patient_reader=_Reader(),
        clinical_service=clinical,
        app_default_timezone="UTC",
    )


def test_chart_and_encounter_baseline_flow() -> None:
    ops = _ops()
    card = asyncio.run(ops.open_chart_summary(doctor_id="d1", clinic_id="c1", patient_id="p1"))
    assert card and card.patient_id == "p1"
    encounter = asyncio.run(ops.open_or_get_encounter(doctor_id="d1", clinic_id="c1", patient_id="p1", booking_id="b1"))
    assert encounter and encounter.status == "open"
    note = asyncio.run(ops.add_encounter_note(doctor_id="d1", encounter_id=encounter.encounter_id, note_type="soap", note_text="compact note"))
    assert note and note.note_text == "compact note"
    diagnosis_id = asyncio.run(ops.set_chart_diagnosis(doctor_id="d1", clinic_id="c1", patient_id="p1", diagnosis_text="Caries"))
    plan_id = asyncio.run(ops.set_chart_treatment_plan(doctor_id="d1", clinic_id="c1", patient_id="p1", title="Plan A", plan_text="Treat and review"))
    assert diagnosis_id and plan_id


def test_diagnosis_and_treatment_plan_versioned_current_semantics() -> None:
    ops = _ops()
    _ = asyncio.run(ops.set_chart_diagnosis(doctor_id="d1", clinic_id="c1", patient_id="p1", diagnosis_text="Initial diagnosis"))
    _ = asyncio.run(ops.set_chart_diagnosis(doctor_id="d1", clinic_id="c1", patient_id="p1", diagnosis_text="Revised diagnosis"))
    _ = asyncio.run(ops.set_chart_treatment_plan(doctor_id="d1", clinic_id="c1", patient_id="p1", title="Plan A", plan_text="First plan"))
    _ = asyncio.run(ops.set_chart_treatment_plan(doctor_id="d1", clinic_id="c1", patient_id="p1", title="Plan B", plan_text="Revised plan"))

    card = asyncio.run(ops.open_chart_summary(doctor_id="d1", clinic_id="c1", patient_id="p1"))
    assert card is not None
    assert card.latest_diagnosis_text == "Revised diagnosis"
    assert card.latest_treatment_plan_text == "Plan B"

    repo = ops.clinical_service.repository
    diagnoses = sorted(repo.diagnoses.values(), key=lambda d: d.version_no)
    plans = sorted(repo.plans.values(), key=lambda p: p.version_no)
    assert [d.version_no for d in diagnoses] == [1, 2]
    assert diagnoses[0].is_current is False and diagnoses[0].superseded_at is not None
    assert diagnoses[1].is_current is True and diagnoses[1].supersedes_diagnosis_id == diagnoses[0].diagnosis_id
    assert [p.version_no for p in plans] == [1, 2]
    assert plans[0].is_current is False and plans[0].superseded_at is not None
    assert plans[1].is_current is True and plans[1].supersedes_treatment_plan_id == plans[0].treatment_plan_id


def test_doctor_cannot_open_unrelated_chart() -> None:
    ops = _ops()
    denied = asyncio.run(ops.open_chart_summary(doctor_id="d1", clinic_id="c1", patient_id="p2"))
    assert denied is None


def test_imaging_url_and_odontogram_snapshot_baseline() -> None:
    ops = _ops()
    ref = asyncio.run(ops.attach_chart_imaging(doctor_id="d1", clinic_id="c1", patient_id="p1", imaging_type="ct", external_url="https://example.com/ct/1"))
    assert ref and ref.external_url == "https://example.com/ct/1"
    snap = asyncio.run(ops.save_chart_odontogram(doctor_id="d1", clinic_id="c1", patient_id="p1", snapshot_payload_json={"teeth": [{"id": "11", "state": "filled"}]}))
    assert snap and snap.snapshot_payload_json["teeth"][0]["id"] == "11"


def test_chart_summary_note_count_and_latest_note_include_closed_encounters() -> None:
    ops = _ops()
    encounter = asyncio.run(ops.open_or_get_encounter(doctor_id="d1", clinic_id="c1", patient_id="p1", booking_id="b1"))
    assert encounter is not None
    _ = asyncio.run(ops.add_encounter_note(doctor_id="d1", encounter_id=encounter.encounter_id, note_type="soap", note_text="open note"))
    closed = asyncio.run(ops.clinical_service.close_encounter(encounter.encounter_id))
    assert closed and closed.status == "closed"
    second = asyncio.run(ops.open_or_get_encounter(doctor_id="d1", clinic_id="c1", patient_id="p1"))
    assert second is not None
    _ = asyncio.run(ops.add_encounter_note(doctor_id="d1", encounter_id=second.encounter_id, note_type="progress", note_text="latest chart note"))
    card = asyncio.run(ops.open_chart_summary(doctor_id="d1", clinic_id="c1", patient_id="p1"))
    assert card is not None
    assert card.note_count == 2
    assert card.latest_note_snippet == "latest chart note"


def test_doctor_timezones_use_branch_then_clinic_then_app_default() -> None:
    ops = _ops()
    booking = replace(ops.booking_service.repository.booking, branch_id="b1", clinic_id="c1")
    ops.booking_service.repository.booking = booking
    assert ops.booking_service.repository.booking.scheduled_start_at.tzinfo == timezone.utc
    ops.reference_service.repository.upsert_branch(
        Branch(
            branch_id="b1",
            clinic_id="c1",
            display_name="Main",
            address_text="-",
            timezone="Europe/Warsaw",
            status=RecordStatus.ACTIVE,
        )
    )
    row = asyncio.run(ops.get_booking_detail(doctor_id="d1", booking_id="b1"))
    assert row and row.scheduled_label.endswith("CEST")

    ops.reference_service.repository.branches.clear()
    row2 = asyncio.run(ops.get_booking_detail(doctor_id="d1", booking_id="b1"))
    assert row2 and row2.scheduled_label.endswith("UTC")

    ops.reference_service.repository.clinics["c1"] = replace(ops.reference_service.repository.clinics["c1"], timezone="")
    ops.app_default_timezone = "America/New_York"
    row3 = asyncio.run(ops.get_booking_detail(doctor_id="d1", booking_id="b1"))
    assert row3 and row3.scheduled_label.endswith("EDT")
