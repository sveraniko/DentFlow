import os
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from app.domain.patient_registry import PreVisitQuestionnaire, PreVisitQuestionnaireAnswer
from app.infrastructure.db.bootstrap import bootstrap_database
from app.infrastructure.db.engine import create_engine
from app.infrastructure.db.patient_repository import (
    DbPatientRegistryRepository,
    _map_pre_visit_questionnaire,
    _map_pre_visit_questionnaire_answer,
)
from app.config.settings import DatabaseConfig

ROOT = Path(__file__).resolve().parents[1]


def test_repository_methods_exist() -> None:
    for name in [
        "get_pre_visit_questionnaire",
        "list_pre_visit_questionnaires",
        "upsert_pre_visit_questionnaire",
        "complete_pre_visit_questionnaire",
        "list_pre_visit_questionnaire_answers",
        "upsert_pre_visit_questionnaire_answer",
        "upsert_pre_visit_questionnaire_answers",
        "delete_pre_visit_questionnaire_answer",
        "get_latest_pre_visit_questionnaire_for_booking",
        "get_latest_pre_visit_questionnaire_for_patient",
    ]:
        assert hasattr(DbPatientRegistryRepository, name)


def test_map_pre_visit_questionnaire() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "questionnaire_id": "q1",
        "clinic_id": "c1",
        "patient_id": "p1",
        "booking_id": "b1",
        "questionnaire_type": "intake",
        "status": "in_progress",
        "version": 1,
        "completed_at": None,
        "created_at": now,
        "updated_at": now,
    }
    mapped = _map_pre_visit_questionnaire(row)
    assert isinstance(mapped, PreVisitQuestionnaire)
    assert mapped.questionnaire_id == "q1"


def test_map_pre_visit_questionnaire_answer_json_shapes() -> None:
    now = datetime.now(timezone.utc)
    dict_row = {
        "answer_id": "a1",
        "questionnaire_id": "q1",
        "question_key": "allergy",
        "answer_value": {"value": "none"},
        "answer_type": "text",
        "visibility": "staff_only",
        "created_at": now,
        "updated_at": now,
    }
    list_row = {**dict_row, "answer_id": "a2", "answer_value": ["a", "b"]}
    mapped_dict = _map_pre_visit_questionnaire_answer(dict_row)
    mapped_list = _map_pre_visit_questionnaire_answer(list_row)
    assert isinstance(mapped_dict, PreVisitQuestionnaireAnswer)
    assert isinstance(mapped_list, PreVisitQuestionnaireAnswer)
    assert mapped_dict.answer_value == {"value": "none"}
    assert mapped_list.answer_value == ["a", "b"]


def test_upsert_answer_serializes_jsonb_param(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeResult:
        def mappings(self):
            return self

        def one(self):
            now = datetime.now(timezone.utc)
            return {
                "answer_id": "a1",
                "questionnaire_id": "q1",
                "question_key": "allergy",
                "answer_value": {"value": "latex"},
                "answer_type": "json",
                "visibility": "staff_only",
                "created_at": now,
                "updated_at": now,
            }

    class _FakeConn:
        async def execute(self, _sql, params):
            captured.update(params)
            return _FakeResult()

    class _FakeBegin:
        async def __aenter__(self):
            return _FakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _FakeEngine:
        def begin(self):
            return _FakeBegin()

        async def dispose(self):
            return None

    monkeypatch.setattr("app.infrastructure.db.patient_repository.create_engine", lambda _cfg: _FakeEngine())
    repo = DbPatientRegistryRepository(DatabaseConfig(dsn="postgresql+asyncpg://unused"))
    answer = PreVisitQuestionnaireAnswer("a1", "q1", "allergy", {"value": "latex"}, "json")

    persisted = asyncio.run(repo.upsert_pre_visit_questionnaire_answer(answer))

    assert isinstance(persisted, PreVisitQuestionnaireAnswer)
    assert captured["answer_value"] == '{"value": "latex"}'


async def _build_db_repo() -> DbPatientRegistryRepository:
    dsn = os.getenv("DENTFLOW_TEST_DB_DSN")
    if not dsn:
        pytest.skip("DENTFLOW_TEST_DB_DSN is not set")
    db_config = DatabaseConfig(dsn=dsn)
    await bootstrap_database(db_config)
    engine = create_engine(db_config)
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE booking.bookings, core_patient.pre_visit_questionnaire_answers, core_patient.pre_visit_questionnaires, core_patient.patients, core_reference.doctors, core_reference.services, core_reference.branches, core_reference.clinics CASCADE"))
        await conn.execute(text("INSERT INTO core_reference.clinics (clinic_id, code, display_name, timezone, default_locale, status) VALUES ('c1','c1','Clinic','UTC','en','active')"))
        await conn.execute(text("INSERT INTO core_reference.branches (branch_id, clinic_id, display_name, timezone, status) VALUES ('br1','c1','Branch','UTC','active')"))
        await conn.execute(text("INSERT INTO core_reference.doctors (doctor_id, clinic_id, branch_id, display_name, specialty_code, public_booking_enabled, status) VALUES ('d1','c1','br1','Doc','general',TRUE,'active')"))
        await conn.execute(text("INSERT INTO core_reference.services (service_id, clinic_id, code, title_key, duration_minutes, specialty_required, status) VALUES ('s1','c1','svc','svc',30,FALSE,'active')"))
        await conn.execute(text("INSERT INTO core_patient.patients (patient_id, clinic_id, full_name_legal, first_name, last_name, display_name, status) VALUES ('p1','c1','Pat One','Pat','One','Pat One','active')"))
        await conn.execute(text("INSERT INTO booking.bookings (booking_id, clinic_id, branch_id, patient_id, doctor_id, service_id, booking_mode, source_channel, scheduled_start_at, scheduled_end_at, status) VALUES ('b1','c1','br1','p1','d1','s1','manual','staff',NOW(),NOW()+INTERVAL '30 minutes','confirmed')"))
    await engine.dispose()
    return DbPatientRegistryRepository(db_config)


def test_db_questionnaire_lifecycle() -> None:
    db_repo = asyncio.run(_build_db_repo())
    q = PreVisitQuestionnaire(
        questionnaire_id="q1", clinic_id="c1", patient_id="p1", booking_id="b1", questionnaire_type="intake", status="in_progress"
    )
    created = asyncio.run(db_repo.upsert_pre_visit_questionnaire(q))
    fetched = asyncio.run(db_repo.get_pre_visit_questionnaire(clinic_id="c1", questionnaire_id="q1"))
    listed_patient = asyncio.run(db_repo.list_pre_visit_questionnaires(clinic_id="c1", patient_id="p1"))
    listed_booking = asyncio.run(db_repo.list_pre_visit_questionnaires(clinic_id="c1", patient_id="p1", booking_id="b1"))
    updated = asyncio.run(db_repo.upsert_pre_visit_questionnaire(
        PreVisitQuestionnaire(
            questionnaire_id="q1",
            clinic_id="c1",
            patient_id="p1",
            booking_id="b1",
            questionnaire_type="intake",
            status="ready",
            version=2,
        )
    ))
    assert created.questionnaire_id == "q1"
    assert fetched is not None and fetched.booking_id == "b1"
    assert len(listed_patient) >= 1
    assert len(listed_booking) >= 1
    assert updated.status == "ready"
    assert updated.version == 2


def test_db_answer_upsert_list_delete() -> None:
    db_repo = asyncio.run(_build_db_repo())
    asyncio.run(db_repo.upsert_pre_visit_questionnaire(PreVisitQuestionnaire("q2", "c1", "p1", "intake", "in_progress", "b1")))
    a1 = PreVisitQuestionnaireAnswer("a1", "q2", "allergy", {"value": "none"}, "json")
    persisted = asyncio.run(db_repo.upsert_pre_visit_questionnaire_answer(a1))
    asyncio.run(db_repo.upsert_pre_visit_questionnaire_answer(PreVisitQuestionnaireAnswer("a1", "q2", "allergy", {"value": "latex"}, "json", "staff_only")))
    asyncio.run(db_repo.upsert_pre_visit_questionnaire_answers([
        PreVisitQuestionnaireAnswer("a2", "q2", "pain", [1, 2], "json"),
        PreVisitQuestionnaireAnswer("a3", "q2", "notes", "hello", "text"),
    ]))
    answers = asyncio.run(db_repo.list_pre_visit_questionnaire_answers(questionnaire_id="q2"))
    deleted = asyncio.run(db_repo.delete_pre_visit_questionnaire_answer(questionnaire_id="q2", question_key="pain"))
    remaining = asyncio.run(db_repo.list_pre_visit_questionnaire_answers(questionnaire_id="q2"))
    assert persisted.answer_id == "a1"
    assert any(a.question_key == "allergy" and a.answer_value.get("value") == "latex" for a in answers)
    assert deleted is True
    assert all(a.question_key != "pain" for a in remaining)


def test_db_complete_and_latest_ordering() -> None:
    db_repo = asyncio.run(_build_db_repo())
    base = datetime.now(timezone.utc)
    asyncio.run(db_repo.upsert_pre_visit_questionnaire(PreVisitQuestionnaire("q3", "c1", "p1", "intake", "in_progress", "b1", 1, None, base - timedelta(minutes=5), base - timedelta(minutes=5))))
    asyncio.run(db_repo.upsert_pre_visit_questionnaire(PreVisitQuestionnaire("q4", "c1", "p1", "intake", "in_progress", "b1", 1, None, base - timedelta(minutes=2), base - timedelta(minutes=2))))
    completed = asyncio.run(db_repo.complete_pre_visit_questionnaire(clinic_id="c1", questionnaire_id="q3"))
    latest_booking = asyncio.run(db_repo.get_latest_pre_visit_questionnaire_for_booking(clinic_id="c1", booking_id="b1"))
    latest_patient = asyncio.run(db_repo.get_latest_pre_visit_questionnaire_for_patient(clinic_id="c1", patient_id="p1"))
    assert completed is not None and completed.status == "completed" and completed.completed_at is not None
    assert latest_booking is not None and latest_booking.questionnaire_id == "q3"
    assert latest_patient is not None and latest_patient.questionnaire_id == "q3"


def test_no_alembic_versions_added() -> None:
    assert not (ROOT / "alembic/versions").exists()
