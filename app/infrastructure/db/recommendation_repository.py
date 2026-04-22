from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sqlalchemy import text

from app.domain.events import build_event
from app.domain.recommendations import Recommendation
from app.infrastructure.db.engine import create_engine
from app.infrastructure.outbox.repository import OutboxRepository

_EVENT_BY_STATUS = {
    "prepared": "recommendation.prepared",
    "issued": "recommendation.issued",
    "viewed": "recommendation.viewed",
    "acknowledged": "recommendation.acknowledged",
    "accepted": "recommendation.accepted",
    "declined": "recommendation.declined",
    "expired": "recommendation.expired",
    "withdrawn": "recommendation.withdrawn",
}


class DbRecommendationRepository:
    def __init__(self, db_config: Any) -> None:
        self._db_config = db_config

    async def get(self, recommendation_id: str) -> Recommendation | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT recommendation_id, clinic_id, patient_id, booking_id, encounter_id, chart_id,
                   issued_by_actor_id, source_kind, recommendation_type, title, body_text, rationale_text,
                   status, issued_at, viewed_at, acknowledged_at, accepted_at, declined_at,
                   expired_at, withdrawn_at, created_at, updated_at
            FROM recommendation.recommendations
            WHERE recommendation_id=:recommendation_id
            """,
            {"recommendation_id": recommendation_id},
        )
        return Recommendation(**row) if row else None

    async def list_for_patient(self, *, patient_id: str, include_terminal: bool = False) -> list[Recommendation]:
        terminal_sql = "" if include_terminal else "AND status NOT IN ('withdrawn','expired')"
        rows = await _fetch_all(
            self._db_config,
            f"""
            SELECT recommendation_id, clinic_id, patient_id, booking_id, encounter_id, chart_id,
                   issued_by_actor_id, source_kind, recommendation_type, title, body_text, rationale_text,
                   status, issued_at, viewed_at, acknowledged_at, accepted_at, declined_at,
                   expired_at, withdrawn_at, created_at, updated_at
            FROM recommendation.recommendations
            WHERE patient_id=:patient_id {terminal_sql}
            ORDER BY created_at DESC
            """,
            {"patient_id": patient_id},
        )
        return [Recommendation(**row) for row in rows]

    async def list_for_booking(self, *, booking_id: str) -> list[Recommendation]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT recommendation_id, clinic_id, patient_id, booking_id, encounter_id, chart_id,
                   issued_by_actor_id, source_kind, recommendation_type, title, body_text, rationale_text,
                   status, issued_at, viewed_at, acknowledged_at, accepted_at, declined_at,
                   expired_at, withdrawn_at, created_at, updated_at
            FROM recommendation.recommendations
            WHERE booking_id=:booking_id
            ORDER BY created_at DESC
            """,
            {"booking_id": booking_id},
        )
        return [Recommendation(**row) for row in rows]

    async def list_for_chart(self, *, chart_id: str) -> list[Recommendation]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT recommendation_id, clinic_id, patient_id, booking_id, encounter_id, chart_id,
                   issued_by_actor_id, source_kind, recommendation_type, title, body_text, rationale_text,
                   status, issued_at, viewed_at, acknowledged_at, accepted_at, declined_at,
                   expired_at, withdrawn_at, created_at, updated_at
            FROM recommendation.recommendations
            WHERE chart_id=:chart_id
            ORDER BY created_at DESC
            """,
            {"chart_id": chart_id},
        )
        return [Recommendation(**row) for row in rows]

    async def save(self, item: Recommendation) -> None:
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                previous = (
                    await conn.execute(
                        text("SELECT status FROM recommendation.recommendations WHERE recommendation_id=:recommendation_id"),
                        {"recommendation_id": item.recommendation_id},
                    )
                ).scalar_one_or_none()
                await conn.execute(
                    text(
                        """
                        INSERT INTO recommendation.recommendations (
                          recommendation_id, clinic_id, patient_id, booking_id, encounter_id, chart_id,
                          issued_by_actor_id, source_kind, recommendation_type, title, body_text, rationale_text,
                          status, issued_at, viewed_at, acknowledged_at, accepted_at, declined_at,
                          expired_at, withdrawn_at, created_at, updated_at
                        ) VALUES (
                          :recommendation_id, :clinic_id, :patient_id, :booking_id, :encounter_id, :chart_id,
                          :issued_by_actor_id, :source_kind, :recommendation_type, :title, :body_text, :rationale_text,
                          :status, :issued_at, :viewed_at, :acknowledged_at, :accepted_at, :declined_at,
                          :expired_at, :withdrawn_at, :created_at, :updated_at
                        )
                        ON CONFLICT (recommendation_id) DO UPDATE SET
                          booking_id=EXCLUDED.booking_id,
                          encounter_id=EXCLUDED.encounter_id,
                          chart_id=EXCLUDED.chart_id,
                          issued_by_actor_id=EXCLUDED.issued_by_actor_id,
                          title=EXCLUDED.title,
                          body_text=EXCLUDED.body_text,
                          rationale_text=EXCLUDED.rationale_text,
                          status=EXCLUDED.status,
                          issued_at=EXCLUDED.issued_at,
                          viewed_at=EXCLUDED.viewed_at,
                          acknowledged_at=EXCLUDED.acknowledged_at,
                          accepted_at=EXCLUDED.accepted_at,
                          declined_at=EXCLUDED.declined_at,
                          expired_at=EXCLUDED.expired_at,
                          withdrawn_at=EXCLUDED.withdrawn_at,
                          updated_at=EXCLUDED.updated_at
                        """
                    ),
                    asdict(item),
                )
                if previous is None:
                    await OutboxRepository(self._db_config).append_on_connection(
                        conn,
                        build_event(
                            event_name="recommendation.created",
                            producer_context="recommendation.lifecycle",
                            clinic_id=item.clinic_id,
                            entity_type="recommendation",
                            entity_id=item.recommendation_id,
                            actor_type="staff" if item.issued_by_actor_id else None,
                            actor_id=item.issued_by_actor_id,
                            occurred_at=item.created_at,
                            payload={
                                "patient_id": item.patient_id,
                                "booking_id": item.booking_id,
                                "encounter_id": item.encounter_id,
                                "chart_id": item.chart_id,
                                "status": item.status,
                                "recommendation_type": item.recommendation_type,
                                "source_kind": item.source_kind,
                            },
                        ),
                    )
                if previous == item.status:
                    return
                event_name = _EVENT_BY_STATUS.get(item.status)
                if not event_name:
                    return
                await OutboxRepository(self._db_config).append_on_connection(
                    conn,
                    build_event(
                        event_name=event_name,
                        producer_context="recommendation.lifecycle",
                        clinic_id=item.clinic_id,
                        entity_type="recommendation",
                        entity_id=item.recommendation_id,
                        actor_type="staff" if item.issued_by_actor_id else None,
                        actor_id=item.issued_by_actor_id,
                        occurred_at=item.updated_at,
                        payload={
                            "patient_id": item.patient_id,
                            "booking_id": item.booking_id,
                            "encounter_id": item.encounter_id,
                            "chart_id": item.chart_id,
                            "status": item.status,
                            "recommendation_type": item.recommendation_type,
                            "source_kind": item.source_kind,
                        },
                    ),
                )
        finally:
            await engine.dispose()

    async def find_patient_id_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> str | None:
        rows = await self.find_patient_ids_by_telegram_user(clinic_id=clinic_id, telegram_user_id=telegram_user_id)
        if len(rows) != 1:
            return None
        return rows[0]

    async def find_patient_ids_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> list[str]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT p.patient_id
            FROM core_patient.patient_contacts p
            JOIN core_patient.patients cp ON cp.patient_id=p.patient_id
            WHERE cp.clinic_id=:clinic_id
              AND p.contact_type='telegram'
              AND p.normalized_value=:telegram_user_id
              AND p.is_active=TRUE
            """,
            {"clinic_id": clinic_id, "telegram_user_id": str(telegram_user_id)},
        )
        return [str(row["patient_id"]) for row in rows]

    async def find_primary_phone_by_patient(self, *, clinic_id: str, patient_id: str) -> str | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT p.contact_value
            FROM core_patient.patient_contacts p
            JOIN core_patient.patients cp ON cp.patient_id=p.patient_id
            WHERE cp.clinic_id=:clinic_id
              AND p.patient_id=:patient_id
              AND p.contact_type='phone'
              AND p.is_active=TRUE
            ORDER BY p.is_primary DESC, p.updated_at DESC, p.created_at DESC
            LIMIT 1
            """,
            {"clinic_id": clinic_id, "patient_id": patient_id},
        )
        if row is None:
            return None
        value = str(row.get("contact_value") or "").strip()
        return value or None

    async def find_telegram_user_ids_by_patient(self, *, clinic_id: str, patient_id: str) -> list[int]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT p.normalized_value
            FROM core_patient.patient_contacts p
            JOIN core_patient.patients cp ON cp.patient_id=p.patient_id
            WHERE cp.clinic_id=:clinic_id
              AND p.patient_id=:patient_id
              AND p.contact_type='telegram'
              AND p.is_active=TRUE
            """,
            {"clinic_id": clinic_id, "patient_id": patient_id},
        )
        trusted: list[int] = []
        for row in rows:
            raw = str(row.get("normalized_value") or "").strip()
            if raw.isdigit():
                trusted.append(int(raw))
        return trusted


async def _fetch_one(db_config: Any, sql: str, params: dict[str, object]) -> dict[str, object] | None:
    engine = create_engine(db_config)
    try:
        async with engine.connect() as conn:
            row = (await conn.execute(text(sql), params)).mappings().first()
            return dict(row) if row else None
    finally:
        await engine.dispose()


async def _fetch_all(db_config: Any, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
    engine = create_engine(db_config)
    try:
        async with engine.connect() as conn:
            rows = (await conn.execute(text(sql), params)).mappings().all()
            return [dict(row) for row in rows]
    finally:
        await engine.dispose()
