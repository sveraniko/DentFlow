from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.config.settings import Settings
from app.projections.analytics import AnalyticsEventLedgerProjector
from app.projections.runtime.projectors import Projector


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
    return registry

