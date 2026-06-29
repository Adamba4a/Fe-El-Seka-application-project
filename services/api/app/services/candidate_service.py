from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import datetime

from app.core.database import get_pool
from app.models.route import (
    CandidateListResponse,
    GeoPoint,
    RideCandidate,
    RouteGeometry,
)
from app.services import route_service
from app.services.pricing_service import get_pricing_config
from app.services.route_service import RouteServiceUnavailableError

logger = logging.getLogger(__name__)

_STAGE1_POOL_CAP = 500
_STAGE2_CONCURRENCY = 10


# ── Helpers ───────────────────────────────────────────────────────────────────


def _bbox(
    origin: GeoPoint, destination: GeoPoint, pad_km: float
) -> tuple[float, float, float, float]:
    """Return (min_lng, min_lat, max_lng, max_lat) with padding in km."""
    center_lat = (origin.lat + destination.lat) / 2
    lat_pad = pad_km / 111.32
    lng_pad = pad_km / (111.32 * math.cos(math.radians(center_lat)))
    return (
        min(origin.lng, destination.lng) - lng_pad,
        min(origin.lat, destination.lat) - lat_pad,
        max(origin.lng, destination.lng) + lng_pad,
        max(origin.lat, destination.lat) + lat_pad,
    )


# ── T025: Stage 1 — index-driven SQL filter ──────────────────────────────────


async def _stage1_query(
    origin: GeoPoint,
    destination: GeoPoint,
    config: dict,
) -> list[dict]:
    pad_km = float(config["max_premium_detour_km"])
    min_lng, min_lat, max_lng, max_lat = _bbox(origin, destination, pad_km)

    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
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
            WHERE
                status = 'scheduled'
                AND available_seats > 0
                AND route_geometry IS NOT NULL
                AND departure_datetime > NOW()
                AND route_geometry && ST_MakeEnvelope($1, $2, $3, $4, 4326)
            ORDER BY departure_datetime
            LIMIT $5
            """,
            min_lng,
            min_lat,
            max_lng,
            max_lat,
            _STAGE1_POOL_CAP,
        )

    rides = [dict(r) for r in rows]
    if len(rides) == _STAGE1_POOL_CAP:
        logger.warning(
            "Stage 1 hit pool cap (%d) — some candidates may be excluded",
            _STAGE1_POOL_CAP,
        )
    logger.info("Stage 1: %d candidate rides", len(rides))
    return rides


# ── T026: Stage 2 — per-ride compatibility pipeline ──────────────────────────


async def _assess_ride(
    ride: dict,
    origin: GeoPoint,
    destination: GeoPoint,
    passenger_route: RouteGeometry,
    config: dict,
    sem: asyncio.Semaphore,
    dest_bbox: dict | None = None,
) -> tuple[dict, object] | None:
    async with sem:
        return (
            ride,
            await route_service.assess_compatibility(
                ride, origin, destination, passenger_route, config, dest_bbox=dest_bbox
            ),
        )


# ── T024: generate_candidates ────────────────────────────────────────────────


async def generate_candidates(
    origin: GeoPoint,
    destination: GeoPoint,
    config: dict | None = None,
    dest_bbox: dict | None = None,
) -> CandidateListResponse:
    t0 = time.monotonic()
    logger.info(
        "generate_candidates origin=(%.5f,%.5f) dest=(%.5f,%.5f)",
        origin.lat, origin.lng, destination.lat, destination.lng,
    )

    if config is None:
        config = get_pricing_config()

    rides = await _stage1_query(origin, destination, config)
    if not rides:
        return CandidateListResponse(standard=[], premium=[], total_count=0)

    # Passenger route computed once and reused across all Stage 2 assessments
    passenger_route = await route_service.calculate_route(origin, destination)
    if not passenger_route.is_routable:
        return CandidateListResponse(standard=[], premium=[], total_count=0)

    sem = asyncio.Semaphore(_STAGE2_CONCURRENCY)
    raw_results = await asyncio.gather(
        *[
            _assess_ride(ride, origin, destination, passenger_route, config, sem, dest_bbox=dest_bbox)
            for ride in rides
        ],
        return_exceptions=True,
    )

    standard: list[RideCandidate] = []
    premium: list[RideCandidate] = []

    for item in raw_results:
        if isinstance(item, RouteServiceUnavailableError):
            raise item  # propagate → endpoint returns 503
        if isinstance(item, Exception):
            logger.warning("Skipping ride due to assessment error: %s", item)
            continue
        if item is None:
            continue

        ride, compat = item

        base = dict(
            ride_id=ride["id"],
            driver_id=ride["driver_id"],
            departure_time=ride["departure_datetime"],
            available_seats=ride["available_seats"],
            price_per_seat_egp=float(ride["price_per_seat"]),
            compatibility=compat,
        )

        if compat.is_compatible:
            standard.append(RideCandidate(candidate_type="standard", **base))
        elif compat.premium_pickup_available or compat.premium_dropoff_available:
            premium.append(RideCandidate(candidate_type="premium", **base))

    standard.sort(key=lambda r: r.compatibility.overlap_pct, reverse=True)
    premium.sort(
        key=lambda r: (
            (r.compatibility.premium_pickup_fee_egp or 0.0)
            + (r.compatibility.premium_dropoff_fee_egp or 0.0)
        )
    )

    elapsed_ms = round((time.monotonic() - t0) * 1000)
    logger.info(
        "Stage 2: %d standard, %d premium (from %d Stage 1 candidates) elapsed_ms=%d",
        len(standard),
        len(premium),
        len(rides),
        elapsed_ms,
    )
    return CandidateListResponse(
        standard=standard,
        premium=premium,
        total_count=len(standard) + len(premium),
    )
