from __future__ import annotations

import asyncio
import logging
import signal
from dataclasses import dataclass

from app.config.settings import Settings
from app.infrastructure.outbox.repository import OutboxRepository, ProjectorCheckpointRepository
from app.projections.runtime.projectors import ProjectorRunResult, ProjectorRunner
from app.projections.runtime.registry import ProjectorRegistry


@dataclass(frozen=True, slots=True)
class ProjectorWorkerConfig:
    batch_limit: int = 200
    poll_interval_sec: float = 1.0
    startup_catchup_max_batches: int = 20


class ProjectorWorkerRuntime:
    def __init__(
        self,
        *,
        settings: Settings,
        registry: ProjectorRegistry,
        config: ProjectorWorkerConfig,
        stop_event: asyncio.Event | None = None,
        runner: ProjectorRunner | None = None,
    ) -> None:
        self._settings = settings
        self._registry = registry
        self._config = config
        self._stop_event = stop_event or asyncio.Event()
        self._logger = logging.getLogger("dentflow.projector_worker")
        self._runner = runner or ProjectorRunner(
            outbox_repository=OutboxRepository(settings.db),
            checkpoint_repository=ProjectorCheckpointRepository(settings.db),
            projectors=registry.build_projectors(settings),
        )

    @property
    def stop_event(self) -> asyncio.Event:
        return self._stop_event

    def install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._stop_event.set)
            except NotImplementedError:
                self._logger.warning("signal handlers not supported", extra={"extra": {"signal": sig.name}})

    async def run_forever(self) -> None:
        if not self._runner.projectors:
            self._logger.warning("projector worker has no registered projectors")
            return
        self._logger.info("projector worker started", extra={"extra": {"projectors": [p.name for p in self._runner.projectors]}})
        await self._run_startup_catchup()
        while not self._stop_event.is_set():
            result = await self._run_batch()
            if result.scanned_events == 0 and not self._stop_event.is_set():
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self._config.poll_interval_sec)
                except TimeoutError:
                    pass
        self._logger.info("projector worker stopped")

    async def _run_startup_catchup(self) -> None:
        for _ in range(self._config.startup_catchup_max_batches):
            if self._stop_event.is_set():
                return
            result = await self._run_batch()
            if result.scanned_events == 0 or result.failed_outbox_event_id is not None:
                return

    async def _run_batch(self) -> ProjectorRunResult:
        result = await self._runner.run_once(limit=self._config.batch_limit)
        if result.scanned_events:
            self._logger.info(
                "projector batch processed",
                extra={
                    "extra": {
                        "scanned_events": result.scanned_events,
                        "handled": result.handled_by_projector,
                        "failed_outbox_event_id": result.failed_outbox_event_id,
                    }
                },
            )
        return result
