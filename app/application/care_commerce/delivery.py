from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.common.i18n import I18nService
from app.domain.patient_registry.models import PatientPreference


class PatientCareOrderTelegramBindingReader(Protocol):
    async def find_telegram_user_ids_by_patient(self, *, clinic_id: str, patient_id: str) -> list[int | str]: ...


class PatientCareOrderDeliverySender(Protocol):
    async def send_patient_care_pickup_ready_delivery(
        self,
        *,
        telegram_user_id: int,
        text: str,
        button_text: str,
        callback_data: str,
    ) -> None: ...


class PatientCareOrderLocaleReader(Protocol):
    async def get_preferences(self, patient_id: str) -> PatientPreference | None: ...


@dataclass(frozen=True, slots=True)
class PatientCareOrderDeliveryResult:
    status: str
    care_order_id: str


@dataclass(slots=True)
class PatientCareOrderDeliveryService:
    binding_reader: PatientCareOrderTelegramBindingReader | None = None
    sender: PatientCareOrderDeliverySender | None = None
    i18n: I18nService | None = None
    locale_reader: PatientCareOrderLocaleReader | None = None

    async def deliver_pickup_ready_if_possible(
        self,
        *,
        clinic_id: str,
        patient_id: str,
        care_order_id: str,
        locale: str = "en",
        pickup_branch_label: str | None = None,
    ) -> PatientCareOrderDeliveryResult:
        if self.binding_reader is None or self.sender is None:
            return PatientCareOrderDeliveryResult(status="skipped_unavailable", care_order_id=care_order_id)
        try:
            raw_rows = await self.binding_reader.find_telegram_user_ids_by_patient(clinic_id=clinic_id, patient_id=patient_id)
        except Exception:
            return PatientCareOrderDeliveryResult(status="failed_safe", care_order_id=care_order_id)
        trusted_targets = self._trusted_targets(raw_rows)
        if len(trusted_targets) == 0:
            return PatientCareOrderDeliveryResult(status="skipped_no_binding", care_order_id=care_order_id)
        if len(trusted_targets) > 1:
            return PatientCareOrderDeliveryResult(status="skipped_ambiguous_binding", care_order_id=care_order_id)
        effective_locale = await self._resolve_patient_locale(patient_id=patient_id, locale_hint=locale)
        try:
            await self.sender.send_patient_care_pickup_ready_delivery(
                telegram_user_id=trusted_targets[0],
                text=self._message_text(locale=effective_locale, pickup_branch_label=pickup_branch_label),
                button_text=self._button_text(locale=effective_locale),
                callback_data=f"careo:open:{care_order_id}",
            )
        except Exception:
            return PatientCareOrderDeliveryResult(status="failed_safe", care_order_id=care_order_id)
        return PatientCareOrderDeliveryResult(status="delivered", care_order_id=care_order_id)

    async def _resolve_patient_locale(self, *, patient_id: str, locale_hint: str) -> str:
        normalized_hint = str(locale_hint or "").strip().lower() or "en"
        if self.locale_reader is None:
            return normalized_hint
        try:
            preference = await self.locale_reader.get_preferences(patient_id)
        except Exception:
            return normalized_hint
        preferred = str(preference.preferred_language or "").strip().lower() if preference is not None else ""
        return preferred or normalized_hint

    def _trusted_targets(self, rows: list[int | str] | tuple[int | str, ...] | None) -> tuple[int, ...]:
        if not rows:
            return ()
        trusted: set[int] = set()
        for row in rows:
            normalized = str(row).strip()
            if normalized.isdigit():
                trusted.add(int(normalized))
        return tuple(sorted(trusted))

    def _message_text(self, *, locale: str, pickup_branch_label: str | None) -> str:
        if self.i18n is None:
            if str(locale).lower().startswith("ru"):
                if pickup_branch_label:
                    return f"Ваш заказ готов к выдаче в филиале {pickup_branch_label}."
                return "Ваш заказ готов к выдаче."
            if pickup_branch_label:
                return f"Your care order is ready for pickup at {pickup_branch_label}."
            return "Your care order is ready for pickup."
        key = "patient.care.pickup_ready.proactive.text.with_branch" if pickup_branch_label else "patient.care.pickup_ready.proactive.text"
        translated = self.i18n.t(key, locale)
        if translated == key:
            translated = self.i18n.t(key, "en")
        return translated.format(branch=pickup_branch_label) if pickup_branch_label else translated

    def _button_text(self, *, locale: str) -> str:
        key = "patient.care.pickup_ready.proactive.open_order.button"
        if self.i18n is None:
            return "Открыть заказ" if str(locale).lower().startswith("ru") else "Open current order"
        translated = self.i18n.t(key, locale)
        if translated != key:
            return translated
        return self.i18n.t(key, "en")
