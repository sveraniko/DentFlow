from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class MediaAsset:
    media_asset_id: str
    clinic_id: str
    asset_kind: str
    storage_provider: str
    storage_ref: str
    content_type: str | None = None
    byte_size: int | None = None
    checksum_sha256: str | None = None
    created_by_actor_id: str | None = None
    media_type: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    telegram_file_id: str | None = None
    telegram_file_unique_id: str | None = None
    object_key: str | None = None
    uploaded_by_actor_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class MediaLink:
    link_id: str
    clinic_id: str
    media_asset_id: str
    owner_type: str
    owner_id: str
    role: str
    visibility: str
    sort_order: int = 0
    is_primary: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
