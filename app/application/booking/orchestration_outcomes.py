from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from app.domain.booking import AdminEscalation, Booking, BookingSession, SlotHold, WaitlistEntry

TEntity = TypeVar("TEntity")


@dataclass(frozen=True, slots=True)
class OrchestrationSuccess(Generic[TEntity]):
    kind: str
    entity: TEntity


@dataclass(frozen=True, slots=True)
class NoMatchOutcome:
    kind: str
    reason: str


@dataclass(frozen=True, slots=True)
class AmbiguousMatchOutcome:
    kind: str
    reason: str
    candidate_patient_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SlotUnavailableOutcome:
    kind: str
    reason: str


@dataclass(frozen=True, slots=True)
class ConflictOutcome:
    kind: str
    reason: str


@dataclass(frozen=True, slots=True)
class EscalatedOutcome:
    kind: str
    reason: str
    escalation: AdminEscalation


@dataclass(frozen=True, slots=True)
class InvalidStateOutcome:
    kind: str
    reason: str


BookingSessionOutcome = (
    OrchestrationSuccess[BookingSession]
    | NoMatchOutcome
    | AmbiguousMatchOutcome
    | SlotUnavailableOutcome
    | ConflictOutcome
    | EscalatedOutcome
    | InvalidStateOutcome
)

BookingOutcome = OrchestrationSuccess[Booking] | ConflictOutcome | InvalidStateOutcome
HoldOutcome = OrchestrationSuccess[SlotHold] | SlotUnavailableOutcome | ConflictOutcome | InvalidStateOutcome
WaitlistOutcome = OrchestrationSuccess[WaitlistEntry] | InvalidStateOutcome
