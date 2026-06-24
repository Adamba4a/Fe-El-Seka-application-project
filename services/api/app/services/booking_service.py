from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

import asyncpg
from fastapi import HTTPException

from app.core.database import get_pool
from app.services.notification_service import enqueue_booking_notification

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


async def create_booking(
    conn,
    ride_id: uuid.UUID,
    passenger_id: uuid.UUID,
    boarding_lat: float,
    boarding_lng: float,
    alighting_lat: float,
    alighting_lng: float,
    premium_pickup: bool,
    premium_dropoff: bool,
    premium_pickup_fee: Optional[float],
    premium_dropoff_fee: Optional[float],
) -> dict:
    """Atomically reserve a seat and create a pending booking. Must be called with a pool conn."""
    async with conn.transaction():
        # 1. Lock the ride row to prevent concurrent seat races
        ride = await conn.fetchrow(
            "SELECT id, status, departure_datetime, price_per_seat, booked_seats, total_seats, driver_id FROM rides WHERE id = $1 FOR UPDATE",
            ride_id,
        )
        if ride is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Ride not found"})

        if ride["status"] != "scheduled":
            raise HTTPException(status_code=422, detail={"error": "ride_not_schedulable", "message": "Ride is not accepting bookings"})

        dep = ride["departure_datetime"]
        if dep.tzinfo is None:
            dep = dep.replace(tzinfo=timezone.utc)
        if dep <= datetime.now(timezone.utc):
            raise HTTPException(status_code=422, detail={"error": "ride_departed", "message": "Ride has already departed"})

        # 2. Atomic seat claim — zero rows means fully booked
        claimed = await conn.fetchrow(
            "UPDATE rides SET booked_seats = booked_seats + 1 WHERE id = $1 AND booked_seats < total_seats RETURNING id",
            ride_id,
        )
        if claimed is None:
            raise HTTPException(status_code=409, detail={"error": "no_seats_available", "message": "No seats available on this ride"})

        # 3. Compute pricing
        per_seat = Decimal(str(ride["price_per_seat"]))
        pu_fee = Decimal(str(premium_pickup_fee)) if premium_pickup and premium_pickup_fee else Decimal("0")
        do_fee = Decimal(str(premium_dropoff_fee)) if premium_dropoff and premium_dropoff_fee else Decimal("0")
        total = per_seat + pu_fee + do_fee

        # 4. Insert booking — unique index raises UniqueViolation on duplicate active booking
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO bookings (
                    ride_id, passenger_id, per_seat_price, total_price,
                    passenger_pickup_point, passenger_dropoff_point,
                    premium_pickup_requested, premium_dropoff_requested,
                    premium_pickup_fee, premium_dropoff_fee
                ) VALUES (
                    $1, $2, $3, $4,
                    ST_SetSRID(ST_MakePoint($5, $6), 4326),
                    ST_SetSRID(ST_MakePoint($7, $8), 4326),
                    $9, $10, $11, $12
                ) RETURNING id, status, per_seat_price, total_price,
                           premium_pickup_requested, premium_dropoff_requested,
                           premium_pickup_fee, premium_dropoff_fee, created_at
                """,
                ride_id, passenger_id, per_seat, total,
                boarding_lng, boarding_lat,      # MakePoint(lng, lat)
                alighting_lng, alighting_lat,
                premium_pickup, premium_dropoff,
                pu_fee if premium_pickup else None,
                do_fee if premium_dropoff else None,
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(status_code=409, detail={"error": "duplicate_booking", "message": "You already have an active booking for this ride"})

        booking = dict(row)
        booking_id = booking["id"]

        # 5. Audit log
        await _insert_audit_log(conn, booking_id, "created", passenger_id, "passenger", None, "pending")

        # 6. Notification
        driver_id = ride["driver_id"]
        await enqueue_booking_notification(
            conn,
            "booking_created",
            passenger_id,
            {"ride_id": str(ride_id), "booking_id": str(booking_id)},
        )

        return booking


async def confirm_booking(
    conn,
    booking_id: uuid.UUID,
    ride_id: uuid.UUID,
    driver_id: uuid.UUID,
) -> dict:
    """Transition a pending booking to confirmed. Must be called with a pool conn."""
    await _assert_ride_owner(conn, ride_id, driver_id)

    async with conn.transaction():
        row = await conn.fetchrow(
            "SELECT id, status, ride_id, passenger_id FROM bookings WHERE id = $1 FOR UPDATE",
            booking_id,
        )
        if row is None or row["ride_id"] != ride_id:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Booking not found"})
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail={"error": "booking_not_pending", "message": "Booking is not in pending status"})

        updated = await conn.fetchrow(
            "UPDATE bookings SET status = 'confirmed', confirmed_at = now() WHERE id = $1 RETURNING id, status, confirmed_at",
            booking_id,
        )

        await _insert_audit_log(conn, booking_id, "confirmed", driver_id, "driver", "pending", "confirmed")

        await enqueue_booking_notification(
            conn,
            "booking_confirmed",
            row["passenger_id"],
            {"ride_id": str(ride_id), "booking_id": str(booking_id)},
        )

    return dict(updated)


async def reject_booking(
    conn,
    booking_id: uuid.UUID,
    ride_id: uuid.UUID,
    driver_id: uuid.UUID,
    reason: Optional[str] = None,
) -> dict:
    """Reject a pending booking, applying premium fallback rule (FR-021) when applicable."""
    await _assert_ride_owner(conn, ride_id, driver_id)

    async with conn.transaction():
        row = await conn.fetchrow(
            """
            SELECT b.id, b.status, b.ride_id, b.passenger_id,
                   b.premium_pickup_requested, b.per_seat_price
            FROM bookings b
            WHERE b.id = $1
            FOR UPDATE
            """,
            booking_id,
        )
        if row is None or row["ride_id"] != ride_id:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Booking not found"})
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail={"error": "booking_not_pending", "message": "Booking is not in pending status"})

        fallback_applied = False

        if row["premium_pickup_requested"]:
            walk_m = await conn.fetchval(
                """
                SELECT ST_Distance(
                    b.passenger_pickup_point::geography,
                    ST_ClosestPoint(r.route_geometry::geometry, b.passenger_pickup_point::geometry)::geography
                )
                FROM bookings b
                JOIN rides r ON r.id = b.ride_id
                WHERE b.id = $1
                """,
                booking_id,
            )
            if walk_m is not None and walk_m <= 500:
                # Fallback: keep as confirmed at base price, remove premium
                await conn.execute(
                    """
                    UPDATE bookings
                    SET status = 'confirmed',
                        confirmed_at = now(),
                        premium_pickup_requested = false,
                        premium_pickup_fee = null,
                        total_price = per_seat_price
                    WHERE id = $1
                    """,
                    booking_id,
                )
                await _insert_audit_log(
                    conn, booking_id, "confirmed", driver_id, "driver", "pending", "confirmed",
                    {"fallback_applied": True, "reason": reason},
                )
                await enqueue_booking_notification(
                    conn,
                    "booking_confirmed",
                    row["passenger_id"],
                    {"ride_id": str(ride_id), "booking_id": str(booking_id), "fallback_applied": True},
                )
                fallback_applied = True
                return {"id": booking_id, "status": "confirmed", "cancelled_by": None, "fallback_applied": True}

        # No fallback — cancel the booking and release the seat
        await conn.execute(
            "UPDATE rides SET booked_seats = GREATEST(booked_seats - 1, 0) WHERE id = $1",
            ride_id,
        )
        updated = await conn.fetchrow(
            """
            UPDATE bookings
            SET status = 'cancelled',
                cancelled_by = 'driver',
                cancellation_reason = $2,
                cancelled_at = now()
            WHERE id = $1
            RETURNING id, status, cancelled_by
            """,
            booking_id,
            reason,
        )

        await _insert_audit_log(conn, booking_id, "rejected", driver_id, "driver", "pending", "cancelled", {"reason": reason})

        await enqueue_booking_notification(
            conn,
            "booking_rejected",
            row["passenger_id"],
            {"ride_id": str(ride_id), "booking_id": str(booking_id)},
        )

    result = dict(updated)
    result["fallback_applied"] = False
    return result


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
