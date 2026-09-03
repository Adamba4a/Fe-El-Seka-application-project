from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.database import get_pool
from app.dependencies.roles import get_current_admin
from app.services import audit_service

router = APIRouter()

_VALID_STATUSES = ("scheduled", "in_progress", "completed", "cancelled")


def _markup_fields(price_per_seat, fair_price_per_seat) -> dict:
    price = Decimal(str(price_per_seat))
    fair = Decimal(str(fair_price_per_seat))
    markup = price - fair
    return {
        "fair_price_per_seat": str(fair),
        "markup_egp": str(markup),
        "markup_percentage": round(float(markup) / float(fair) * 100) if fair > 0 else 0,
    }


# Net commission actually realized on a ride — NOT a simple 20% of price_per_seat.
# COMMISSION_DEBIT (cash bookings) and the SPONSORED_RIDE_CREDIT gap (sponsored
# bookings) are both gross figures that still include the ride's distance_fee, which
# isn't platform revenue: it's credited straight back to the driver in the same
# transaction as a CASH_BACK_CREDIT entry (see commission_service.deduct_commission
# and booking_service._settle_sponsored_booking). Subtracting every CASH_BACK_CREDIT
# tied to this ride turns the gross debit into the platform's true take. Zero for a
# ride with no settled (completed/sponsored-confirmed) bookings yet.
# Correlated on r.id — embed directly into a SELECT list against a query whose FROM
# includes "rides r".
_NET_COMMISSION_SUBQUERY_SQL = """(
    SELECT
        COALESCE(SUM(l.amount_egp) FILTER (WHERE l.type = 'COMMISSION_DEBIT'), 0)
        + COALESCE(SUM(b.total_price - l.amount_egp) FILTER (WHERE l.type = 'SPONSORED_RIDE_CREDIT'), 0)
        - COALESCE(SUM(l.amount_egp) FILTER (WHERE l.type = 'CASH_BACK_CREDIT'), 0)
    FROM driver_ledger_entries l
    LEFT JOIN bookings b ON b.id = l.booking_id AND l.type = 'SPONSORED_RIDE_CREDIT'
    WHERE l.ride_id = r.id
)"""


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
                r.price_per_seat, r.fair_price_per_seat, r.created_at,
                r.driver_id, p.display_name AS driver_display_name,
                r.is_featured, r.featured_at, fb.display_name AS featured_by_display_name,
                {_NET_COMMISSION_SUBQUERY_SQL} AS net_commission_egp
            FROM rides r
            JOIN profiles p ON p.id = r.driver_id
            LEFT JOIN profiles fb ON fb.id = r.featured_by
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
            **_markup_fields(r["price_per_seat"], r["fair_price_per_seat"]),
            "net_commission_egp": str(r["net_commission_egp"]),
            "created_at": r["created_at"].isoformat(),
            "driver_id": str(r["driver_id"]),
            "driver_display_name": r["driver_display_name"] or "",
            "is_featured": r["is_featured"],
            "featured_at": r["featured_at"].isoformat() if r["featured_at"] else None,
            "featured_by_display_name": r["featured_by_display_name"],
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
            f"""
            SELECT
                r.id, r.status, r.departure_datetime,
                r.origin_address, r.destination_address,
                r.total_seats, r.booked_seats, r.available_seats,
                r.price_per_seat, r.fair_price_per_seat, r.notes,
                r.cancellation_reason, r.cancellation_source,
                r.created_at, r.updated_at,
                r.driver_id, p.display_name AS driver_display_name, p.email AS driver_email,
                p.rating_avg AS driver_rating_avg, p.rating_count AS driver_rating_count,
                v.plate_number, v.make, v.model, v.color,
                r.is_featured, r.featured_at, fb.display_name AS featured_by_display_name,
                {_NET_COMMISSION_SUBQUERY_SQL} AS net_commission_egp
            FROM rides r
            JOIN profiles p ON p.id = r.driver_id
            JOIN vehicles v ON v.id = r.vehicle_id
            LEFT JOIN profiles fb ON fb.id = r.featured_by
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
            **_markup_fields(ride["price_per_seat"], ride["fair_price_per_seat"]),
            "net_commission_egp": str(ride["net_commission_egp"]),
            "notes": ride["notes"],
            "cancellation_reason": ride["cancellation_reason"],
            "cancellation_source": ride["cancellation_source"],
            "created_at": ride["created_at"].isoformat(),
            "updated_at": ride["updated_at"].isoformat(),
            "is_featured": ride["is_featured"],
            "featured_at": ride["featured_at"].isoformat() if ride["featured_at"] else None,
            "featured_by_display_name": ride["featured_by_display_name"],
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


@router.post("/{ride_id}/feature")
async def feature_ride(
    ride_id: uuid.UUID,
    admin: dict = Depends(get_current_admin),
) -> dict:
    admin_id = uuid.UUID(str(admin["id"]))
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, departure_datetime, available_seats, driver_id FROM rides WHERE id = $1",
            ride_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Ride not found"})

        if row["status"] != "scheduled":
            raise HTTPException(
                status_code=409,
                detail={"error": "not_eligible", "message": "Ride is not eligible: status must be scheduled"},
            )
        if row["departure_datetime"] <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=409,
                detail={"error": "not_eligible", "message": "Ride is not eligible: departure has already passed"},
            )
        if row["available_seats"] <= 0:
            raise HTTPException(
                status_code=409,
                detail={"error": "not_eligible", "message": "Ride is not eligible: no seats available"},
            )

        updated = await conn.fetchrow(
            """
            UPDATE rides
            SET is_featured = true, featured_at = now(), featured_by = $2
            WHERE id = $1
            RETURNING featured_at, featured_by
            """,
            ride_id, admin_id,
        )
        driver_id = row["driver_id"]

    audit_service.append_log(
        str(admin_id), "ride_featured", str(driver_id), ride_id=str(ride_id),
    )
    return {
        "ride_id": str(ride_id),
        "is_featured": True,
        "featured_at": updated["featured_at"].isoformat(),
        "featured_by": str(updated["featured_by"]),
    }


@router.post("/{ride_id}/unfeature")
async def unfeature_ride(
    ride_id: uuid.UUID,
    admin: dict = Depends(get_current_admin),
) -> dict:
    admin_id = uuid.UUID(str(admin["id"]))
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT driver_id FROM rides WHERE id = $1", ride_id)
        if row is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Ride not found"})

        updated = await conn.fetchrow(
            """
            UPDATE rides
            SET is_featured = false, featured_at = now(), featured_by = $2
            WHERE id = $1
            RETURNING featured_at, featured_by
            """,
            ride_id, admin_id,
        )
        driver_id = row["driver_id"]

    audit_service.append_log(
        str(admin_id), "ride_unfeatured", str(driver_id), ride_id=str(ride_id),
    )
    return {
        "ride_id": str(ride_id),
        "is_featured": False,
        "featured_at": updated["featured_at"].isoformat(),
        "featured_by": str(updated["featured_by"]),
    }
