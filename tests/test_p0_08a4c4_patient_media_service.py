from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace

import pytest

from app.application.patient.media import PatientMediaService
from app.domain.media import MediaAsset, MediaLink


def run(coro):
    return asyncio.run(coro)


@dataclass
class FakeMediaRepo:
    assets: dict[tuple[str, str], MediaAsset] = field(default_factory=dict)
    by_unique: dict[tuple[str, str], str] = field(default_factory=dict)
    links: dict[tuple[str, str], MediaLink] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    async def get_media_asset(self, *, clinic_id: str, media_asset_id: str):
        self.calls.append("get_media_asset")
        return self.assets.get((clinic_id, media_asset_id))

    async def upsert_media_asset(self, asset: MediaAsset):
        self.calls.append("upsert_media_asset")
        self.assets[(asset.clinic_id, asset.media_asset_id)] = asset
        if asset.telegram_file_unique_id:
            self.by_unique[(asset.clinic_id, asset.telegram_file_unique_id)] = asset.media_asset_id
        return asset

    async def find_media_asset_by_telegram_file_unique_id(self, *, clinic_id: str, telegram_file_unique_id: str):
        self.calls.append("find_media_asset_by_telegram_file_unique_id")
        aid = self.by_unique.get((clinic_id, telegram_file_unique_id))
        return self.assets.get((clinic_id, aid)) if aid else None

    async def list_media_assets_by_ids(self, *, clinic_id: str, media_asset_ids: list[str]):
        self.calls.append("list_media_assets_by_ids")
        return [self.assets[(clinic_id, i)] for i in media_asset_ids if (clinic_id, i) in self.assets]

    async def get_media_link(self, *, clinic_id: str, link_id: str):
        self.calls.append("get_media_link")
        return self.links.get((clinic_id, link_id))

    async def attach_media(self, link: MediaLink):
        self.calls.append("attach_media")
        self.links[(link.clinic_id, link.link_id)] = link
        return link

    async def list_media_links(self, *, clinic_id: str, owner_type: str, owner_id: str, role: str | None = None, visibility: str | None = None):
        self.calls.append("list_media_links")
        out = [l for (c, _), l in self.links.items() if c == clinic_id and l.owner_type == owner_type and l.owner_id == owner_id]
        if role is not None:
            out = [l for l in out if l.role == role]
        if visibility is not None:
            out = [l for l in out if l.visibility == visibility]
        return out

    async def list_media_for_owner(self, *, clinic_id: str, owner_type: str, owner_id: str, role: str | None = None, visibility: str | None = None):
        self.calls.append("list_media_for_owner")
        links = await self.list_media_links(clinic_id=clinic_id, owner_type=owner_type, owner_id=owner_id, role=role, visibility=visibility)
        links = sorted(links, key=lambda x: (not x.is_primary, x.sort_order))
        return [(l, self.assets[(clinic_id, l.media_asset_id)]) for l in links]

    async def set_primary_media(self, *, clinic_id: str, owner_type: str, owner_id: str, role: str, link_id: str):
        self.calls.append("set_primary_media")
        selected = self.links.get((clinic_id, link_id))
        if selected is None:
            return None
        for k, link in list(self.links.items()):
            if k[0] == clinic_id and link.owner_type == owner_type and link.owner_id == owner_id and link.role == role:
                self.links[k] = replace(link, is_primary=False)
        self.links[(clinic_id, link_id)] = replace(selected, is_primary=True)
        return self.links[(clinic_id, link_id)]

    async def remove_media_link(self, *, clinic_id: str, link_id: str):
        self.calls.append("remove_media_link")
        return self.links.pop((clinic_id, link_id), None) is not None


def test_service_exists_and_methods_exist() -> None:
    service = PatientMediaService(FakeMediaRepo())
    for method in ["register_telegram_asset", "attach_media_to_owner", "register_and_attach_telegram_media", "list_owner_media", "set_primary_owner_media", "remove_owner_media_link", "get_patient_avatar", "get_product_cover"]:
        assert hasattr(service, method)


def test_register_telegram_asset_behaviors() -> None:
    repo = FakeMediaRepo()
    service = PatientMediaService(repo, id_factory=lambda prefix: f"{prefix}_id")
    created = run(service.register_telegram_asset(clinic_id="c1", telegram_file_id="f1", telegram_file_unique_id="u1", media_type="photo", mime_type="image/jpeg", size_bytes=12))
    assert created.storage_provider == "telegram" and created.telegram_file_id == "f1"
    existing = run(service.register_telegram_asset(clinic_id="c1", telegram_file_id="f2", telegram_file_unique_id="u1", media_type="photo", mime_type="image/webp", size_bytes=20))
    assert existing.media_asset_id == "media_id" and existing.mime_type == "image/webp" and "Bot" not in " ".join(repo.calls)
    with pytest.raises(ValueError): run(service.register_telegram_asset(clinic_id="c1", telegram_file_id="", telegram_file_unique_id="u", media_type="photo"))
    with pytest.raises(ValueError): run(service.register_telegram_asset(clinic_id="c1", telegram_file_id="f", telegram_file_unique_id="", media_type="photo"))
    with pytest.raises(ValueError): run(service.register_telegram_asset(clinic_id="c1", telegram_file_id="f", telegram_file_unique_id="u2", media_type="audio"))
    with pytest.raises(ValueError): run(service.register_telegram_asset(clinic_id="c1", telegram_file_id="f", telegram_file_unique_id="u2", media_type="photo", size_bytes=-1))


def test_attach_media_defaults_and_primary() -> None:
    repo = FakeMediaRepo()
    service = PatientMediaService(repo, id_factory=lambda prefix: f"{prefix}_x")
    run(repo.upsert_media_asset(MediaAsset("m1", "c1", "photo", "telegram", "r1")))
    cover = run(service.attach_media_to_owner(clinic_id="c1", media_asset_id="m1", owner_type="care_product", owner_id="p1", role="product_cover"))
    assert cover.visibility == "patient_visible" and cover.is_primary is True and "set_primary_media" in repo.calls
    avatar = run(service.attach_media_to_owner(clinic_id="c1", media_asset_id="m1", owner_type="patient_profile", owner_id="pat1", role="patient_avatar"))
    assert avatar.visibility == "staff_only" and avatar.is_primary is True
    gallery = run(service.attach_media_to_owner(clinic_id="c1", media_asset_id="m1", owner_type="care_product", owner_id="p1", role="product_gallery"))
    assert gallery.is_primary is False
    clinical = run(service.attach_media_to_owner(clinic_id="c1", media_asset_id="m1", owner_type="booking", owner_id="b1", role="clinical_photo"))
    assert clinical.visibility == "doctor_only"


def test_invalid_owner_role_combos_and_visibility() -> None:
    repo = FakeMediaRepo(); run(repo.upsert_media_asset(MediaAsset("m1", "c1", "photo", "telegram", "r1")))
    service = PatientMediaService(repo)
    with pytest.raises(ValueError): run(service.attach_media_to_owner(clinic_id="c1", media_asset_id="m1", owner_type="care_product", owner_id="x", role="patient_avatar"))
    with pytest.raises(ValueError): run(service.attach_media_to_owner(clinic_id="c1", media_asset_id="m1", owner_type="patient_profile", owner_id="x", role="product_cover"))
    with pytest.raises(ValueError): run(service.attach_media_to_owner(clinic_id="c1", media_asset_id="m1", owner_type="care_order", owner_id="x", role="clinical_photo"))
    with pytest.raises(ValueError): run(service.attach_media_to_owner(clinic_id="c1", media_asset_id="m1", owner_type="care_product", owner_id="x", role="product_cover", visibility="public"))


def test_register_and_attach_order_and_ids() -> None:
    repo = FakeMediaRepo(); ids = iter(["media_det", "mlink_det"])
    service = PatientMediaService(repo, id_factory=lambda _p: next(ids))
    asset, link = run(service.register_and_attach_telegram_media(clinic_id="c1", telegram_file_id="f1", telegram_file_unique_id="u1", media_type="photo", owner_type="care_product", owner_id="pr1", role="product_cover"))
    assert asset.media_asset_id == "media_det" and link.link_id == "mlink_det"
    assert repo.calls[:4] == ["find_media_asset_by_telegram_file_unique_id", "upsert_media_asset", "get_media_asset", "attach_media"]


def test_list_set_primary_remove_and_helpers() -> None:
    repo = FakeMediaRepo(); service = PatientMediaService(repo)
    run(repo.upsert_media_asset(MediaAsset("m1", "c1", "photo", "telegram", "r1")))
    run(repo.upsert_media_asset(MediaAsset("m2", "c1", "photo", "telegram", "r2")))
    run(service.attach_media_to_owner(clinic_id="c1", media_asset_id="m1", owner_type="patient_profile", owner_id="pat1", role="patient_avatar", link_id="l1"))
    run(service.attach_media_to_owner(clinic_id="c1", media_asset_id="m2", owner_type="care_product", owner_id="prod1", role="product_cover", link_id="l2"))
    listed = run(service.list_owner_media(clinic_id="c1", owner_type="patient_profile", owner_id="pat1"))
    assert isinstance(listed, tuple)
    assert run(service.set_primary_owner_media(clinic_id="c1", owner_type="patient_profile", owner_id="pat1", role="patient_avatar", link_id="l1")) is not None
    assert run(service.remove_owner_media_link(clinic_id="c1", link_id="l1")) is True
    assert ("c1", "m1") in repo.assets
    assert run(service.get_patient_avatar(clinic_id="c1", patient_id="pat1")) is None
    assert run(service.get_product_cover(clinic_id="c1", product_id="prod1")) is not None
