from __future__ import annotations

import asyncio
from pathlib import Path

from app.application.care_commerce.delivery import PatientCareOrderDeliveryService
from app.common.i18n import I18nService


class _BindingReader:
    def __init__(self, rows):
        self._rows = rows

    async def find_telegram_user_ids_by_patient(self, *, clinic_id: str, patient_id: str):
        _ = clinic_id, patient_id
        return list(self._rows)


class _Sender:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    async def send_patient_care_pickup_ready_delivery(
        self,
        *,
        telegram_user_id: int,
        text: str,
        button_text: str,
        callback_data: str,
    ) -> None:
        self.payloads.append(
            {
                "telegram_user_id": telegram_user_id,
                "text": text,
                "button_text": button_text,
                "callback_data": callback_data,
            }
        )


class _PreferenceReader:
    def __init__(self, preferred_language: str | None) -> None:
        self._preferred_language = preferred_language

    async def get_preferences(self, patient_id: str):
        _ = patient_id
        if self._preferred_language is None:
            return None
        class _Pref:
            preferred_language = self._preferred_language
        return _Pref()


def test_pickup_ready_delivery_uses_canonical_careo_open_callback() -> None:
    sender = _Sender()
    service = PatientCareOrderDeliveryService(
        binding_reader=_BindingReader(rows=[123456]),
        sender=sender,
        i18n=I18nService(locales_path=Path("locales"), default_locale="en"),
    )

    result = asyncio.run(
        service.deliver_pickup_ready_if_possible(
            clinic_id="c1",
            patient_id="p1",
            care_order_id="co-42",
            locale="en",
            pickup_branch_label="Main branch",
        )
    )

    assert result.status == "delivered"
    assert sender.payloads[0]["callback_data"] == "careo:open:co-42"
    assert "ready for pickup" in str(sender.payloads[0]["text"]).lower()


def test_pickup_ready_delivery_skips_on_ambiguous_binding() -> None:
    sender = _Sender()
    service = PatientCareOrderDeliveryService(
        binding_reader=_BindingReader(rows=[1001, "1002"]),
        sender=sender,
        i18n=I18nService(locales_path=Path("locales"), default_locale="en"),
    )

    result = asyncio.run(
        service.deliver_pickup_ready_if_possible(
            clinic_id="c1",
            patient_id="p1",
            care_order_id="co-ambiguous",
            locale="en",
        )
    )

    assert result.status == "skipped_ambiguous_binding"
    assert sender.payloads == []


def test_pickup_ready_delivery_skips_without_binding_and_does_not_send() -> None:
    sender = _Sender()
    service = PatientCareOrderDeliveryService(
        binding_reader=_BindingReader(rows=[]),
        sender=sender,
        i18n=I18nService(locales_path=Path("locales"), default_locale="en"),
    )

    result = asyncio.run(
        service.deliver_pickup_ready_if_possible(
            clinic_id="c1",
            patient_id="p1",
            care_order_id="co-no-binding",
            locale="en",
        )
    )

    assert result.status == "skipped_no_binding"
    assert sender.payloads == []


def test_pickup_ready_delivery_uses_patient_preferred_locale_over_hint() -> None:
    sender = _Sender()
    service = PatientCareOrderDeliveryService(
        binding_reader=_BindingReader(rows=[123456]),
        sender=sender,
        i18n=I18nService(locales_path=Path("locales"), default_locale="en"),
        locale_reader=_PreferenceReader(preferred_language="ru"),
    )

    result = asyncio.run(
        service.deliver_pickup_ready_if_possible(
            clinic_id="c1",
            patient_id="p1",
            care_order_id="co-locale",
            locale="en",
        )
    )

    assert result.status == "delivered"
    assert "ваш заказ готов к выдаче" in str(sender.payloads[0]["text"]).lower()


def test_pickup_ready_delivery_falls_back_to_locale_hint_without_patient_preference() -> None:
    sender = _Sender()
    service = PatientCareOrderDeliveryService(
        binding_reader=_BindingReader(rows=[123456]),
        sender=sender,
        i18n=I18nService(locales_path=Path("locales"), default_locale="en"),
        locale_reader=_PreferenceReader(preferred_language=None),
    )

    result = asyncio.run(
        service.deliver_pickup_ready_if_possible(
            clinic_id="c1",
            patient_id="p1",
            care_order_id="co-locale-fallback",
            locale="en",
        )
    )

    assert result.status == "delivered"
    assert "ready for pickup" in str(sender.payloads[0]["text"]).lower()
