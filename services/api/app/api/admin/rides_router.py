from __future__ import annotations

import uuid
from datetime import date as date_type, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.database import get_pool
from app.dependencies.roles import get_current_admin

router = APIRouter()

_VALID_STATUSES = ("scheduled", "in_progress", "completed", "cancelled")


@router.get("/")
async def list_rides(
    status: str | None = Query(None),
    q: str | None = Query(None),
    date: str | None = Query(None, description="Filter to a single day, YYYY-MM-DD (UTC)"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _admin: dict = Depends(get_current_admin),
) -> dict:
    if status is not None and status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": f"status must be one of {', '.join(_VALID_STATUSES)}"},
        )

    day_start: datetime | None = None
    day_end: datetime | None = None
    if date is not None:
        try:
            day = date_type.fromisoformat(date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"error": "validation_error", "message": "date must be in YYYY-MM-DD format"},
            )
        day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

    offset = (page - 1) * limit
    pool = get_pool()
    async with pool.acquire() as conn:
        conditions = []
        params: list = []

        if status:
            params.append(status)
            conditions.append(f"r.status = ${len(params)}")
        if q:
            params.append(f"%{q}%")
            conditions.append(
                f"(p.display_name ILIKE ${len(params)} OR r.origin_address ILIKE ${len(params)}"
                f" OR r.destination_address ILIKE ${len(params)})"
            )
        if day_start is not None:
            params.append(day_start)
            conditions.append(f"r.departure_datetime >= ${len(params)}")
            params.append(day_end)
            conditions.append(f"r.departure_datetime < ${len(params)}")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        total = await conn.fetchval(
            f"""
            SELECT COUNT(*) FROM rides r
            JOIN profiles p ON p.id = r.driver_id
            {where_clause}
            """,
            *params,
        )

        order_clause = "ASC" if day_start is not None else "DESC"
        rows = await conn.fetch(
            f"""
            SELECT
                r.id, r.status, r.departure_datetime,
                r.origin_address, r.destination_address,
                r.total_seats, r.booked_seats, r.available_seats,
                r.price_per_seat, r.created_at,
                r.driver_id, p.display_name AS driver_display_name
            FROM rides r
            JOIN profiles p ON p.id = r.driver_id
            {where_clause}
            ORDER BY r.departure_datetime {order_clause}
            LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
            """,
            *params, limit, offset,
        )

    items = [
        {
            "ride_id": str(r["id"]),
            "status": r["status"],
            "departure_datetime": r["departure_datetime"].isoformat(),
            "origin_address": r["origin_address"],
            "destination_address": r["destination_address"],
            "total_seats": r["total_seats"],
            "booked_seats": r["booked_seats"],
            "available_seats": r["available_seats"],
            "price_per_seat": str(r["price_per_seat"]),
            "created_at": r["created_at"].isoformat(),
            "driver_id": str(r["driver_id"]),
            "driver_display_name": r["driver_display_name"] or "",
        }
        for r in rows
    ]
    return {"total": total, "page": page, "limit": limit, "items": items}


@router.get("/{ride_id}")
async def get_ride_detail(
    ride_id: uuid.UUID,
    _admin: dict = Depends(get_current_admin),
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                r.id, r.status, r.departure_datetime,
                r.origin_address, r.destination_address,
                r.total_seats, r.booked_seats, r.available_seats,
                r.price_per_seat, r.notes,
                r.cancellation_reason, r.cancellation_source,
                r.created_at, r.updated_at,
                r.driver_id, p.display_name AS driver_display_name, p.email AS driver_email,
                p.rating_avg AS driver_rating_avg, p.rating_count AS driver_rating_count,
                v.plate_number, v.make, v.model, v.color
            FROM rides r
            JOIN profiles p ON p.id = r.driver_id
            JOIN vehicles v ON v.id = r.vehicle_id
            WHERE r.id = $1
            """,
            ride_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Ride not found"})

        booking_rows = await conn.fetch(
            """
            SELECT
                b.id, b.status, b.seats, b.total_price, b.created_at,
                b.passenger_id, p.display_name AS passenger_display_name
            FROM bookings b
            JOIN profiles p ON p.id = b.passenger_id
            WHERE b.ride_id = $1
            ORDER BY b.created_at ASC
            """,
            ride_id,
        )

    ride = dict(row)

    return {
        "ride": {
            "ride_id": str(ride["id"]),
            "status": ride["status"],
            "departure_datetime": ride["departure_datetime"].isoformat(),
            "origin_address": ride["origin_address"],
            "destination_address": ride["destination_address"],
            "total_seats": ride["total_seats"],
            "booked_seats": ride["booked_seats"],
            "available_seats": ride["available_seats"],
            "price_per_seat": str(ride["price_per_seat"]),
            "notes": ride["notes"],
            "cancellation_reason": ride["cancellation_reason"],
            "cancellation_source": ride["cancellation_source"],
            "created_at": ride["created_at"].isoformat(),
            "updated_at": ride["updated_at"].isoformat(),
            "driver": {
                "driver_id": str(ride["driver_id"]),
                "display_name": ride["driver_display_name"] or "",
                "email": ride["driver_email"] or "",
                "rating_avg": float(ride["driver_rating_avg"]) if ride["driver_rating_avg"] is not None else None,
                "rating_count": ride["driver_rating_count"],
            },
            "vehicle": {
                "plate_number": ride["plate_number"],
                "make": ride["make"],
                "model": ride["model"],
                "color": ride["color"],
            },
        },
        "bookings": [
            {
                "booking_id": str(b["id"]),
                "status": b["status"],
                "seats": b["seats"],
                "total_price": str(b["total_price"]),
                "created_at": b["created_at"].isoformat(),
                "passenger_id": str(b["passenger_id"]),
                "passenger_display_name": b["passenger_display_name"] or "",
            }
            for b in booking_rows
        ],
    }
