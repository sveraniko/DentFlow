from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from app.domain.media_docs import DOCUMENT_GENERATION_STATUSES, DocumentTemplate, GeneratedDocument, MediaAsset

_ALLOWED_DOCUMENT_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"generating", "failed"},
    "generating": {"generated", "failed"},
    "generated": set(),
    "failed": set(),
}


class TemplateResolutionError(ValueError):
    pass


class DocumentTemplateRepository(Protocol):
    async def save_template(self, item: DocumentTemplate) -> None: ...
    async def list_active_templates(self, *, template_type: str, locale: str, clinic_id: str | None) -> list[DocumentTemplate]: ...


class GeneratedDocumentRepository(Protocol):
    async def save_generated_document(self, item: GeneratedDocument) -> None: ...
    async def get_generated_document(self, generated_document_id: str) -> GeneratedDocument | None: ...
    async def list_for_patient(self, *, patient_id: str, clinic_id: str | None = None) -> list[GeneratedDocument]: ...
    async def list_for_chart(self, *, chart_id: str) -> list[GeneratedDocument]: ...
    async def list_for_booking(self, *, booking_id: str) -> list[GeneratedDocument]: ...


class MediaAssetRepository(Protocol):
    async def save_media_asset(self, item: MediaAsset) -> None: ...
    async def get_media_asset(self, media_asset_id: str) -> MediaAsset | None: ...


@dataclass(slots=True)
class DocumentTemplateRegistryService:
    repository: DocumentTemplateRepository

    async def register_template(
        self,
        *,
        template_type: str,
        locale: str,
        render_engine: str,
        template_source_ref: str,
        clinic_id: str | None = None,
        template_version: int = 1,
        is_active: bool = True,
    ) -> DocumentTemplate:
        now = datetime.now(timezone.utc)
        existing_active = await self.repository.list_active_templates(
            template_type=template_type.strip(),
            locale=locale.strip().lower(),
            clinic_id=clinic_id,
        )
        if is_active and any(item.template_version == template_version for item in existing_active):
            scope = clinic_id if clinic_id is not None else "default"
            raise ValueError(
                f"active template version already exists for scope={scope}, template_type={template_type.strip()}, locale={locale.strip().lower()}, template_version={template_version}"
            )
        template = DocumentTemplate(
            document_template_id=f"dtpl_{uuid4().hex[:16]}",
            clinic_id=clinic_id,
            template_type=template_type.strip(),
            template_version=template_version,
            locale=locale.strip().lower(),
            render_engine=render_engine.strip(),
            template_source_ref=template_source_ref.strip(),
            is_active=is_active,
            created_at=now,
            updated_at=now,
        )
        await self.repository.save_template(template)
        return template

    async def resolve_active_template(
        self,
        *,
        template_type: str,
        locale: str,
        clinic_id: str | None,
        template_version: int | None = None,
    ) -> DocumentTemplate:
        locale_key = locale.strip().lower()
        if clinic_id:
            clinic_templates = await self.repository.list_active_templates(
                template_type=template_type,
                locale=locale_key,
                clinic_id=clinic_id,
            )
            matched = self._select_template(
                clinic_templates,
                template_version=template_version,
                scope_label=f"clinic:{clinic_id}",
                template_type=template_type,
                locale=locale_key,
            )
            if matched is not None:
                return matched
        default_templates = await self.repository.list_active_templates(
            template_type=template_type,
            locale=locale_key,
            clinic_id=None,
        )
        matched_default = self._select_template(
            default_templates,
            template_version=template_version,
            scope_label="default",
            template_type=template_type,
            locale=locale_key,
        )
        if matched_default is not None:
            return matched_default
        raise TemplateResolutionError(
            f"No active template for template_type={template_type}, locale={locale_key}, clinic_id={clinic_id}, template_version={template_version}"
        )

    def _select_template(
        self,
        templates: list[DocumentTemplate],
        *,
        template_version: int | None,
        scope_label: str,
        template_type: str,
        locale: str,
    ) -> DocumentTemplate | None:
        if template_version is not None:
            matches = [template for template in templates if template.template_version == template_version]
            if len(matches) > 1:
                raise TemplateResolutionError(
                    f"Ambiguous active templates for scope={scope_label}, template_type={template_type}, locale={locale}, template_version={template_version}"
                )
            if len(matches) == 1:
                return matches[0]
            return None
        if not templates:
            return None
        highest_version = max(template.template_version for template in templates)
        highest_matches = [template for template in templates if template.template_version == highest_version]
        if len(highest_matches) > 1:
            raise TemplateResolutionError(
                f"Ambiguous active templates for scope={scope_label}, template_type={template_type}, locale={locale}, template_version={highest_version}"
            )
        return templates[0]


@dataclass(slots=True)
class GeneratedDocumentRegistryService:
    repository: GeneratedDocumentRepository

    async def create_generated_document(
        self,
        *,
        clinic_id: str,
        patient_id: str,
        document_template_id: str,
        document_type: str,
        chart_id: str | None = None,
        encounter_id: str | None = None,
        booking_id: str | None = None,
        created_by_actor_id: str | None = None,
    ) -> GeneratedDocument:
        now = datetime.now(timezone.utc)
        item = GeneratedDocument(
            generated_document_id=f"gdoc_{uuid4().hex[:16]}",
            clinic_id=clinic_id,
            patient_id=patient_id,
            chart_id=chart_id,
            encounter_id=encounter_id,
            booking_id=booking_id,
            document_template_id=document_template_id,
            document_type=document_type,
            generation_status="pending",
            generated_file_asset_id=None,
            editable_source_asset_id=None,
            created_by_actor_id=created_by_actor_id,
            created_at=now,
            updated_at=now,
            generation_error_text=None,
        )
        await self.repository.save_generated_document(item)
        return item

    async def mark_generation_started(self, *, generated_document_id: str) -> GeneratedDocument:
        return await self._transition(generated_document_id=generated_document_id, to_status="generating")

    async def mark_generation_success(
        self,
        *,
        generated_document_id: str,
        generated_file_asset_id: str,
        editable_source_asset_id: str | None = None,
    ) -> GeneratedDocument:
        generated_asset = generated_file_asset_id.strip()
        if not generated_asset:
            raise ValueError("generated_file_asset_id is required when marking success")
        return await self._transition(
            generated_document_id=generated_document_id,
            to_status="generated",
            updates={
                "generated_file_asset_id": generated_asset,
                "editable_source_asset_id": (editable_source_asset_id or "").strip() or None,
                "generation_error_text": None,
            },
        )

    async def mark_generation_failed(self, *, generated_document_id: str, error_text: str) -> GeneratedDocument:
        return await self._transition(
            generated_document_id=generated_document_id,
            to_status="failed",
            updates={
                "generation_error_text": error_text.strip()[:4000],
                "generated_file_asset_id": None,
                "editable_source_asset_id": None,
            },
        )

    async def bind_editable_source_asset(self, *, generated_document_id: str, editable_source_asset_id: str) -> GeneratedDocument:
        editable_asset = editable_source_asset_id.strip()
        if not editable_asset:
            raise ValueError("editable_source_asset_id must be non-empty")
        item = await self._require_generated_document(generated_document_id)
        if item.generation_status not in {"pending", "generating"}:
            raise ValueError(f"editable source binding is only allowed before generation success/failure; current={item.generation_status}")
        payload = asdict(item)
        payload["editable_source_asset_id"] = editable_asset
        payload["updated_at"] = datetime.now(timezone.utc)
        updated = GeneratedDocument(**payload)
        await self.repository.save_generated_document(updated)
        return updated

    async def get_generated_document(self, generated_document_id: str) -> GeneratedDocument | None:
        return await self.repository.get_generated_document(generated_document_id)

    async def list_for_patient(self, *, patient_id: str, clinic_id: str | None = None) -> list[GeneratedDocument]:
        return await self.repository.list_for_patient(patient_id=patient_id, clinic_id=clinic_id)

    async def list_for_chart(self, *, chart_id: str) -> list[GeneratedDocument]:
        return await self.repository.list_for_chart(chart_id=chart_id)

    async def list_for_booking(self, *, booking_id: str) -> list[GeneratedDocument]:
        return await self.repository.list_for_booking(booking_id=booking_id)

    async def _transition(self, *, generated_document_id: str, to_status: str, updates: dict[str, object] | None = None) -> GeneratedDocument:
        if to_status not in DOCUMENT_GENERATION_STATUSES:
            raise ValueError(f"Unsupported status: {to_status}")
        item = await self._require_generated_document(generated_document_id)
        allowed = _ALLOWED_DOCUMENT_STATUS_TRANSITIONS.get(item.generation_status, set())
        if to_status not in allowed and item.generation_status != to_status:
            raise ValueError(f"invalid generated-document transition: {item.generation_status} -> {to_status}")
        payload = asdict(item)
        payload["generation_status"] = to_status
        payload["updated_at"] = datetime.now(timezone.utc)
        if updates:
            payload.update(updates)
        updated = GeneratedDocument(**payload)
        await self.repository.save_generated_document(updated)
        return updated

    async def _require_generated_document(self, generated_document_id: str) -> GeneratedDocument:
        item = await self.repository.get_generated_document(generated_document_id)
        if item is None:
            raise ValueError(f"generated document not found: {generated_document_id}")
        return item


@dataclass(slots=True)
class MediaAssetRegistryService:
    repository: MediaAssetRepository

    async def create_asset(
        self,
        *,
        clinic_id: str,
        asset_kind: str,
        storage_provider: str,
        storage_ref: str,
        content_type: str | None,
        byte_size: int | None,
        checksum_sha256: str | None,
        created_by_actor_id: str | None = None,
    ) -> MediaAsset:
        now = datetime.now(timezone.utc)
        item = MediaAsset(
            media_asset_id=f"masset_{uuid4().hex[:16]}",
            clinic_id=clinic_id,
            asset_kind=asset_kind.strip(),
            storage_provider=storage_provider.strip(),
            storage_ref=storage_ref.strip(),
            content_type=(content_type or "").strip() or None,
            byte_size=byte_size,
            checksum_sha256=(checksum_sha256 or "").strip() or None,
            created_by_actor_id=(created_by_actor_id or "").strip() or None,
            created_at=now,
            updated_at=now,
        )
        await self.repository.save_media_asset(item)
        return item

    async def get_media_asset(self, media_asset_id: str) -> MediaAsset | None:
        return await self.repository.get_media_asset(media_asset_id)
