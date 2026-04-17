from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.application.communication import ReminderRecoveryService


async def run_reminder_recovery_once(*, service: ReminderRecoveryService, batch_limit: int = 100) -> int:
    now = datetime.now(timezone.utc)
    logger = logging.getLogger("dentflow.worker")
    try:
        stale = await service.recover_stale_queued_reminders(now=now, limit=batch_limit)
        failed = await service.escalate_failed_delivery_reminders(now=now, limit=batch_limit)
        no_response = await service.detect_confirmation_no_response(now=now, limit=batch_limit)
        total = stale.stale_requeued + stale.stale_failed + failed.failed_escalated + no_response.no_response_escalated
        logger.info(
            "reminder recovery task completed",
            extra={
                "extra": {
                    "stale_requeued": stale.stale_requeued,
                    "stale_failed": stale.stale_failed,
                    "failed_escalated": failed.failed_escalated,
                    "no_response_escalated": no_response.no_response_escalated,
                }
            },
        )
        return total
    except Exception as exc:  # noqa: BLE001
        logger.warning("reminder recovery task failed", extra={"extra": {"error": str(exc), "batch_limit": batch_limit}})
        return 0
