import pytest

pytest.importorskip("aiogram")
pytest.importorskip("sqlalchemy")

from types import SimpleNamespace
from app.bootstrap.runtime import RuntimeRegistry
from app.config.settings import Settings
from app.infrastructure.db import patient_repository
from app.infrastructure.db import repositories


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

    RuntimeRegistry(Settings())
    assert calls == ["clinic", "access", "policy", "patients"]
