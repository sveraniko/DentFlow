import pytest

pytest.importorskip("pydantic")
pytest.importorskip("pydantic_settings")

from app.worker import run_worker_once


@pytest.mark.asyncio
async def test_worker_bootstrap(required_env) -> None:
    await run_worker_once()
