import pytest

pytest.importorskip("pydantic")
pytest.importorskip("pydantic_settings")

from app.application.policy import InMemoryPolicyRepository
from app.worker import run_worker_once


def test_worker_bootstrap(required_env, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    from types import SimpleNamespace

    calls: list[str] = []

    async def _policy(_):
        calls.append("policy")
        return InMemoryPolicyRepository()

    async def _task(*, service, batch_limit):  # type: ignore[no-untyped-def]
        return 0

    import app.worker as worker_module

    monkeypatch.setattr(worker_module.DbPolicyRepository, "load", _policy)
    monkeypatch.setattr(worker_module, "DbReminderJobRepository", lambda _: SimpleNamespace())
    monkeypatch.setattr(worker_module, "DbBookingRepository", lambda _: SimpleNamespace())
    monkeypatch.setattr(worker_module, "DbTelegramReminderRecipientResolver", lambda _: SimpleNamespace())
    monkeypatch.setattr(worker_module, "AiogramTelegramReminderSender", lambda _: SimpleNamespace())
    monkeypatch.setattr(worker_module, "run_reminder_delivery_once", _task)
    monkeypatch.setattr(worker_module, "run_reminder_recovery_once", _task)
    asyncio.run(run_worker_once())
    assert calls == ["policy"]


def test_telegram_delivery_module_import_has_no_eager_aiogram_dependency(monkeypatch) -> None:
    import builtins
    import importlib
    import sys

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
        if name == "aiogram":
            raise RuntimeError("aiogram import should be lazy")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    sys.modules.pop("app.infrastructure.communication.telegram_delivery", None)
    module = importlib.import_module("app.infrastructure.communication.telegram_delivery")
    assert hasattr(module, "AiogramTelegramReminderSender")



def test_worker_mode_dispatch_projector(required_env, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    called: list[str] = []

    async def _projector() -> None:
        called.append("projector")

    async def _reminder() -> None:
        called.append("reminder")

    monkeypatch.setenv("WORKER_MODE", "projector")
    monkeypatch.setattr("app.worker.run_projector_worker_forever", _projector)
    monkeypatch.setattr("app.worker.run_reminder_worker_forever", _reminder)

    from app.worker import run_worker_forever

    asyncio.run(run_worker_forever())
    assert called == ["projector"]


def test_worker_mode_dispatch_reminder(required_env, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    called: list[str] = []

    async def _projector() -> None:
        called.append("projector")

    async def _reminder() -> None:
        called.append("reminder")

    monkeypatch.setenv("WORKER_MODE", "reminder")
    monkeypatch.setattr("app.worker.run_projector_worker_forever", _projector)
    monkeypatch.setattr("app.worker.run_reminder_worker_forever", _reminder)

    from app.worker import run_worker_forever

    asyncio.run(run_worker_forever())
    assert called == ["reminder"]


def test_worker_mode_dispatch_invalid(required_env, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    monkeypatch.setenv("WORKER_MODE", "oops")

    from app.worker import run_worker_forever

    with pytest.raises(ValueError):
        asyncio.run(run_worker_forever())
