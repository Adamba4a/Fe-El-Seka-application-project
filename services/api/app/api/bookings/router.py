from __future__ import annotations

import uuid

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.core.database import get_pool
from app.dependencies.auth import get_current_user
from app.dependencies.verification import get_current_verified_passenger
from app.models.booking import (
    BookingCancelRequest,
    BookingCreateRequest,
    BookingListItem,
    BookingListResponse,
)
from app.services import booking_service, storage_service
from app.services.booking_service import create_booking

router = APIRouter()


# ── POST /api/v1/bookings ────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def book_ride(
    body: BookingCreateRequest,
    profile: dict = Depends(get_current_verified_passenger),
):
    passenger_id = uuid.UUID(str(profile["id"]))

    pool = get_pool()
    async with pool.acquire() as conn:
        booking = await create_booking(
            conn=conn,
            ride_id=body.ride_id,
            passenger_id=passenger_id,
            boarding_lat=body.boarding_point.lat,
            boarding_lng=body.boarding_point.lng,
            alighting_lat=body.alighting_point.lat,
            alighting_lng=body.alighting_point.lng,
            premium_pickup=body.premium_pickup_requested,
            premium_dropoff=body.premium_dropoff_requested,
            premium_pickup_fee=body.premium_pickup_fee,
            premium_dropoff_fee=body.premium_dropoff_fee,
        )

    return JSONResponse(
        status_code=201,
        content={
            "booking_id": str(booking["id"]),
            "ride_id": str(body.ride_id),
            "status": booking["status"],
            "per_seat_price": str(booking["per_seat_price"]),
            "total_price": str(booking["total_price"]),
            "premium_pickup_requested": booking["premium_pickup_requested"],
            "premium_dropoff_requested": booking["premium_dropoff_requested"],
            "premium_pickup_fee": str(booking["premium_pickup_fee"]) if booking["premium_pickup_fee"] is not None else None,
            "premium_dropoff_fee": str(booking["premium_dropoff_fee"]) if booking["premium_dropoff_fee"] is not None else None,
            "created_at": booking["created_at"].isoformat(),
        },
    )


# ── GET /api/v1/bookings  (T037) ────────────────────────────────────────────

@router.get("")
async def list_bookings(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    profile: dict = Depends(get_current_verified_passenger),
):
    passenger_id = uuid.UUID(str(profile["id"]))
    page_size = min(page_size, 50)
    offset = (page - 1) * page_size

    pool = get_pool()
    async with pool.acquire() as conn:
        where = "WHERE b.passenger_id = $1"
        params: list = [passenger_id]

        if status_filter:
            params.append(status_filter)
            where += f" AND b.status = ${len(params)}"

        rows = await conn.fetch(
            f"""
            SELECT
                b.id, b.ride_id, b.status,
                b.per_seat_price, b.total_price,
                b.premium_pickup_requested, b.premium_dropoff_requested,
                b.premium_pickup_fee, b.premium_dropoff_fee,
                b.created_at, b.confirmed_at, b.cancelled_at,
                r.departure_datetime, r.origin_address, r.destination_address,
                p.display_name AS driver_display_name
            FROM bookings b
            JOIN rides r ON r.id = b.ride_id
            JOIN profiles p ON p.id = r.driver_id
            {where}
            ORDER BY r.departure_datetime DESC
            LIMIT {page_size} OFFSET {offset}
            """,
            *params,
        )
        total = await conn.fetchval(
            f"""
            SELECT COUNT(*)
            FROM bookings b
            JOIN rides r ON r.id = b.ride_id
            {where}
            """,
            *params,
        )

    items = [
        BookingListItem(
            booking_id=r["id"],
            ride_id=r["ride_id"],
            status=r["status"],
            driver_display_name=r["driver_display_name"],
            departure_datetime=r["departure_datetime"],
            origin_address=r["origin_address"],
            destination_address=r["destination_address"],
            per_seat_price=f"{float(r['per_seat_price']):.2f}",
            total_price=f"{float(r['total_price']):.2f}",
            premium_pickup_requested=r["premium_pickup_requested"],
            premium_dropoff_requested=r["premium_dropoff_requested"],
            premium_pickup_fee=f"{float(r['premium_pickup_fee']):.2f}" if r["premium_pickup_fee"] is not None else None,
            premium_dropoff_fee=f"{float(r['premium_dropoff_fee']):.2f}" if r["premium_dropoff_fee"] is not None else None,
            created_at=r["created_at"],
            confirmed_at=r["confirmed_at"],
            cancelled_at=r["cancelled_at"],
        )
        for r in rows
    ]

    return BookingListResponse(
        bookings=items,
        total=total,
        page=page,
        page_size=page_size,
    ).model_dump(mode="json")


# ── GET /api/v1/bookings/{booking_id}  (T038 — implemented in Phase 7) ───────

@router.get("/{booking_id}")
async def get_booking(
    booking_id: uuid.UUID,
    user: dict = Depends(get_current_user),
):
    caller_id = uuid.UUID(str(user["id"]))
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                b.id, b.ride_id, b.passenger_id, b.status,
                b.per_seat_price, b.total_price,
                b.premium_pickup_requested, b.premium_dropoff_requested,
                b.premium_pickup_fee, b.premium_dropoff_fee,
                b.cancellation_reason, b.late_cancellation,
                b.created_at, b.confirmed_at, b.cancelled_at,
                ST_Y(b.passenger_pickup_point::geometry)  AS boarding_lat,
                ST_X(b.passenger_pickup_point::geometry)  AS boarding_lng,
                ST_Y(b.passenger_dropoff_point::geometry) AS alighting_lat,
                ST_X(b.passenger_dropoff_point::geometry) AS alighting_lng,
                r.departure_datetime, r.driver_id,
                p.display_name AS driver_display_name,
                p.profile_photo_path AS driver_avatar_url
            FROM bookings b
            JOIN rides r ON r.id = b.ride_id
            JOIN profiles p ON p.id = r.driver_id
            WHERE b.id = $1
            """,
            booking_id,
        )

    if row is None:
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "message": "Booking not found"},
        )

    b = dict(row)
    if b["passenger_id"] != caller_id and b["driver_id"] != caller_id:
        return JSONResponse(
            status_code=403,
            content={"error": "forbidden", "message": "Access denied"},
        )

    return {
        "booking_id": str(b["id"]),
        "ride_id": str(b["ride_id"]),
        "status": b["status"],
        "driver_display_name": b["driver_display_name"],
        "driver_avatar_url": storage_service.generate_signed_url(
            "profile-photos", b["driver_avatar_url"]
        ),
        "departure_datetime": b["departure_datetime"].isoformat() if b["departure_datetime"] else None,
        "per_seat_price": f"{float(b['per_seat_price']):.2f}",
        "total_price": f"{float(b['total_price']):.2f}",
        "premium_pickup_requested": b["premium_pickup_requested"],
        "premium_dropoff_requested": b["premium_dropoff_requested"],
        "premium_pickup_fee": f"{float(b['premium_pickup_fee']):.2f}" if b["premium_pickup_fee"] is not None else None,
        "premium_dropoff_fee": f"{float(b['premium_dropoff_fee']):.2f}" if b["premium_dropoff_fee"] is not None else None,
        "boarding_point": {"lat": b["boarding_lat"], "lng": b["boarding_lng"]},
        "alighting_point": {"lat": b["alighting_lat"], "lng": b["alighting_lng"]},
        "cancellation_reason": b["cancellation_reason"],
        "late_cancellation": b["late_cancellation"],
        "created_at": b["created_at"].isoformat(),
        "confirmed_at": b["confirmed_at"].isoformat() if b["confirmed_at"] else None,
        "cancelled_at": b["cancelled_at"].isoformat() if b["cancelled_at"] else None,
    }


# ── POST /api/v1/bookings/{booking_id}/cancel ────────────────────────────────

@router.post("/{booking_id}/cancel")
async def cancel_booking_passenger(
    booking_id: uuid.UUID,
    payload: BookingCancelRequest = None,
    profile: dict = Depends(get_current_verified_passenger),
):
    passenger_id = uuid.UUID(str(profile["id"]))
    reason = payload.reason if payload else None
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await booking_service.cancel_booking(
            conn, booking_id, passenger_id, "passenger", reason
        )
    return {
        "booking_id": str(result["id"]),
        "status": result["status"],
        "cancelled_by": result["cancelled_by"],
        "late_cancellation": result["late_cancellation"],
        "cancelled_at": result["cancelled_at"].isoformat(),
    }
