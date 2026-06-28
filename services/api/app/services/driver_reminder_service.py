from __future__ import annotations

import asyncio
import logging

from app.core.database import get_pool

logger = logging.getLogger(__name__)


async def _check_overdue_pending_bookings() -> None:
    """Atomically find pending bookings older than 2 hours with no existing reminder
    and insert one booking_received notification_event per booking.

    The INSERT ... SELECT with NOT EXISTS is atomic — no separate check-then-insert
    race is possible, satisfying FR-033 (exactly one reminder per overdue booking).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            INSERT INTO notification_events (recipient_user_id, event_type, payload)
            SELECT
                r.driver_id,
                'booking_received',
                jsonb_build_object(
                    'ride_id',            r.id::text,
                    'booking_id',         b.id::text,
                    'departure_datetime', r.departure_datetime::text,
                    'deep_link',          '/(driver)/rides/' || r.id::text || '/bookings'
                )
            FROM bookings b
            JOIN rides r ON r.id = b.ride_id
            WHERE b.status = 'pending'
              AND b.created_at < NOW() - INTERVAL '2 hours'
              AND NOT EXISTS (
                  SELECT 1
                  FROM notification_events ne
                  WHERE ne.event_type = 'booking_received'
                    AND (ne.payload->>'booking_id')::uuid = b.id
              )
            """
        )
        # asyncpg returns "INSERT 0 N" as a string; extract the count for logging
        inserted = int(result.split()[-1]) if result else 0
        if inserted:
            logger.info("Driver reminder: inserted %d overdue booking_received event(s)", inserted)


async def driver_reminder_loop() -> None:
    """Background task: sweep for overdue unresponded bookings every 5 minutes."""
    while True:
        try:
            await _check_overdue_pending_bookings()
        except Exception as exc:
            logger.error("Driver reminder sweep error: %s", exc)
        await asyncio.sleep(300)
