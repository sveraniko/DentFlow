import pytest

pytest.importorskip("sqlalchemy")

from app.infrastructure.db import bootstrap as db_bootstrap


class _Conn:
    def __init__(self) -> None:
        self.executed: list[str] = []

    async def execute(self, statement) -> None:
        self.executed.append(str(statement))


class _BeginCtx:
    def __init__(self, conn: _Conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Engine:
    def __init__(self) -> None:
        self.conn = _Conn()

    def begin(self):
        return _BeginCtx(self.conn)

    async def dispose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_db_bootstrap_creates_all_schemas(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _Engine()
    monkeypatch.setattr(db_bootstrap, "create_engine", lambda config: engine)

    await db_bootstrap.bootstrap_database(object())

    assert len(engine.conn.executed) == len(db_bootstrap.SCHEMAS)
    assert "core_patient" in " ".join(engine.conn.executed)
    assert "owner_views" in " ".join(engine.conn.executed)
