from __future__ import annotations

import asyncio
import logging

from app.core.database import get_pool

logger = logging.getLogger(__name__)


async def _check_overdue_pending_bookings() -> None:
    """Atomically insert a booking_reminder notification for each pending booking
    older than 2 hours that has not yet received a reminder.

    Uses event_type='booking_reminder' (not 'booking_received') so the NOT EXISTS
    guard does not conflict with the initial booking_received event inserted by
    create_booking(). This is the fix for the logical deadlock identified in review.

    The INSERT...SELECT with NOT EXISTS is a single statement — no check-then-insert
    race is possible, satisfying FR-033 (exactly one reminder per overdue booking).

    passenger_name is fetched via JOIN on profiles so the payload matches the shape
    produced by create_booking() (which also includes passenger_name).

    to_char() is used instead of ::text to produce ISO-8601 datetime strings that
    match Python's datetime.isoformat() output (T-separator, colon-separated offset).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            INSERT INTO notification_events (recipient_user_id, event_type, payload)
            SELECT
                r.driver_id,
                'booking_reminder',
                jsonb_build_object(
                    'ride_id',            r.id::text,
                    'booking_id',         b.id::text,
                    'passenger_name',     COALESCE(p.display_name, ''),
                    'departure_datetime', to_char(
                                              r.departure_datetime AT TIME ZONE 'UTC',
                                              'YYYY-MM-DD"T"HH24:MI:SS+00:00'
                                          ),
                    'deep_link',          '/(driver)/rides/' || r.id::text || '/bookings'
                )
            FROM bookings b
            JOIN rides r   ON r.id = b.ride_id
            JOIN profiles p ON p.id = b.passenger_id
            WHERE b.status = 'pending'
              AND b.created_at < NOW() - INTERVAL '2 hours'
              AND NOT EXISTS (
                  SELECT 1
                  FROM notification_events ne
                  WHERE ne.event_type = 'booking_reminder'
                    AND (ne.payload->>'booking_id')::uuid = b.id
              )
            """
        )
        inserted = int(result.split()[-1]) if result else 0
        if inserted:
            logger.info("Driver reminder: inserted %d booking_reminder event(s)", inserted)


async def driver_reminder_loop() -> None:
    """Background task: sweep for overdue unresponded bookings every 5 minutes."""
    while True:
        try:
            await _check_overdue_pending_bookings()
        except Exception as exc:
            logger.error("Driver reminder sweep error: %s", exc)
        await asyncio.sleep(300)
