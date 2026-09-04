from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

from app.core.database import get_pool

logger = logging.getLogger(__name__)

_RETENTION_INTERVAL_DAYS = 30
_RETENTION_TICK_SECONDS = 86400


async def record_ping(
    ride_id: uuid.UUID,
    driver_id: uuid.UUID,
    lat: float,
    lng: float,
    recorded_at: datetime,
) -> None:
    """Fire-and-forget entry point: append one driver_location_history row.
    Called via asyncio.create_task from update_driver_location — must never
    raise, since the location-update response has already been (or is about
    to be) sent regardless of this task's outcome (FR-003/NFR-001). Mirrors
    match_logging_service.persist_match_events exactly (research.md R2)."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO driver_location_history
                    (ride_id, driver_id, location, recorded_at)
                VALUES
                    ($1, $2, ST_SetSRID(ST_MakePoint($4, $3), 4326), $5)
                """,
                ride_id, driver_id, lat, lng, recorded_at,
            )
    except Exception as exc:
        logger.error(
            "location_history record_ping failed for ride_id=%s driver_id=%s: %s",
            ride_id, driver_id, exc,
        )


async def purge_expired() -> int:
    """Deletes driver_location_history rows older than the rolling 30-day
    window (FR-004/FR-005). Idempotent: a run with nothing to delete is a
    no-op, not an error (NFR-003). Never raises — a failure is logged and
    treated as zero rows purged this tick."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                f"""
                DELETE FROM driver_location_history
                WHERE recorded_at < now() - interval '{_RETENTION_INTERVAL_DAYS} days'
                """,
            )
        # asyncpg execute() returns a status string like "DELETE 12"
        return int(result.split()[-1])
    except Exception as exc:
        logger.error("location_history purge_expired failed: %s", exc)
        return 0


async def location_history_retention_loop() -> None:
    """Background task: daily purge of driver_location_history rows past the
    30-day retention window (research.md R3 — reuses the existing in-process
    loop pattern already used by retraining_scheduler_loop and the other
    background loops in main.py, no new scheduling dependency)."""
    while True:
        try:
            deleted = await purge_expired()
            if deleted:
                logger.info("location_history_retention_loop purged %d expired row(s)", deleted)
        except Exception as exc:
            logger.error("location_history_retention_loop tick error: %s", exc)
        await asyncio.sleep(_RETENTION_TICK_SECONDS)
