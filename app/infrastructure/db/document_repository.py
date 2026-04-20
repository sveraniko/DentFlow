from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import text

from app.domain.media_docs import DocumentTemplate, GeneratedDocument
from app.infrastructure.db.engine import create_engine


class DbDocumentTemplateRepository:
    def __init__(self, db_config) -> None:
        self._db_config = db_config

    async def save_template(self, item: DocumentTemplate) -> None:
        payload = asdict(item)
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO media_docs.document_templates (
                      document_template_id, clinic_id, template_type, template_version, locale,
                      render_engine, template_source_ref, is_active, created_at, updated_at
                    )
                    VALUES (
                      :document_template_id, :clinic_id, :template_type, :template_version, :locale,
                      :render_engine, :template_source_ref, :is_active, :created_at, :updated_at
                    )
                    ON CONFLICT (document_template_id) DO UPDATE SET
                      clinic_id=EXCLUDED.clinic_id,
                      template_type=EXCLUDED.template_type,
                      template_version=EXCLUDED.template_version,
                      locale=EXCLUDED.locale,
                      render_engine=EXCLUDED.render_engine,
                      template_source_ref=EXCLUDED.template_source_ref,
                      is_active=EXCLUDED.is_active,
                      updated_at=EXCLUDED.updated_at
                    """
                ),
                payload,
            )
        await engine.dispose()

    async def list_active_templates(self, *, template_type: str, locale: str, clinic_id: str | None) -> list[DocumentTemplate]:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            rows = list(
                (
                    await conn.execute(
                        text(
                            """
                            SELECT document_template_id, clinic_id, template_type, template_version, locale,
                                   render_engine, template_source_ref, is_active, created_at, updated_at
                            FROM media_docs.document_templates
                            WHERE template_type=:template_type
                              AND locale=:locale
                              AND clinic_id IS NOT DISTINCT FROM :clinic_id
                              AND is_active=TRUE
                            ORDER BY template_version DESC, updated_at DESC, created_at DESC, document_template_id DESC
                            """
                        ),
                        {"template_type": template_type, "locale": locale, "clinic_id": clinic_id},
                    )
                ).mappings()
            )
        await engine.dispose()
        return [DocumentTemplate(**dict(row)) for row in rows]


class DbGeneratedDocumentRepository:
    def __init__(self, db_config) -> None:
        self._db_config = db_config

    async def save_generated_document(self, item: GeneratedDocument) -> None:
        payload = asdict(item)
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO media_docs.generated_documents (
                      generated_document_id, clinic_id, patient_id, chart_id, encounter_id, booking_id,
                      document_template_id, document_type, generation_status,
                      generated_file_asset_id, editable_source_asset_id, created_by_actor_id,
                      created_at, updated_at, generation_error_text
                    )
                    VALUES (
                      :generated_document_id, :clinic_id, :patient_id, :chart_id, :encounter_id, :booking_id,
                      :document_template_id, :document_type, :generation_status,
                      :generated_file_asset_id, :editable_source_asset_id, :created_by_actor_id,
                      :created_at, :updated_at, :generation_error_text
                    )
                    ON CONFLICT (generated_document_id) DO UPDATE SET
                      clinic_id=EXCLUDED.clinic_id,
                      patient_id=EXCLUDED.patient_id,
                      chart_id=EXCLUDED.chart_id,
                      encounter_id=EXCLUDED.encounter_id,
                      booking_id=EXCLUDED.booking_id,
                      document_template_id=EXCLUDED.document_template_id,
                      document_type=EXCLUDED.document_type,
                      generation_status=EXCLUDED.generation_status,
                      generated_file_asset_id=EXCLUDED.generated_file_asset_id,
                      editable_source_asset_id=EXCLUDED.editable_source_asset_id,
                      created_by_actor_id=EXCLUDED.created_by_actor_id,
                      updated_at=EXCLUDED.updated_at,
                      generation_error_text=EXCLUDED.generation_error_text
                    """
                ),
                payload,
            )
        await engine.dispose()

    async def get_generated_document(self, generated_document_id: str) -> GeneratedDocument | None:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT generated_document_id, clinic_id, patient_id, chart_id, encounter_id, booking_id,
                               document_template_id, document_type, generation_status,
                               generated_file_asset_id, editable_source_asset_id, created_by_actor_id,
                               created_at, updated_at, generation_error_text
                        FROM media_docs.generated_documents
                        WHERE generated_document_id=:generated_document_id
                        """
                    ),
                    {"generated_document_id": generated_document_id},
                )
            ).mappings().first()
        await engine.dispose()
        return GeneratedDocument(**dict(row)) if row is not None else None

    async def list_for_patient(self, *, patient_id: str, clinic_id: str | None = None) -> list[GeneratedDocument]:
        return await self._list(
            where_sql="patient_id=:patient_id AND clinic_id IS NOT DISTINCT FROM COALESCE(:clinic_id, clinic_id)",
            params={"patient_id": patient_id, "clinic_id": clinic_id},
        )

    async def list_for_chart(self, *, chart_id: str) -> list[GeneratedDocument]:
        return await self._list(where_sql="chart_id=:chart_id", params={"chart_id": chart_id})

    async def list_for_booking(self, *, booking_id: str) -> list[GeneratedDocument]:
        return await self._list(where_sql="booking_id=:booking_id", params={"booking_id": booking_id})

    async def _list(self, *, where_sql: str, params: dict[str, object]) -> list[GeneratedDocument]:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            rows = list(
                (
                    await conn.execute(
                        text(
                            f"""
                            SELECT generated_document_id, clinic_id, patient_id, chart_id, encounter_id, booking_id,
                                   document_template_id, document_type, generation_status,
                                   generated_file_asset_id, editable_source_asset_id, created_by_actor_id,
                                   created_at, updated_at, generation_error_text
                            FROM media_docs.generated_documents
                            WHERE {where_sql}
                            ORDER BY created_at DESC, generated_document_id DESC
                            """
                        ),
                        params,
                    )
                ).mappings()
            )
        await engine.dispose()
        return [GeneratedDocument(**dict(row)) for row in rows]
