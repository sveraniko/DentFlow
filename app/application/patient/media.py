from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from app.domain.media import MediaAsset, MediaLink

_ALLOWED_STORAGE_PROVIDERS = {"telegram", "object_storage", "local"}
_ALLOWED_MEDIA_TYPES = {"photo", "video", "document"}
_ALLOWED_OWNER_TYPES = {"care_product", "patient_profile", "booking", "clinical_note", "recommendation", "care_order", "document"}
_ALLOWED_ROLES = {"product_cover", "product_gallery", "product_video", "patient_avatar", "clinical_photo", "document_attachment"}
_ALLOWED_VISIBILITY = {"patient_visible", "staff_only", "doctor_only", "admin_only"}
_ROLE_OWNER_RULES = {
    "product_cover": {"care_product"},
    "product_gallery": {"care_product"},
    "product_video": {"care_product"},
    "patient_avatar": {"patient_profile"},
    "clinical_photo": {"patient_profile", "booking", "clinical_note"},
    "document_attachment": {"document", "booking", "patient_profile", "clinical_note"},
}
_DEFAULT_VISIBILITY = {
    "product_cover": "patient_visible",
    "product_gallery": "patient_visible",
    "product_video": "patient_visible",
    "patient_avatar": "staff_only",
    "clinical_photo": "doctor_only",
    "document_attachment": "staff_only",
}


class PatientMediaRepositoryProtocol(Protocol):
    async def get_media_asset(self, *, clinic_id: str, media_asset_id: str) -> MediaAsset | None: ...
    async def upsert_media_asset(self, asset: MediaAsset) -> MediaAsset: ...
    async def find_media_asset_by_telegram_file_unique_id(self, *, clinic_id: str, telegram_file_unique_id: str) -> MediaAsset | None: ...
    async def list_media_assets_by_ids(self, *, clinic_id: str, media_asset_ids: list[str]) -> list[MediaAsset]: ...
    async def get_media_link(self, *, clinic_id: str, link_id: str) -> MediaLink | None: ...
    async def attach_media(self, link: MediaLink) -> MediaLink: ...
    async def list_media_links(self, *, clinic_id: str, owner_type: str, owner_id: str, role: str | None = None, visibility: str | None = None) -> list[MediaLink]: ...
    async def list_media_for_owner(self, *, clinic_id: str, owner_type: str, owner_id: str, role: str | None = None, visibility: str | None = None) -> list[tuple[MediaLink, MediaAsset]]: ...
    async def set_primary_media(self, *, clinic_id: str, owner_type: str, owner_id: str, role: str, link_id: str) -> MediaLink | None: ...
    async def remove_media_link(self, *, clinic_id: str, link_id: str) -> bool: ...


class PatientMediaService:
    def __init__(self, repository: PatientMediaRepositoryProtocol, *, clock=None, id_factory=None) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda prefix: f"{prefix}_{uuid4().hex}")

    async def register_telegram_asset(self, *, clinic_id: str, telegram_file_id: str, telegram_file_unique_id: str, media_type: str, mime_type: str | None = None, size_bytes: int | None = None, uploaded_by_actor_id: str | None = None, media_asset_id: str | None = None) -> MediaAsset:
        self._require_non_empty("clinic_id", clinic_id)
        self._require_non_empty("telegram_file_id", telegram_file_id)
        self._require_non_empty("telegram_file_unique_id", telegram_file_unique_id)
        self._validate_media_type(media_type)
        self._validate_non_negative("size_bytes", size_bytes)

        existing = await self._repository.find_media_asset_by_telegram_file_unique_id(clinic_id=clinic_id, telegram_file_unique_id=telegram_file_unique_id)
        if existing is not None:
            updated = replace(
                existing,
                storage_provider="telegram",
                storage_ref=telegram_file_id,
                asset_kind=media_type,
                content_type=mime_type or existing.content_type,
                byte_size=size_bytes if size_bytes is not None else existing.byte_size,
                media_type=media_type,
                mime_type=mime_type or existing.mime_type,
                size_bytes=size_bytes if size_bytes is not None else existing.size_bytes,
                telegram_file_id=telegram_file_id,
                telegram_file_unique_id=telegram_file_unique_id,
                uploaded_by_actor_id=uploaded_by_actor_id or existing.uploaded_by_actor_id,
                updated_at=self._clock(),
            )
            return await self._repository.upsert_media_asset(updated)

        asset = MediaAsset(
            media_asset_id=media_asset_id or self._id_factory("media"),
            clinic_id=clinic_id,
            asset_kind=media_type,
            storage_provider="telegram",
            storage_ref=telegram_file_id,
            content_type=mime_type,
            byte_size=size_bytes,
            media_type=media_type,
            mime_type=mime_type,
            size_bytes=size_bytes,
            telegram_file_id=telegram_file_id,
            telegram_file_unique_id=telegram_file_unique_id,
            uploaded_by_actor_id=uploaded_by_actor_id,
        )
        return await self._repository.upsert_media_asset(asset)

    async def attach_media_to_owner(self, *, clinic_id: str, media_asset_id: str, owner_type: str, owner_id: str, role: str, visibility: str | None = None, sort_order: int = 0, is_primary: bool | None = None, link_id: str | None = None) -> MediaLink:
        self._require_non_empty("clinic_id", clinic_id)
        self._require_non_empty("media_asset_id", media_asset_id)
        self._require_non_empty("owner_id", owner_id)
        self._validate_owner_role(owner_type, role)
        self._validate_non_negative("sort_order", sort_order)
        resolved_visibility = visibility or _DEFAULT_VISIBILITY[role]
        self._validate_visibility(resolved_visibility)

        asset = await self._repository.get_media_asset(clinic_id=clinic_id, media_asset_id=media_asset_id)
        if asset is None:
            raise ValueError("media asset not found for clinic")

        resolved_primary = is_primary if is_primary is not None else role in {"product_cover", "patient_avatar"}
        link = MediaLink(
            link_id=link_id or self._id_factory("mlink"),
            clinic_id=clinic_id,
            media_asset_id=media_asset_id,
            owner_type=owner_type,
            owner_id=owner_id,
            role=role,
            visibility=resolved_visibility,
            sort_order=sort_order,
            is_primary=resolved_primary,
        )
        attached = await self._repository.attach_media(link)
        if resolved_primary:
            promoted = await self._repository.set_primary_media(clinic_id=clinic_id, owner_type=owner_type, owner_id=owner_id, role=role, link_id=attached.link_id)
            return promoted or attached
        return attached

    async def register_and_attach_telegram_media(self, **kwargs):
        asset = await self.register_telegram_asset(
            clinic_id=kwargs["clinic_id"], telegram_file_id=kwargs["telegram_file_id"], telegram_file_unique_id=kwargs["telegram_file_unique_id"],
            media_type=kwargs["media_type"], mime_type=kwargs.get("mime_type"), size_bytes=kwargs.get("size_bytes"),
            uploaded_by_actor_id=kwargs.get("uploaded_by_actor_id"), media_asset_id=kwargs.get("media_asset_id")
        )
        link = await self.attach_media_to_owner(
            clinic_id=kwargs["clinic_id"], media_asset_id=asset.media_asset_id, owner_type=kwargs["owner_type"], owner_id=kwargs["owner_id"], role=kwargs["role"],
            visibility=kwargs.get("visibility"), sort_order=kwargs.get("sort_order", 0), is_primary=kwargs.get("is_primary"), link_id=kwargs.get("link_id")
        )
        return asset, link

    async def list_owner_media(self, *, clinic_id: str, owner_type: str, owner_id: str, role: str | None = None, visibility: str | None = None) -> tuple[tuple[MediaLink, MediaAsset], ...]:
        self._require_non_empty("clinic_id", clinic_id)
        self._require_non_empty("owner_id", owner_id)
        if role is not None:
            self._validate_role(role)
        self._validate_owner_type(owner_type)
        if visibility is not None:
            self._validate_visibility(visibility)
        return tuple(await self._repository.list_media_for_owner(clinic_id=clinic_id, owner_type=owner_type, owner_id=owner_id, role=role, visibility=visibility))

    async def set_primary_owner_media(self, *, clinic_id: str, owner_type: str, owner_id: str, role: str, link_id: str) -> MediaLink | None:
        self._require_non_empty("clinic_id", clinic_id)
        self._require_non_empty("owner_id", owner_id)
        self._require_non_empty("link_id", link_id)
        self._validate_owner_role(owner_type, role)
        return await self._repository.set_primary_media(clinic_id=clinic_id, owner_type=owner_type, owner_id=owner_id, role=role, link_id=link_id)

    async def remove_owner_media_link(self, *, clinic_id: str, link_id: str) -> bool:
        self._require_non_empty("clinic_id", clinic_id)
        self._require_non_empty("link_id", link_id)
        return await self._repository.remove_media_link(clinic_id=clinic_id, link_id=link_id)

    async def get_patient_avatar(self, *, clinic_id: str, patient_id: str) -> MediaAsset | None:
        pairs = await self.list_owner_media(clinic_id=clinic_id, owner_type="patient_profile", owner_id=patient_id, role="patient_avatar")
        return pairs[0][1] if pairs else None

    async def get_product_cover(self, *, clinic_id: str, product_id: str) -> MediaAsset | None:
        pairs = await self.list_owner_media(clinic_id=clinic_id, owner_type="care_product", owner_id=product_id, role="product_cover")
        return pairs[0][1] if pairs else None

    def _require_non_empty(self, field: str, value: str) -> None:
        if not value or not value.strip():
            raise ValueError(f"{field} is required")

    def _validate_non_negative(self, field: str, value: int | None) -> None:
        if value is not None and value < 0:
            raise ValueError(f"{field} must be >= 0")

    def _validate_media_type(self, media_type: str) -> None:
        if media_type not in _ALLOWED_MEDIA_TYPES:
            raise ValueError("unsupported media_type")

    def _validate_owner_type(self, owner_type: str) -> None:
        if owner_type not in _ALLOWED_OWNER_TYPES:
            raise ValueError("unsupported owner_type")

    def _validate_role(self, role: str) -> None:
        if role not in _ALLOWED_ROLES:
            raise ValueError("unsupported role")

    def _validate_visibility(self, visibility: str) -> None:
        if visibility not in _ALLOWED_VISIBILITY:
            raise ValueError("unsupported visibility")

    def _validate_owner_role(self, owner_type: str, role: str) -> None:
        self._validate_owner_type(owner_type)
        self._validate_role(role)
        if owner_type not in _ROLE_OWNER_RULES[role]:
            raise ValueError(f"role '{role}' is not allowed for owner_type '{owner_type}'")
