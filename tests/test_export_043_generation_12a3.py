from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.application.export import (
    DocumentExportApplicationService,
    DocumentTemplateRegistryService,
    ExportAssemblyRequest,
    GeneratedDocumentRegistryService,
    LocalArtifactStorage,
    MediaAssetRegistryService,
    PlainText043Renderer,
    Structured043ExportAssembler,
)
from app.application.patient.registry import InMemoryPatientRegistryRepository, PatientRegistryService
from app.application.timezone import DoctorTimezoneFormatter
from app.domain.booking import Booking
from app.domain.clinical import ClinicalEncounter, Diagnosis, EncounterNote, ImagingReference, OdontogramSnapshot, PatientChart, TreatmentPlan
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, Service
from app.domain.media_docs import DocumentTemplate, GeneratedDocument, MediaAsset


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


class InMemoryMediaAssetRepository:
    def __init__(self) -> None:
        self.rows: dict[str, MediaAsset] = {}

    async def save_media_asset(self, item: MediaAsset) -> None:
        self.rows[item.media_asset_id] = item

    async def get_media_asset(self, media_asset_id: str) -> MediaAsset | None:
        return self.rows.get(media_asset_id)


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


def _build_export_context(tmp_path: Path) -> tuple[DocumentExportApplicationService, InMemoryGeneratedDocumentRepository, InMemoryMediaAssetRepository, str]:
    patient_repo = InMemoryPatientRegistryRepository()
    patient_service = PatientRegistryService(patient_repo)
    ref_repo = InMemoryClinicReferenceRepository()
    reference_service = ClinicReferenceService(ref_repo)
    timezone_formatter = DoctorTimezoneFormatter(reference_service, app_default_timezone="UTC")

    ref_repo.upsert_clinic(Clinic(clinic_id="clinic_1", code="main", display_name="Main Clinic", timezone="Europe/Kyiv", default_locale="en"))
    ref_repo.upsert_branch(Branch(branch_id="branch_1", clinic_id="clinic_1", display_name="Central Branch", address_text="Addr", timezone="Europe/Kyiv"))
    ref_repo.upsert_doctor(Doctor(doctor_id="doctor_1", clinic_id="clinic_1", display_name="Dr. Ada", specialty_code="gen", branch_id="branch_1"))
    ref_repo.upsert_service(Service(service_id="svc_1", clinic_id="clinic_1", code="CONS", title_key="service.cleaning", duration_minutes=30))

    patient = patient_service.create_patient(
        clinic_id="clinic_1",
        first_name="Iryna",
        last_name="Bond",
        full_name_legal="Iryna Bond",
        display_name="Iryna Bond",
        patient_number="P-001",
    )
    patient_service.upsert_contact(patient_id=patient.patient_id, contact_type="phone", contact_value="+380501112233", is_primary=True)
    patient_service.upsert_preferences(patient_id=patient.patient_id, preferred_language="en", preferred_reminder_channel="telegram")

    now = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
    chart = PatientChart(
        chart_id="chart_1",
        patient_id=patient.patient_id,
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
        patient_id=patient.patient_id,
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

    template_repo = InMemoryTemplateRepository()
    generated_repo = InMemoryGeneratedDocumentRepository()
    media_repo = InMemoryMediaAssetRepository()

    template_registry = DocumentTemplateRegistryService(template_repo)
    generated_registry = GeneratedDocumentRegistryService(generated_repo)
    media_registry = MediaAssetRegistryService(media_repo)

    asyncio.run(
        template_registry.register_template(
            template_type="043_card_export",
            locale="en",
            clinic_id=None,
            render_engine="plain_text_043_v1",
            template_source_ref="builtin://043/plain_text/v1",
            template_version=1,
            is_active=True,
        )
    )

    app_service = DocumentExportApplicationService(
        template_registry=template_registry,
        generated_document_registry=generated_registry,
        payload_assembler=assembler,
        renderer=PlainText043Renderer(),
        artifact_storage=LocalArtifactStorage(base_dir=tmp_path / "artifacts"),
        media_asset_registry=media_registry,
    )
    return app_service, generated_repo, media_repo, patient.patient_id


def test_generate_043_export_creates_artifact_and_marks_generated(tmp_path: Path) -> None:
    app_service, generated_repo, media_repo, patient_id = _build_export_context(tmp_path)

    result = asyncio.run(
        app_service.generate_043_export(
            ExportAssemblyRequest(
                clinic_id="clinic_1",
                patient_id=patient_id,
                chart_id="chart_1",
                encounter_id="enc_1",
                booking_id="booking_1",
                template_type="043_card_export",
                template_locale="en",
                assembled_by_actor_id="actor_1",
            )
        )
    )

    gdoc = generated_repo.rows[result.generated_document_id]
    assert gdoc.generation_status == "generated"
    assert gdoc.generated_file_asset_id == result.generated_file_asset_id

    asset = media_repo.rows[result.generated_file_asset_id]
    assert asset.asset_kind == "generated_document"
    artifact_path = Path(asset.storage_ref)
    assert artifact_path.exists()
    text = artifact_path.read_text(encoding="utf-8")
    assert "Service: Teeth cleaning" in text
    assert "Contact: Phone: +380501112233" in text
    assert "Doctor: Dr. Ada" in text
    assert "Branch: Central Branch" in text


def test_generate_043_export_marks_failed_and_persists_error_on_storage_failure(tmp_path: Path) -> None:
    app_service, generated_repo, _media_repo, patient_id = _build_export_context(tmp_path)

    class _FailingStorage(LocalArtifactStorage):
        def store(self, *, generated_document_id: str, artifact):
            raise RuntimeError("storage offline")

    app_service = replace(app_service, artifact_storage=_FailingStorage(base_dir=tmp_path / "broken"))

    with pytest.raises(RuntimeError, match="storage offline"):
        asyncio.run(
            app_service.generate_043_export(
                ExportAssemblyRequest(
                    clinic_id="clinic_1",
                    patient_id=patient_id,
                    chart_id="chart_1",
                    encounter_id="enc_1",
                    booking_id="booking_1",
                    template_type="043_card_export",
                    template_locale="en",
                )
            )
        )

    failed_doc = next(iter(generated_repo.rows.values()))
    assert failed_doc.generation_status == "failed"
    assert failed_doc.generation_error_text == "storage offline"
    assert failed_doc.generated_file_asset_id is None


def test_plain_text_renderer_humanizes_machine_labels_when_needed(tmp_path: Path) -> None:
    app_service, generated_repo, media_repo, patient_id = _build_export_context(tmp_path)
    # Force machine-shaped labels into payload seam to verify final render polish.
    original_assembler = app_service.payload_assembler

    class _AssemblerProxy:
        async def assemble_payload(self, request: ExportAssemblyRequest):
            payload = await original_assembler.assemble_payload(request)
            return replace(
                payload,
                patient=replace(payload.patient, primary_contact_hint="telegram:iryna_bond"),
                booking=replace(
                    payload.booking,
                    service_label="service.root_canal_initial",
                    doctor_label="doctor_1",
                    branch_label="branch_1",
                ),
            )

    app_service = replace(app_service, payload_assembler=_AssemblerProxy())

    result = asyncio.run(
        app_service.generate_043_export(
            ExportAssemblyRequest(
                clinic_id="clinic_1",
                patient_id=patient_id,
                chart_id="chart_1",
                encounter_id="enc_1",
                booking_id="booking_1",
                template_type="043_card_export",
                template_locale="en",
            )
        )
    )

    asset = media_repo.rows[result.generated_file_asset_id]
    output = Path(asset.storage_ref).read_text(encoding="utf-8")
    assert "service.root_canal_initial" not in output
    assert "Contact: Telegram: iryna_bond" in output
    assert "Doctor: Doctor 1" in output
    assert "Branch: Branch 1" in output
    assert "Service: Root canal initial" in output
    assert generated_repo.rows[result.generated_document_id].generation_status == "generated"
