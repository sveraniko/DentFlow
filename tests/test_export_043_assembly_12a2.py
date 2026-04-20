from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.application.export import (
    DocumentExportApplicationService,
    DocumentTemplateRegistryService,
    ExportAssemblyRequest,
    GeneratedDocumentRegistryService,
    Structured043ExportAssembler,
)
from app.application.export.services import TemplateResolutionError
from app.application.patient.registry import InMemoryPatientRegistryRepository, PatientRegistryService
from app.application.timezone import DoctorTimezoneFormatter
from app.domain.booking import Booking
from app.domain.clinical import ClinicalEncounter, Diagnosis, EncounterNote, ImagingReference, OdontogramSnapshot, PatientChart, TreatmentPlan
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, Service
from app.domain.media_docs import DocumentTemplate, GeneratedDocument


class InMemoryTemplateRepository:
    def __init__(self) -> None:
        self.rows: dict[str, DocumentTemplate] = {}

    async def save_template(self, item: DocumentTemplate) -> None:
        self.rows[item.document_template_id] = item

    async def list_active_templates(self, *, template_type: str, locale: str, clinic_id: str | None) -> list[DocumentTemplate]:
        rows = [
            row
            for row in self.rows.values()
            if row.is_active and row.template_type == template_type and row.locale == locale and row.clinic_id == clinic_id
        ]
        return sorted(rows, key=lambda row: (row.template_version, row.updated_at, row.created_at, row.document_template_id), reverse=True)


class InMemoryGeneratedDocumentRepository:
    def __init__(self) -> None:
        self.rows: dict[str, GeneratedDocument] = {}

    async def save_generated_document(self, item: GeneratedDocument) -> None:
        self.rows[item.generated_document_id] = item

    async def get_generated_document(self, generated_document_id: str) -> GeneratedDocument | None:
        return self.rows.get(generated_document_id)

    async def list_for_patient(self, *, patient_id: str, clinic_id: str | None = None) -> list[GeneratedDocument]:
        return [row for row in self.rows.values() if row.patient_id == patient_id and (clinic_id is None or row.clinic_id == clinic_id)]

    async def list_for_chart(self, *, chart_id: str) -> list[GeneratedDocument]:
        return [row for row in self.rows.values() if row.chart_id == chart_id]

    async def list_for_booking(self, *, booking_id: str) -> list[GeneratedDocument]:
        return [row for row in self.rows.values() if row.booking_id == booking_id]


class InMemoryBookingRepository:
    def __init__(self, booking: Booking | None) -> None:
        self.booking = booking

    async def get_booking(self, booking_id: str) -> Booking | None:
        if self.booking and self.booking.booking_id == booking_id:
            return self.booking
        return None


class InMemoryClinicalRepository:
    def __init__(
        self,
        *,
        chart: PatientChart,
        current_diagnosis: Diagnosis | None,
        current_treatment_plan: TreatmentPlan | None,
        notes: list[EncounterNote],
        imaging: list[ImagingReference],
        odontogram: OdontogramSnapshot | None,
        encounter: ClinicalEncounter | None,
    ) -> None:
        self.chart = chart
        self.current_diagnosis = current_diagnosis
        self.current_treatment_plan = current_treatment_plan
        self.notes = notes
        self.imaging = imaging
        self.odontogram = odontogram
        self.encounter = encounter

    async def get_chart(self, chart_id: str) -> PatientChart | None:
        return self.chart if self.chart.chart_id == chart_id else None

    async def get_current_primary_diagnosis(self, *, chart_id: str):
        return self.current_diagnosis if self.chart.chart_id == chart_id else None

    async def get_current_treatment_plan(self, *, chart_id: str):
        return self.current_treatment_plan if self.chart.chart_id == chart_id else None

    async def list_chart_notes(self, *, chart_id: str) -> list[EncounterNote]:
        return self.notes if self.chart.chart_id == chart_id else []

    async def list_imaging_references(self, *, chart_id: str) -> list[ImagingReference]:
        return self.imaging if self.chart.chart_id == chart_id else []

    async def get_latest_odontogram_snapshot(self, *, chart_id: str) -> OdontogramSnapshot | None:
        return self.odontogram if self.chart.chart_id == chart_id else None

    async def get_encounter(self, encounter_id: str) -> ClinicalEncounter | None:
        if self.encounter and self.encounter.encounter_id == encounter_id:
            return self.encounter
        return None


def _build_registry() -> tuple[PatientRegistryService, ClinicReferenceService, DoctorTimezoneFormatter]:
    patient_repo = InMemoryPatientRegistryRepository()
    patient_service = PatientRegistryService(patient_repo)
    reference_repo = InMemoryClinicReferenceRepository()
    reference_service = ClinicReferenceService(reference_repo)
    timezone_formatter = DoctorTimezoneFormatter(reference_service, app_default_timezone="UTC")

    reference_repo.upsert_clinic(Clinic(clinic_id="clinic_1", code="main", display_name="Main Clinic", timezone="Europe/Kyiv", default_locale="uk"))
    reference_repo.upsert_branch(Branch(branch_id="branch_1", clinic_id="clinic_1", display_name="Central", address_text="Addr", timezone="Europe/Kyiv"))
    reference_repo.upsert_doctor(Doctor(doctor_id="doctor_1", clinic_id="clinic_1", display_name="Dr. Ada", specialty_code="gen", branch_id="branch_1"))
    reference_repo.upsert_service(Service(service_id="svc_1", clinic_id="clinic_1", code="CONS", title_key="Consultation", duration_minutes=30))

    patient = patient_service.create_patient(
        clinic_id="clinic_1",
        first_name="Iryna",
        last_name="Bond",
        full_name_legal="Iryna Bond",
        display_name="Iryna Bond",
        patient_number="P-001",
    )
    patient_service.upsert_contact(patient_id=patient.patient_id, contact_type="phone", contact_value="+380501112233", is_primary=True)
    patient_service.upsert_preferences(patient_id=patient.patient_id, preferred_language="uk", preferred_reminder_channel="telegram")
    patient_service.upsert_external_id(patient_id=patient.patient_id, external_system="legacy", external_id="L-77", is_primary=True)
    return patient_service, reference_service, timezone_formatter


def test_043_payload_assembly_includes_patient_booking_and_current_clinical_truth() -> None:
    patient_service, reference_service, timezone_formatter = _build_registry()
    now = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)

    chart = PatientChart(
        chart_id="chart_1",
        patient_id=next(iter(patient_service.repository.patients.values())).patient_id,
        clinic_id="clinic_1",
        chart_number="CH-100",
        opened_at=now,
        status="active",
        notes_summary="Intermittent pain",
        created_at=now,
        updated_at=now,
    )
    diagnosis = Diagnosis(
        diagnosis_id="dx_current",
        chart_id="chart_1",
        encounter_id="enc_1",
        diagnosis_code="K04.7",
        diagnosis_text="Pulpitis",
        is_primary=True,
        version_no=2,
        is_current=True,
        status="active",
        supersedes_diagnosis_id="dx_old",
        superseded_at=None,
        recorded_by_actor_id="doc",
        recorded_at=now,
        created_at=now,
        updated_at=now,
    )
    treatment_plan = TreatmentPlan(
        treatment_plan_id="tp_current",
        chart_id="chart_1",
        encounter_id="enc_1",
        title="Root canal",
        plan_text="3 visits",
        version_no=3,
        is_current=True,
        status="active",
        supersedes_treatment_plan_id="tp_old",
        superseded_at=None,
        estimated_cost_amount=120.0,
        currency_code="USD",
        approved_by_patient_at=None,
        created_at=now,
        updated_at=now,
    )
    encounter = ClinicalEncounter(
        encounter_id="enc_1",
        chart_id="chart_1",
        booking_id="booking_1",
        doctor_id="doctor_1",
        opened_at=now,
        status="open",
        created_at=now,
        updated_at=now,
    )
    note = EncounterNote(
        encounter_note_id="note_1",
        encounter_id="enc_1",
        note_type="assessment",
        note_text="Deep caries in 26",
        recorded_at=now,
        recorded_by_actor_id="doc",
        created_at=now,
        updated_at=now,
    )
    imaging = ImagingReference(
        imaging_ref_id="img_1",
        chart_id="chart_1",
        encounter_id="enc_1",
        imaging_type="xray",
        media_asset_id="asset_1",
        external_url=None,
        description="Bitewing",
        taken_at=None,
        uploaded_at=now,
        uploaded_by_actor_id="doc",
        is_primary_for_case=True,
        created_at=now,
        updated_at=now,
    )
    odontogram = OdontogramSnapshot(
        odontogram_snapshot_id="odg_1",
        chart_id="chart_1",
        encounter_id="enc_1",
        snapshot_payload_json={"surfaces": ["11-O", "26-M"]},
        recorded_at=now,
        recorded_by_actor_id="doc",
        created_at=now,
    )
    booking = Booking(
        booking_id="booking_1",
        clinic_id="clinic_1",
        branch_id="branch_1",
        patient_id=chart.patient_id,
        doctor_id="doctor_1",
        service_id="svc_1",
        slot_id=None,
        booking_mode="admin",
        source_channel="telegram",
        scheduled_start_at=now,
        scheduled_end_at=now,
        status="confirmed",
        reason_for_visit_short="Pain",
        patient_note=None,
        confirmation_required=True,
        confirmed_at=None,
        canceled_at=None,
        checked_in_at=None,
        in_service_at=None,
        completed_at=None,
        no_show_at=None,
        created_at=now,
        updated_at=now,
    )

    assembler = Structured043ExportAssembler(
        patient_registry=patient_service,
        booking_repository=InMemoryBookingRepository(booking),
        clinical_repository=InMemoryClinicalRepository(
            chart=chart,
            current_diagnosis=diagnosis,
            current_treatment_plan=treatment_plan,
            notes=[note],
            imaging=[imaging],
            odontogram=odontogram,
            encounter=encounter,
        ),
        reference_service=reference_service,
        timezone_formatter=timezone_formatter,
    )

    payload = asyncio.run(
        assembler.assemble_payload(
            ExportAssemblyRequest(
                clinic_id="clinic_1",
                patient_id=chart.patient_id,
                chart_id=chart.chart_id,
                encounter_id=encounter.encounter_id,
                booking_id=booking.booking_id,
                template_type="043_card_export",
                template_locale="uk",
            )
        )
    )

    assert payload.patient.display_name == "Iryna Bond"
    assert payload.patient.primary_contact_hint == "phone:+380501112233"
    assert payload.booking.doctor_label == "Dr. Ada"
    assert payload.booking.service_label == "Consultation"
    assert payload.booking.branch_label == "Central"
    assert payload.diagnosis.diagnosis_id == "dx_current"
    assert payload.treatment_plan.treatment_plan_id == "tp_current"
    assert payload.complaint_and_notes.note_count == 1
    assert payload.imaging.total_count == 1
    assert payload.odontogram.surface_count_hint == 2


def test_043_payload_assembly_is_sparse_safe() -> None:
    patient_service, reference_service, timezone_formatter = _build_registry()
    now = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
    patient_id = next(iter(patient_service.repository.patients.values())).patient_id
    chart = PatientChart(
        chart_id="chart_sparse",
        patient_id=patient_id,
        clinic_id="clinic_1",
        chart_number=None,
        opened_at=now,
        status="active",
        notes_summary=None,
        created_at=now,
        updated_at=now,
    )

    assembler = Structured043ExportAssembler(
        patient_registry=patient_service,
        booking_repository=InMemoryBookingRepository(None),
        clinical_repository=InMemoryClinicalRepository(
            chart=chart,
            current_diagnosis=None,
            current_treatment_plan=None,
            notes=[],
            imaging=[],
            odontogram=None,
            encounter=None,
        ),
        reference_service=reference_service,
        timezone_formatter=timezone_formatter,
    )

    payload = asyncio.run(
        assembler.assemble_payload(
            ExportAssemblyRequest(
                clinic_id="clinic_1",
                patient_id=patient_id,
                chart_id="chart_sparse",
                template_type="043_card_export",
                template_locale="uk",
            )
        )
    )

    assert payload.diagnosis.diagnosis_id is None
    assert payload.treatment_plan.treatment_plan_id is None
    assert payload.imaging.total_count == 0
    assert payload.chart.encounter_id is None
    assert "current_diagnosis_missing" in payload.warnings
    assert "current_treatment_plan_missing" in payload.warnings
    assert "imaging_references_missing" in payload.warnings
    assert "patient_contact_missing" not in payload.warnings


def test_043_payload_assembly_flags_missing_contacts_and_unresolved_booking_refs() -> None:
    patient_repo = InMemoryPatientRegistryRepository()
    patient_service = PatientRegistryService(patient_repo)
    reference_repo = InMemoryClinicReferenceRepository()
    reference_service = ClinicReferenceService(reference_repo)
    timezone_formatter = DoctorTimezoneFormatter(reference_service, app_default_timezone="UTC")
    now = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)

    reference_repo.upsert_clinic(Clinic(clinic_id="clinic_1", code="main", display_name="Main Clinic", timezone="UTC", default_locale="en"))
    patient = patient_service.create_patient(
        clinic_id="clinic_1",
        first_name="Pat",
        last_name="NoContact",
        full_name_legal="Pat NoContact",
        display_name="Pat NoContact",
        patient_number="P-404",
    )
    chart = PatientChart(
        chart_id="chart_404",
        patient_id=patient.patient_id,
        clinic_id="clinic_1",
        chart_number="CH-404",
        opened_at=now,
        status="active",
        created_at=now,
        updated_at=now,
    )
    booking = Booking(
        booking_id="booking_404",
        clinic_id="clinic_1",
        branch_id="branch_missing",
        patient_id=patient.patient_id,
        doctor_id="doctor_missing",
        service_id="service_missing",
        slot_id=None,
        booking_mode="admin",
        source_channel="telegram",
        scheduled_start_at=now,
        scheduled_end_at=now,
        status="confirmed",
        reason_for_visit_short=None,
        patient_note=None,
        confirmation_required=False,
        confirmed_at=None,
        canceled_at=None,
        checked_in_at=None,
        in_service_at=None,
        completed_at=None,
        no_show_at=None,
        created_at=now,
        updated_at=now,
    )
    assembler = Structured043ExportAssembler(
        patient_registry=patient_service,
        booking_repository=InMemoryBookingRepository(booking),
        clinical_repository=InMemoryClinicalRepository(
            chart=chart,
            current_diagnosis=None,
            current_treatment_plan=None,
            notes=[],
            imaging=[],
            odontogram=None,
            encounter=None,
        ),
        reference_service=reference_service,
        timezone_formatter=timezone_formatter,
    )
    payload = asyncio.run(
        assembler.assemble_payload(
            ExportAssemblyRequest(
                clinic_id="clinic_1",
                patient_id=patient.patient_id,
                chart_id=chart.chart_id,
                booking_id=booking.booking_id,
                template_type="043_card_export",
                template_locale="en",
            )
        )
    )
    assert payload.patient.primary_contact_hint is None
    assert payload.booking.doctor_label is None
    assert payload.booking.service_label is None
    assert payload.booking.branch_label is None
    assert "patient_contact_missing" in payload.warnings
    assert "booking_doctor_unresolved" in payload.warnings
    assert "booking_service_unresolved" in payload.warnings
    assert "booking_branch_unresolved" in payload.warnings


def test_template_registry_rejects_duplicate_default_active_version() -> None:
    template_repo = InMemoryTemplateRepository()
    service = DocumentTemplateRegistryService(template_repo)

    asyncio.run(
        service.register_template(
            template_type="043_card_export",
            locale="ru",
            clinic_id=None,
            render_engine="jinja2",
            template_source_ref="git://template/v1",
            template_version=1,
            is_active=True,
        )
    )

    with pytest.raises(ValueError):
        asyncio.run(
            service.register_template(
                template_type="043_card_export",
                locale="ru",
                clinic_id=None,
                render_engine="jinja2",
                template_source_ref="git://template/v1b",
                template_version=1,
                is_active=True,
            )
        )


def test_application_seam_creates_and_starts_generated_document_and_returns_payload() -> None:
    patient_service, reference_service, timezone_formatter = _build_registry()
    now = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
    patient_id = next(iter(patient_service.repository.patients.values())).patient_id
    chart = PatientChart(
        chart_id="chart_2",
        patient_id=patient_id,
        clinic_id="clinic_1",
        chart_number="CH-2",
        opened_at=now,
        status="active",
        created_at=now,
        updated_at=now,
    )

    template_repo = InMemoryTemplateRepository()
    generated_repo = InMemoryGeneratedDocumentRepository()
    template_registry = DocumentTemplateRegistryService(template_repo)
    generated_registry = GeneratedDocumentRegistryService(generated_repo)

    template = asyncio.run(
        template_registry.register_template(
            template_type="043_card_export",
            locale="uk",
            clinic_id=None,
            render_engine="jinja2",
            template_source_ref="git://template/v1",
            template_version=1,
            is_active=True,
        )
    )

    assembler = Structured043ExportAssembler(
        patient_registry=patient_service,
        booking_repository=InMemoryBookingRepository(None),
        clinical_repository=InMemoryClinicalRepository(
            chart=chart,
            current_diagnosis=None,
            current_treatment_plan=None,
            notes=[],
            imaging=[],
            odontogram=None,
            encounter=None,
        ),
        reference_service=reference_service,
        timezone_formatter=timezone_formatter,
    )
    app_service = DocumentExportApplicationService(
        template_registry=template_registry,
        generated_document_registry=generated_registry,
        payload_assembler=assembler,
    )

    result = asyncio.run(
        app_service.assemble_043_export(
            ExportAssemblyRequest(
                clinic_id="clinic_1",
                patient_id=patient_id,
                chart_id=chart.chart_id,
                template_type="043_card_export",
                template_locale="uk",
                assembled_by_actor_id="actor_1",
            )
        )
    )

    persisted = generated_repo.rows[result.generated_document_id]
    assert result.document_template_id == template.document_template_id
    assert result.payload.metadata.assembled_by_actor_id == "actor_1"
    assert persisted.generation_status == "generating"
    assert persisted.document_type == "043_card_export"


def test_template_registry_raises_on_ambiguous_highest_version_selection() -> None:
    now = datetime(2026, 4, 20, tzinfo=timezone.utc)
    template_repo = InMemoryTemplateRepository()
    template_repo.rows["a"] = DocumentTemplate(
        document_template_id="a",
        clinic_id=None,
        template_type="043_card_export",
        template_version=4,
        locale="en",
        render_engine="plain",
        template_source_ref="builtin://043/plain_text/v1",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    template_repo.rows["b"] = DocumentTemplate(
        document_template_id="b",
        clinic_id=None,
        template_type="043_card_export",
        template_version=4,
        locale="en",
        render_engine="plain",
        template_source_ref="builtin://043/plain_text/clinic_v1",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    service = DocumentTemplateRegistryService(template_repo)
    with pytest.raises(TemplateResolutionError, match="Ambiguous active templates"):
        asyncio.run(service.resolve_active_template(template_type="043_card_export", locale="en", clinic_id=None, template_version=None))
