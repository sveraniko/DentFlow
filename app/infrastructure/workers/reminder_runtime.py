from __future__ import annotations

import asyncio
import logging
import signal
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.application.communication import ReminderDeliveryService, ReminderRecoveryService
from app.infrastructure.workers.reminder_delivery import run_reminder_delivery_once
from app.infrastructure.workers.reminder_recovery import run_reminder_recovery_once


@dataclass(frozen=True, slots=True)
class ReminderWorkerConfig:
    delivery_batch_limit: int = 50
    recovery_batch_limit: int = 100
    poll_interval_sec: float = 2.0
    startup_catchup_max_batches: int = 10
    lease_ttl_sec: int = 30
    max_consecutive_error_batches: int = 3
    error_cooldown_sec: float = 10.0


@dataclass(frozen=True, slots=True)
class ReminderWorkerBatchResult:
    delivery_claimed: int
    recovery_processed: int

    @property
    def total_processed(self) -> int:
        return self.delivery_claimed + self.recovery_processed


@dataclass(slots=True)
class ReminderWorkerRunner:
    delivery_service: ReminderDeliveryService
    recovery_service: ReminderRecoveryService

    async def run_once(self, *, delivery_batch_limit: int, recovery_batch_limit: int) -> ReminderWorkerBatchResult:
        delivery_claimed = await run_reminder_delivery_once(
            service=self.delivery_service,
            batch_limit=delivery_batch_limit,
        )
        recovery_processed = await run_reminder_recovery_once(
            service=self.recovery_service,
            batch_limit=recovery_batch_limit,
        )
        return ReminderWorkerBatchResult(
            delivery_claimed=delivery_claimed,
            recovery_processed=recovery_processed,
        )


class ReminderWorkerOps(Protocol):
    async def try_acquire_or_renew_lease(self, *, lease_name: str, owner_token: str, now: datetime, ttl: timedelta) -> bool: ...
    async def release_lease(self, *, lease_name: str, owner_token: str, now: datetime) -> None: ...
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
    ) -> None: ...


class ReminderWorkerRuntime:
    def __init__(
        self,
        *,
        runner: ReminderWorkerRunner,
        config: ReminderWorkerConfig,
        ops: ReminderWorkerOps,
        worker_name: str = "reminder",
        owner_token: str = "unknown-worker",
        stop_event: asyncio.Event | None = None,
    ) -> None:
        self._runner = runner
        self._config = config
        self._ops = ops
        self._worker_name = worker_name
        self._lease_name = f"{worker_name}:primary"
        self._owner_token = owner_token
        self._stop_event = stop_event or asyncio.Event()
        self._logger = logging.getLogger("dentflow.reminder_worker")
        self._consecutive_errors = 0

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
        self._logger.info(
            "reminder worker started",
            extra={
                "extra": {
                    "delivery_batch_limit": self._config.delivery_batch_limit,
                    "recovery_batch_limit": self._config.recovery_batch_limit,
                    "poll_interval_sec": self._config.poll_interval_sec,
                    "startup_catchup_max_batches": self._config.startup_catchup_max_batches,
                    "lease_ttl_sec": self._config.lease_ttl_sec,
                    "owner_token": self._owner_token,
                }
            },
        )
        await self._run_startup_catchup()
        while not self._stop_event.is_set():
            result = await self._run_safe_batch()
            if result.total_processed == 0 and not self._stop_event.is_set():
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self._config.poll_interval_sec)
                except (TimeoutError, asyncio.TimeoutError):
                    pass
        await self._release_lease()
        self._logger.info("reminder worker stopped")

    async def _run_startup_catchup(self) -> None:
        for _ in range(self._config.startup_catchup_max_batches):
            if self._stop_event.is_set():
                return
            result = await self._run_safe_batch()
            if result.total_processed == 0:
                return

    async def _run_safe_batch(self) -> ReminderWorkerBatchResult:
        now = datetime.now(timezone.utc)
        lease_acquired = await self._ops.try_acquire_or_renew_lease(
            lease_name=self._lease_name,
            owner_token=self._owner_token,
            now=now,
            ttl=timedelta(seconds=max(self._config.lease_ttl_sec, 1)),
        )
        if not lease_acquired:
            await self._ops.upsert_worker_status(
                worker_name=self._worker_name,
                owner_token=self._owner_token,
                mode="standby",
                heartbeat_at=now,
            )
            return ReminderWorkerBatchResult(delivery_claimed=0, recovery_processed=0)

        await self._ops.upsert_worker_status(
            worker_name=self._worker_name,
            owner_token=self._owner_token,
            mode="active",
            heartbeat_at=now,
        )
        try:
            result = await self._run_batch()
            if result.total_processed > 0:
                await self._ops.upsert_worker_status(
                    worker_name=self._worker_name,
                    owner_token=self._owner_token,
                    mode="active",
                    heartbeat_at=now,
                    last_success_at=now,
                )
            self._consecutive_errors = 0
            return result
        except Exception as exc:  # noqa: BLE001
            self._consecutive_errors += 1
            await self._ops.upsert_worker_status(
                worker_name=self._worker_name,
                owner_token=self._owner_token,
                mode="active",
                heartbeat_at=now,
                last_error_at=now,
                last_error_text=str(exc)[:500],
            )
            self._logger.warning(
                "reminder worker batch failed",
                extra={"extra": {"error": str(exc), "consecutive_errors": self._consecutive_errors}},
            )
            if self._consecutive_errors >= self._config.max_consecutive_error_batches:
                self._consecutive_errors = 0
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self._config.error_cooldown_sec)
                except (TimeoutError, asyncio.TimeoutError):
                    pass
            return ReminderWorkerBatchResult(delivery_claimed=0, recovery_processed=0)

    async def _run_batch(self) -> ReminderWorkerBatchResult:
        result = await self._runner.run_once(
            delivery_batch_limit=self._config.delivery_batch_limit,
            recovery_batch_limit=self._config.recovery_batch_limit,
        )
        if result.total_processed > 0:
            self._logger.info(
                "reminder batch processed",
                extra={
                    "extra": {
                        "delivery_claimed": result.delivery_claimed,
                        "recovery_processed": result.recovery_processed,
                        "total_processed": result.total_processed,
                    }
                },
            )
        return result

    async def _release_lease(self) -> None:
        now = datetime.now(timezone.utc)
        await self._ops.release_lease(
            lease_name=self._lease_name,
            owner_token=self._owner_token,
            now=now,
        )
