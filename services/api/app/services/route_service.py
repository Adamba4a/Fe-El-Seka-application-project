from __future__ import annotations

import asyncio
import logging
import time

import httpx

from app.core.config import settings
from app.core.database import get_pool
from app.models.route import CompatibilityResult, GeoPoint, RouteGeometry
from app.services.pricing_service import calculate_premium_detour_fee

logger = logging.getLogger(__name__)


class RouteServiceUnavailableError(Exception):
    pass


_http_client = httpx.AsyncClient(
    base_url=settings.osrm_url,
    timeout=10.0,
)


# ── Private helpers ───────────────────────────────────────────────────────────


def _geopoint_to_wkt(point: GeoPoint) -> str:
    return f"POINT({point.lng} {point.lat})"


def _wkt_point_to_lng_lat(wkt: str) -> tuple[float, float]:
    """Parse 'POINT(lng lat)' WKT → (lng, lat)."""
    inner = wkt.strip().split("(", 1)[1].rstrip(")")
    lng_str, lat_str = inner.split()
    return float(lng_str), float(lat_str)


def _geojson_linestring_to_wkt(geojson: dict) -> str:
    coords = geojson.get("coordinates", [])
    if len(coords) < 2:
        return "LINESTRING EMPTY"
    coord_str = ", ".join(f"{lng} {lat}" for lng, lat in coords)
    return f"LINESTRING({coord_str})"


async def _osrm_get(path: str, params: dict) -> dict:
    """Shared OSRM HTTP call. Raises RouteServiceUnavailableError on network/5xx."""
    try:
        response = await _http_client.get(path, params=params)
    except httpx.RequestError as exc:
        logger.error("OSRM request error path=%s error=%s", path, exc)
        raise RouteServiceUnavailableError(str(exc)) from exc
    if response.status_code >= 500:
        logger.error("OSRM returned HTTP %d for path=%s", response.status_code, path)
        raise RouteServiceUnavailableError(f"OSRM returned HTTP {response.status_code}")
    return response.json()


# ── T014: US1 — Route path calculation ───────────────────────────────────────


async def calculate_route(origin: GeoPoint, destination: GeoPoint) -> RouteGeometry:
    t0 = time.monotonic()
    path = (
        f"/route/v1/driving/{origin.lng},{origin.lat}"
        f";{destination.lng},{destination.lat}"
    )
    data = await _osrm_get(
        path, {"overview": "full", "geometries": "geojson", "steps": "false"}
    )

    if data.get("code") != "Ok" or not data.get("routes"):
        elapsed_ms = round((time.monotonic() - t0) * 1000)
        logger.info(
            "calculate_route origin=(%.5f,%.5f) dest=(%.5f,%.5f) "
            "is_routable=False elapsed_ms=%d",
            origin.lat, origin.lng, destination.lat, destination.lng, elapsed_ms,
        )
        return RouteGeometry(
            is_routable=False,
            distance_km=0.0,
            duration_minutes=0,
            geojson_linestring={},
        )

    route = data["routes"][0]
    # OSRM snaps coordinates to the nearest road. When both ends snap to the
    # same point (e.g. ocean coordinates far from any road), distance == 0.
    # Treat this as unroutable so callers get a 422 instead of a zero-fare ride.
    if route["distance"] == 0:
        elapsed_ms = round((time.monotonic() - t0) * 1000)
        logger.info(
            "calculate_route origin=(%.5f,%.5f) dest=(%.5f,%.5f) "
            "is_routable=False (zero-distance snap) elapsed_ms=%d",
            origin.lat, origin.lng, destination.lat, destination.lng, elapsed_ms,
        )
        return RouteGeometry(
            is_routable=False,
            distance_km=0.0,
            duration_minutes=0,
            geojson_linestring={},
        )

    result = RouteGeometry(
        is_routable=True,
        distance_km=round(route["distance"] / 1000, 3),
        duration_minutes=round(route["duration"] / 60),
        geojson_linestring=route["geometry"],
    )
    elapsed_ms = round((time.monotonic() - t0) * 1000)
    logger.info(
        "calculate_route origin=(%.5f,%.5f) dest=(%.5f,%.5f) "
        "is_routable=True distance_km=%.3f duration_min=%d elapsed_ms=%d",
        origin.lat, origin.lng, destination.lat, destination.lng,
        result.distance_km, result.duration_minutes, elapsed_ms,
    )
    return result


# ── T018: US2 — PostGIS route corridor overlap ────────────────────────────────


async def calculate_overlap_pct(
    ride_geometry_wkt: str,
    passenger_route_wkt: str,
    buffer_m: int,
) -> float:
    """% of passenger route covered by a buffered corridor around the driver route."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                ST_Length(
                    ST_Intersection(
                        ST_Buffer(ST_GeomFromText($1, 4326)::geography, $2)::geometry,
                        ST_GeomFromText($3, 4326)
                    )::geography
                )
                / NULLIF(ST_Length(ST_GeomFromText($3, 4326)::geography), 0)
                * 100 AS overlap_pct
            """,
            ride_geometry_wkt,
            buffer_m,
            passenger_route_wkt,
        )
    return float(row["overlap_pct"] or 0.0)


# ── T019: US2 — Walk distance to nearest point on route ──────────────────────


async def calculate_walk_distance(
    point_wkt: str,
    route_wkt: str,
) -> tuple[float, str]:
    """Returns (walk_metres, nearest_point_wkt).
    nearest_point_wkt feeds into calculate_detour as an OSRM waypoint."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                ST_Distance(
                    ST_GeomFromText($1, 4326)::geography,
                    cp::geography
                ) AS walk_m,
                ST_AsText(cp) AS nearest_wkt
            FROM (
                SELECT ST_ClosestPoint(
                    ST_GeomFromText($2, 4326),
                    ST_GeomFromText($1, 4326)
                ) AS cp
            ) sub
            """,
            point_wkt,
            route_wkt,
        )
    walk_m = float(row["walk_m"] or 0.0)
    nearest_wkt = row["nearest_wkt"] or point_wkt
    return walk_m, nearest_wkt


# ── T020: US2 — Standard detour (driver deviates via route corridor points) ───


async def calculate_detour(
    driver_origin: GeoPoint,
    pickup_point_wkt: str,
    dropoff_point_wkt: str,
    driver_destination: GeoPoint,
    original_distance_km: float,
    original_duration_minutes: int,
) -> tuple[float, int]:
    """Returns (detour_km, detour_minutes) above the driver's original route."""
    pickup_lng, pickup_lat = _wkt_point_to_lng_lat(pickup_point_wkt)
    dropoff_lng, dropoff_lat = _wkt_point_to_lng_lat(dropoff_point_wkt)
    waypoints = (
        f"{driver_origin.lng},{driver_origin.lat}"
        f";{pickup_lng},{pickup_lat}"
        f";{dropoff_lng},{dropoff_lat}"
        f";{driver_destination.lng},{driver_destination.lat}"
    )
    data = await _osrm_get(
        f"/route/v1/driving/{waypoints}", {"overview": "false", "steps": "false"}
    )
    if data.get("code") != "Ok" or not data.get("routes"):
        return (0.0, 0)
    route = data["routes"][0]
    total_km = route["distance"] / 1000
    total_minutes = round(route["duration"] / 60)
    return (
        max(0.0, round(total_km - original_distance_km, 3)),
        max(0, total_minutes - original_duration_minutes),
    )


# ── T021: US2 — Premium detour (driver deviates to passenger's exact point) ───


async def calculate_premium_detour(
    driver_origin: GeoPoint,
    passenger_point: GeoPoint,
    driver_destination: GeoPoint,
    original_distance_km: float,
    original_duration_minutes: int,
) -> tuple[float, int]:
    """Returns (detour_km, detour_minutes) when the driver goes to the exact passenger point."""
    waypoints = (
        f"{driver_origin.lng},{driver_origin.lat}"
        f";{passenger_point.lng},{passenger_point.lat}"
        f";{driver_destination.lng},{driver_destination.lat}"
    )
    data = await _osrm_get(
        f"/route/v1/driving/{waypoints}", {"overview": "false", "steps": "false"}
    )
    if data.get("code") != "Ok" or not data.get("routes"):
        return (0.0, 0)
    route = data["routes"][0]
    total_km = route["distance"] / 1000
    total_minutes = round(route["duration"] / 60)
    return (
        max(0.0, round(total_km - original_distance_km, 3)),
        max(0, total_minutes - original_duration_minutes),
    )


# ── T023: US2 — Compatibility assessment orchestrator ────────────────────────


async def assess_compatibility(
    ride: dict,
    passenger_origin: GeoPoint,
    passenger_destination: GeoPoint,
    passenger_route_geom: RouteGeometry,
    config: dict,
    dest_bbox: dict | None = None,
) -> CompatibilityResult:
    """Orchestrates overlap, walk, detour, and premium eligibility checks.

    ride dict must include: route_geometry_wkt, route_distance_km,
    route_duration_minutes, origin_lat, origin_lng, destination_lat, destination_lng.
    """
    ride_wkt = ride["route_geometry_wkt"]
    passenger_route_wkt = _geojson_linestring_to_wkt(
        passenger_route_geom.geojson_linestring
    )
    origin_wkt = _geopoint_to_wkt(passenger_origin)
    dest_wkt = _geopoint_to_wkt(passenger_destination)

    driver_origin = GeoPoint(lat=ride["origin_lat"], lng=ride["origin_lng"])
    driver_dest = GeoPoint(lat=ride["destination_lat"], lng=ride["destination_lng"])
    original_distance_km = float(ride["route_distance_km"])
    original_duration_minutes = int(ride.get("route_duration_minutes") or 0)

    # Overlap and both walk distances in parallel — three DB round-trips at once
    overlap_pct, pickup_result, dropoff_result = await asyncio.gather(
        calculate_overlap_pct(
            ride_wkt, passenger_route_wkt, int(config["corridor_buffer_radius_m"])
        ),
        calculate_walk_distance(origin_wkt, ride_wkt),
        calculate_walk_distance(dest_wkt, ride_wkt),
    )
    pickup_walk_m, pickup_nearest_wkt = pickup_result
    dropoff_walk_m, dropoff_nearest_wkt = dropoff_result

    max_pickup_walk = float(config["max_pickup_walk_m"])
    max_dropoff_walk = float(config["max_dropoff_walk_m"])
    min_overlap = float(config["min_overlap_pct"])
    max_detour_km = float(config["max_detour_km"])
    max_detour_minutes = int(config["max_detour_minutes"])
    max_premium_detour_km = float(config["max_premium_detour_km"])

    overlap_ok = overlap_pct >= min_overlap
    pickup_ok = pickup_walk_m <= max_pickup_walk

    # Dropoff: standard walk check OR driver's destination falls inside the
    # passenger's geocoded bounding box (handles area searches like "Giza" where
    # the Nominatim centroid is far from where the driver actually ends up within
    # that administrative area — e.g. Cairo University is inside the Giza bbox).
    driver_dest_in_bbox = False
    if dest_bbox:
        d_lat = float(ride["destination_lat"])
        d_lng = float(ride["destination_lng"])
        driver_dest_in_bbox = (
            dest_bbox["south"] <= d_lat <= dest_bbox["north"]
            and dest_bbox["west"] <= d_lng <= dest_bbox["east"]
        )

    dropoff_ok = dropoff_walk_m <= max_dropoff_walk or driver_dest_in_bbox

    detour_km = 0.0
    detour_minutes = 0
    is_compatible = False

    # Pickup walk distance is informational only (surfaced to the passenger as
    # pickup_walk_m) — it no longer gates standard-match eligibility. The passenger
    # decides whether the walk is acceptable, or requests a paid premium pickup instead.
    if overlap_ok and dropoff_ok:
        detour_km, detour_minutes = await calculate_detour(
            driver_origin,
            pickup_nearest_wkt,
            dropoff_nearest_wkt,
            driver_dest,
            original_distance_km,
            original_duration_minutes,
        )
        is_compatible = (
            detour_km <= max_detour_km and detour_minutes <= max_detour_minutes
        )

    # Premium pickup — walk exceeds standard; offered as a paid door-to-door option
    # regardless of how large the driver's detour is. No distance cap: the fee scales
    # with the real detour, and the driver can accept or decline the specific request.
    premium_pickup_available = False
    premium_pickup_detour_km = 0.0
    premium_pickup_fee_egp = None

    if not pickup_ok:
        p_km, _ = await calculate_premium_detour(
            driver_origin,
            passenger_origin,
            driver_dest,
            original_distance_km,
            original_duration_minutes,
        )
        premium_pickup_available = True
        premium_pickup_detour_km = p_km
        premium_pickup_fee_egp = calculate_premium_detour_fee(p_km)

    # Premium dropoff — same logic for the dropoff side
    premium_dropoff_available = False
    premium_dropoff_detour_km = 0.0
    premium_dropoff_fee_egp = None

    if not dropoff_ok:
        d_km, _ = await calculate_premium_detour(
            driver_origin,
            passenger_destination,
            driver_dest,
            original_distance_km,
            original_duration_minutes,
        )
        if d_km <= max_premium_detour_km:
            premium_dropoff_available = True
            premium_dropoff_detour_km = d_km
            premium_dropoff_fee_egp = calculate_premium_detour_fee(d_km)

    # Nearby endpoint — last-resort fallback when the passenger's destination
    # is beyond both the walk and premium-detour range of the driver's route,
    # but the driver's own endpoint is still a reasonably short trip away from
    # it. Unlike premium dropoff, the driver makes no detour at all — they
    # already end their route there — so there's no fee, just a distance to
    # surface to the passenger.
    nearby_endpoint_available = False
    nearby_endpoint_distance_km = 0.0
    nearby_endpoint_duration_minutes = 0

    if overlap_ok and not dropoff_ok and not premium_dropoff_available:
        max_nearby_endpoint_km = float(config["max_nearby_endpoint_km"])
        endpoint_route = await calculate_route(driver_dest, passenger_destination)
        if endpoint_route.is_routable and endpoint_route.distance_km <= max_nearby_endpoint_km:
            nearby_endpoint_available = True
            nearby_endpoint_distance_km = endpoint_route.distance_km
            nearby_endpoint_duration_minutes = endpoint_route.duration_minutes

    return CompatibilityResult(
        overlap_pct=round(overlap_pct, 2),
        pickup_walk_m=round(pickup_walk_m, 1),
        dropoff_walk_m=round(dropoff_walk_m, 1),
        detour_km=round(detour_km, 3),
        detour_minutes=detour_minutes,
        is_compatible=is_compatible,
        premium_pickup_available=premium_pickup_available,
        premium_pickup_detour_km=round(premium_pickup_detour_km, 3),
        premium_pickup_fee_egp=premium_pickup_fee_egp,
        premium_dropoff_available=premium_dropoff_available,
        premium_dropoff_detour_km=round(premium_dropoff_detour_km, 3),
        premium_dropoff_fee_egp=premium_dropoff_fee_egp,
        nearby_endpoint_available=nearby_endpoint_available,
        nearby_endpoint_distance_km=round(nearby_endpoint_distance_km, 3),
        nearby_endpoint_duration_minutes=nearby_endpoint_duration_minutes,
    )
