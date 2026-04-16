import pytest

pytest.importorskip("aiogram")

import inspect

from app.bootstrap import runtime


def test_runtime_has_no_auto_seed_hook() -> None:
    source = inspect.getsource(runtime)
    assert "SeedBootstrap" not in source
    assert "stack1_seed.json" not in source
