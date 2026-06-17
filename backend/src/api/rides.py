from __future__ import annotations

import os
import uuid
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.ride import (
    CancelRideRequest,
    CreateRideRequest,
    EditRideRequest,
    RideDetailResponse,
    RideListResponse,
    RideResponse,
)
from ..services import ride_service, revocation_service

router = APIRouter(prefix="/api/v1", tags=["rides"])


# ─────────────────────────────────────────────────────────────────────────────
# Error helpers (T020)
# ─────────────────────────────────────────────────────────────────────────────

def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": code, "message": message})


def _service_error_to_http(exc: ride_service.RideServiceError) -> HTTPException:
    return _err(exc.code, exc.message, exc.status_code)


# ─────────────────────────────────────────────────────────────────────────────
# JWT decode helper
# ─────────────────────────────────────────────────────────────────────────────

def _decode_token(token: str) -> dict:
    secret = os.getenv("SUPABASE_JWT_SECRET", "")
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
    except jwt.ExpiredSignatureError:
        raise _err("token_expired", "Token has expired.", 401)
    except jwt.InvalidTokenError:
        raise _err("invalid_token", "Invalid authentication token.", 401)


# ─────────────────────────────────────────────────────────────────────────────
# Verified driver dependency (T019)
# ─────────────────────────────────────────────────────────────────────────────

async def get_verified_driver(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> tuple[uuid.UUID, uuid.UUID, int]:
    """Returns (driver_id, vehicle_id, vehicle_seat_count) for a verified driver."""
    if not authorization.startswith("Bearer "):
        raise _err("invalid_token", "Missing Bearer token.", 401)

    token = authorization.removeprefix("Bearer ").strip()
    payload = _decode_token(token)
    user_id = uuid.UUID(payload["sub"])

    # Check profile verification status
    from sqlalchemy import text
    profile_result = await db.execute(
        text("SELECT verification_status FROM public.profiles WHERE id = :uid"),
        {"uid": str(user_id)},
    )
    profile = profile_result.fetchone()
    if not profile or profile.verification_status != "verified":
        raise _err("not_verified_driver", "Complete identity and vehicle verification before creating rides.", 403)

    # Check approved vehicle
    vehicle_result = await db.execute(
        text("SELECT id, seat_count FROM public.vehicles WHERE driver_id = :uid AND is_active = true"),
        {"uid": str(user_id)},
    )
    vehicle = vehicle_result.fetchone()
    if not vehicle:
        raise _err("not_verified_driver", "Complete identity and vehicle verification before creating rides.", 403)

    return user_id, uuid.UUID(str(vehicle.id)), int(vehicle.seat_count)


async def get_driver_id(authorization: str = Header(...)) -> uuid.UUID:
    """Returns driver_id without checking verification — for read-only endpoints."""
    if not authorization.startswith("Bearer "):
        raise _err("invalid_token", "Missing Bearer token.", 401)
    token = authorization.removeprefix("Bearer ").strip()
    payload = _decode_token(token)
    return uuid.UUID(payload["sub"])


# ─────────────────────────────────────────────────────────────────────────────
# Ride endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/rides", status_code=201)
async def create_ride(
    body: CreateRideRequest,
    driver_info: tuple = Depends(get_verified_driver),
    db: AsyncSession = Depends(get_db),
) -> dict:
    driver_id, vehicle_id, seat_count = driver_info
    try:
        ride = await ride_service.create_ride(db, driver_id, vehicle_id, seat_count, body)
    except ride_service.RideServiceError as exc:
        raise _service_error_to_http(exc)
    return {"ride": ride.model_dump()}


@router.get("/rides")
async def list_rides(
    driver_id: uuid.UUID = Depends(get_driver_id),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> RideListResponse:
    return await ride_service.list_rides(db, driver_id, status, page, page_size)


@router.get("/rides/{ride_id}")
async def get_ride(
    ride_id: uuid.UUID,
    driver_id: uuid.UUID = Depends(get_driver_id),
    db: AsyncSession = Depends(get_db),
) -> RideDetailResponse:
    try:
        return await ride_service.get_ride(db, ride_id, driver_id)
    except ride_service.RideServiceError as exc:
        raise _service_error_to_http(exc)


@router.patch("/rides/{ride_id}")
async def edit_ride(
    ride_id: uuid.UUID,
    body: EditRideRequest,
    driver_id: uuid.UUID = Depends(get_driver_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        ride = await ride_service.edit_ride(db, ride_id, driver_id, body)
    except ride_service.RideServiceError as exc:
        raise _service_error_to_http(exc)
    return {"ride": ride.model_dump()}


@router.post("/rides/{ride_id}/cancel")
async def cancel_ride(
    ride_id: uuid.UUID,
    body: CancelRideRequest,
    driver_id: uuid.UUID = Depends(get_driver_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not body.reason or not body.reason.strip():
        raise _err("reason_required", "A cancellation reason is required.")
    try:
        ride = await ride_service.cancel_ride(db, ride_id, driver_id, body.reason)
    except ride_service.RideServiceError as exc:
        raise _service_error_to_http(exc)
    return {"ride": ride.model_dump()}


@router.post("/rides/{ride_id}/start")
async def start_ride(
    ride_id: uuid.UUID,
    driver_id: uuid.UUID = Depends(get_driver_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        ride = await ride_service.start_ride(db, ride_id, driver_id)
    except ride_service.RideServiceError as exc:
        raise _service_error_to_http(exc)
    return {"ride": ride.model_dump()}


@router.post("/rides/{ride_id}/complete")
async def complete_ride(
    ride_id: uuid.UUID,
    driver_id: uuid.UUID = Depends(get_driver_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        ride = await ride_service.complete_ride(db, ride_id, driver_id)
    except ride_service.RideServiceError as exc:
        raise _service_error_to_http(exc)
    return {"ride": ride.model_dump()}


# ─────────────────────────────────────────────────────────────────────────────
# Internal webhook — driver revocation (T055)
# ─────────────────────────────────────────────────────────────────────────────

class RevocationPayload(BaseModel):
    driver_id: uuid.UUID
    revocation_type: str


@router.post("/internal/driver-revocation")
async def driver_revocation_webhook(
    body: RevocationPayload,
    x_webhook_secret: str = Header(..., alias="X-Webhook-Secret"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    expected = os.getenv("WEBHOOK_SECRET", "")
    if not expected or x_webhook_secret != expected:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Invalid webhook secret."})

    result = await revocation_service.handle_driver_revocation(db, body.driver_id, body.revocation_type)
    return result
