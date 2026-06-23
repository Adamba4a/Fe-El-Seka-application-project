from __future__ import annotations

import uuid
import logging
from typing import Any, Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)


async def get_booking_or_404(conn, booking_id: uuid.UUID, caller_id: uuid.UUID) -> dict:
    """Fetch a booking by ID and verify the caller has access (passenger or ride driver)."""
    row = await conn.fetchrow(
        """
        SELECT b.*, r.driver_id
        FROM bookings b
        JOIN rides r ON r.id = b.ride_id
        WHERE b.id = $1
        """,
        booking_id,
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Booking not found"},
        )
    booking = dict(row)
    if booking["passenger_id"] != caller_id and booking["driver_id"] != caller_id:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "Access denied"},
        )
    return booking


async def _assert_ride_owner(conn, ride_id: uuid.UUID, driver_id: uuid.UUID) -> None:
    """Raise HTTP 403 if driver_id does not own the ride."""
    row = await conn.fetchrow(
        "SELECT driver_id FROM rides WHERE id = $1",
        ride_id,
    )
    if row is None or row["driver_id"] != driver_id:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "You do not own this ride"},
        )


async def _insert_audit_log(
    conn,
    booking_id: uuid.UUID,
    event_type: str,
    actor_id: Optional[uuid.UUID],
    actor_role: str,
    prev_status: Optional[str],
    new_status: str,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Append one immutable row to booking_audit_log."""
    await conn.execute(
        """
        INSERT INTO booking_audit_log
            (booking_id, event_type, actor_id, actor_role, previous_status, new_status, metadata)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        booking_id,
        event_type,
        actor_id,
        actor_role,
        prev_status,
        new_status,
        metadata or {},
    )
