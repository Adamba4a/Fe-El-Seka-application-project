from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.core.database import get_pool
from app.dependencies.verification import get_current_verified_passenger
from app.models.booking import BookingCreateRequest
from app.services.booking_service import create_booking

router = APIRouter()


# ── POST /api/v1/bookings ────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
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
            "premium_pickup_fee": str(booking["premium_pickup_fee"]) if booking["premium_pickup_fee"] else None,
            "premium_dropoff_fee": str(booking["premium_dropoff_fee"]) if booking["premium_dropoff_fee"] else None,
            "created_at": booking["created_at"].isoformat(),
        },
    )
