from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.core.database import get_pool
from app.dependencies.verification import get_current_verified_driver
from app.models.ride import (
    CancelRideRequest,
    CreateRideRequest,
    EditRideRequest,
)
from app.models.route import GeoPoint
from app.services import ride_service, route_service
from app.services.pricing_service import calculate_fare
from app.services.ride_service import RideServiceError
from app.services.route_service import RouteServiceUnavailableError

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
    if payload.price_per_seat is not None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "price_override_not_allowed",
                "message": "price_per_seat is system-calculated and cannot be set by the driver.",
            },
        )

    driver_id = uuid.UUID(str(profile["id"]))
    vehicle = await _get_active_vehicle(driver_id)

    origin = GeoPoint(
        lat=payload.origin.coordinates.lat,
        lng=payload.origin.coordinates.lng,
    )
    destination = GeoPoint(
        lat=payload.destination.coordinates.lat,
        lng=payload.destination.coordinates.lng,
    )

    try:
        route = await route_service.calculate_route(origin, destination)
    except RouteServiceUnavailableError:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "route_intelligence_unavailable",
                "message": "Route intelligence temporarily unavailable. Please try again shortly.",
            },
        )

    if not route.is_routable:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "unroutable",
                "message": "No road-network route found between the provided points. Ride creation is blocked until a valid route exists.",
            },
        )

    fare = calculate_fare(route.distance_km, payload.total_seats)

    try:
        ride = await ride_service.create_ride(
            driver_id=driver_id,
            vehicle_id=uuid.UUID(str(vehicle["id"])),
            vehicle_seat_count=vehicle["seat_count"],
            payload=payload,
            route_geometry_geojson=route.geojson_linestring,
            route_distance_km=route.distance_km,
            route_duration_minutes=route.duration_minutes,
            fuel_cost_egp=fare.fuel_cost_egp,
            platform_commission_egp=fare.platform_commission_egp,
            safety_margin_egp=fare.safety_margin_egp,
            fare_per_seat_egp=fare.per_seat_price_egp,
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

