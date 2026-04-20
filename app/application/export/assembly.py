from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from app.application.clinic_reference import ClinicReferenceService
from app.application.export.models import (
    ExportAssemblyRequest,
    ExportAssemblyResult,
    ExportGenerationResult,
    ExportBookingContext043,
    ExportChartContext043,
    ExportDiagnosis043,
    ExportImagingSummary043,
    ExportMetadata043,
    ExportNoteSummary043,
    ExportOdontogramSummary043,
    ExportPatientIdentity043,
    ExportTreatmentPlan043,
    Structured043ExportPayload,
)
from app.application.export.rendering import ArtifactStorage, Export043Renderer
from app.application.export.services import DocumentTemplateRegistryService, GeneratedDocumentRegistryService, MediaAssetRegistryService
from app.application.patient.registry import PatientRegistryService
from app.application.timezone import DoctorTimezoneFormatter
from app.domain.booking import Booking
from app.domain.clinical import ClinicalEncounter, EncounterNote, ImagingReference, OdontogramSnapshot, PatientChart


class BookingReadRepository(Protocol):
    async def get_booking(self, booking_id: str) -> Booking | None: ...


class ClinicalExportReadRepository(Protocol):
    async def get_chart(self, chart_id: str) -> PatientChart | None: ...
    async def get_current_primary_diagnosis(self, *, chart_id: str): ...
    async def get_current_treatment_plan(self, *, chart_id: str): ...
    async def list_chart_notes(self, *, chart_id: str) -> list[EncounterNote]: ...
    async def list_imaging_references(self, *, chart_id: str) -> list[ImagingReference]: ...
    async def get_latest_odontogram_snapshot(self, *, chart_id: str) -> OdontogramSnapshot | None: ...
    async def get_encounter(self, encounter_id: str) -> ClinicalEncounter | None: ...


@dataclass(slots=True)
class Structured043ExportAssembler:
    patient_registry: PatientRegistryService
    booking_repository: BookingReadRepository
    clinical_repository: ClinicalExportReadRepository
    reference_service: ClinicReferenceService
    timezone_formatter: DoctorTimezoneFormatter

    async def assemble_payload(self, request: ExportAssemblyRequest) -> Structured043ExportPayload:
        patient = self.patient_registry.get_patient(request.patient_id)
        if patient is None:
            raise ValueError(f"patient not found: {request.patient_id}")
        chart = await self.clinical_repository.get_chart(request.chart_id)
        if chart is None:
            raise ValueError(f"chart not found: {request.chart_id}")

        warnings: list[str] = []
        preferences = self.patient_registry.get_preferences(request.patient_id)
        external_ids = self.patient_registry.list_external_ids(request.patient_id)
        contacts = [
            item
            for item in self.patient_registry.repository.contacts.values()
            if item.patient_id == request.patient_id and item.is_active
        ]
        contacts_sorted = sorted(contacts, key=lambda item: (item.is_primary, item.is_verified), reverse=True)
        primary_contact_hint = None
        if contacts_sorted:
            contact = contacts_sorted[0]
            primary_contact_hint = f"{contact.contact_type}:{contact.contact_value}"

        booking = await self._resolve_booking(request=request, chart=chart)
        if booking is None:
            warnings.append("booking_context_missing")

        encounter = None
        if request.encounter_id:
            encounter = await self.clinical_repository.get_encounter(request.encounter_id)
            if encounter is None:
                warnings.append("encounter_not_found_for_requested_id")

        diagnosis = await self.clinical_repository.get_current_primary_diagnosis(chart_id=request.chart_id)
        if diagnosis is None:
            warnings.append("current_diagnosis_missing")

        treatment_plan = await self.clinical_repository.get_current_treatment_plan(chart_id=request.chart_id)
        if treatment_plan is None:
            warnings.append("current_treatment_plan_missing")

        notes = await self.clinical_repository.list_chart_notes(chart_id=request.chart_id)
        imaging = await self.clinical_repository.list_imaging_references(chart_id=request.chart_id)
        odontogram = await self.clinical_repository.get_latest_odontogram_snapshot(chart_id=request.chart_id)

        if not imaging:
            warnings.append("imaging_references_missing")

        doctor_label = None
        service_label = None
        branch_label = None
        start_local = None
        end_local = None
        if booking is not None:
            doctor = self.reference_service.get_doctor(request.clinic_id, booking.doctor_id)
            service = self.reference_service.get_service(request.clinic_id, booking.service_id)
            branch = self.reference_service.get_branch(request.clinic_id, booking.branch_id) if booking.branch_id else None
            doctor_label = doctor.display_name if doctor else booking.doctor_id
            service_label = service.title_key if service else booking.service_id
            branch_label = branch.display_name if branch else booking.branch_id
            start_local = self.timezone_formatter.format_booking_time(
                clinic_id=request.clinic_id,
                branch_id=booking.branch_id,
                when=booking.scheduled_start_at,
                fmt="%Y-%m-%d %H:%M",
            )
            end_local = self.timezone_formatter.format_booking_time(
                clinic_id=request.clinic_id,
                branch_id=booking.branch_id,
                when=booking.scheduled_end_at,
                fmt="%Y-%m-%d %H:%M",
            )

        latest_note = max(notes, key=lambda item: item.recorded_at) if notes else None
        latest_imaging = max(imaging, key=lambda item: item.uploaded_at) if imaging else None
        primary_imaging = next((row for row in imaging if row.is_primary_for_case), None)

        return Structured043ExportPayload(
            patient=ExportPatientIdentity043(
                patient_id=patient.patient_id,
                display_name=patient.display_name,
                full_name_legal=patient.full_name_legal,
                patient_number=patient.patient_number,
                preferred_language=preferences.preferred_language if preferences else None,
                preferred_reminder_channel=preferences.preferred_reminder_channel if preferences else None,
                primary_contact_hint=primary_contact_hint,
                external_reference=external_ids[0].external_id if external_ids else None,
            ),
            booking=ExportBookingContext043(
                booking_id=booking.booking_id if booking else request.booking_id,
                booking_status=booking.status if booking else None,
                scheduled_start_at_utc=booking.scheduled_start_at if booking else None,
                scheduled_start_local_label=start_local,
                scheduled_end_local_label=end_local,
                doctor_label=doctor_label,
                service_label=service_label,
                branch_label=branch_label,
            ),
            chart=ExportChartContext043(
                chart_id=chart.chart_id,
                chart_number=chart.chart_number,
                chart_opened_at=chart.opened_at,
                chart_notes_summary=chart.notes_summary,
                encounter_id=encounter.encounter_id if encounter else request.encounter_id,
                encounter_opened_at=encounter.opened_at if encounter else None,
                encounter_status=encounter.status if encounter else None,
            ),
            diagnosis=ExportDiagnosis043(
                diagnosis_id=diagnosis.diagnosis_id if diagnosis else None,
                diagnosis_text=diagnosis.diagnosis_text if diagnosis else None,
                diagnosis_code=diagnosis.diagnosis_code if diagnosis else None,
                is_primary=diagnosis.is_primary if diagnosis else None,
                version_no=diagnosis.version_no if diagnosis else None,
                recorded_at=diagnosis.recorded_at if diagnosis else None,
            ),
            treatment_plan=ExportTreatmentPlan043(
                treatment_plan_id=treatment_plan.treatment_plan_id if treatment_plan else None,
                title=treatment_plan.title if treatment_plan else None,
                plan_text=treatment_plan.plan_text if treatment_plan else None,
                version_no=treatment_plan.version_no if treatment_plan else None,
                estimated_cost_amount=treatment_plan.estimated_cost_amount if treatment_plan else None,
                currency_code=treatment_plan.currency_code if treatment_plan else None,
                approved_by_patient_at=treatment_plan.approved_by_patient_at if treatment_plan else None,
            ),
            complaint_and_notes=ExportNoteSummary043(
                note_count=len(notes),
                latest_note_type=latest_note.note_type if latest_note else None,
                latest_note_text=latest_note.note_text if latest_note else chart.notes_summary,
                latest_note_recorded_at=latest_note.recorded_at if latest_note else None,
            ),
            imaging=ExportImagingSummary043(
                total_count=len(imaging),
                primary_imaging_ref_id=primary_imaging.imaging_ref_id if primary_imaging else None,
                latest_imaging_ref_id=latest_imaging.imaging_ref_id if latest_imaging else None,
                latest_imaging_type=latest_imaging.imaging_type if latest_imaging else None,
                latest_imaging_description=latest_imaging.description if latest_imaging else None,
            ),
            odontogram=ExportOdontogramSummary043(
                has_snapshot=odontogram is not None,
                odontogram_snapshot_id=odontogram.odontogram_snapshot_id if odontogram else None,
                recorded_at=odontogram.recorded_at if odontogram else None,
                surface_count_hint=self._surface_count_hint(odontogram),
            ),
            metadata=ExportMetadata043(
                assembled_at=datetime.now(timezone.utc),
                assembled_by_actor_id=request.assembled_by_actor_id,
                template_type=request.template_type,
                template_locale=request.template_locale,
                template_version=request.template_version,
            ),
            warnings=tuple(sorted(set(warnings))),
        )

    async def _resolve_booking(self, *, request: ExportAssemblyRequest, chart: PatientChart) -> Booking | None:
        if request.booking_id:
            return await self.booking_repository.get_booking(request.booking_id)
        if request.encounter_id:
            encounter = await self.clinical_repository.get_encounter(request.encounter_id)
            if encounter and encounter.booking_id:
                return await self.booking_repository.get_booking(encounter.booking_id)
        return None

    def _surface_count_hint(self, snapshot: OdontogramSnapshot | None) -> int | None:
        if snapshot is None:
            return None
        surfaces = snapshot.snapshot_payload_json.get("surfaces")
        if isinstance(surfaces, list):
            return len(surfaces)
        return None


@dataclass(slots=True)
class DocumentExportApplicationService:
    template_registry: DocumentTemplateRegistryService
    generated_document_registry: GeneratedDocumentRegistryService
    payload_assembler: Structured043ExportAssembler
    renderer: Export043Renderer | None = None
    artifact_storage: ArtifactStorage | None = None
    media_asset_registry: MediaAssetRegistryService | None = None

    async def assemble_043_export(self, request: ExportAssemblyRequest) -> ExportAssemblyResult:
        template = await self.template_registry.resolve_active_template(
            template_type=request.template_type,
            locale=request.template_locale,
            clinic_id=request.clinic_id,
            template_version=request.template_version,
        )
        generated_document = await self.generated_document_registry.create_generated_document(
            clinic_id=request.clinic_id,
            patient_id=request.patient_id,
            chart_id=request.chart_id,
            encounter_id=request.encounter_id,
            booking_id=request.booking_id,
            document_template_id=template.document_template_id,
            document_type=request.template_type,
            created_by_actor_id=request.assembled_by_actor_id,
        )
        try:
            await self.generated_document_registry.mark_generation_started(generated_document_id=generated_document.generated_document_id)
            payload = await self.payload_assembler.assemble_payload(request)
        except Exception as exc:
            await self.generated_document_registry.mark_generation_failed(
                generated_document_id=generated_document.generated_document_id,
                error_text=str(exc),
            )
            raise
        return ExportAssemblyResult(
            generated_document_id=generated_document.generated_document_id,
            document_template_id=template.document_template_id,
            payload=payload,
        )

    async def generate_043_export(self, request: ExportAssemblyRequest) -> ExportGenerationResult:
        if self.renderer is None or self.artifact_storage is None or self.media_asset_registry is None:
            raise ValueError("renderer, artifact_storage, and media_asset_registry must be configured for generation")
        template = await self.template_registry.resolve_active_template(
            template_type=request.template_type,
            locale=request.template_locale,
            clinic_id=request.clinic_id,
            template_version=request.template_version,
        )
        generated_document = await self.generated_document_registry.create_generated_document(
            clinic_id=request.clinic_id,
            patient_id=request.patient_id,
            chart_id=request.chart_id,
            encounter_id=request.encounter_id,
            booking_id=request.booking_id,
            document_template_id=template.document_template_id,
            document_type=request.template_type,
            created_by_actor_id=request.assembled_by_actor_id,
        )
        try:
            await self.generated_document_registry.mark_generation_started(generated_document_id=generated_document.generated_document_id)
            payload = await self.payload_assembler.assemble_payload(request)
            rendered = self.renderer.render(payload=payload, locale=request.template_locale, template_source_ref=template.template_source_ref)
            stored = self.artifact_storage.store(generated_document_id=generated_document.generated_document_id, artifact=rendered)
            asset = await self.media_asset_registry.create_asset(
                clinic_id=request.clinic_id,
                asset_kind="generated_document",
                storage_provider=stored.storage_provider,
                storage_ref=stored.storage_ref,
                content_type=rendered.content_type,
                byte_size=stored.byte_size,
                checksum_sha256=stored.checksum_sha256,
                created_by_actor_id=request.assembled_by_actor_id,
            )
            editable_source_asset_id = None
            if rendered.editable_source is not None:
                editable_stored = self.artifact_storage.store(
                    generated_document_id=f"{generated_document.generated_document_id}.editable",
                    artifact=rendered.editable_source,
                )
                editable_asset = await self.media_asset_registry.create_asset(
                    clinic_id=request.clinic_id,
                    asset_kind="generated_document_editable_source",
                    storage_provider=editable_stored.storage_provider,
                    storage_ref=editable_stored.storage_ref,
                    content_type=rendered.editable_source.content_type,
                    byte_size=editable_stored.byte_size,
                    checksum_sha256=editable_stored.checksum_sha256,
                    created_by_actor_id=request.assembled_by_actor_id,
                )
                editable_source_asset_id = editable_asset.media_asset_id
            await self.generated_document_registry.mark_generation_success(
                generated_document_id=generated_document.generated_document_id,
                generated_file_asset_id=asset.media_asset_id,
                editable_source_asset_id=editable_source_asset_id,
            )
            return ExportGenerationResult(
                generated_document_id=generated_document.generated_document_id,
                document_template_id=template.document_template_id,
                generated_file_asset_id=asset.media_asset_id,
                artifact_storage_ref=asset.storage_ref,
            )
        except Exception as exc:
            await self.generated_document_registry.mark_generation_failed(
                generated_document_id=generated_document.generated_document_id,
                error_text=str(exc),
            )
            raise
