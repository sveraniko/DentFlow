from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.config.settings import Settings
from app.projections.admin import AdminWorkdeskProjector
from app.projections.analytics import AnalyticsEventLedgerProjector
from app.projections.integrations import GoogleCalendarScheduleProjector
from app.projections.owner import OwnerDailyMetricsProjector
from app.projections.runtime.projectors import Projector
from app.projections.search import PatientSearchProjector


ProjectorFactory = Callable[[Settings], Projector]


@dataclass(frozen=True, slots=True)
class RegisteredProjector:
    name: str
    factory: ProjectorFactory


class ProjectorRegistry:
    def __init__(self) -> None:
        self._projectors: dict[str, RegisteredProjector] = {}

    def register(self, projector: RegisteredProjector) -> None:
        self._projectors[projector.name] = projector

    def names(self) -> tuple[str, ...]:
        return tuple(self._projectors.keys())

    def build_projectors(self, settings: Settings) -> tuple[Projector, ...]:
        return tuple(defn.factory(settings) for defn in self._projectors.values())


def build_default_projector_registry() -> ProjectorRegistry:
    registry = ProjectorRegistry()
    registry.register(
        RegisteredProjector(
            name="analytics.event_ledger",
            factory=lambda settings: AnalyticsEventLedgerProjector(settings.db),
        )
    )
    registry.register(
        RegisteredProjector(
            name="admin.workdesk",
            factory=lambda settings: AdminWorkdeskProjector(
                settings.db,
                app_default_timezone=settings.app.default_timezone,
            ),
        )
    )
    registry.register(
        RegisteredProjector(
            name="owner.daily_metrics",
            factory=lambda settings: OwnerDailyMetricsProjector(settings.db),
        )
    )
    registry.register(
        RegisteredProjector(
            name="integrations.google_calendar_schedule",
            factory=lambda settings: GoogleCalendarScheduleProjector(
                db_config=settings.db,
                app_default_timezone=settings.app.default_timezone,
                google_calendar_enabled=settings.integrations.google_calendar_enabled,
                google_calendar_credentials_path=settings.integrations.google_calendar_credentials_path,
                google_calendar_subject_email=settings.integrations.google_calendar_subject_email,
                google_calendar_application_name=settings.integrations.google_calendar_application_name,
                google_calendar_timeout_sec=settings.integrations.google_calendar_timeout_sec,
                dentflow_base_url=settings.integrations.dentflow_base_url,
            ),
        )
    )
    registry.register(
        RegisteredProjector(
            name="search.patient_projection",
            factory=lambda settings: PatientSearchProjector(settings.db),
        )
    )
    return registry
