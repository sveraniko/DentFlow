from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.application.communication import ReminderDeliveryService


async def run_reminder_delivery_once(*, service: ReminderDeliveryService, batch_limit: int = 50) -> int:
    now = datetime.now(timezone.utc)
    logger = logging.getLogger("dentflow.worker")
    claimed = await service.deliver_due_reminders(now=now, batch_limit=batch_limit)
    logger.info(
        "reminder delivery task completed",
        extra={"extra": {"claimed": claimed, "batch_limit": batch_limit}},
    )
    return claimed
