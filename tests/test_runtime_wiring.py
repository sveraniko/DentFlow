import asyncio

import pytest

pytest.importorskip("aiogram")
pytest.importorskip("sqlalchemy")

from types import SimpleNamespace
from app.bootstrap.runtime import RuntimeRegistry
from app.config.settings import Settings
from app.infrastructure.db import patient_repository
from app.infrastructure.db import repositories
from app.interfaces.cards import InMemoryRedis


def test_runtime_wiring_loads_db_repositories(monkeypatch: pytest.MonkeyPatch, required_env: None) -> None:
    calls: list[str] = []

    async def _load_clinic(_):
        calls.append("clinic")
        return SimpleNamespace()

    async def _load_access(_):
        calls.append("access")
        return SimpleNamespace()

    async def _load_policy(_):
        calls.append("policy")
        return SimpleNamespace()

    async def _load_patients(_):
        calls.append("patients")
        return SimpleNamespace()

    monkeypatch.setattr(repositories.DbClinicReferenceRepository, "load", _load_clinic)
    monkeypatch.setattr(repositories.DbAccessRepository, "load", _load_access)
    monkeypatch.setattr(repositories.DbPolicyRepository, "load", _load_policy)
    monkeypatch.setattr(patient_repository.DbPatientRegistryRepository, "load", _load_patients)

    runtime = RuntimeRegistry(Settings())
    assert calls == ["clinic", "access", "policy", "patients"]
    assert runtime.card_runtime is not None
    assert runtime.card_callback_codec is not None


def test_runtime_wiring_uses_configured_redis_runtime_adapter(monkeypatch: pytest.MonkeyPatch, required_env: None) -> None:
    async def _load_stub(_):
        return SimpleNamespace()

    monkeypatch.setattr(repositories.DbClinicReferenceRepository, "load", _load_stub)
    monkeypatch.setattr(repositories.DbAccessRepository, "load", _load_stub)
    monkeypatch.setattr(repositories.DbPolicyRepository, "load", _load_stub)
    monkeypatch.setattr(patient_repository.DbPatientRegistryRepository, "load", _load_stub)

    redis_client = InMemoryRedis()
    monkeypatch.setattr("app.bootstrap.runtime.build_card_runtime_redis", lambda _settings: redis_client)

    runtime = RuntimeRegistry(Settings())
    payload = {"entity_id": "p1", "state_token": "rev-1"}
    token = asyncio.run(runtime.card_runtime.store_callback(payload))
    resolved = asyncio.run(runtime.card_runtime.resolve_callback(token))
    assert resolved == payload
