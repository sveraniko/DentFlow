from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

RECOMMENDATION_STATUSES: frozenset[str] = frozenset(
    {
        "draft",
        "prepared",
        "issued",
        "viewed",
        "acknowledged",
        "accepted",
        "declined",
        "expired",
        "withdrawn",
    }
)

RECOMMENDATION_TYPES: frozenset[str] = frozenset(
    {
        "aftercare",
        "follow_up",
        "next_step",
        "hygiene_support",
        "monitoring",
        "general_guidance",
    }
)

RECOMMENDATION_SOURCE_KINDS: frozenset[str] = frozenset(
    {
        "doctor_manual",
        "booking_trigger",
        "encounter_trigger",
        "clinical_trigger",
        "system_template",
    }
)


@dataclass(frozen=True)
class Recommendation:
    recommendation_id: str
    clinic_id: str
    patient_id: str
    booking_id: str | None
    encounter_id: str | None
    chart_id: str | None
    issued_by_actor_id: str | None
    source_kind: str
    recommendation_type: str
    title: str
    body_text: str
    rationale_text: str | None
    status: str
    issued_at: datetime | None
    viewed_at: datetime | None
    acknowledged_at: datetime | None
    accepted_at: datetime | None
    declined_at: datetime | None
    expired_at: datetime | None
    withdrawn_at: datetime | None
    created_at: datetime
    updated_at: datetime
