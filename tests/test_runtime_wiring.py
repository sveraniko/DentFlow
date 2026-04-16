import pytest

pytest.importorskip("aiogram")

import inspect

from app.bootstrap.runtime import RuntimeRegistry


def test_runtime_wiring_uses_db_repositories() -> None:
    source = inspect.getsource(RuntimeRegistry)
    assert "DbClinicReferenceRepository.load" in source
    assert "DbAccessRepository.load" in source
    assert "DbPolicyRepository.load" in source
