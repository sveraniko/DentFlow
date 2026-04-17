import pytest

pytest.importorskip("pydantic")
pytest.importorskip("pydantic_settings")

from app.worker import run_worker_once


def test_worker_bootstrap(required_env) -> None:
    import asyncio

    asyncio.run(run_worker_once())


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
