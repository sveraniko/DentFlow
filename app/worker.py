import asyncio
import logging
import os

from app.bootstrap.logging import configure_logging
from app.application.communication import ReminderDeliveryService, ReminderRecoveryService
from app.application.policy import PolicyResolver
from app.config.settings import get_settings
from app.infrastructure.communication import AiogramTelegramReminderSender, DbTelegramReminderRecipientResolver
from app.infrastructure.db.booking_repository import DbBookingRepository
from app.infrastructure.db.communication_repository import DbReminderJobRepository
from app.infrastructure.db.repositories import DbPolicyRepository
from app.infrastructure.workers.reminder_delivery import run_reminder_delivery_once
from app.infrastructure.workers.reminder_recovery import run_reminder_recovery_once
from app.infrastructure.workers.tasks import TaskRegistry, placeholder_heartbeat_task
from app.projections.runtime import ProjectorWorkerConfig, ProjectorWorkerRuntime, build_default_projector_registry


async def run_worker_once() -> None:
    settings = get_settings()
    configure_logging(settings.logging)
    logger = logging.getLogger("dentflow.worker")
    logger.info("worker bootstrap started")

    reminder_repository = DbReminderJobRepository(settings.db)
    policy_repository = await DbPolicyRepository.load(settings.db)
    policy_resolver = PolicyResolver(policy_repository)
    booking_repository = DbBookingRepository(settings.db)
    delivery_service = ReminderDeliveryService(
        repository=reminder_repository,
        booking_reader=booking_repository,
        recipient_resolver=DbTelegramReminderRecipientResolver(settings.db),
        sender=AiogramTelegramReminderSender(settings.telegram.patient_bot_token),
        policy_resolver=policy_resolver,
    )
    recovery_service = ReminderRecoveryService(
        reminder_repository=reminder_repository,
        booking_repository=booking_repository,
        policy_resolver=policy_resolver,
    )
    batch_limit = int(os.getenv("REMINDER_DELIVERY_BATCH_LIMIT", "50"))

    registry = TaskRegistry()
    registry.register("heartbeat", placeholder_heartbeat_task)
    registry.register("reminder_delivery", lambda: run_reminder_delivery_once(service=delivery_service, batch_limit=batch_limit))
    registry.register("reminder_recovery", lambda: run_reminder_recovery_once(service=recovery_service, batch_limit=batch_limit))

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


async def run_worker_forever() -> None:
    settings = get_settings()
    configure_logging(settings.logging)
    logger = logging.getLogger("dentflow.worker")
    logger.info("worker runtime started")
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


def main() -> None:
    asyncio.run(run_worker_forever())


if __name__ == "__main__":
    main()
