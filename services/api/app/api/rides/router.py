from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.core.database import get_pool
from app.dependencies.auth import get_current_user
from app.dependencies.verification import get_current_verified_driver
from app.models.booking import BookingCancelRequest, DriverBookingItem, DriverBookingListResponse, DriverConfirmResponse, DriverRejectResponse
from app.models.location import LocationUpdateRequest
from app.models.ride import (
    CancelRideRequest,
    CreateRideRequest,
    EditRideRequest,
)
from app.models.route import GeoPoint
from app.services import ride_service, route_service
from app.services import booking_service, location_service
from app.services.location_service import LocationServiceError
from app.services.pricing_service import calculate_fare, get_pricing_config
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
            price_per_seat=fare.per_seat_price_egp,
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
# POST /api/v1/rides/{ride_id}/location  (T027)
# ─────────────────────────────────────────────────────────────────────────────

def _location_error_response(exc: LocationServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message},
    )


@router.post("/{ride_id}/location", status_code=status.HTTP_200_OK)
async def update_driver_location(
    ride_id: uuid.UUID,
    payload: LocationUpdateRequest,
    profile: dict = Depends(get_current_verified_driver),
):
    t0 = time.monotonic()
    driver_id = uuid.UUID(str(profile["id"]))
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            result = await location_service.upsert_location(
                conn=conn,
                ride_id=ride_id,
                driver_id=driver_id,
                lat=payload.lat,
                lng=payload.lng,
                bearing=payload.bearing,
                speed_kmh=payload.speed_kmh,
                client_timestamp=payload.client_timestamp,
            )
        except LocationServiceError as exc:
            logger.warning(
                "POST /rides/%s/location | driver_id=%s | error=%s | duration_ms=%.1f",
                ride_id, driver_id, exc.code, (time.monotonic() - t0) * 1000,
            )
            return _location_error_response(exc)
    logger.info(
        "POST /rides/%s/location | driver_id=%s lat=%.5f lng=%.5f bearing=%s | duration_ms=%.1f",
        ride_id, driver_id, payload.lat, payload.lng, payload.bearing,
        (time.monotonic() - t0) * 1000,
    )
    return {
        "location_id": str(result.location_id),
        "ride_id": str(result.ride_id),
        "updated_at": result.updated_at.isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/rides/{ride_id}/location  (T027)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{ride_id}/location")
async def get_driver_location(
    ride_id: uuid.UUID,
    profile: dict = Depends(get_current_user),
):
    t0 = time.monotonic()
    caller_id = uuid.UUID(str(profile["id"]))
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            result = await location_service.read_location(
                conn=conn,
                ride_id=ride_id,
                caller_id=caller_id,
            )
        except LocationServiceError as exc:
            logger.warning(
                "GET /rides/%s/location | caller_id=%s | error=%s | duration_ms=%.1f",
                ride_id, caller_id, exc.code, (time.monotonic() - t0) * 1000,
            )
            return _location_error_response(exc)
    logger.info(
        "GET /rides/%s/location | caller_id=%s | lat=%.5f lng=%.5f | duration_ms=%.1f",
        ride_id, caller_id, result.lat, result.lng, (time.monotonic() - t0) * 1000,
    )
    return {
        "ride_id": str(result.ride_id),
        "lat": result.lat,
        "lng": result.lng,
        "bearing": result.bearing,
        "client_timestamp": result.client_timestamp.isoformat(),
        "updated_at": result.updated_at.isoformat(),
    }


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
# GET /api/v1/rides/{ride_id}/passenger-detail
# ─────────────────────────────────────────────────────────────────────────────

def _parse_wkt_point(wkt: str) -> tuple[float, float]:
    """Parse 'POINT(lng lat)' WKT → (lng, lat)."""
    inner = wkt.strip().split("(", 1)[1].rstrip(")")
    lng_str, lat_str = inner.split()
    return float(lng_str), float(lat_str)


@router.get("/{ride_id}/passenger-detail")
async def get_ride_passenger_detail(
    ride_id: uuid.UUID,
    origin_lat: float = Query(...),
    origin_lng: float = Query(...),
    destination_lat: float = Query(...),
    destination_lng: float = Query(...),
    departure_at: Optional[datetime] = Query(None),
    _user: dict = Depends(get_current_user),
):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                r.id, r.status, r.driver_id, r.departure_datetime,
                r.available_seats, r.price_per_seat,
                r.route_distance_km, r.route_duration_minutes,
                ST_AsText(r.route_geometry)    AS route_geometry_wkt,
                ST_AsGeoJSON(r.route_geometry) AS route_geometry_geojson,
                ST_Y(r.origin_coordinates::geometry)       AS origin_lat,
                ST_X(r.origin_coordinates::geometry)       AS origin_lng,
                ST_Y(r.destination_coordinates::geometry)  AS destination_lat,
                ST_X(r.destination_coordinates::geometry)  AS destination_lng,
                p.display_name, p.profile_photo_path AS avatar_url, p.verification_status
            FROM rides r
            JOIN profiles p ON p.id = r.driver_id
            WHERE r.id = $1
            """,
            ride_id,
        )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Ride not found"},
        )

    ride = dict(row)

    if ride["status"] in ("cancelled", "completed"):
        raise HTTPException(
            status_code=410,
            detail={"error": "ride_gone", "message": "This ride is no longer available"},
        )

    if ride["route_geometry_wkt"] is None:
        raise HTTPException(
            status_code=422,
            detail={"error": "no_route", "message": "Ride has no route geometry yet"},
        )

    passenger_origin = GeoPoint(lat=origin_lat, lng=origin_lng)
    passenger_destination = GeoPoint(lat=destination_lat, lng=destination_lng)

    origin_wkt = f"POINT({origin_lng} {origin_lat})"
    dest_wkt = f"POINT({destination_lng} {destination_lat})"

    # Compute boarding/alighting nearest points and passenger route in parallel
    (pickup_walk_m, pickup_nearest_wkt), (dropoff_walk_m, dropoff_nearest_wkt), passenger_route = (
        await asyncio.gather(
            route_service.calculate_walk_distance(origin_wkt, ride["route_geometry_wkt"]),
            route_service.calculate_walk_distance(dest_wkt, ride["route_geometry_wkt"]),
            route_service.calculate_route(passenger_origin, passenger_destination),
        )
    )

    config = get_pricing_config()
    compat = await route_service.assess_compatibility(
        ride, passenger_origin, passenger_destination, passenger_route, config
    )

    # Parse nearest-point WKT to lat/lng for boarding/alighting
    pickup_lng_val, pickup_lat_val = _parse_wkt_point(pickup_nearest_wkt)
    dropoff_lng_val, dropoff_lat_val = _parse_wkt_point(dropoff_nearest_wkt)

    # Estimate passenger travel time as share of driver route duration
    duration_min = ride["route_duration_minutes"] or 0
    estimated_travel_minutes = max(1, round(duration_min * compat.overlap_pct / 100)) if duration_min else None

    route_geojson = json.loads(ride["route_geometry_geojson"]) if ride["route_geometry_geojson"] else None

    match_score_pct = None
    if departure_at is not None:
        try:
            from app.models.ai import CandidateFeatures, PassengerRequestFeatures, ZoneCentroid
            from app.services import ai_client as _ai
            from app.utils.zone_lookup import nearest_zone as _nz

            p_orig_zone, p_orig_c = _nz(origin_lat, origin_lng)
            p_dest_zone, p_dest_c = _nz(destination_lat, destination_lng)
            d_orig_zone, d_orig_c = _nz(float(ride["origin_lat"]), float(ride["origin_lng"]))
            d_dest_zone, d_dest_c = _nz(float(ride["destination_lat"]), float(ride["destination_lng"]))

            passenger_req = PassengerRequestFeatures(
                origin_zone=p_orig_zone,
                destination_zone=p_dest_zone,
                origin_centroid=ZoneCentroid(**p_orig_c),
                destination_centroid=ZoneCentroid(**p_dest_c),
                departure_at=departure_at,
            )
            candidate_feat = CandidateFeatures(
                ride_id=str(ride_id),
                driver_origin_zone=d_orig_zone,
                driver_destination_zone=d_dest_zone,
                driver_origin_centroid=ZoneCentroid(**d_orig_c),
                driver_dest_centroid=ZoneCentroid(**d_dest_c),
                driver_departure_at=ride["departure_datetime"],
                estimated_overlap_ratio=max(0.0, min(1.0, compat.overlap_pct / 100)),
                estimated_pickup_detour_km=max(0.0, compat.pickup_walk_m / 1000),
                estimated_dropoff_distance_km=max(0.0, compat.dropoff_walk_m / 1000),
            )
            scored, _ = await _ai.score_candidates(passenger_req, [candidate_feat])
            if scored:
                match_score_pct = scored[0].match_score_pct
        except Exception:
            pass

    return JSONResponse({
        "ride": {
            "id": str(ride["id"]),
            "status": ride["status"],
            "driver": {
                "display_name": ride["display_name"],
                "avatar_url": ride["avatar_url"],
                "is_verified": ride["verification_status"] == "verified",
            },
            "departure_datetime": ride["departure_datetime"].isoformat(),
            "available_seats": ride["available_seats"],
            "per_seat_price": f"{float(ride['price_per_seat']):.2f}",
            "route_geometry": route_geojson,
            "route_distance_km": float(ride["route_distance_km"] or 0),
            "route_duration_minutes": duration_min,
        },
        "passenger_context": {
            "boarding_point": {"lat": pickup_lat_val, "lng": pickup_lng_val},
            "alighting_point": {"lat": dropoff_lat_val, "lng": dropoff_lng_val},
            "pickup_walk_meters": round(compat.pickup_walk_m),
            "dropoff_walk_meters": round(compat.dropoff_walk_m),
            "estimated_travel_minutes": estimated_travel_minutes,
            "premium_pickup_available": compat.premium_pickup_available,
            "premium_pickup_fee": compat.premium_pickup_fee_egp,
            "premium_dropoff_available": compat.premium_dropoff_available,
            "premium_dropoff_fee": compat.premium_dropoff_fee_egp,
        },
        "match_score_pct": match_score_pct,
    })


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
# GET /api/v1/rides/{ride_id}/bookings  (T026)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{ride_id}/bookings")
async def list_ride_bookings(
    ride_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    profile: dict = Depends(get_current_verified_driver),
):
    driver_id = uuid.UUID(str(profile["id"]))
    pool = get_pool()
    async with pool.acquire() as conn:
        await booking_service._assert_ride_owner(conn, ride_id, driver_id)

        query = """
            SELECT
                b.id              AS booking_id,
                b.status,
                b.per_seat_price,
                b.total_price,
                b.premium_pickup_requested,
                b.premium_pickup_fee,
                b.premium_dropoff_requested,
                b.premium_dropoff_fee,
                b.created_at,
                ST_Y(b.passenger_pickup_point::geometry)  AS boarding_lat,
                ST_X(b.passenger_pickup_point::geometry)  AS boarding_lng,
                ST_Y(b.passenger_dropoff_point::geometry) AS alighting_lat,
                ST_X(b.passenger_dropoff_point::geometry) AS alighting_lng,
                p.display_name        AS passenger_display_name,
                p.profile_photo_path  AS passenger_avatar_url
            FROM bookings b
            JOIN profiles p ON p.id = b.passenger_id
            WHERE b.ride_id = $1
        """
        params: list = [ride_id]

        if status_filter:
            query += " AND b.status = $2"
            params.append(status_filter)

        query += " ORDER BY b.created_at ASC"

        rows = await conn.fetch(query, *params)

    items = [
        DriverBookingItem(
            booking_id=r["booking_id"],
            passenger={
                "display_name": r["passenger_display_name"],
                "avatar_url": r["passenger_avatar_url"],
            },
            status=r["status"],
            per_seat_price=f"{float(r['per_seat_price']):.2f}",
            total_price=f"{float(r['total_price']):.2f}",
            boarding_point={"lat": r["boarding_lat"], "lng": r["boarding_lng"]},
            alighting_point={"lat": r["alighting_lat"], "lng": r["alighting_lng"]},
            premium_pickup_requested=r["premium_pickup_requested"],
            premium_pickup_fee=f"{float(r['premium_pickup_fee']):.2f}" if r["premium_pickup_fee"] is not None else None,
            premium_dropoff_requested=r["premium_dropoff_requested"],
            premium_dropoff_fee=f"{float(r['premium_dropoff_fee']):.2f}" if r["premium_dropoff_fee"] is not None else None,
            created_at=r["created_at"],
        )
        for r in rows
    ]
    return DriverBookingListResponse(bookings=items, total=len(items)).model_dump(mode="json")


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/rides/{ride_id}/bookings/{booking_id}/confirm  (T027)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{ride_id}/bookings/{booking_id}/confirm")
async def confirm_booking(
    ride_id: uuid.UUID,
    booking_id: uuid.UUID,
    profile: dict = Depends(get_current_verified_driver),
):
    driver_id = uuid.UUID(str(profile["id"]))
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await booking_service.confirm_booking(conn, booking_id, ride_id, driver_id)
    return DriverConfirmResponse(
        booking_id=result["id"],
        status=result["status"],
        confirmed_at=result.get("confirmed_at"),
    ).model_dump(mode="json")


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/rides/{ride_id}/bookings/{booking_id}/reject  (T028)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{ride_id}/bookings/{booking_id}/reject")
async def reject_booking(
    ride_id: uuid.UUID,
    booking_id: uuid.UUID,
    payload: BookingCancelRequest = None,
    profile: dict = Depends(get_current_verified_driver),
):
    driver_id = uuid.UUID(str(profile["id"]))
    reason = payload.reason if payload else None
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await booking_service.reject_booking(conn, booking_id, ride_id, driver_id, reason)
    return DriverRejectResponse(
        booking_id=result.get("id") or booking_id,
        status=result["status"],
        cancelled_by=result.get("cancelled_by"),
        fallback_applied=result.get("fallback_applied", False),
    ).model_dump(mode="json")


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/rides/{ride_id}/bookings/{booking_id}/cancel  (T034)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{ride_id}/bookings/{booking_id}/cancel")
async def cancel_booking_driver(
    ride_id: uuid.UUID,
    booking_id: uuid.UUID,
    payload: BookingCancelRequest = None,
    profile: dict = Depends(get_current_verified_driver),
):
    driver_id = uuid.UUID(str(profile["id"]))
    reason = payload.reason if payload else None
    pool = get_pool()
    async with pool.acquire() as conn:
        await booking_service._assert_ride_owner(conn, ride_id, driver_id)
        result = await booking_service.cancel_booking(
            conn, booking_id, driver_id, "driver", reason
        )
    return {
        "booking_id": str(result["id"]),
        "status": result["status"],
        "cancelled_by": result["cancelled_by"],
        "late_cancellation": result["late_cancellation"],
        "cancelled_at": result["cancelled_at"].isoformat(),
    }

