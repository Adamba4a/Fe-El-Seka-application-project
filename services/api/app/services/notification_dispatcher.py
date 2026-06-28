from __future__ import annotations

import asyncio
import logging
import time

from app.core.database import get_pool
from app.services import fcm_service

logger = logging.getLogger(__name__)


async def _process_pending_notifications() -> None:
    t0 = time.monotonic()
    pool = get_pool()
    dispatched = 0
    failed = 0

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, recipient_user_id, event_type, payload, retry_count
            FROM notification_events
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 100
            """
        )

    for row in rows:
        async with pool.acquire() as conn:
            async with conn.transaction():
                locked = await conn.fetchrow(
                    """
                    SELECT id, recipient_user_id, event_type, payload, retry_count
                    FROM notification_events
                    WHERE id = $1 AND status = 'pending'
                    FOR UPDATE SKIP LOCKED
                    """,
                    row["id"],
                )
                if locked is None:
                    continue

                try:
                    success_count = await fcm_service.send_push_notifications(
                        conn,
                        locked["recipient_user_id"],
                        locked["event_type"],
                        dict(locked["payload"]),
                    )
                    await conn.execute(
                        "UPDATE notification_events SET status = 'dispatched', dispatched_at = now() WHERE id = $1",
                        locked["id"],
                    )
                    logger.debug(
                        "FCM dispatched %s → user %s (%d token(s) reached)",
                        locked["event_type"],
                        locked["recipient_user_id"],
                        success_count,
                    )
                    dispatched += 1
                except Exception as exc:
                    new_retry = locked["retry_count"] + 1
                    new_status = "failed" if new_retry >= 3 else "pending"
                    await conn.execute(
                        "UPDATE notification_events SET retry_count = $2, status = $3 WHERE id = $1",
                        locked["id"],
                        new_retry,
                        new_status,
                    )
                    logger.warning(
                        "FCM dispatch failed for event %s (retry %d/%d): %s",
                        locked["id"],
                        new_retry,
                        3,
                        exc,
                    )
                    failed += 1

    if rows:
        logger.info(
            "notification_dispatcher_loop sweep | candidates=%d dispatched=%d failed=%d | duration_ms=%.1f",
            len(rows), dispatched, failed, (time.monotonic() - t0) * 1000,
        )


async def notification_dispatcher_loop() -> None:
    """Background task: poll notification_events and dispatch FCM pushes every 30 seconds."""
    while True:
        try:
            await _process_pending_notifications()
        except Exception as exc:
            logger.error("Notification dispatcher sweep error: %s", exc)
        await asyncio.sleep(30)
