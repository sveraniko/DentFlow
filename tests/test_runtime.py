import pytest

pytest.importorskip("aiogram")
pytest.importorskip("pydantic")
pytest.importorskip("pydantic_settings")

from app.bootstrap.runtime import RuntimeRegistry
from app.config.settings import Settings


def test_dispatcher_bootstrap(required_env) -> None:
    runtime = RuntimeRegistry(Settings())
    dispatcher = runtime.build_dispatcher()
    assert len(dispatcher.sub_routers) == 4
