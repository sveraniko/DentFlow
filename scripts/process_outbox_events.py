from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import argparse
import asyncio

from app.config.settings import get_settings
from app.infrastructure.outbox.repository import OutboxRepository, ProjectorCheckpointRepository
from app.projections.admin import AdminWorkdeskProjector
from app.projections.integrations import GoogleCalendarScheduleProjector
from app.projections.analytics import AnalyticsEventLedgerProjector
from app.projections.owner.daily_metrics_projector import OwnerDailyMetricsProjector
from app.projections.runtime import ProjectorRunner
from app.projections.search.patient_event_projector import PatientSearchProjector


async def _run(limit: int) -> None:
    settings = get_settings()
    runner = ProjectorRunner(
        outbox_repository=OutboxRepository(settings.db),
        checkpoint_repository=ProjectorCheckpointRepository(settings.db),
        projectors=(
            AnalyticsEventLedgerProjector(settings.db),
            PatientSearchProjector(settings.db),
            OwnerDailyMetricsProjector(settings.db),
            AdminWorkdeskProjector(settings.db, app_default_timezone=settings.app.default_timezone),
            GoogleCalendarScheduleProjector(
                settings.db,
                app_default_timezone=settings.app.default_timezone,
                google_calendar_enabled=settings.integrations.google_calendar_enabled,
                google_calendar_credentials_path=settings.integrations.google_calendar_credentials_path,
                google_calendar_subject_email=settings.integrations.google_calendar_subject_email,
                google_calendar_application_name=settings.integrations.google_calendar_application_name,
                google_calendar_timeout_sec=settings.integrations.google_calendar_timeout_sec,
                dentflow_base_url=settings.integrations.dentflow_base_url,
            ),
        ),
    )
    print(await runner.run_once(limit=limit))


def main() -> None:
    parser = argparse.ArgumentParser(description="Process DentFlow outbox events with configured projectors")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    asyncio.run(_run(args.limit))


if __name__ == "__main__":
    main()
