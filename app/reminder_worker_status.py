import asyncio

from app.bootstrap.logging import configure_logging
from app.config.settings import get_settings
from app.worker import inspect_reminder_worker_health


def main() -> None:
    settings = get_settings()
    configure_logging(settings.logging)
    print(asyncio.run(inspect_reminder_worker_health()))


if __name__ == "__main__":
    main()
