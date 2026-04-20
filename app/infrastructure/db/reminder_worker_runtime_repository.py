from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.infrastructure.db.engine import create_engine


@dataclass(frozen=True, slots=True)
class ReminderWorkerStatusView:
    worker_name: str
    owner_token: str
    mode: str
    heartbeat_at: datetime | None
    last_success_at: datetime | None
    last_error_at: datetime | None
    last_error_text: str | None
    lease_owner_token: str | None
    lease_expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class ReminderWorkerHealth:
    status: str
    worker_name: str
    mode: str | None
    heartbeat_age_sec: float | None
    last_success_age_sec: float | None
    lease_owner_token: str | None
    details: str


class DbReminderWorkerRuntimeRepository:
    def __init__(self, db_config) -> None:
        self._db_config = db_config

    async def try_acquire_or_renew_lease(self, *, lease_name: str, owner_token: str, now: datetime, ttl: timedelta) -> bool:
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        """
                        INSERT INTO system_runtime.worker_leases (
                          lease_name, owner_token, lease_expires_at, heartbeat_at, updated_at
                        )
                        VALUES (
                          :lease_name, :owner_token, :lease_expires_at, :now, :now
                        )
                        ON CONFLICT (lease_name) DO UPDATE
                        SET
                          owner_token = CASE
                            WHEN system_runtime.worker_leases.owner_token = :owner_token
                              OR system_runtime.worker_leases.lease_expires_at <= :now
                            THEN :owner_token
                            ELSE system_runtime.worker_leases.owner_token
                          END,
                          lease_expires_at = CASE
                            WHEN system_runtime.worker_leases.owner_token = :owner_token
                              OR system_runtime.worker_leases.lease_expires_at <= :now
                            THEN :lease_expires_at
                            ELSE system_runtime.worker_leases.lease_expires_at
                          END,
                          heartbeat_at = CASE
                            WHEN system_runtime.worker_leases.owner_token = :owner_token
                              OR system_runtime.worker_leases.lease_expires_at <= :now
                            THEN :now
                            ELSE system_runtime.worker_leases.heartbeat_at
                          END,
                          updated_at = :now
                        RETURNING owner_token
                        """
                    ),
                    {
                        "lease_name": lease_name,
                        "owner_token": owner_token,
                        "now": now,
                        "lease_expires_at": now + ttl,
                    },
                )
                row = result.mappings().first()
                return bool(row and row["owner_token"] == owner_token)
        finally:
            await engine.dispose()

    async def release_lease(self, *, lease_name: str, owner_token: str, now: datetime) -> None:
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        UPDATE system_runtime.worker_leases
                        SET lease_expires_at=:now, heartbeat_at=:now, updated_at=:now
                        WHERE lease_name=:lease_name
                          AND owner_token=:owner_token
                        """
                    ),
                    {"lease_name": lease_name, "owner_token": owner_token, "now": now},
                )
        finally:
            await engine.dispose()

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
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        INSERT INTO system_runtime.worker_status (
                          worker_name, owner_token, mode, heartbeat_at,
                          last_success_at, last_error_at, last_error_text, updated_at
                        )
                        VALUES (
                          :worker_name, :owner_token, :mode, :heartbeat_at,
                          :last_success_at, :last_error_at, :last_error_text, :heartbeat_at
                        )
                        ON CONFLICT (worker_name) DO UPDATE
                        SET owner_token=:owner_token,
                            mode=:mode,
                            heartbeat_at=:heartbeat_at,
                            last_success_at=COALESCE(:last_success_at, system_runtime.worker_status.last_success_at),
                            last_error_at=COALESCE(:last_error_at, system_runtime.worker_status.last_error_at),
                            last_error_text=CASE
                                WHEN :last_error_at IS NULL THEN system_runtime.worker_status.last_error_text
                                ELSE :last_error_text
                            END,
                            updated_at=:heartbeat_at
                        """
                    ),
                    {
                        "worker_name": worker_name,
                        "owner_token": owner_token,
                        "mode": mode,
                        "heartbeat_at": heartbeat_at,
                        "last_success_at": last_success_at,
                        "last_error_at": last_error_at,
                        "last_error_text": last_error_text,
                    },
                )
        finally:
            await engine.dispose()

    async def get_worker_status_view(self, *, worker_name: str, lease_name: str) -> ReminderWorkerStatusView | None:
        engine = create_engine(self._db_config)
        try:
            async with engine.connect() as conn:
                row = (
                    await conn.execute(
                        text(
                            """
                            SELECT
                              s.worker_name,
                              s.owner_token,
                              s.mode,
                              s.heartbeat_at,
                              s.last_success_at,
                              s.last_error_at,
                              s.last_error_text,
                              l.owner_token AS lease_owner_token,
                              l.lease_expires_at
                            FROM system_runtime.worker_status s
                            LEFT JOIN system_runtime.worker_leases l
                              ON l.lease_name = :lease_name
                            WHERE s.worker_name = :worker_name
                            """
                        ),
                        {"worker_name": worker_name, "lease_name": lease_name},
                    )
                ).mappings().first()
            if row is None:
                return None
            return ReminderWorkerStatusView(**dict(row))
        finally:
            await engine.dispose()


class ReminderWorkerHealthInspector:
    def __init__(
        self,
        repository: DbReminderWorkerRuntimeRepository,
        *,
        worker_name: str = "reminder",
        lease_name: str = "reminder:primary",
        heartbeat_stale_after_sec: int = 90,
        success_stale_after_sec: int = 300,
    ) -> None:
        self._repository = repository
        self._worker_name = worker_name
        self._lease_name = lease_name
        self._heartbeat_stale_after_sec = heartbeat_stale_after_sec
        self._success_stale_after_sec = success_stale_after_sec

    async def inspect(self) -> ReminderWorkerHealth:
        now = datetime.now(timezone.utc)
        status = await self._repository.get_worker_status_view(worker_name=self._worker_name, lease_name=self._lease_name)
        if status is None:
            return ReminderWorkerHealth(
                status="unhealthy",
                worker_name=self._worker_name,
                mode=None,
                heartbeat_age_sec=None,
                last_success_age_sec=None,
                lease_owner_token=None,
                details="no worker status recorded",
            )

        heartbeat_age = _age_sec(now, status.heartbeat_at)
        success_age = _age_sec(now, status.last_success_at)
        lease_active = bool(status.lease_expires_at and status.lease_expires_at > now)

        if status.mode == "active" and lease_active and heartbeat_age is not None and heartbeat_age <= self._heartbeat_stale_after_sec:
            if success_age is None or success_age <= self._success_stale_after_sec:
                return ReminderWorkerHealth(
                    status="healthy",
                    worker_name=status.worker_name,
                    mode=status.mode,
                    heartbeat_age_sec=heartbeat_age,
                    last_success_age_sec=success_age,
                    lease_owner_token=status.lease_owner_token,
                    details="active lease and fresh heartbeat",
                )
            return ReminderWorkerHealth(
                status="degraded",
                worker_name=status.worker_name,
                mode=status.mode,
                heartbeat_age_sec=heartbeat_age,
                last_success_age_sec=success_age,
                lease_owner_token=status.lease_owner_token,
                details="worker active but last success is stale",
            )

        return ReminderWorkerHealth(
            status="unhealthy",
            worker_name=status.worker_name,
            mode=status.mode,
            heartbeat_age_sec=heartbeat_age,
            last_success_age_sec=success_age,
            lease_owner_token=status.lease_owner_token,
            details="worker heartbeat stale or lease inactive",
        )


def _age_sec(now: datetime, value: datetime | None) -> float | None:
    if value is None:
        return None
    return max(0.0, (now - value).total_seconds())
