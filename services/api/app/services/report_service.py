from __future__ import annotations

import uuid

from fastapi import HTTPException


async def submit_report(
    conn,
    ride_id: uuid.UUID,
    booking_id: uuid.UUID,
    reporter_id: uuid.UUID,
    reported_user_id: uuid.UUID,
    category: str,
    description: str,
) -> dict:
    """Submit a safety report against another party on a ride. Must be called with a pool conn."""
    if reported_user_id == reporter_id:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "You cannot report yourself"},
        )

    row = await conn.fetchrow(
        """
        SELECT b.id, b.passenger_id, r.driver_id, r.status AS ride_status
        FROM bookings b
        JOIN rides r ON r.id = b.ride_id
        WHERE b.id = $1 AND b.ride_id = $2
        """,
        booking_id, ride_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Ride or booking not found"})

    parties = {row["passenger_id"], row["driver_id"]}
    if reporter_id not in parties or reported_user_id not in parties:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "You were not a party to this ride"},
        )

    if row["ride_status"] not in ("in_progress", "completed"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "ride_not_reportable",
                "message": "Reports can only be filed for in-progress or completed rides",
            },
        )

    report_row = await conn.fetchrow(
        """
        INSERT INTO reports (ride_id, booking_id, reporter_id, reported_user_id, category, description)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, status
        """,
        ride_id, booking_id, reporter_id, reported_user_id, category, description,
    )

    return {"report_id": report_row["id"], "status": report_row["status"]}


async def get_own_reports(conn, user_id: uuid.UUID) -> list[dict]:
    """Reporter's own report history, status only — never exposes resolution fields (FR-016)."""
    rows = await conn.fetch(
        """
        SELECT id, category, status, created_at
        FROM reports
        WHERE reporter_id = $1
        ORDER BY created_at DESC
        """,
        user_id,
    )
    return [
        {
            "report_id": r["id"],
            "category": r["category"],
            "status": r["status"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
