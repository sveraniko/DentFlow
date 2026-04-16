from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True, frozen=True)
class PatientResolutionCandidate:
    patient_id: str
    clinic_id: str
    display_name: str


@dataclass(slots=True, frozen=True)
class BookingPatientResolutionResult:
    resolution_kind: str
    candidates: tuple[PatientResolutionCandidate, ...]
    match_reason: str
    normalized_lookup_value: str | None = None


class BookingPatientFinder(Protocol):
    async def find_patients_by_exact_contact(self, *, contact_type: str, contact_value: str) -> list[dict]: ...
    async def find_patients_by_external_id(self, *, external_system: str, external_id: str) -> list[dict]: ...


@dataclass(slots=True)
class BookingPatientResolutionService:
    finder: BookingPatientFinder

    async def resolve_by_exact_normalized_contact(self, *, contact_type: str, contact_value: str) -> BookingPatientResolutionResult:
        rows = await self.finder.find_patients_by_exact_contact(contact_type=contact_type, contact_value=contact_value)
        normalized = _extract_normalized_value(rows)
        return _build_result(rows, match_reason="exact_contact", normalized_lookup_value=normalized)

    async def resolve_by_external_system_id(self, *, external_system: str, external_id: str) -> BookingPatientResolutionResult:
        rows = await self.finder.find_patients_by_external_id(external_system=external_system, external_id=external_id)
        return _build_result(rows, match_reason=f"external_id:{external_system}", normalized_lookup_value=external_id)


def _extract_normalized_value(rows: list[dict]) -> str | None:
    if not rows:
        return None
    return str(rows[0].get("normalized_lookup_value")) if rows[0].get("normalized_lookup_value") is not None else None


def _build_result(rows: list[dict], *, match_reason: str, normalized_lookup_value: str | None) -> BookingPatientResolutionResult:
    candidates = tuple(
        PatientResolutionCandidate(
            patient_id=row["patient_id"],
            clinic_id=row["clinic_id"],
            display_name=row["display_name"],
        )
        for row in rows
    )
    if len(candidates) == 0:
        kind = "no_match"
    elif len(candidates) == 1:
        kind = "exact_match"
    else:
        kind = "ambiguous_match"
    return BookingPatientResolutionResult(
        resolution_kind=kind,
        candidates=candidates,
        match_reason=match_reason,
        normalized_lookup_value=normalized_lookup_value,
    )
