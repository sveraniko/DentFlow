from __future__ import annotations

from dataclasses import asdict
from typing import Any, Sequence

from sqlalchemy import text

from app.config.settings import DatabaseConfig
from app.domain.media import MediaAsset, MediaLink
from app.infrastructure.db.engine import create_engine


def _map_media_asset(row: Any) -> MediaAsset:
    media_type = row.get("media_type") if row.get("media_type") is not None else row.get("asset_kind")
    mime_type = row.get("mime_type") if row.get("mime_type") is not None else row.get("content_type")
    size_bytes = row.get("size_bytes") if row.get("size_bytes") is not None else row.get("byte_size")
    return MediaAsset(
        media_asset_id=row["media_asset_id"],
        clinic_id=row["clinic_id"],
        asset_kind=row["asset_kind"],
        storage_provider=row["storage_provider"],
        storage_ref=row["storage_ref"],
        content_type=row.get("content_type"),
        byte_size=row.get("byte_size"),
        checksum_sha256=row.get("checksum_sha256"),
        created_by_actor_id=row.get("created_by_actor_id"),
        media_type=media_type,
        mime_type=mime_type,
        size_bytes=size_bytes,
        telegram_file_id=row.get("telegram_file_id"),
        telegram_file_unique_id=row.get("telegram_file_unique_id"),
        object_key=row.get("object_key"),
        uploaded_by_actor_id=row.get("uploaded_by_actor_id"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _map_media_link(row: Any) -> MediaLink:
    return MediaLink(
        link_id=row["link_id"],
        clinic_id=row["clinic_id"],
        media_asset_id=row["media_asset_id"],
        owner_type=row["owner_type"],
        owner_id=row["owner_id"],
        role=row["role"],
        visibility=row["visibility"],
        sort_order=row.get("sort_order", 0),
        is_primary=row.get("is_primary", False),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


class DbMediaRepository:
    def __init__(self, db_config: DatabaseConfig) -> None:
        self._db_config = db_config

    async def get_media_asset(self, *, clinic_id: str, media_asset_id: str) -> MediaAsset | None:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT media_asset_id, clinic_id, asset_kind, storage_provider, storage_ref,
                               content_type, byte_size, checksum_sha256, created_by_actor_id,
                               media_type, mime_type, size_bytes, telegram_file_id, telegram_file_unique_id,
                               object_key, uploaded_by_actor_id, created_at, updated_at
                        FROM media_docs.media_assets
                        WHERE clinic_id=:clinic_id AND media_asset_id=:media_asset_id
                        """
                    ),
                    {"clinic_id": clinic_id, "media_asset_id": media_asset_id},
                )
            ).mappings().first()
        await engine.dispose()
        return _map_media_asset(row) if row is not None else None

    async def upsert_media_asset(self, asset: MediaAsset) -> MediaAsset:
        payload = asdict(asset)
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        INSERT INTO media_docs.media_assets (
                          media_asset_id, clinic_id, asset_kind, storage_provider, storage_ref,
                          content_type, byte_size, checksum_sha256, created_by_actor_id,
                          media_type, mime_type, size_bytes, telegram_file_id, telegram_file_unique_id,
                          object_key, uploaded_by_actor_id, created_at, updated_at
                        )
                        VALUES (
                          :media_asset_id, :clinic_id, :asset_kind, :storage_provider, :storage_ref,
                          :content_type, :byte_size, :checksum_sha256, :created_by_actor_id,
                          :media_type, :mime_type, :size_bytes, :telegram_file_id, :telegram_file_unique_id,
                          :object_key, :uploaded_by_actor_id, COALESCE(:created_at, NOW()), COALESCE(:updated_at, NOW())
                        )
                        ON CONFLICT (media_asset_id) DO UPDATE SET
                          clinic_id=EXCLUDED.clinic_id,
                          asset_kind=EXCLUDED.asset_kind,
                          storage_provider=EXCLUDED.storage_provider,
                          storage_ref=EXCLUDED.storage_ref,
                          content_type=EXCLUDED.content_type,
                          byte_size=EXCLUDED.byte_size,
                          checksum_sha256=EXCLUDED.checksum_sha256,
                          created_by_actor_id=EXCLUDED.created_by_actor_id,
                          media_type=EXCLUDED.media_type,
                          mime_type=EXCLUDED.mime_type,
                          size_bytes=EXCLUDED.size_bytes,
                          telegram_file_id=EXCLUDED.telegram_file_id,
                          telegram_file_unique_id=EXCLUDED.telegram_file_unique_id,
                          object_key=EXCLUDED.object_key,
                          uploaded_by_actor_id=EXCLUDED.uploaded_by_actor_id,
                          created_at=media_docs.media_assets.created_at,
                          updated_at=EXCLUDED.updated_at
                        RETURNING media_asset_id, clinic_id, asset_kind, storage_provider, storage_ref,
                                  content_type, byte_size, checksum_sha256, created_by_actor_id,
                                  media_type, mime_type, size_bytes, telegram_file_id, telegram_file_unique_id,
                                  object_key, uploaded_by_actor_id, created_at, updated_at
                        """
                    ),
                    payload,
                )
            ).mappings().one()
        await engine.dispose()
        return _map_media_asset(row)

    async def find_media_asset_by_telegram_file_unique_id(self, *, clinic_id: str, telegram_file_unique_id: str) -> MediaAsset | None:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT media_asset_id, clinic_id, asset_kind, storage_provider, storage_ref,
                               content_type, byte_size, checksum_sha256, created_by_actor_id,
                               media_type, mime_type, size_bytes, telegram_file_id, telegram_file_unique_id,
                               object_key, uploaded_by_actor_id, created_at, updated_at
                        FROM media_docs.media_assets
                        WHERE clinic_id=:clinic_id AND telegram_file_unique_id=:telegram_file_unique_id
                        ORDER BY updated_at DESC, created_at DESC, media_asset_id DESC
                        LIMIT 1
                        """
                    ),
                    {"clinic_id": clinic_id, "telegram_file_unique_id": telegram_file_unique_id},
                )
            ).mappings().first()
        await engine.dispose()
        return _map_media_asset(row) if row is not None else None

    async def list_media_assets_by_ids(self, *, clinic_id: str, media_asset_ids: Sequence[str]) -> list[MediaAsset]:
        if not media_asset_ids:
            return []
        ids = list(dict.fromkeys(media_asset_ids))
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            rows = list((await conn.execute(text(
                """
                SELECT media_asset_id, clinic_id, asset_kind, storage_provider, storage_ref,
                       content_type, byte_size, checksum_sha256, created_by_actor_id,
                       media_type, mime_type, size_bytes, telegram_file_id, telegram_file_unique_id,
                       object_key, uploaded_by_actor_id, created_at, updated_at
                FROM media_docs.media_assets
                WHERE clinic_id=:clinic_id AND media_asset_id = ANY(:media_asset_ids)
                ORDER BY created_at ASC, media_asset_id ASC
                """
            ), {"clinic_id": clinic_id, "media_asset_ids": ids})).mappings())
        await engine.dispose()
        return [_map_media_asset(row) for row in rows]

    async def get_media_link(self, *, clinic_id: str, link_id: str) -> MediaLink | None:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            row = (await conn.execute(text("SELECT link_id, clinic_id, media_asset_id, owner_type, owner_id, role, visibility, sort_order, is_primary, created_at, updated_at FROM media_docs.media_links WHERE clinic_id=:clinic_id AND link_id=:link_id"), {"clinic_id": clinic_id, "link_id": link_id})).mappings().first()
        await engine.dispose()
        return _map_media_link(row) if row is not None else None

    async def attach_media(self, link: MediaLink) -> MediaLink:
        payload = asdict(link)
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            row = (await conn.execute(text("""
                INSERT INTO media_docs.media_links (
                  link_id, clinic_id, media_asset_id, owner_type, owner_id, role, visibility,
                  sort_order, is_primary, created_at, updated_at
                ) VALUES (
                  :link_id, :clinic_id, :media_asset_id, :owner_type, :owner_id, :role, :visibility,
                  :sort_order, :is_primary, COALESCE(:created_at, NOW()), COALESCE(:updated_at, NOW())
                )
                ON CONFLICT (link_id) DO UPDATE SET
                  clinic_id=EXCLUDED.clinic_id,
                  media_asset_id=EXCLUDED.media_asset_id,
                  owner_type=EXCLUDED.owner_type,
                  owner_id=EXCLUDED.owner_id,
                  role=EXCLUDED.role,
                  visibility=EXCLUDED.visibility,
                  sort_order=EXCLUDED.sort_order,
                  is_primary=EXCLUDED.is_primary,
                  created_at=media_docs.media_links.created_at,
                  updated_at=EXCLUDED.updated_at
                RETURNING link_id, clinic_id, media_asset_id, owner_type, owner_id, role, visibility, sort_order, is_primary, created_at, updated_at
            """), payload)).mappings().one()
        await engine.dispose()
        return _map_media_link(row)

    async def list_media_links(self, *, clinic_id: str, owner_type: str, owner_id: str, role: str | None = None, visibility: str | None = None) -> list[MediaLink]:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            rows = list((await conn.execute(text("""
                SELECT link_id, clinic_id, media_asset_id, owner_type, owner_id, role, visibility, sort_order, is_primary, created_at, updated_at
                FROM media_docs.media_links
                WHERE clinic_id=:clinic_id AND owner_type=:owner_type AND owner_id=:owner_id
                  AND (CAST(:role AS TEXT) IS NULL OR role=:role)
                  AND (CAST(:visibility AS TEXT) IS NULL OR visibility=:visibility)
                ORDER BY is_primary DESC, sort_order ASC, created_at ASC
            """), {"clinic_id": clinic_id, "owner_type": owner_type, "owner_id": owner_id, "role": role, "visibility": visibility})).mappings())
        await engine.dispose()
        return [_map_media_link(row) for row in rows]

    async def list_media_for_owner(self, *, clinic_id: str, owner_type: str, owner_id: str, role: str | None = None, visibility: str | None = None) -> list[tuple[MediaLink, MediaAsset]]:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            rows = list((await conn.execute(text("""
                SELECT
                  l.link_id, l.clinic_id AS link_clinic_id, l.media_asset_id, l.owner_type, l.owner_id, l.role, l.visibility,
                  l.sort_order, l.is_primary, l.created_at AS link_created_at, l.updated_at AS link_updated_at,
                  a.clinic_id AS asset_clinic_id, a.asset_kind, a.storage_provider, a.storage_ref,
                  a.content_type, a.byte_size, a.checksum_sha256, a.created_by_actor_id,
                  a.media_type, a.mime_type, a.size_bytes, a.telegram_file_id, a.telegram_file_unique_id,
                  a.object_key, a.uploaded_by_actor_id, a.created_at AS asset_created_at, a.updated_at AS asset_updated_at
                FROM media_docs.media_links l
                JOIN media_docs.media_assets a ON a.media_asset_id=l.media_asset_id
                WHERE l.clinic_id=:clinic_id AND l.owner_type=:owner_type AND l.owner_id=:owner_id
                  AND (CAST(:role AS TEXT) IS NULL OR l.role=:role)
                  AND (CAST(:visibility AS TEXT) IS NULL OR l.visibility=:visibility)
                ORDER BY l.is_primary DESC, l.sort_order ASC, l.created_at ASC
            """), {"clinic_id": clinic_id, "owner_type": owner_type, "owner_id": owner_id, "role": role, "visibility": visibility})).mappings())
        await engine.dispose()
        items: list[tuple[MediaLink, MediaAsset]] = []
        for row in rows:
            link = _map_media_link({
                "link_id": row["link_id"], "clinic_id": row["link_clinic_id"], "media_asset_id": row["media_asset_id"], "owner_type": row["owner_type"],
                "owner_id": row["owner_id"], "role": row["role"], "visibility": row["visibility"], "sort_order": row["sort_order"],
                "is_primary": row["is_primary"], "created_at": row["link_created_at"], "updated_at": row["link_updated_at"],
            })
            asset = _map_media_asset({
                "media_asset_id": row["media_asset_id"], "clinic_id": row["asset_clinic_id"], "asset_kind": row["asset_kind"], "storage_provider": row["storage_provider"],
                "storage_ref": row["storage_ref"], "content_type": row["content_type"], "byte_size": row["byte_size"], "checksum_sha256": row["checksum_sha256"],
                "created_by_actor_id": row["created_by_actor_id"], "media_type": row["media_type"], "mime_type": row["mime_type"], "size_bytes": row["size_bytes"],
                "telegram_file_id": row["telegram_file_id"], "telegram_file_unique_id": row["telegram_file_unique_id"], "object_key": row["object_key"],
                "uploaded_by_actor_id": row["uploaded_by_actor_id"], "created_at": row["asset_created_at"], "updated_at": row["asset_updated_at"],
            })
            items.append((link, asset))
        return items

    async def set_primary_media(self, *, clinic_id: str, owner_type: str, owner_id: str, role: str, link_id: str) -> MediaLink | None:
        engine = create_engine(self._db_config)
        row = None
        async with engine.begin() as conn:
            exists = (await conn.execute(text("""
                SELECT link_id FROM media_docs.media_links
                WHERE clinic_id=:clinic_id AND owner_type=:owner_type AND owner_id=:owner_id AND role=:role AND link_id=:link_id
            """), {"clinic_id": clinic_id, "owner_type": owner_type, "owner_id": owner_id, "role": role, "link_id": link_id})).mappings().first()
            if exists is not None:
                await conn.execute(text("""
                    UPDATE media_docs.media_links
                    SET is_primary=FALSE, updated_at=NOW()
                    WHERE clinic_id=:clinic_id AND owner_type=:owner_type AND owner_id=:owner_id AND role=:role
                """), {"clinic_id": clinic_id, "owner_type": owner_type, "owner_id": owner_id, "role": role})
                row = (await conn.execute(text("""
                    UPDATE media_docs.media_links
                    SET is_primary=TRUE, updated_at=NOW()
                    WHERE clinic_id=:clinic_id AND owner_type=:owner_type AND owner_id=:owner_id AND role=:role AND link_id=:link_id
                    RETURNING link_id, clinic_id, media_asset_id, owner_type, owner_id, role, visibility, sort_order, is_primary, created_at, updated_at
                """), {"clinic_id": clinic_id, "owner_type": owner_type, "owner_id": owner_id, "role": role, "link_id": link_id})).mappings().first()
        await engine.dispose()
        return _map_media_link(row) if row is not None else None

    async def remove_media_link(self, *, clinic_id: str, link_id: str) -> bool:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            result = await conn.execute(text("DELETE FROM media_docs.media_links WHERE clinic_id=:clinic_id AND link_id=:link_id"), {"clinic_id": clinic_id, "link_id": link_id})
        await engine.dispose()
        return bool(result.rowcount)
