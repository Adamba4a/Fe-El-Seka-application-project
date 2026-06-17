from __future__ import annotations

import uuid
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.ride import Ride, RideHistoryLog, RideStatus, RideAction
from ..services.notification_service import enqueue_cancellation_emails

logger = logging.getLogger(__name__)


async def handle_driver_revocation(
    db: AsyncSession,
    driver_id: uuid.UUID,
    revocation_type: str,
) -> dict:
    """Bulk-cancel all scheduled rides for a driver whose verification was revoked.

    Returns counts of cancelled rides and queued notification emails.
    """
    result = await db.execute(
        select(Ride)
        .where(
            Ride.driver_id == driver_id,
            Ride.status == RideStatus.scheduled,
        )
        .with_for_update()
    )
    rides = result.scalars().all()

    cancelled_count = 0
    emails_queued = 0
    reason = "Driver verification revoked"

    for ride in rides:
        ride.status = RideStatus.cancelled
        ride.cancellation_reason = reason
        ride.cancellation_source = "system"

        log = RideHistoryLog(
            ride_id=ride.id,
            actor_id=None,
            action=RideAction.cancelled,
            reason=reason,
        )
        db.add(log)
        cancelled_count += 1

    await db.flush()

    for ride in rides:
        queued = await enqueue_cancellation_emails(db, ride.id)
        emails_queued += queued

    await db.commit()

    logger.info(
        "Revocation handled: driver=%s type=%s cancelled=%d emails=%d",
        driver_id,
        revocation_type,
        cancelled_count,
        emails_queued,
    )

    return {"cancelled_rides": cancelled_count, "notification_emails_queued": emails_queued}
