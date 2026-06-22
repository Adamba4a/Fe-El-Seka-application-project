from __future__ import annotations

from datetime import timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.config import settings
from app.core.database import get_pool
from app.models.route import (
    CompatibilityFeatures,
    CompatibilityFeaturesRequest,
)
from app.services import route_service
from app.services.pricing_service import get_pricing_config
from app.services.route_service import RouteServiceUnavailableError

router = APIRouter()

_RIDE_COLS = """
    SELECT
        id,
        driver_id,
        departure_datetime,
        available_seats,
        price_per_seat,
        route_distance_km,
        route_duration_minutes,
        ST_Y(origin_coordinates::geometry)      AS origin_lat,
        ST_X(origin_coordinates::geometry)      AS origin_lng,
        ST_Y(destination_coordinates::geometry) AS destination_lat,
        ST_X(destination_coordinates::geometry) AS destination_lng,
        ST_AsText(route_geometry)               AS route_geometry_wkt
    FROM rides
    WHERE id = $1 AND route_geometry IS NOT NULL
"""


def _require_internal_secret(
    x_internal_secret: Optional[str] = Header(None),
) -> None:
    if not settings.internal_secret or x_internal_secret != settings.internal_secret:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "Invalid or missing internal secret."},
        )


def _utc(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.post(
    "/compatibility",
    response_model=CompatibilityFeatures,
    include_in_schema=False,
)
async def compatibility_features(
    body: CompatibilityFeaturesRequest,
    _: None = Depends(_require_internal_secret),
) -> CompatibilityFeatures:
    # Fetch ride — 404 if missing or lacks route geometry (legacy Phase 4 ride)
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_RIDE_COLS, body.ride_id)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Ride not found or has no route geometry.",
            },
        )

    ride = dict(row)

    try:
        passenger_route = await route_service.calculate_route(
            body.passenger_origin, body.passenger_destination
        )
    except RouteServiceUnavailableError:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "route_intelligence_unavailable",
                "message": "Route intelligence temporarily unavailable.",
            },
        )

    if not passenger_route.is_routable:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "unroutable",
                "message": "No road-network route found for the passenger's journey.",
            },
        )

    config = get_pricing_config()

    try:
        compat = await route_service.assess_compatibility(
            ride,
            body.passenger_origin,
            body.passenger_destination,
            passenger_route,
            config,
        )
    except RouteServiceUnavailableError:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "route_intelligence_unavailable",
                "message": "Route intelligence temporarily unavailable.",
            },
        )

    departure_delta_minutes = round(
        abs(
            (
                _utc(ride["departure_datetime"]) - _utc(body.requested_departure_time)
            ).total_seconds()
        )
        / 60
    )

    return CompatibilityFeatures(
        ride_id=body.ride_id,
        overlap_pct=compat.overlap_pct,
        pickup_walk_m=compat.pickup_walk_m,
        dropoff_walk_m=compat.dropoff_walk_m,
        detour_km=compat.detour_km,
        detour_minutes=compat.detour_minutes,
        passenger_route_km=round(passenger_route.distance_km, 3),
        driver_route_km=round(float(ride["route_distance_km"]), 3),
        available_seats=ride["available_seats"],
        departure_delta_minutes=departure_delta_minutes,
        price_per_seat_egp=float(ride["price_per_seat"]),
        is_compatible=compat.is_compatible,
        premium_pickup_available=compat.premium_pickup_available,
        premium_dropoff_available=compat.premium_dropoff_available,
    )
