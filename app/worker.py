import asyncio
import logging
import os
from dataclasses import dataclass

from app.bootstrap.logging import configure_logging
from app.application.communication import ReminderDeliveryService, ReminderRecoveryService
from app.application.policy import PolicyResolver
from app.config.settings import Settings, get_settings
from app.infrastructure.communication import AiogramTelegramReminderSender, DbTelegramReminderRecipientResolver
from app.infrastructure.db.booking_repository import DbBookingRepository
from app.infrastructure.db.communication_repository import DbReminderJobRepository
from app.infrastructure.db.repositories import DbPolicyRepository
from app.infrastructure.workers.reminder_delivery import run_reminder_delivery_once
from app.infrastructure.workers.reminder_recovery import run_reminder_recovery_once
from app.infrastructure.workers.reminder_runtime import ReminderWorkerConfig, ReminderWorkerRunner, ReminderWorkerRuntime
from app.infrastructure.workers.tasks import TaskRegistry, placeholder_heartbeat_task
from app.projections.runtime import ProjectorWorkerConfig, ProjectorWorkerRuntime, build_default_projector_registry


@dataclass(frozen=True, slots=True)
class ReminderWorkerServices:
    delivery: ReminderDeliveryService
    recovery: ReminderRecoveryService


async def build_reminder_worker_services(settings: Settings) -> ReminderWorkerServices:
    reminder_repository = DbReminderJobRepository(settings.db)
    policy_repository = await DbPolicyRepository.load(settings.db)
    policy_resolver = PolicyResolver(policy_repository)
    booking_repository = DbBookingRepository(settings.db)
    return ReminderWorkerServices(
        delivery=ReminderDeliveryService(
            repository=reminder_repository,
            booking_reader=booking_repository,
            recipient_resolver=DbTelegramReminderRecipientResolver(settings.db),
            sender=AiogramTelegramReminderSender(settings.telegram.patient_bot_token),
            policy_resolver=policy_resolver,
        ),
        recovery=ReminderRecoveryService(
            reminder_repository=reminder_repository,
            booking_repository=booking_repository,
            policy_resolver=policy_resolver,
        ),
    )


async def run_worker_once() -> None:
    settings = get_settings()
    configure_logging(settings.logging)
    logger = logging.getLogger("dentflow.worker")
    logger.info("worker bootstrap started")

    services = await build_reminder_worker_services(settings)
    batch_limit = int(os.getenv("REMINDER_DELIVERY_BATCH_LIMIT", "50"))

    registry = TaskRegistry()
    registry.register("heartbeat", placeholder_heartbeat_task)
    registry.register("reminder_delivery", lambda: run_reminder_delivery_once(service=services.delivery, batch_limit=batch_limit))
    registry.register("reminder_recovery", lambda: run_reminder_recovery_once(service=services.recovery, batch_limit=batch_limit))

    for name, task in registry.items():
        logger.info("running task", extra={"extra": {"task": name}})
        await task()

    logger.info("worker bootstrap finished")


def _projector_worker_config_from_env() -> ProjectorWorkerConfig:
    return ProjectorWorkerConfig(
        batch_limit=max(1, int(os.getenv("PROJECTOR_WORKER_BATCH_LIMIT", "200"))),
        poll_interval_sec=max(0.1, float(os.getenv("PROJECTOR_WORKER_POLL_INTERVAL_SEC", "1.0"))),
        startup_catchup_max_batches=max(1, int(os.getenv("PROJECTOR_WORKER_STARTUP_CATCHUP_MAX_BATCHES", "20"))),
    )


def _reminder_worker_config_from_env() -> ReminderWorkerConfig:
    return ReminderWorkerConfig(
        delivery_batch_limit=max(1, int(os.getenv("REMINDER_WORKER_DELIVERY_BATCH_LIMIT", "50"))),
        recovery_batch_limit=max(1, int(os.getenv("REMINDER_WORKER_RECOVERY_BATCH_LIMIT", "100"))),
        poll_interval_sec=max(0.1, float(os.getenv("REMINDER_WORKER_POLL_INTERVAL_SEC", "2.0"))),
        startup_catchup_max_batches=max(1, int(os.getenv("REMINDER_WORKER_STARTUP_CATCHUP_MAX_BATCHES", "10"))),
    )


async def run_projector_worker_forever() -> None:
    settings = get_settings()
    configure_logging(settings.logging)
    logger = logging.getLogger("dentflow.worker")
    logger.info("projector worker runtime started")
    registry = build_default_projector_registry()
    projector_enabled = os.getenv("PROJECTOR_WORKER_ENABLED", "1").strip().lower() not in {"0", "false", "off"}
    if projector_enabled:
        projector_worker = ProjectorWorkerRuntime(
            settings=settings,
            registry=registry,
            config=_projector_worker_config_from_env(),
        )
        projector_worker.install_signal_handlers()
        await projector_worker.run_forever()
    else:
        logger.info("projector worker disabled via PROJECTOR_WORKER_ENABLED")


async def run_reminder_worker_forever() -> None:
    settings = get_settings()
    configure_logging(settings.logging)
    logger = logging.getLogger("dentflow.worker")
    logger.info("reminder worker runtime started")
    services = await build_reminder_worker_services(settings)
    reminder_worker = ReminderWorkerRuntime(
        runner=ReminderWorkerRunner(
            delivery_service=services.delivery,
            recovery_service=services.recovery,
        ),
        config=_reminder_worker_config_from_env(),
    )
    reminder_worker.install_signal_handlers()
    await reminder_worker.run_forever()


async def run_worker_forever() -> None:
    mode = os.getenv("WORKER_MODE", "projector").strip().lower()
    if mode == "projector":
        await run_projector_worker_forever()
        return
    if mode == "reminder":
        await run_reminder_worker_forever()
        return
    if mode == "all":
        await asyncio.gather(run_projector_worker_forever(), run_reminder_worker_forever())
        return
    raise ValueError("invalid WORKER_MODE; expected one of: projector, reminder, all")


def main() -> None:
    asyncio.run(run_worker_forever())


if __name__ == "__main__":
    main()
