import pytest

pytest.importorskip("aiogram")
pytest.importorskip("pydantic")
pytest.importorskip("pydantic_settings")

from app.application.access import InMemoryAccessRepository
from app.application.clinic_reference import InMemoryClinicReferenceRepository
from app.application.policy import InMemoryPolicyRepository
from app.bootstrap.runtime import RuntimeRegistry
from app.config.settings import Settings


def test_dispatcher_bootstrap(required_env, monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"clinic": 0, "access": 0, "policy": 0}

    async def _clinic(_):
        called["clinic"] += 1
        return InMemoryClinicReferenceRepository()

    async def _access(_):
        called["access"] += 1
        return InMemoryAccessRepository()

    async def _policy(_):
        called["policy"] += 1
        return InMemoryPolicyRepository()

    monkeypatch.setattr("app.bootstrap.runtime.DbClinicReferenceRepository.load", _clinic)
    monkeypatch.setattr("app.bootstrap.runtime.DbAccessRepository.load", _access)
    monkeypatch.setattr("app.bootstrap.runtime.DbPolicyRepository.load", _policy)

    runtime = RuntimeRegistry(Settings())
    dispatcher = runtime.build_dispatcher()
    assert len(dispatcher.sub_routers) == 4
    assert called == {"clinic": 1, "access": 1, "policy": 1}
    assert runtime.booking_service is not None
    assert runtime.booking_patient_resolution_service is not None
