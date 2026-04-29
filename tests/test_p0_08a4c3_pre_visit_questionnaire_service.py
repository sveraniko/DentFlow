from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import pytest

from app.application.patient.questionnaire import PreVisitQuestionnaireService
from app.domain.patient_registry.models import PreVisitQuestionnaire, PreVisitQuestionnaireAnswer


def run(coro):
    return asyncio.run(coro)


@dataclass
class FakeQuestionnaireRepo:
    questionnaire: PreVisitQuestionnaire | None = None
    answers: dict[tuple[str, str], PreVisitQuestionnaireAnswer] = field(default_factory=dict)
    last_upsert_questionnaire: PreVisitQuestionnaire | None = None

    async def get_pre_visit_questionnaire(self, *, clinic_id: str, questionnaire_id: str): return self.questionnaire if self.questionnaire and self.questionnaire.questionnaire_id == questionnaire_id else None
    async def list_pre_visit_questionnaires(self, *, clinic_id: str, patient_id: str, booking_id: str | None = None, status: str | None = None): return [self.questionnaire] if self.questionnaire else []
    async def upsert_pre_visit_questionnaire(self, questionnaire: PreVisitQuestionnaire): self.last_upsert_questionnaire = questionnaire; self.questionnaire = questionnaire; return questionnaire
    async def complete_pre_visit_questionnaire(self, *, clinic_id: str, questionnaire_id: str, completed_at: datetime):
        if self.questionnaire is None or self.questionnaire.questionnaire_id != questionnaire_id:
            return None
        self.questionnaire = PreVisitQuestionnaire(**{**asdict(self.questionnaire), "status": "completed", "completed_at": completed_at})
        return self.questionnaire
    async def list_pre_visit_questionnaire_answers(self, *, questionnaire_id: str): return [a for a in self.answers.values() if a.questionnaire_id == questionnaire_id]
    async def upsert_pre_visit_questionnaire_answer(self, answer: PreVisitQuestionnaireAnswer): self.answers[(answer.questionnaire_id, answer.question_key)] = answer; return answer
    async def upsert_pre_visit_questionnaire_answers(self, answers):
        for answer in answers: self.answers[(answer.questionnaire_id, answer.question_key)] = answer
        return list(answers)
    async def delete_pre_visit_questionnaire_answer(self, *, questionnaire_id: str, question_key: str): return self.answers.pop((questionnaire_id, question_key), None) is not None
    async def get_latest_pre_visit_questionnaire_for_booking(self, *, clinic_id: str, booking_id: str, questionnaire_type: str | None = None): return self.questionnaire
    async def get_latest_pre_visit_questionnaire_for_patient(self, *, clinic_id: str, patient_id: str, questionnaire_type: str | None = None): return self.questionnaire


def test_service_exists_and_methods_exist() -> None:
    service = PreVisitQuestionnaireService(FakeQuestionnaireRepo())
    for method in ["start_questionnaire", "get_questionnaire", "list_questionnaires", "save_answer", "save_answers", "list_answers", "delete_answer", "complete_questionnaire", "get_latest_for_booking", "get_latest_for_patient"]:
        assert hasattr(service, method)


def test_start_questionnaire_validates_and_delegates() -> None:
    repo = FakeQuestionnaireRepo(); service = PreVisitQuestionnaireService(repo)
    q = run(service.start_questionnaire(clinic_id="cl_1", patient_id="pat_1", booking_id="b_1", questionnaire_type="pre_visit", version=2))
    assert q.status == "in_progress" and q.questionnaire_id.startswith("pvq_") and repo.last_upsert_questionnaire is not None


def test_invalid_start_inputs() -> None:
    service = PreVisitQuestionnaireService(FakeQuestionnaireRepo())
    with pytest.raises(ValueError): run(service.start_questionnaire(clinic_id="cl", patient_id="pat", questionnaire_type="bad"))
    with pytest.raises(ValueError): run(service.start_questionnaire(clinic_id="cl", patient_id="pat", version=0))
    with pytest.raises(ValueError): run(service.start_questionnaire(clinic_id="cl", patient_id="  "))


def test_save_answer_validation_normalization_and_idempotency() -> None:
    service = PreVisitQuestionnaireService(FakeQuestionnaireRepo())
    a1 = run(service.save_answer(questionnaire_id="q1", question_key=" has allergy ", answer_value={"v": "none"}, answer_type="json", visibility="staff_only"))
    a2 = run(service.save_answer(questionnaire_id="q1", question_key="has   allergy", answer_value={"v": "latex"}, answer_type="json", visibility="staff_only"))
    assert a1.question_key == "has_allergy"
    assert a1.answer_id == a2.answer_id


def test_save_answers_bulk_tuple_and_model_inputs() -> None:
    service = PreVisitQuestionnaireService(FakeQuestionnaireRepo())
    out1 = run(service.save_answers(questionnaire_id="q1", answers=[("pain", 2, "number"), ("notes", "ok", "text")]))
    out2 = run(service.save_answers(questionnaire_id="q1", answers=[PreVisitQuestionnaireAnswer("x", "q1", "when", "2026-01-01", "date")]))
    assert isinstance(out1, tuple) and len(out1) == 2 and isinstance(out2, tuple) and len(out2) == 1




def test_answer_value_accepts_json_scalar_and_array_types() -> None:
    service = PreVisitQuestionnaireService(FakeQuestionnaireRepo())
    values = [
        ("note", "text ok", "text"),
        ("symptoms", ["pain", "swelling"], "json"),
        ("pain_level", 3, "number"),
        ("consent", True, "boolean"),
    ]
    persisted = [run(service.save_answer(questionnaire_id="q1", question_key=k, answer_value=v, answer_type=t)) for k, v, t in values]
    assert [a.answer_value for a in persisted] == ["text ok", ["pain", "swelling"], 3, True]

def test_invalid_answer_inputs() -> None:
    service = PreVisitQuestionnaireService(FakeQuestionnaireRepo())
    with pytest.raises(ValueError): run(service.save_answer(questionnaire_id="q1", question_key="", answer_value="x", answer_type="text"))
    with pytest.raises(ValueError): run(service.save_answer(questionnaire_id="q1", question_key="x", answer_value="x", answer_type="bad"))
    with pytest.raises(ValueError): run(service.save_answer(questionnaire_id="q1", question_key="x", answer_value="x", answer_type="text", visibility="bad"))
    with pytest.raises(ValueError): run(service.save_answer(questionnaire_id="q1", question_key="x", answer_value=set([1]), answer_type="json"))


def test_complete_and_latest_delegate() -> None:
    repo = FakeQuestionnaireRepo(questionnaire=PreVisitQuestionnaire("q1", "cl_1", "pat_1", "pre_visit", "in_progress", "b_1"))
    service = PreVisitQuestionnaireService(repo, clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
    done = run(service.complete_questionnaire(clinic_id="cl_1", questionnaire_id="q1"))
    missing = run(service.complete_questionnaire(clinic_id="cl_1", questionnaire_id="missing"))
    assert done is not None and done.status == "completed" and missing is None
    assert run(service.get_latest_for_booking(clinic_id="cl_1", booking_id="b_1")) is not None
    assert run(service.get_latest_for_patient(clinic_id="cl_1", patient_id="pat_1")) is not None


def test_no_migrations_or_router_changes() -> None:
    import pathlib
    migration_like = [p for p in pathlib.Path('.').rglob('*') if p.is_file() and ('alembic' in str(p).lower() or 'migration' in str(p).lower())]
    assert not migration_like
