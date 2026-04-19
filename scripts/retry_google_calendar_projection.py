from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import argparse
import asyncio

from app.application.integration.google_calendar_projection import GoogleCalendarProjectionService
from app.config.settings import get_settings
from app.infrastructure.db.google_calendar_projection_repository import DbGoogleCalendarProjectionRepository
from app.integrations.google_calendar import create_google_calendar_gateway


async def _run(limit: int, booking_id: str | None) -> None:
    settings = get_settings()
    repo = DbGoogleCalendarProjectionRepository(settings.db, app_default_timezone=settings.app.default_timezone)
    service = GoogleCalendarProjectionService(
        repository=repo,
        gateway=create_google_calendar_gateway(
            enabled=settings.integrations.google_calendar_enabled,
            credentials_path=settings.integrations.google_calendar_credentials_path,
            subject_email=settings.integrations.google_calendar_subject_email,
            application_name=settings.integrations.google_calendar_application_name,
            timeout_sec=settings.integrations.google_calendar_timeout_sec,
        ),
        dentflow_base_url=settings.integrations.dentflow_base_url,
    )

    booking_ids = [booking_id] if booking_id else await repo.retry_failed(limit=limit)
    for bid in booking_ids:
        await service.sync_booking(booking_id=bid)
    print({"retried": len(booking_ids)})


def main() -> None:
    parser = argparse.ArgumentParser(description="Retry failed Google Calendar projection syncs")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--booking-id", type=str, default=None)
    args = parser.parse_args()
    asyncio.run(_run(limit=args.limit, booking_id=args.booking_id))


if __name__ == "__main__":
    main()
