from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
from fastapi import HTTPException

from app.services import match_logging_service

RATING_WINDOW = timedelta(days=14)


async def submit_rating(
    conn,
    booking_id: uuid.UUID,
    rater_id: uuid.UUID,
    stars: int,
    comment: str | None,
) -> dict:
    """Submit one direction of a mutual post-ride rating. Must be called with a pool conn."""
    row = await conn.fetchrow(
        """
        SELECT b.id, b.ride_id, b.passenger_id, b.status, r.driver_id, r.completed_at
        FROM bookings b
        JOIN rides r ON r.id = b.ride_id
        WHERE b.id = $1
        """,
        booking_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Booking not found"})

    if row["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail={"error": "booking_not_completed", "message": "Only completed bookings can be rated"},
        )

    passenger_id = row["passenger_id"]
    driver_id = row["driver_id"]
    if rater_id == passenger_id:
        rater_role = "passenger"
        ratee_id = driver_id
    elif rater_id == driver_id:
        rater_role = "driver"
        ratee_id = passenger_id
    else:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "You were not a party to this booking"},
        )

    completed_at = row["completed_at"]
    if completed_at is not None:
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - completed_at > RATING_WINDOW:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "rating_window_closed",
                    "message": "Ratings must be submitted within 14 days of ride completion",
                },
            )

    async with conn.transaction():
        try:
            rating_row = await conn.fetchrow(
                """
                INSERT INTO ratings (booking_id, ride_id, rater_id, ratee_id, rater_role, stars, comment)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                booking_id, row["ride_id"], rater_id, ratee_id, rater_role, stars, comment,
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(
                status_code=409,
                detail={"error": "duplicate_rating", "message": "You have already rated this booking"},
            )

        agg = await conn.fetchrow(
            "SELECT AVG(stars)::numeric(3,2) AS avg, COUNT(*) AS count FROM ratings WHERE ratee_id = $1",
            ratee_id,
        )
        await conn.execute(
            "UPDATE profiles SET rating_avg = $2, rating_count = $3 WHERE id = $1",
            ratee_id, agg["avg"], agg["count"],
        )

        counterpart_exists = await conn.fetchval(
            "SELECT 1 FROM ratings WHERE booking_id = $1 AND rater_id = $2",
            booking_id, ratee_id,
        )

        await match_logging_service.record_outcome(
            conn, row["ride_id"], passenger_id, "rated", {"stars": stars},
        )

    return {
        "rating_id": rating_row["id"],
        "booking_id": booking_id,
        "revealed": counterpart_exists is not None,
    }


async def get_own_rating_summary(conn, user_id: uuid.UUID) -> dict:
    """Own aggregate rating + anonymized, double-blind-filtered comment list (FR-006–FR-010)."""
    profile = await conn.fetchrow(
        "SELECT rating_avg, rating_count FROM profiles WHERE id = $1",
        user_id,
    )

    rows = await conn.fetch(
        """
        SELECT r.comment, r.created_at
        FROM ratings r
        JOIN rides ri ON ri.id = r.ride_id
        WHERE r.ratee_id = $1
          AND r.comment IS NOT NULL
          AND (
            EXISTS (
                SELECT 1 FROM ratings r2
                WHERE r2.booking_id = r.booking_id AND r2.rater_id = r.ratee_id
            )
            OR ri.completed_at IS NULL
            OR now() - ri.completed_at >= INTERVAL '14 days'
          )
        ORDER BY r.created_at DESC
        """,
        user_id,
    )

    return {
        "rating_avg": float(profile["rating_avg"]) if profile and profile["rating_avg"] is not None else None,
        "rating_count": profile["rating_count"] if profile else 0,
        "comments": [{"comment": r["comment"], "created_at": r["created_at"]} for r in rows],
    }
