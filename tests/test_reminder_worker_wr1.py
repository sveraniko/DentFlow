from __future__ import annotations

import asyncio

import pytest

from app.infrastructure.workers.reminder_runtime import (
    ReminderWorkerBatchResult,
    ReminderWorkerConfig,
    ReminderWorkerRuntime,
)


class _FakeRunner:
    def __init__(self, *, results: list[ReminderWorkerBatchResult], stop_event: asyncio.Event | None = None) -> None:
        self._results = results
        self._stop_event = stop_event
        self.calls = 0
        self.delivery_limits: list[int] = []
        self.recovery_limits: list[int] = []

    async def run_once(self, *, delivery_batch_limit: int, recovery_batch_limit: int) -> ReminderWorkerBatchResult:
        self.calls += 1
        self.delivery_limits.append(delivery_batch_limit)
        self.recovery_limits.append(recovery_batch_limit)
        if self.calls - 1 < len(self._results):
            return self._results[self.calls - 1]
        if self._stop_event is not None:
            self._stop_event.set()
        return ReminderWorkerBatchResult(delivery_claimed=0, recovery_processed=0)


def test_reminder_worker_startup_catchup_is_bounded() -> None:
    stop_event = asyncio.Event()
    runner = _FakeRunner(
        results=[
            ReminderWorkerBatchResult(delivery_claimed=2, recovery_processed=1),
            ReminderWorkerBatchResult(delivery_claimed=1, recovery_processed=1),
            ReminderWorkerBatchResult(delivery_claimed=1, recovery_processed=0),
        ],
        stop_event=stop_event,
    )
    runtime = ReminderWorkerRuntime(
        runner=runner,  # type: ignore[arg-type]
        config=ReminderWorkerConfig(
            delivery_batch_limit=5,
            recovery_batch_limit=7,
            poll_interval_sec=0.01,
            startup_catchup_max_batches=2,
        ),
        stop_event=stop_event,
    )

    asyncio.run(runtime.run_forever())
    assert runner.calls == 4
    assert runner.delivery_limits == [5, 5, 5, 5]
    assert runner.recovery_limits == [7, 7, 7, 7]


def test_reminder_worker_graceful_shutdown_stops_at_batch_boundary() -> None:
    stop_event = asyncio.Event()

    class _BoundaryRunner(_FakeRunner):
        async def run_once(self, *, delivery_batch_limit: int, recovery_batch_limit: int) -> ReminderWorkerBatchResult:
            self.calls += 1
            self.delivery_limits.append(delivery_batch_limit)
            self.recovery_limits.append(recovery_batch_limit)
            await asyncio.sleep(0.02)
            return ReminderWorkerBatchResult(delivery_claimed=1, recovery_processed=1)

    runner = _BoundaryRunner(results=[])
    runtime = ReminderWorkerRuntime(
        runner=runner,  # type: ignore[arg-type]
        config=ReminderWorkerConfig(
            delivery_batch_limit=3,
            recovery_batch_limit=4,
            poll_interval_sec=0.01,
            startup_catchup_max_batches=1,
        ),
        stop_event=stop_event,
    )

    async def _run() -> None:
        task = asyncio.create_task(runtime.run_forever())
        await asyncio.sleep(0.005)
        stop_event.set()
        await task

    asyncio.run(_run())
    assert runner.calls == 1


@pytest.mark.parametrize(
    ("results", "expected_calls"),
    [([ReminderWorkerBatchResult(delivery_claimed=0, recovery_processed=0)], 1), ([ReminderWorkerBatchResult(delivery_claimed=1, recovery_processed=0), ReminderWorkerBatchResult(delivery_claimed=0, recovery_processed=0)], 2)],
)
def test_reminder_worker_startup_catchup_stops_when_backlog_drained(
    results: list[ReminderWorkerBatchResult],
    expected_calls: int,
) -> None:
    stop_event = asyncio.Event()
    runner = _FakeRunner(results=results, stop_event=stop_event)
    runtime = ReminderWorkerRuntime(
        runner=runner,  # type: ignore[arg-type]
        config=ReminderWorkerConfig(
            delivery_batch_limit=2,
            recovery_batch_limit=2,
            poll_interval_sec=0.01,
            startup_catchup_max_batches=10,
        ),
        stop_event=stop_event,
    )
    asyncio.run(runtime._run_startup_catchup())
    assert runner.calls == expected_calls
