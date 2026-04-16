import logging

from app.bootstrap.logging import configure_logging
from app.bootstrap.runtime import RuntimeRegistry
from app.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    configure_logging(settings.logging)
    logger = logging.getLogger("dentflow.main")
    logger.info("DentFlow runtime bootstrap started")
    runtime = RuntimeRegistry(settings)
    runtime.build_dispatcher()
    logger.info("DentFlow runtime skeleton ready")


if __name__ == "__main__":
    main()
