from __future__ import annotations

import uuid
import logging

from app.core.database import get_pool

logger = logging.getLogger(__name__)


async def handle_driver_revocation(driver_id: uuid.UUID, revocation_type: str) -> dict:
    """
    Bulk-cancel all scheduled rides for a driver whose verification was revoked.
    Returns a count of cancelled rides.
    """
    reason = f"Driver verification revoked: {revocation_type}"
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            cancelled_ids = await conn.fetch(
                """
                UPDATE rides
                SET status = 'cancelled',
                    cancellation_reason = $2,
                    cancellation_source = 'system',
                    updated_at = now()
                WHERE driver_id = $1
                  AND status = 'scheduled'
                RETURNING id
                """,
                driver_id, reason,
            )

            if cancelled_ids:
                # Bulk insert history log entries
                await conn.executemany(
                    """
                    INSERT INTO ride_history_logs (ride_id, actor_id, action, reason)
                    VALUES ($1, $2, 'cancelled', $3)
                    """,
                    [(row["id"], driver_id, reason) for row in cancelled_ids],
                )

    count = len(cancelled_ids) if cancelled_ids else 0
    logger.info("Revocation: cancelled %d scheduled rides for driver %s", count, driver_id)

    # Enqueue cancellation emails for each affected ride (outside transaction)
    if count > 0:
        from app.services.notification_service import enqueue_cancellation_emails
        for row in cancelled_ids:
            try:
                await enqueue_cancellation_emails(row["id"])
            except Exception as exc:
                logger.warning("Failed to enqueue emails for ride %s: %s", row["id"], exc)

    return {"cancelled_rides": count}
