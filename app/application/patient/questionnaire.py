from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha1
from typing import Protocol, Sequence
from uuid import uuid4

from app.domain.patient_registry.models import PreVisitQuestionnaire, PreVisitQuestionnaireAnswer

_ALLOWED_TYPES = {"pre_visit", "medical_history", "consent", "dental_history", "custom"}
_ALLOWED_STATUSES = {"draft", "in_progress", "completed", "cancelled", "expired"}
_ALLOWED_ANSWER_TYPES = {"text", "number", "boolean", "choice", "multi_choice", "date", "json"}
_ALLOWED_VISIBILITY = {"patient_visible", "staff_only", "doctor_only", "admin_only"}


class PreVisitQuestionnaireRepositoryProtocol(Protocol):
    async def get_pre_visit_questionnaire(self, *, clinic_id: str, questionnaire_id: str) -> PreVisitQuestionnaire | None: ...
    async def list_pre_visit_questionnaires(
        self, *, clinic_id: str, patient_id: str, booking_id: str | None = None, status: str | None = None
    ) -> list[PreVisitQuestionnaire]: ...
    async def upsert_pre_visit_questionnaire(self, questionnaire: PreVisitQuestionnaire) -> PreVisitQuestionnaire: ...
    async def complete_pre_visit_questionnaire(self, *, clinic_id: str, questionnaire_id: str, completed_at: datetime) -> PreVisitQuestionnaire | None: ...
    async def list_pre_visit_questionnaire_answers(self, *, questionnaire_id: str) -> list[PreVisitQuestionnaireAnswer]: ...
    async def upsert_pre_visit_questionnaire_answer(self, answer: PreVisitQuestionnaireAnswer) -> PreVisitQuestionnaireAnswer: ...
    async def upsert_pre_visit_questionnaire_answers(self, answers: Sequence[PreVisitQuestionnaireAnswer]) -> list[PreVisitQuestionnaireAnswer]: ...
    async def delete_pre_visit_questionnaire_answer(self, *, questionnaire_id: str, question_key: str) -> bool: ...
    async def get_latest_pre_visit_questionnaire_for_booking(
        self, *, clinic_id: str, booking_id: str, questionnaire_type: str | None = None
    ) -> PreVisitQuestionnaire | None: ...
    async def get_latest_pre_visit_questionnaire_for_patient(
        self, *, clinic_id: str, patient_id: str, questionnaire_type: str | None = None
    ) -> PreVisitQuestionnaire | None: ...


class PreVisitQuestionnaireService:
    def __init__(self, repository: PreVisitQuestionnaireRepositoryProtocol, *, clock=None) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def start_questionnaire(
        self, *, clinic_id: str, patient_id: str, booking_id: str | None = None, questionnaire_type: str = "pre_visit", version: int = 1
    ) -> PreVisitQuestionnaire:
        self._require_non_empty("clinic_id", clinic_id)
        self._require_non_empty("patient_id", patient_id)
        self._validate_questionnaire_type(questionnaire_type)
        if version < 1:
            raise ValueError("version must be >= 1")
        questionnaire = PreVisitQuestionnaire(
            questionnaire_id=f"pvq_{uuid4().hex}",
            clinic_id=clinic_id,
            patient_id=patient_id,
            booking_id=booking_id,
            questionnaire_type=questionnaire_type,
            status="in_progress",
            version=version,
        )
        return await self._repository.upsert_pre_visit_questionnaire(questionnaire)

    async def get_questionnaire(self, *, clinic_id: str, questionnaire_id: str) -> PreVisitQuestionnaire | None:
        self._require_non_empty("clinic_id", clinic_id)
        self._require_non_empty("questionnaire_id", questionnaire_id)
        return await self._repository.get_pre_visit_questionnaire(clinic_id=clinic_id, questionnaire_id=questionnaire_id)

    async def list_questionnaires(
        self, *, clinic_id: str, patient_id: str, booking_id: str | None = None, status: str | None = None
    ) -> tuple[PreVisitQuestionnaire, ...]:
        self._require_non_empty("clinic_id", clinic_id)
        self._require_non_empty("patient_id", patient_id)
        if status is not None and status not in _ALLOWED_STATUSES:
            raise ValueError("Invalid status")
        return tuple(
            await self._repository.list_pre_visit_questionnaires(
                clinic_id=clinic_id,
                patient_id=patient_id,
                booking_id=booking_id,
                status=status,
            )
        )

    async def save_answer(self, *, questionnaire_id: str, question_key: str, answer_value: object, answer_type: str, visibility: str = "staff_only") -> PreVisitQuestionnaireAnswer:
        self._require_non_empty("questionnaire_id", questionnaire_id)
        normalized_key = self._normalize_question_key(question_key)
        self._validate_answer_type(answer_type)
        self._validate_visibility(visibility)
        self._ensure_json_serializable(answer_value)
        answer = PreVisitQuestionnaireAnswer(
            answer_id=self._build_answer_id(questionnaire_id=questionnaire_id, normalized_question_key=normalized_key),
            questionnaire_id=questionnaire_id,
            question_key=normalized_key,
            answer_value=answer_value,
            answer_type=answer_type,
            visibility=visibility,
        )
        return await self._repository.upsert_pre_visit_questionnaire_answer(answer)

    async def save_answers(self, *, questionnaire_id: str, answers: Sequence[tuple[str, object, str]] | Sequence[PreVisitQuestionnaireAnswer], visibility: str = "staff_only") -> tuple[PreVisitQuestionnaireAnswer, ...]:
        persisted: list[PreVisitQuestionnaireAnswer] = []
        for item in answers:
            if isinstance(item, PreVisitQuestionnaireAnswer):
                persisted.append(
                    await self.save_answer(
                        questionnaire_id=questionnaire_id,
                        question_key=item.question_key,
                        answer_value=item.answer_value,
                        answer_type=item.answer_type,
                        visibility=item.visibility,
                    )
                )
            else:
                question_key, answer_value, answer_type = item
                persisted.append(
                    await self.save_answer(
                        questionnaire_id=questionnaire_id,
                        question_key=question_key,
                        answer_value=answer_value,
                        answer_type=answer_type,
                        visibility=visibility,
                    )
                )
        return tuple(persisted)

    async def list_answers(self, *, questionnaire_id: str) -> tuple[PreVisitQuestionnaireAnswer, ...]:
        self._require_non_empty("questionnaire_id", questionnaire_id)
        return tuple(await self._repository.list_pre_visit_questionnaire_answers(questionnaire_id=questionnaire_id))

    async def delete_answer(self, *, questionnaire_id: str, question_key: str) -> bool:
        self._require_non_empty("questionnaire_id", questionnaire_id)
        normalized_key = self._normalize_question_key(question_key)
        return await self._repository.delete_pre_visit_questionnaire_answer(questionnaire_id=questionnaire_id, question_key=normalized_key)

    async def complete_questionnaire(self, *, clinic_id: str, questionnaire_id: str) -> PreVisitQuestionnaire | None:
        self._require_non_empty("clinic_id", clinic_id)
        self._require_non_empty("questionnaire_id", questionnaire_id)
        return await self._repository.complete_pre_visit_questionnaire(
            clinic_id=clinic_id, questionnaire_id=questionnaire_id, completed_at=self._clock()
        )

    async def get_latest_for_booking(self, *, clinic_id: str, booking_id: str, questionnaire_type: str | None = None) -> PreVisitQuestionnaire | None:
        self._require_non_empty("clinic_id", clinic_id)
        self._require_non_empty("booking_id", booking_id)
        if questionnaire_type is not None:
            self._validate_questionnaire_type(questionnaire_type)
        return await self._repository.get_latest_pre_visit_questionnaire_for_booking(
            clinic_id=clinic_id, booking_id=booking_id, questionnaire_type=questionnaire_type
        )

    async def get_latest_for_patient(self, *, clinic_id: str, patient_id: str, questionnaire_type: str | None = None) -> PreVisitQuestionnaire | None:
        self._require_non_empty("clinic_id", clinic_id)
        self._require_non_empty("patient_id", patient_id)
        if questionnaire_type is not None:
            self._validate_questionnaire_type(questionnaire_type)
        return await self._repository.get_latest_pre_visit_questionnaire_for_patient(
            clinic_id=clinic_id, patient_id=patient_id, questionnaire_type=questionnaire_type
        )

    def _build_answer_id(self, *, questionnaire_id: str, normalized_question_key: str) -> str:
        base = f"pvqa_{questionnaire_id}_{normalized_question_key}"
        if len(base) <= 120 and all(ch.isalnum() or ch in {"_", "-"} for ch in base):
            return base
        return f"pvqa_{sha1(base.encode('utf-8')).hexdigest()[:24]}"

    def _require_non_empty(self, field: str, value: str) -> None:
        if not value or not value.strip():
            raise ValueError(f"{field} is required")

    def _validate_questionnaire_type(self, questionnaire_type: str) -> None:
        if questionnaire_type not in _ALLOWED_TYPES:
            raise ValueError("Invalid questionnaire_type")

    def _validate_answer_type(self, answer_type: str) -> None:
        if answer_type not in _ALLOWED_ANSWER_TYPES:
            raise ValueError("Invalid answer_type")

    def _validate_visibility(self, visibility: str) -> None:
        if visibility not in _ALLOWED_VISIBILITY:
            raise ValueError("Invalid visibility")

    def _normalize_question_key(self, question_key: str) -> str:
        self._require_non_empty("question_key", question_key)
        return "_".join(question_key.strip().split())

    def _ensure_json_serializable(self, answer_value: object) -> None:
        try:
            json.dumps(answer_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("answer_value must be JSON-serializable") from exc
