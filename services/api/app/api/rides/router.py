from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import get_pool
from app.dependencies.verification import get_current_verified_driver
from app.models.ride import (
    CancelRideRequest,
    CreateRideRequest,
    EditRideRequest,
    RevocationPayload,
)
from app.services import revocation_service, ride_service
from app.services.ride_service import RideServiceError

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _get_active_vehicle(driver_id: uuid.UUID) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, seat_count FROM vehicles WHERE driver_id = $1 AND is_active = true LIMIT 1",
            driver_id,
        )
    if row is None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "no_active_vehicle",
                "message": "You need an active vehicle to post a ride.",
            },
        )
    return dict(row)


def _service_error_response(exc: RideServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message},
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/rides
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_ride(
    payload: CreateRideRequest,
    profile: dict = Depends(get_current_verified_driver),
):
    driver_id = uuid.UUID(str(profile["id"]))
    vehicle = await _get_active_vehicle(driver_id)
    try:
        ride = await ride_service.create_ride(
            driver_id=driver_id,
            vehicle_id=uuid.UUID(str(vehicle["id"])),
            vehicle_seat_count=vehicle["seat_count"],
            payload=payload,
        )
    except RideServiceError as exc:
        return _service_error_response(exc)
    return {"ride": ride.model_dump(mode="json")}


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/rides
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/")
async def list_rides(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    profile: dict = Depends(get_current_verified_driver),
):
    driver_id = uuid.UUID(str(profile["id"]))
    result = await ride_service.list_rides(
        driver_id=driver_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return result.model_dump(mode="json")


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/rides/{ride_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{ride_id}")
async def get_ride(
    ride_id: uuid.UUID,
    profile: dict = Depends(get_current_verified_driver),
):
    driver_id = uuid.UUID(str(profile["id"]))
    try:
        detail = await ride_service.get_ride(ride_id=ride_id, driver_id=driver_id)
    except RideServiceError as exc:
        return _service_error_response(exc)
    return detail.model_dump(mode="json")


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/v1/rides/{ride_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.patch("/{ride_id}")
async def edit_ride(
    ride_id: uuid.UUID,
    payload: EditRideRequest,
    profile: dict = Depends(get_current_verified_driver),
):
    driver_id = uuid.UUID(str(profile["id"]))
    try:
        ride = await ride_service.edit_ride(
            ride_id=ride_id,
            driver_id=driver_id,
            payload=payload,
        )
    except RideServiceError as exc:
        return _service_error_response(exc)
    return {"ride": ride.model_dump(mode="json")}


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/rides/{ride_id}/cancel
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{ride_id}/cancel")
async def cancel_ride(
    ride_id: uuid.UUID,
    payload: CancelRideRequest,
    profile: dict = Depends(get_current_verified_driver),
):
    driver_id = uuid.UUID(str(profile["id"]))
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(status_code=400, detail={"error": "reason_required", "message": "Cancellation reason is required."})
    try:
        ride = await ride_service.cancel_ride(
            ride_id=ride_id,
            driver_id=driver_id,
            reason=payload.reason,
            cancellation_source="driver",
            actor_id=driver_id,
        )
    except RideServiceError as exc:
        return _service_error_response(exc)
    return {"ride": ride.model_dump(mode="json")}


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/rides/{ride_id}/start
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{ride_id}/start")
async def start_ride(
    ride_id: uuid.UUID,
    profile: dict = Depends(get_current_verified_driver),
):
    driver_id = uuid.UUID(str(profile["id"]))
    try:
        ride = await ride_service.start_ride(ride_id=ride_id, driver_id=driver_id)
    except RideServiceError as exc:
        return _service_error_response(exc)
    return {"ride": ride.model_dump(mode="json")}


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/rides/{ride_id}/complete
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{ride_id}/complete")
async def complete_ride(
    ride_id: uuid.UUID,
    profile: dict = Depends(get_current_verified_driver),
):
    driver_id = uuid.UUID(str(profile["id"]))
    try:
        ride = await ride_service.complete_ride(ride_id=ride_id, driver_id=driver_id)
    except RideServiceError as exc:
        return _service_error_response(exc)
    return {"ride": ride.model_dump(mode="json")}


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/internal/driver-revocation  (Supabase webhook)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/internal/driver-revocation", include_in_schema=False)
async def driver_revocation_webhook(
    payload: RevocationPayload,
    x_webhook_secret: Optional[str] = Header(None),
):
    if not settings.webhook_secret or x_webhook_secret != settings.webhook_secret:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Invalid webhook secret."})
    result = await revocation_service.handle_driver_revocation(
        driver_id=payload.driver_id,
        revocation_type=payload.revocation_type,
    )
    return result
