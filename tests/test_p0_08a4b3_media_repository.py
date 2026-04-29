import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from app.config.settings import DatabaseConfig
from app.domain.media import MediaAsset, MediaLink
from app.infrastructure.db.bootstrap import bootstrap_database
from app.infrastructure.db.engine import create_engine
from app.infrastructure.db.media_repository import DbMediaRepository, _map_media_asset, _map_media_link

ROOT = Path(__file__).resolve().parents[1]


def test_repository_methods_exist() -> None:
    for name in [
        "get_media_asset",
        "upsert_media_asset",
        "find_media_asset_by_telegram_file_unique_id",
        "list_media_assets_by_ids",
        "get_media_link",
        "attach_media",
        "list_media_links",
        "list_media_for_owner",
        "set_primary_media",
        "remove_media_link",
    ]:
        assert hasattr(DbMediaRepository, name)


def test_mapping_helpers_support_old_and_new_fields() -> None:
    now = datetime.now(timezone.utc)
    asset = _map_media_asset({
        "media_asset_id": "m1", "clinic_id": "c1", "asset_kind": "photo", "storage_provider": "telegram", "storage_ref": "s1",
        "content_type": "image/jpeg", "byte_size": 77, "checksum_sha256": "abc", "created_by_actor_id": "a1",
        "telegram_file_id": "f1", "telegram_file_unique_id": "u1", "object_key": "obj", "uploaded_by_actor_id": "a2",
        "created_at": now, "updated_at": now,
    })
    assert isinstance(asset, MediaAsset)
    assert asset.content_type == "image/jpeg"
    assert asset.byte_size == 77
    assert asset.storage_ref == "s1"
    assert asset.telegram_file_id == "f1"
    assert asset.telegram_file_unique_id == "u1"
    assert asset.object_key == "obj"
    assert asset.uploaded_by_actor_id == "a2"
    link = _map_media_link({
        "link_id": "l1", "clinic_id": "c1", "media_asset_id": "m1", "owner_type": "patient_profile", "owner_id": "p1",
        "role": "avatar", "visibility": "staff_only", "sort_order": 1, "is_primary": True, "created_at": now, "updated_at": now,
    })
    assert isinstance(link, MediaLink)


def test_upsert_sql_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_sql: list[str] = []
    captured: list[dict[str, object]] = []

    class _FakeResult:
        def __init__(self, row):
            self._row = row

        def mappings(self):
            return self

        def one(self):
            return self._row

    class _FakeConn:
        async def execute(self, sql, params):
            seen_sql.append(str(sql))
            captured.append(params)
            now = datetime.now(timezone.utc)
            if "media_docs.media_links" in str(sql):
                row = {"link_id": "l1", "clinic_id": "c1", "media_asset_id": "m1", "owner_type": "patient_profile", "owner_id": "p1", "role": "avatar", "visibility": "staff_only", "sort_order": 0, "is_primary": False, "created_at": now, "updated_at": now}
            else:
                row = {"media_asset_id": "m1", "clinic_id": "c1", "asset_kind": "photo", "storage_provider": "telegram", "storage_ref": "s", "content_type": None, "byte_size": None, "checksum_sha256": None, "created_by_actor_id": None, "media_type": "photo", "mime_type": "image/jpeg", "size_bytes": 10, "telegram_file_id": "f", "telegram_file_unique_id": "u", "object_key": None, "uploaded_by_actor_id": None, "created_at": now, "updated_at": now}
            return _FakeResult(row)

    class _FakeBegin:
        async def __aenter__(self):
            return _FakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _FakeEngine:
        def begin(self):
            return _FakeBegin()

        async def dispose(self):
            return None

    monkeypatch.setattr("app.infrastructure.db.media_repository.create_engine", lambda _cfg: _FakeEngine())
    repo = DbMediaRepository(DatabaseConfig(dsn="postgresql+asyncpg://unused"))
    now = datetime.now(timezone.utc)
    asyncio.run(repo.upsert_media_asset(MediaAsset("m1", "c1", "photo", "telegram", "r1", media_type="photo", mime_type="image/jpeg", size_bytes=10, telegram_file_id="f", telegram_file_unique_id="u", created_at=now, updated_at=now)))
    asyncio.run(repo.attach_media(MediaLink("l1", "c1", "m1", "patient_profile", "p1", "avatar", "staff_only", created_at=now, updated_at=now)))
    merged_sql = "\n".join(seen_sql)
    assert "created_at=media_docs.media_assets.created_at" in merged_sql
    assert "updated_at=EXCLUDED.updated_at" in merged_sql
    assert "telegram_file_id" in merged_sql and "telegram_file_unique_id" in merged_sql
    assert "created_at=media_docs.media_links.created_at" in merged_sql


def test_set_primary_media_missing_link_disposes_once(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_sql: list[str] = []

    class _FakeResult:
        def mappings(self):
            return self

        def first(self):
            return None

    class _FakeConn:
        async def execute(self, sql, params):
            seen_sql.append(str(sql))
            return _FakeResult()

    class _FakeBegin:
        async def __aenter__(self):
            return _FakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _FakeEngine:
        def __init__(self) -> None:
            self.dispose_calls = 0

        def begin(self):
            return _FakeBegin()

        async def dispose(self):
            self.dispose_calls += 1
            return None

    fake_engine = _FakeEngine()
    monkeypatch.setattr("app.infrastructure.db.media_repository.create_engine", lambda _cfg: fake_engine)
    repo = DbMediaRepository(DatabaseConfig(dsn="postgresql+asyncpg://unused"))

    result = asyncio.run(
        repo.set_primary_media(
            clinic_id="c1",
            owner_type="care_product",
            owner_id="SKU-BRUSH-SOFT",
            role="product_cover",
            link_id="missing",
        )
    )

    assert result is None
    assert fake_engine.dispose_calls == 1
    assert len(seen_sql) == 1
    assert "SELECT link_id FROM media_docs.media_links" in seen_sql[0]


async def _build_repo() -> DbMediaRepository:
    dsn = os.getenv("DENTFLOW_TEST_DB_DSN")
    if not dsn:
        pytest.skip("DENTFLOW_TEST_DB_DSN is not set")
    cfg = DatabaseConfig(dsn=dsn)
    await bootstrap_database(cfg)
    engine = create_engine(cfg)
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE media_docs.media_links, media_docs.media_assets, access_identity.actor_identities, core_reference.clinics CASCADE"))
        await conn.execute(text("INSERT INTO core_reference.clinics (clinic_id, code, display_name, timezone, default_locale, status) VALUES ('c1','c1','Clinic','UTC','en','active')"))
        await conn.execute(text("INSERT INTO access_identity.actor_identities (actor_id, actor_type, display_name, status, locale) VALUES ('a1','staff','A One','active','en')"))
    await engine.dispose()
    return DbMediaRepository(cfg)


def test_db_asset_upsert_read_and_telegram_lookup() -> None:
    repo = asyncio.run(_build_repo())
    now = datetime.now(timezone.utc)
    created = asyncio.run(repo.upsert_media_asset(MediaAsset("m1", "c1", "photo", "telegram", "ref1", media_type="photo", mime_type="image/jpeg", size_bytes=111, telegram_file_id="file_abc", telegram_file_unique_id="unique_abc", object_key="obj1", uploaded_by_actor_id="a1", created_at=now, updated_at=now)))
    fetched = asyncio.run(repo.get_media_asset(clinic_id="c1", media_asset_id="m1"))
    by_unique = asyncio.run(repo.find_media_asset_by_telegram_file_unique_id(clinic_id="c1", telegram_file_unique_id="unique_abc"))
    updated = asyncio.run(repo.upsert_media_asset(MediaAsset("m1", "c1", "photo", "telegram", "ref1", media_type="photo", mime_type="image/webp", size_bytes=111, telegram_file_id="file_abc", telegram_file_unique_id="unique_abc", object_key="obj2", uploaded_by_actor_id="a1", created_at=now, updated_at=datetime.now(timezone.utc))))
    assert created.media_asset_id == "m1"
    assert fetched is not None and fetched.telegram_file_id == "file_abc"
    assert by_unique is not None and by_unique.media_asset_id == "m1"
    assert updated.mime_type == "image/webp" and updated.object_key == "obj2"


def test_db_links_owner_list_primary_remove_and_join() -> None:
    repo = asyncio.run(_build_repo())
    now = datetime.now(timezone.utc)
    asyncio.run(repo.upsert_media_asset(MediaAsset("m10", "c1", "photo", "telegram", "ref10", media_type="photo", mime_type="image/jpeg", created_at=now, updated_at=now)))
    asyncio.run(repo.upsert_media_asset(MediaAsset("m11", "c1", "photo", "telegram", "ref11", media_type="photo", mime_type="image/jpeg", created_at=now, updated_at=now)))
    asyncio.run(repo.attach_media(MediaLink("l10", "c1", "m10", "care_product", "SKU-BRUSH-SOFT", "product_cover", "public", 0, True, now, now)))
    asyncio.run(repo.attach_media(MediaLink("l11", "c1", "m11", "care_product", "SKU-BRUSH-SOFT", "product_cover", "public", 1, False, now, now)))
    links = asyncio.run(repo.list_media_links(clinic_id="c1", owner_type="care_product", owner_id="SKU-BRUSH-SOFT", role="product_cover"))
    selected = asyncio.run(repo.set_primary_media(clinic_id="c1", owner_type="care_product", owner_id="SKU-BRUSH-SOFT", role="product_cover", link_id="l11"))
    links_after = asyncio.run(repo.list_media_links(clinic_id="c1", owner_type="care_product", owner_id="SKU-BRUSH-SOFT", role="product_cover"))
    joined = asyncio.run(repo.list_media_for_owner(clinic_id="c1", owner_type="care_product", owner_id="SKU-BRUSH-SOFT", role="product_cover"))
    deleted = asyncio.run(repo.remove_media_link(clinic_id="c1", link_id="l10"))
    still_asset = asyncio.run(repo.get_media_asset(clinic_id="c1", media_asset_id="m10"))
    assert links[0].is_primary is True
    assert selected is not None and selected.link_id == "l11" and selected.is_primary is True
    assert sum(1 for l in links_after if l.is_primary) == 1 and links_after[0].link_id == "l11"
    assert len(joined) == 2 and isinstance(joined[0][0], MediaLink) and isinstance(joined[0][1], MediaAsset)
    assert deleted is True
    assert still_asset is not None


def test_db_set_primary_media_missing_link_returns_none_and_preserves_existing() -> None:
    repo = asyncio.run(_build_repo())
    now = datetime.now(timezone.utc)
    asyncio.run(repo.upsert_media_asset(MediaAsset("m20", "c1", "photo", "telegram", "ref20", media_type="photo", mime_type="image/jpeg", created_at=now, updated_at=now)))
    asyncio.run(repo.upsert_media_asset(MediaAsset("m21", "c1", "photo", "telegram", "ref21", media_type="photo", mime_type="image/jpeg", created_at=now, updated_at=now)))
    asyncio.run(repo.attach_media(MediaLink("l20", "c1", "m20", "care_product", "SKU-PASTE-MINT", "product_cover", "public", 0, True, now, now)))
    asyncio.run(repo.attach_media(MediaLink("l21", "c1", "m21", "care_product", "SKU-PASTE-MINT", "product_cover", "public", 1, False, now, now)))

    before = asyncio.run(repo.list_media_links(clinic_id="c1", owner_type="care_product", owner_id="SKU-PASTE-MINT", role="product_cover"))
    result = asyncio.run(repo.set_primary_media(clinic_id="c1", owner_type="care_product", owner_id="SKU-PASTE-MINT", role="product_cover", link_id="missing-link"))
    after = asyncio.run(repo.list_media_links(clinic_id="c1", owner_type="care_product", owner_id="SKU-PASTE-MINT", role="product_cover"))

    assert result is None
    assert [link.is_primary for link in before] == [link.is_primary for link in after]
    assert [link.link_id for link in before] == [link.link_id for link in after]


def test_no_alembic_versions_added() -> None:
    assert not (ROOT / "alembic/versions").exists()
