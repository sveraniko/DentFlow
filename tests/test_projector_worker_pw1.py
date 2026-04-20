from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.config.settings import Settings
from app.domain.events import build_event
from app.projections.runtime import (
    ProjectorRunResult,
    ProjectorRunner,
    ProjectorWorkerConfig,
    ProjectorWorkerRuntime,
    ProjectorRegistry,
    RegisteredProjector,
    build_default_projector_registry,
)


@dataclass
class _DummyProjector:
    name: str

    async def handle(self, event, outbox_event_id: int) -> bool:  # noqa: ANN001
        return True


class _CheckpointRepo:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    async def get_checkpoint(self, *, projector_name: str) -> int:
        return self.values.get(projector_name, 0)

    async def save_checkpoint(self, *, projector_name: str, last_outbox_event_id: int) -> None:
        self.values[projector_name] = last_outbox_event_id


class _OutboxRepo:
    def __init__(self, rows):
        self.rows = rows
        self.processed: list[int] = []
        self.failed: list[tuple[int, str]] = []

    async def list_after(self, *, last_outbox_event_id: int, limit: int = 200):
        return [r for r in self.rows if r["outbox_event_id"] > last_outbox_event_id][:limit]

    async def mark_event_processed(self, *, outbox_event_id: int):
        self.processed.append(outbox_event_id)

    async def mark_event_failed(self, *, outbox_event_id: int, error_text: str):
        self.failed.append((outbox_event_id, error_text))


class _FakeRunner:
    def __init__(self, *, results: list[ProjectorRunResult], stop_event: asyncio.Event | None = None) -> None:
        self._results = results
        self.calls = 0
        self.limits: list[int] = []
        self.projectors = (_DummyProjector("analytics.event_ledger"),)
        self._stop_event = stop_event

    async def run_once(self, *, limit: int = 200) -> ProjectorRunResult:
        self.calls += 1
        self.limits.append(limit)
        if self.calls - 1 < len(self._results):
            return self._results[self.calls - 1]
        if self._stop_event is not None:
            self._stop_event.set()
        return ProjectorRunResult(scanned_events=0, handled_by_projector={"analytics.event_ledger": 0})


def test_projector_registry_registration_and_lookup(required_env) -> None:
    settings = Settings()
    registry = ProjectorRegistry()
    registry.register(
        RegisteredProjector(
            name="analytics.event_ledger",
            factory=lambda _settings: _DummyProjector("analytics.event_ledger"),
        )
    )
    assert registry.names() == ("analytics.event_ledger",)
    built = registry.build_projectors(settings)
    assert len(built) == 1
    assert built[0].name == "analytics.event_ledger"


def test_default_registry_contains_pw2_key_projectors(required_env) -> None:
    registry = build_default_projector_registry()
    assert registry.names() == (
        "analytics.event_ledger",
        "admin.workdesk",
        "owner.daily_metrics",
        "integrations.google_calendar_schedule",
        "search.patient_projection",
    )


def test_projector_runner_advances_checkpoints_only_on_success() -> None:
    event = build_event(
        event_name="patient.updated",
        producer_context="tests",
        clinic_id="c1",
        entity_type="patient",
        entity_id="p1",
        payload={"display_name": "Ann"},
        occurred_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
    ).to_record()
    event["outbox_event_id"] = 1

    @dataclass
    class _FailsProjector:
        name: str = "analytics.event_ledger"

        async def handle(self, _event, outbox_event_id: int) -> bool:  # noqa: ANN001
            raise RuntimeError(f"fail on {outbox_event_id}")

    outbox = _OutboxRepo([event])
    checkpoints = _CheckpointRepo()
    runner = ProjectorRunner(
        outbox_repository=outbox,
        checkpoint_repository=checkpoints,
        projectors=(_FailsProjector(),),
    )
    result = asyncio.run(runner.run_once(limit=1))
    assert result.failed_outbox_event_id == 1
    assert checkpoints.values == {}
    assert outbox.processed == []


def test_worker_startup_catchup_is_bounded(required_env) -> None:
    stop_event = asyncio.Event()
    runner = _FakeRunner(
        results=[
            ProjectorRunResult(scanned_events=2, handled_by_projector={"analytics.event_ledger": 2}),
            ProjectorRunResult(scanned_events=2, handled_by_projector={"analytics.event_ledger": 2}),
            ProjectorRunResult(scanned_events=2, handled_by_projector={"analytics.event_ledger": 2}),
        ],
        stop_event=stop_event,
    )
    runtime = ProjectorWorkerRuntime(
        settings=Settings(),
        registry=build_default_projector_registry(),
        config=ProjectorWorkerConfig(batch_limit=2, poll_interval_sec=0.01, startup_catchup_max_batches=2),
        stop_event=stop_event,
        runner=runner,  # type: ignore[arg-type]
    )
    asyncio.run(runtime.run_forever())
    assert runner.calls == 4
    assert runner.limits == [2, 2, 2, 2]


def test_worker_graceful_shutdown_stops_at_batch_boundary(required_env) -> None:
    stop_event = asyncio.Event()

    class _BoundaryRunner(_FakeRunner):
        async def run_once(self, *, limit: int = 200) -> ProjectorRunResult:
            self.calls += 1
            self.limits.append(limit)
            await asyncio.sleep(0.02)
            return ProjectorRunResult(scanned_events=1, handled_by_projector={"analytics.event_ledger": 1})

    runner = _BoundaryRunner(results=[])
    runtime = ProjectorWorkerRuntime(
        settings=Settings(),
        registry=build_default_projector_registry(),
        config=ProjectorWorkerConfig(batch_limit=5, poll_interval_sec=0.01, startup_catchup_max_batches=1),
        stop_event=stop_event,
        runner=runner,  # type: ignore[arg-type]
    )

    async def _run() -> None:
        task = asyncio.create_task(runtime.run_forever())
        await asyncio.sleep(0.005)
        stop_event.set()
        await task

    asyncio.run(_run())
    assert runner.calls == 1


def test_default_registry_projector_runs_through_worker_runtime(required_env, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    async def _fake_handle(self, event, outbox_event_id: int):  # noqa: ANN001
        seen.append(f"{self.name}:{event.event_name}:{outbox_event_id}")
        return True

    monkeypatch.setattr("app.projections.analytics.event_ledger_projector.AnalyticsEventLedgerProjector.handle", _fake_handle)
    monkeypatch.setattr("app.projections.admin.workdesk_projector.AdminWorkdeskProjector.handle", _fake_handle)
    monkeypatch.setattr("app.projections.owner.daily_metrics_projector.OwnerDailyMetricsProjector.handle", _fake_handle)
    monkeypatch.setattr(
        "app.projections.integrations.google_calendar_schedule_projector.GoogleCalendarScheduleProjector.handle",
        _fake_handle,
    )
    monkeypatch.setattr("app.projections.search.patient_event_projector.PatientSearchProjector.handle", _fake_handle)
    event = build_event(
        event_name="patient.created",
        producer_context="tests",
        clinic_id="c1",
        entity_type="patient",
        entity_id="p1",
        payload={"display_name": "Ann"},
    ).to_record()
    event["outbox_event_id"] = 1
    outbox = _OutboxRepo([event])
    checkpoints = _CheckpointRepo()
    registry = build_default_projector_registry()
    runner = ProjectorRunner(
        outbox_repository=outbox,
        checkpoint_repository=checkpoints,
        projectors=registry.build_projectors(Settings()),
    )
    stop_event = asyncio.Event()
    runtime = ProjectorWorkerRuntime(
        settings=Settings(),
        registry=registry,
        config=ProjectorWorkerConfig(batch_limit=10, poll_interval_sec=0.01, startup_catchup_max_batches=1),
        stop_event=stop_event,
        runner=runner,
    )
    asyncio.run(runtime._run_startup_catchup())
    assert seen == [
        "analytics.event_ledger:patient.created:1",
        "admin.workdesk:patient.created:1",
        "owner.daily_metrics:patient.created:1",
        "integrations.google_calendar_schedule:patient.created:1",
        "search.patient_projection:patient.created:1",
    ]
    assert checkpoints.values == {
        "analytics.event_ledger": 1,
        "admin.workdesk": 1,
        "owner.daily_metrics": 1,
        "integrations.google_calendar_schedule": 1,
        "search.patient_projection": 1,
    }
