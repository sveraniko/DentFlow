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


def main() -> None:
    asyncio.run(run_worker_once())


if __name__ == "__main__":
    main()
