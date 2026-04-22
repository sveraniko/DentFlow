from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text

from app.application.communication import RecipientResolution, ReminderActionButton, ReminderSendResult, TelegramDeliveryTarget
from app.domain.communication import ReminderJob
from app.infrastructure.db.engine import create_engine

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.types import InlineKeyboardMarkup


@dataclass(slots=True)
class DbTelegramReminderRecipientResolver:
    db_config: object

    async def resolve(self, *, reminder: ReminderJob) -> RecipientResolution:
        engine = create_engine(self.db_config)
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT normalized_value
                        FROM core_patient.patient_contacts
                        WHERE patient_id=:patient_id
                          AND contact_type='telegram'
                          AND is_active=TRUE
                        ORDER BY is_primary DESC, is_verified DESC, updated_at DESC
                        LIMIT 1
                        """
                    ),
                    {"patient_id": reminder.patient_id},
                )
            ).mappings().first()
        await engine.dispose()
        if row is None:
            return RecipientResolution(kind="no_target", reason_code="telegram_target_missing")
        raw_value = str(row["normalized_value"] or "").strip()
        if not raw_value.isdigit():
            return RecipientResolution(kind="invalid_target", reason_code="telegram_target_invalid")
        return RecipientResolution(
            kind="target_found",
            target=TelegramDeliveryTarget(patient_id=reminder.patient_id, telegram_user_id=int(raw_value)),
        )


@dataclass(slots=True)
class AiogramTelegramReminderSender:
    bot_token: str

    async def send_reminder(self, *, target: TelegramDeliveryTarget, text: str, actions: tuple[ReminderActionButton, ...]) -> ReminderSendResult:
        from aiogram import Bot

        bot = Bot(token=self.bot_token)
        try:
            markup = _build_actions_markup(actions)
            message = await bot.send_message(chat_id=target.telegram_user_id, text=text, reply_markup=markup)
            provider_message_id = str(message.message_id) if message is not None else None
            return ReminderSendResult(provider_message_id=provider_message_id)
        finally:
            await bot.session.close()


@dataclass(slots=True)
class AiogramTelegramPatientRecommendationSender:
    bot_token: str

    async def send_patient_recommendation_delivery(
        self,
        *,
        telegram_user_id: int,
        text: str,
        button_text: str,
        callback_data: str,
    ) -> None:
        from aiogram import Bot
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        bot = Bot(token=self.bot_token)
        try:
            await bot.send_message(
                chat_id=telegram_user_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text=button_text, callback_data=callback_data)]]
                ),
            )
        finally:
            await bot.session.close()


@dataclass(slots=True)
class AiogramTelegramPatientCareOrderSender:
    bot_token: str

    async def send_patient_care_pickup_ready_delivery(
        self,
        *,
        telegram_user_id: int,
        text: str,
        button_text: str,
        callback_data: str,
    ) -> None:
        from aiogram import Bot
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        bot = Bot(token=self.bot_token)
        try:
            await bot.send_message(
                chat_id=telegram_user_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text=button_text, callback_data=callback_data)]]
                ),
            )
        finally:
            await bot.session.close()


def _build_actions_markup(actions: tuple[ReminderActionButton, ...]) -> "InlineKeyboardMarkup | None":
    if not actions:
        return None
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    rows = [[InlineKeyboardButton(text=action.label, callback_data=action.callback_data)] for action in actions]
    return InlineKeyboardMarkup(inline_keyboard=rows)
