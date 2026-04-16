import asyncio
import logging

from app.bootstrap.logging import configure_logging
from app.config.settings import get_settings
from app.infrastructure.workers.tasks import TaskRegistry, placeholder_heartbeat_task


async def run_worker_once() -> None:
    settings = get_settings()
    configure_logging(settings.logging)
    logger = logging.getLogger("dentflow.worker")
    logger.info("worker bootstrap started")

    registry = TaskRegistry()
    registry.register("heartbeat", placeholder_heartbeat_task)

    for name, task in registry.items():
        logger.info("running task", extra={"extra": {"task": name}})
        await task()

    logger.info("worker bootstrap finished")


def main() -> None:
    asyncio.run(run_worker_once())


if __name__ == "__main__":
    main()
