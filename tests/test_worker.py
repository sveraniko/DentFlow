import pytest

pytest.importorskip("pydantic")
pytest.importorskip("pydantic_settings")

from app.worker import ReminderWorkerServices, run_worker_once


def test_worker_bootstrap(required_env, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    from types import SimpleNamespace

    calls: list[tuple[str, object]] = []

    async def _build_services(_settings):
        calls.append(("build_services", None))
        return ReminderWorkerServices(delivery=SimpleNamespace(name="delivery"), recovery=SimpleNamespace(name="recovery"))

    def _configure_logging(_logging):
        calls.append(("configure_logging", None))

    async def _heartbeat() -> None:
        calls.append(("heartbeat", None))

    async def _task(*, service, batch_limit):  # type: ignore[no-untyped-def]
        calls.append(("task", (service.name, batch_limit)))
        return 0

    import app.worker as worker_module

    monkeypatch.setenv("REMINDER_DELIVERY_BATCH_LIMIT", "7")
    monkeypatch.setattr(worker_module, "configure_logging", _configure_logging)
    monkeypatch.setattr(worker_module, "build_reminder_worker_services", _build_services)
    monkeypatch.setattr(worker_module, "placeholder_heartbeat_task", _heartbeat)
    monkeypatch.setattr(worker_module, "run_reminder_delivery_once", _task)
    monkeypatch.setattr(worker_module, "run_reminder_recovery_once", _task)

    asyncio.run(run_worker_once())

    assert calls == [
        ("configure_logging", None),
        ("build_services", None),
        ("heartbeat", None),
        ("task", ("delivery", 7)),
        ("task", ("recovery", 7)),
    ]


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


def test_worker_mode_dispatch_all(required_env, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    called: list[str] = []

    async def _projector() -> None:
        called.append("projector")

    async def _reminder() -> None:
        called.append("reminder")

    monkeypatch.setenv("WORKER_MODE", "all")
    monkeypatch.setattr("app.worker.run_projector_worker_forever", _projector)
    monkeypatch.setattr("app.worker.run_reminder_worker_forever", _reminder)

    from app.worker import run_worker_forever

    asyncio.run(run_worker_forever())
    assert sorted(called) == ["projector", "reminder"]


def test_worker_mode_dispatch_invalid(required_env, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    monkeypatch.setenv("WORKER_MODE", "oops")

    from app.worker import run_worker_forever

    with pytest.raises(ValueError):
        asyncio.run(run_worker_forever())
