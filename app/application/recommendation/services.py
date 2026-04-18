from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from app.domain.recommendations import RECOMMENDATION_SOURCE_KINDS, RECOMMENDATION_TYPES, Recommendation

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"prepared", "issued", "withdrawn", "expired"},
    "prepared": {"issued", "withdrawn", "expired"},
    "issued": {"viewed", "acknowledged", "accepted", "declined", "withdrawn", "expired"},
    "viewed": {"acknowledged", "accepted", "declined", "withdrawn", "expired"},
    "acknowledged": {"accepted", "declined", "withdrawn", "expired"},
    "accepted": set(),
    "declined": set(),
    "withdrawn": set(),
    "expired": set(),
}


class RecommendationRepository(Protocol):
    async def get(self, recommendation_id: str) -> Recommendation | None: ...
    async def save(self, item: Recommendation) -> None: ...
    async def list_for_patient(self, *, patient_id: str, include_terminal: bool = False) -> list[Recommendation]: ...
    async def list_for_booking(self, *, booking_id: str) -> list[Recommendation]: ...
    async def list_for_chart(self, *, chart_id: str) -> list[Recommendation]: ...


@dataclass(slots=True)
class RecommendationService:
    repository: RecommendationRepository

    async def create_recommendation(
        self,
        *,
        clinic_id: str,
        patient_id: str,
        recommendation_type: str,
        source_kind: str,
        title: str,
        body_text: str,
        rationale_text: str | None = None,
        booking_id: str | None = None,
        encounter_id: str | None = None,
        chart_id: str | None = None,
        issued_by_actor_id: str | None = None,
        prepared: bool = True,
    ) -> Recommendation:
        self._validate_type_and_source(recommendation_type=recommendation_type, source_kind=source_kind)
        now = datetime.now(timezone.utc)
        item = Recommendation(
            recommendation_id=f"rec_{uuid4().hex[:16]}",
            clinic_id=clinic_id,
            patient_id=patient_id,
            booking_id=booking_id,
            encounter_id=encounter_id,
            chart_id=chart_id,
            issued_by_actor_id=issued_by_actor_id,
            source_kind=source_kind,
            recommendation_type=recommendation_type,
            title=title.strip(),
            body_text=body_text.strip(),
            rationale_text=rationale_text.strip() if rationale_text else None,
            status="prepared" if prepared else "draft",
            issued_at=None,
            viewed_at=None,
            acknowledged_at=None,
            accepted_at=None,
            declined_at=None,
            expired_at=None,
            withdrawn_at=None,
            created_at=now,
            updated_at=now,
        )
        await self.repository.save(item)
        return item

    async def issue(self, *, recommendation_id: str, issued_by_actor_id: str | None = None) -> Recommendation | None:
        item = await self.repository.get(recommendation_id)
        if item is None:
            return None
        now = datetime.now(timezone.utc)
        return await self._transition(
            item,
            to_status="issued",
            updates={"issued_at": item.issued_at or now, "issued_by_actor_id": issued_by_actor_id or item.issued_by_actor_id},
        )

    async def withdraw(self, *, recommendation_id: str) -> Recommendation | None:
        item = await self.repository.get(recommendation_id)
        if item is None:
            return None
        return await self._transition(item, to_status="withdrawn", updates={"withdrawn_at": datetime.now(timezone.utc)})

    async def mark_viewed(self, *, recommendation_id: str) -> Recommendation | None:
        return await self._patient_action(recommendation_id=recommendation_id, to_status="viewed", stamp_field="viewed_at")

    async def acknowledge(self, *, recommendation_id: str) -> Recommendation | None:
        return await self._patient_action(recommendation_id=recommendation_id, to_status="acknowledged", stamp_field="acknowledged_at")

    async def accept(self, *, recommendation_id: str) -> Recommendation | None:
        return await self._patient_action(recommendation_id=recommendation_id, to_status="accepted", stamp_field="accepted_at")

    async def decline(self, *, recommendation_id: str) -> Recommendation | None:
        return await self._patient_action(recommendation_id=recommendation_id, to_status="declined", stamp_field="declined_at")

    async def get(self, recommendation_id: str) -> Recommendation | None:
        return await self.repository.get(recommendation_id)

    async def list_for_patient(self, *, patient_id: str, include_terminal: bool = False) -> list[Recommendation]:
        return await self.repository.list_for_patient(patient_id=patient_id, include_terminal=include_terminal)

    async def list_for_booking(self, *, booking_id: str) -> list[Recommendation]:
        return await self.repository.list_for_booking(booking_id=booking_id)

    async def list_for_chart(self, *, chart_id: str) -> list[Recommendation]:
        return await self.repository.list_for_chart(chart_id=chart_id)

    async def _patient_action(self, *, recommendation_id: str, to_status: str, stamp_field: str) -> Recommendation | None:
        item = await self.repository.get(recommendation_id)
        if item is None:
            return None
        if item.status == to_status:
            return item
        updates: dict[str, object] = {stamp_field: getattr(item, stamp_field) or datetime.now(timezone.utc)}
        if to_status in {"accepted", "declined"} and item.acknowledged_at is None:
            updates["acknowledged_at"] = datetime.now(timezone.utc)
        if to_status in {"acknowledged", "accepted", "declined"} and item.viewed_at is None:
            updates["viewed_at"] = datetime.now(timezone.utc)
        return await self._transition(item, to_status=to_status, updates=updates)

    async def _transition(self, item: Recommendation, *, to_status: str, updates: dict[str, object] | None = None) -> Recommendation:
        allowed = _ALLOWED_TRANSITIONS.get(item.status, set())
        if to_status not in allowed and item.status != to_status:
            raise ValueError(f"invalid recommendation transition: {item.status} -> {to_status}")
        payload = asdict(item)
        payload["status"] = to_status
        payload["updated_at"] = datetime.now(timezone.utc)
        if updates:
            payload.update(updates)
        updated = Recommendation(**payload)
        await self.repository.save(updated)
        return updated

    def _validate_type_and_source(self, *, recommendation_type: str, source_kind: str) -> None:
        if recommendation_type not in RECOMMENDATION_TYPES:
            raise ValueError(f"Unsupported recommendation_type: {recommendation_type}")
        if source_kind not in RECOMMENDATION_SOURCE_KINDS:
            raise ValueError(f"Unsupported source_kind: {source_kind}")
