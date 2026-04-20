from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.infrastructure.db.reminder_worker_runtime_repository import ReminderWorkerHealthInspector
from app.infrastructure.workers.reminder_runtime import ReminderWorkerBatchResult, ReminderWorkerConfig, ReminderWorkerRuntime


class _FakeRunner:
    def __init__(self, results: list[ReminderWorkerBatchResult | Exception], stop_event: asyncio.Event | None = None) -> None:
        self._results = results
        self._stop_event = stop_event
        self.calls = 0

    async def run_once(self, *, delivery_batch_limit: int, recovery_batch_limit: int) -> ReminderWorkerBatchResult:
        self.calls += 1
        if self.calls - 1 < len(self._results):
            item = self._results[self.calls - 1]
            if isinstance(item, Exception):
                raise item
            return item
        if self._stop_event is not None:
            self._stop_event.set()
        return ReminderWorkerBatchResult(delivery_claimed=0, recovery_processed=0)


@dataclass
class _Status:
    worker_name: str
    owner_token: str
    mode: str
    heartbeat_at: datetime | None
    last_success_at: datetime | None
    last_error_at: datetime | None
    last_error_text: str | None
    lease_owner_token: str | None
    lease_expires_at: datetime | None


class _FakeOps:
    def __init__(self, *, lease_grants: list[bool]) -> None:
        self.lease_grants = lease_grants
        self.lease_calls = 0
        self.status_calls: list[tuple[str, str]] = []
        self.release_calls = 0

    async def try_acquire_or_renew_lease(self, *, lease_name: str, owner_token: str, now: datetime, ttl: timedelta) -> bool:
        if self.lease_calls < len(self.lease_grants):
            value = self.lease_grants[self.lease_calls]
        else:
            value = self.lease_grants[-1]
        self.lease_calls += 1
        return value

    async def release_lease(self, *, lease_name: str, owner_token: str, now: datetime) -> None:
        self.release_calls += 1

    async def upsert_worker_status(
        self,
        *,
        worker_name: str,
        owner_token: str,
        mode: str,
        heartbeat_at: datetime,
        last_success_at: datetime | None = None,
        last_error_at: datetime | None = None,
        last_error_text: str | None = None,
    ) -> None:
        self.status_calls.append((mode, "success" if last_success_at else "error" if last_error_at else "heartbeat"))


def test_wr2_lease_blocks_duplicate_processing() -> None:
    stop_event = asyncio.Event()
    runner = _FakeRunner(results=[ReminderWorkerBatchResult(delivery_claimed=1, recovery_processed=0)], stop_event=stop_event)
    ops = _FakeOps(lease_grants=[False, True, True])
    runtime = ReminderWorkerRuntime(
        runner=runner,  # type: ignore[arg-type]
        config=ReminderWorkerConfig(poll_interval_sec=0.01, startup_catchup_max_batches=1),
        ops=ops,
        owner_token="worker-a",
        stop_event=stop_event,
    )

    asyncio.run(runtime.run_forever())
    assert runner.calls >= 1
    assert ops.lease_calls >= 2
    assert ("standby", "heartbeat") in ops.status_calls
    assert ops.release_calls == 1


def test_wr2_error_batches_trigger_cooldown_and_status_error() -> None:
    stop_event = asyncio.Event()

    async def _run() -> None:
        await asyncio.sleep(0.03)
        stop_event.set()

    runner = _FakeRunner(results=[RuntimeError("boom"), RuntimeError("boom2")], stop_event=stop_event)
    ops = _FakeOps(lease_grants=[True, True, True])
    runtime = ReminderWorkerRuntime(
        runner=runner,  # type: ignore[arg-type]
        config=ReminderWorkerConfig(
            poll_interval_sec=0.01,
            startup_catchup_max_batches=1,
            max_consecutive_error_batches=1,
            error_cooldown_sec=0.01,
        ),
        ops=ops,
        owner_token="worker-a",
        stop_event=stop_event,
    )

    async def _main() -> None:
        worker_task = asyncio.create_task(runtime.run_forever())
        stopper_task = asyncio.create_task(_run())
        await asyncio.gather(worker_task, stopper_task)

    asyncio.run(_main())
    assert any(kind == "error" for _, kind in ops.status_calls)


def test_wr2_health_inspection_detects_stale_worker() -> None:
    class _Repo:
        async def get_worker_status_view(self, *, worker_name: str, lease_name: str):
            now = datetime.now(timezone.utc)
            return _Status(
                worker_name="reminder",
                owner_token="worker-a",
                mode="active",
                heartbeat_at=now - timedelta(seconds=300),
                last_success_at=now - timedelta(seconds=301),
                last_error_at=None,
                last_error_text=None,
                lease_owner_token="worker-a",
                lease_expires_at=now - timedelta(seconds=1),
            )

    inspector = ReminderWorkerHealthInspector(_Repo())  # type: ignore[arg-type]
    health = asyncio.run(inspector.inspect())
    assert health.status == "unhealthy"
