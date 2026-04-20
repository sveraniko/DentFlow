from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone

import pytest

from app.application.export import DocumentTemplateRegistryService, GeneratedDocumentRegistryService, TemplateResolutionError
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
        rows = [row for row in self.rows.values() if row.patient_id == patient_id and (clinic_id is None or row.clinic_id == clinic_id)]
        return sorted(rows, key=lambda row: (row.created_at, row.generated_document_id), reverse=True)

    async def list_for_chart(self, *, chart_id: str) -> list[GeneratedDocument]:
        rows = [row for row in self.rows.values() if row.chart_id == chart_id]
        return sorted(rows, key=lambda row: (row.created_at, row.generated_document_id), reverse=True)

    async def list_for_booking(self, *, booking_id: str) -> list[GeneratedDocument]:
        rows = [row for row in self.rows.values() if row.booking_id == booking_id]
        return sorted(rows, key=lambda row: (row.created_at, row.generated_document_id), reverse=True)


def test_template_resolution_prefers_clinic_template_then_falls_back() -> None:
    repo = InMemoryTemplateRepository()
    service = DocumentTemplateRegistryService(repo)

    default = asyncio.run(service.register_template(
        template_type="043_card_export",
        locale="ru",
        clinic_id=None,
        render_engine="jinja2_html",
        template_source_ref="s3://templates/default/v1.html",
        template_version=1,
    ))
    clinic_specific = asyncio.run(service.register_template(
        template_type="043_card_export",
        locale="ru",
        clinic_id="clinic_a",
        render_engine="jinja2_html",
        template_source_ref="s3://templates/clinic_a/v2.html",
        template_version=2,
    ))

    resolved_for_clinic = asyncio.run(service.resolve_active_template(template_type="043_card_export", locale="ru", clinic_id="clinic_a"))
    resolved_for_other = asyncio.run(service.resolve_active_template(template_type="043_card_export", locale="ru", clinic_id="clinic_b"))

    assert resolved_for_clinic.document_template_id == clinic_specific.document_template_id
    assert resolved_for_other.document_template_id == default.document_template_id


def test_template_resolution_is_version_deterministic_and_missing_fails() -> None:
    repo = InMemoryTemplateRepository()
    service = DocumentTemplateRegistryService(repo)

    t1 = asyncio.run(service.register_template(
        template_type="aftercare_pdf",
        locale="en",
        clinic_id=None,
        render_engine="jinja2_pdf",
        template_source_ref="git://templates/aftercare-v1",
        template_version=1,
    ))
    t2 = asyncio.run(service.register_template(
        template_type="aftercare_pdf",
        locale="en",
        clinic_id=None,
        render_engine="jinja2_pdf",
        template_source_ref="git://templates/aftercare-v2",
        template_version=2,
    ))

    resolved_latest = asyncio.run(service.resolve_active_template(template_type="aftercare_pdf", locale="en", clinic_id=None))
    resolved_v1 = asyncio.run(service.resolve_active_template(template_type="aftercare_pdf", locale="en", clinic_id=None, template_version=1))

    assert resolved_latest.document_template_id == t2.document_template_id
    assert resolved_v1.document_template_id == t1.document_template_id

    with pytest.raises(TemplateResolutionError):
        asyncio.run(service.resolve_active_template(template_type="unknown", locale="en", clinic_id="clinic_x"))


def test_generated_document_status_happy_and_failure_paths_preserve_metadata() -> None:
    repo = InMemoryGeneratedDocumentRepository()
    service = GeneratedDocumentRegistryService(repo)

    created = asyncio.run(service.create_generated_document(
        clinic_id="clinic_a",
        patient_id="patient_1",
        chart_id="chart_1",
        encounter_id="enc_1",
        booking_id="booking_1",
        document_template_id="dtpl_1",
        document_type="043_card_export",
        created_by_actor_id="actor_1",
    ))
    assert created.generation_status == "pending"
    assert created.generated_file_asset_id is None

    started = asyncio.run(service.mark_generation_started(generated_document_id=created.generated_document_id))
    with_editable = asyncio.run(service.bind_editable_source_asset(generated_document_id=created.generated_document_id, editable_source_asset_id="asset_source_1"))
    success = asyncio.run(service.mark_generation_success(
        generated_document_id=created.generated_document_id,
        generated_file_asset_id="asset_pdf_1",
        editable_source_asset_id=with_editable.editable_source_asset_id,
    ))

    assert started.generation_status == "generating"
    assert with_editable.editable_source_asset_id == "asset_source_1"
    assert success.generation_status == "generated"
    assert success.generated_file_asset_id == "asset_pdf_1"
    assert success.generation_error_text is None

    created_fail = asyncio.run(service.create_generated_document(
        clinic_id="clinic_a",
        patient_id="patient_1",
        document_template_id="dtpl_1",
        document_type="043_card_export",
    ))
    started_fail = asyncio.run(service.mark_generation_started(generated_document_id=created_fail.generated_document_id))
    failed = asyncio.run(service.mark_generation_failed(generated_document_id=created_fail.generated_document_id, error_text="template parse error"))

    assert started_fail.generation_status == "generating"
    assert failed.generation_status == "failed"
    assert failed.generation_error_text == "template parse error"
    assert failed.generated_file_asset_id is None
    assert failed.editable_source_asset_id is None


def test_generated_document_listing_contexts() -> None:
    repo = InMemoryGeneratedDocumentRepository()
    service = GeneratedDocumentRegistryService(repo)

    a = asyncio.run(service.create_generated_document(
        clinic_id="clinic_a",
        patient_id="patient_1",
        chart_id="chart_1",
        booking_id="booking_1",
        document_template_id="dtpl_1",
        document_type="043_card_export",
    ))
    b = asyncio.run(service.create_generated_document(
        clinic_id="clinic_a",
        patient_id="patient_1",
        chart_id="chart_2",
        booking_id="booking_2",
        document_template_id="dtpl_1",
        document_type="aftercare_pdf",
    ))

    by_patient = asyncio.run(service.list_for_patient(patient_id="patient_1", clinic_id="clinic_a"))
    by_chart_1 = asyncio.run(service.list_for_chart(chart_id="chart_1"))
    by_booking_2 = asyncio.run(service.list_for_booking(booking_id="booking_2"))

    assert {row.generated_document_id for row in by_patient} == {a.generated_document_id, b.generated_document_id}
    assert [row.generated_document_id for row in by_chart_1] == [a.generated_document_id]
    assert [row.generated_document_id for row in by_booking_2] == [b.generated_document_id]


def test_generated_document_invalid_status_transition_rejected() -> None:
    repo = InMemoryGeneratedDocumentRepository()
    service = GeneratedDocumentRegistryService(repo)
    item = asyncio.run(service.create_generated_document(
        clinic_id="clinic_a",
        patient_id="patient_1",
        document_template_id="dtpl_1",
        document_type="043_card_export",
    ))
    asyncio.run(service.mark_generation_started(generated_document_id=item.generated_document_id))
    asyncio.run(service.mark_generation_success(generated_document_id=item.generated_document_id, generated_file_asset_id="asset_pdf_1"))

    with pytest.raises(ValueError):
        asyncio.run(service.mark_generation_failed(generated_document_id=item.generated_document_id, error_text="late failure"))


def test_generated_documents_are_projection_records_not_patient_truth() -> None:
    now = datetime.now(timezone.utc)
    row = GeneratedDocument(
        generated_document_id="gdoc_1",
        clinic_id="clinic_a",
        patient_id="patient_1",
        chart_id="chart_1",
        encounter_id=None,
        booking_id=None,
        document_template_id="dtpl_1",
        document_type="043_card_export",
        generation_status="pending",
        generated_file_asset_id=None,
        editable_source_asset_id=None,
        created_by_actor_id=None,
        created_at=now,
        updated_at=now,
        generation_error_text=None,
    )
    payload = asdict(row)

    assert "first_name" not in payload
    assert "diagnoses" not in payload
    assert "booking_status" not in payload
    assert "raw_blob" not in payload
