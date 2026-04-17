from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy import text

from app.application.communication import RecipientResolution, ReminderSendResult, TelegramDeliveryTarget
from app.domain.communication import ReminderJob
from app.infrastructure.db.engine import create_engine


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

    async def send_reminder(self, *, target: TelegramDeliveryTarget, text: str) -> ReminderSendResult:
        bot = Bot(token=self.bot_token)
        try:
            message = await bot.send_message(chat_id=target.telegram_user_id, text=text)
            provider_message_id = str(message.message_id) if message is not None else None
            return ReminderSendResult(provider_message_id=provider_message_id)
        finally:
            await bot.session.close()
