from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from app.core.database import get_pool
from app.services.pricing_service import calculate_fare, get_pricing_config
from app.models.ai import AIPriceRequest, ZoneCentroid
from app.services import ai_client as _ai_module
from app.services.ai_client import AIServiceUnavailableError as _AIError
from app.utils.zone_lookup import nearest_zone as _nearest_zone
from app.models.ride import (
    CoordinatesSchema,
    CreateRideRequest,
    EditRideRequest,
    HistoryEntryResponse,
    LocationSchema,
    RideDetailResponse,
    RideListResponse,
    RideResponse,
)

# ─────────────────────────────────────────────────────────────────────────────
# Custom exceptions
# ─────────────────────────────────────────────────────────────────────────────

class RideServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_RIDE_COLS = """
    id, driver_id, vehicle_id,
    origin_address, destination_address,
    ST_Y(origin_coordinates::geometry)      AS origin_lat,
    ST_X(origin_coordinates::geometry)      AS origin_lng,
    ST_Y(destination_coordinates::geometry) AS dest_lat,
    ST_X(destination_coordinates::geometry) AS dest_lng,
    departure_datetime, total_seats, booked_seats, available_seats,
    price_per_seat, status, cancellation_reason, cancellation_source,
    notes, created_at, updated_at,
    route_distance_km, route_duration_minutes,
    fuel_cost_egp, platform_commission_egp, safety_margin_egp, price_source,
    started_at, completed_at
"""


def _to_response(row: dict) -> RideResponse:
    return RideResponse(
        id=row["id"],
        driver_id=row["driver_id"],
        vehicle_id=row["vehicle_id"],
        origin=LocationSchema(
            coordinates=CoordinatesSchema(lat=float(row["origin_lat"]), lng=float(row["origin_lng"])),
            address=row["origin_address"],
        ),
        destination=LocationSchema(
            coordinates=CoordinatesSchema(lat=float(row["dest_lat"]), lng=float(row["dest_lng"])),
            address=row["destination_address"],
        ),
        departure_datetime=row["departure_datetime"],
        total_seats=row["total_seats"],
        booked_seats=row["booked_seats"],
        available_seats=row["available_seats"],
        price_per_seat=str(row["price_per_seat"]),
        status=row["status"],
        cancellation_reason=row["cancellation_reason"],
        cancellation_source=row["cancellation_source"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        route_distance_km=(
            float(row["route_distance_km"]) if row["route_distance_km"] is not None else None
        ),
        route_duration_minutes=(
            int(row["route_duration_minutes"]) if row["route_duration_minutes"] is not None else None
        ),
        fuel_cost_egp=(
            float(row["fuel_cost_egp"]) if row["fuel_cost_egp"] is not None else None
        ),
        platform_commission_egp=(
            float(row["platform_commission_egp"]) if row["platform_commission_egp"] is not None else None
        ),
        safety_margin_egp=(
            float(row["safety_margin_egp"]) if row["safety_margin_egp"] is not None else None
        ),
        price_source=row["price_source"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _compute_ai_fare(req: AIPriceRequest) -> Decimal:
    return await _ai_module.get_fare(req)


def _compute_fallback_fare(distance_km: float, pricing_config: dict) -> Decimal:
    fuel = Decimal(str(pricing_config["fuel_price_per_litre"]))
    safety = Decimal(str(pricing_config["safety_margin"]))
    return (Decimal(str(distance_km / 15.0)) * fuel + safety).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


async def _fetch_own_ride(conn, ride_id: uuid.UUID, driver_id: uuid.UUID) -> dict:
    row = await conn.fetchrow(
        f"SELECT {_RIDE_COLS} FROM rides WHERE id = $1",
        ride_id,
    )
    if row is None or row["driver_id"] != driver_id:
        raise RideServiceError("ride_not_found", "Ride not found.", 404)
    return dict(row)


# ─────────────────────────────────────────────────────────────────────────────
# Create ride
# ─────────────────────────────────────────────────────────────────────────────

async def create_ride(
    driver_id: uuid.UUID,
    vehicle_id: uuid.UUID,
    vehicle_seat_count: int,
    payload: CreateRideRequest,
    *,
    route_geometry_geojson: dict,
    route_distance_km: float,
    route_duration_minutes: int,
    fuel_cost_egp: float,
    platform_commission_egp: float,
    safety_margin_egp: float,
) -> RideResponse:
    olat = payload.origin.coordinates.lat
    olng = payload.origin.coordinates.lng
    dlat = payload.destination.coordinates.lat
    dlng = payload.destination.coordinates.lng

    if abs(olat - dlat) < 1e-5 and abs(olng - dlng) < 1e-5:
        raise RideServiceError("ride_same_locations", "Origin and destination must be different locations.")

    now = _now()
    dep = payload.departure_datetime
    if dep.tzinfo is None:
        dep = dep.replace(tzinfo=timezone.utc)

    if dep <= now:
        raise RideServiceError("ride_departure_past", "Departure time must be in the future.")
    if dep > now + timedelta(hours=48):
        raise RideServiceError("ride_departure_too_far", "Rides can only be scheduled up to 48 hours in advance.")
    if payload.total_seats < 1 or payload.total_seats > vehicle_seat_count:
        raise RideServiceError(
            "seat_count_invalid",
            f"Seat count must be between 1 and your vehicle's capacity ({vehicle_seat_count}).",
        )

    origin_zone, origin_centroid = _nearest_zone(olat, olng)
    dest_zone, dest_centroid = _nearest_zone(dlat, dlng)
    ai_price_req = AIPriceRequest(
        origin_zone=origin_zone,
        destination_zone=dest_zone,
        origin_centroid=ZoneCentroid(**origin_centroid),
        destination_centroid=ZoneCentroid(**dest_centroid),
        estimated_distance_km=max(0.01, float(route_distance_km)),
        departure_at=dep,
    )
    try:
        price_per_seat = await _compute_ai_fare(ai_price_req)
    except _AIError:
        price_per_seat = _compute_fallback_fare(route_distance_km, get_pricing_config())

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Advisory lock: prevents concurrent same-driver rides bypassing overlap check
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", str(driver_id))

            conflict = await conn.fetchrow(
                """
                SELECT id FROM rides
                WHERE driver_id = $1
                  AND status IN ('scheduled', 'in_progress')
                  AND departure_datetime >= $2
                  AND departure_datetime <= $3
                """,
                driver_id,
                dep - timedelta(hours=2),
                dep + timedelta(hours=2),
            )
            if conflict:
                raise RideServiceError(
                    "ride_time_conflict",
                    "You already have a ride within 2 hours of this departure time.",
                    409,
                )

            # Phase 8 (FR-014): balance enforcement — lock wallet before ride INSERT so
            # the check and the ride creation are atomic; concurrent rides by the same
            # driver are serialized by the advisory lock already held above.
            from fastapi import HTTPException as _HTTPException
            from app.services import wallet_service as _ws
            from app.services.commission_service import check_available_balance, create_reservation

            max_commission = (Decimal(str(fuel_cost_egp)) * Decimal("0.20")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            wallet = await _ws.get_wallet_with_lock(conn, driver_id)

            if not check_available_balance(wallet, max_commission):
                _balance = Decimal(str(wallet["balance_egp"]))
                _reserved = Decimal(str(wallet["reserved_egp"]))
                raise _HTTPException(
                    status_code=422,
                    detail={
                        "error": "INSUFFICIENT_WALLET_BALANCE",
                        "message": "Insufficient wallet balance to cover this ride's commission.",
                        "available_egp": str(_balance - _reserved),
                        "required_commission_egp": str(max_commission),
                        "balance_egp": str(_balance),
                        "reserved_egp": str(_reserved),
                    },
                )

            row = await conn.fetchrow(
                f"""
                INSERT INTO rides (
                    driver_id, vehicle_id,
                    origin_coordinates, origin_address,
                    destination_coordinates, destination_address,
                    departure_datetime, total_seats, booked_seats, price_per_seat, notes, status,
                    route_geometry, route_distance_km, route_duration_minutes,
                    fuel_cost_egp, platform_commission_egp, safety_margin_egp, price_source
                ) VALUES (
                    $1, $2,
                    ST_GeomFromText($3, 4326)::geography, $4,
                    ST_GeomFromText($5, 4326)::geography, $6,
                    $7, $8, 0, $9, $10, 'scheduled',
                    ST_SetSRID(ST_GeomFromGeoJSON($11), 4326), $12, $13, $14, $15, $16, 'system'
                )
                RETURNING {_RIDE_COLS}
                """,
                driver_id, vehicle_id,
                f"POINT({olng} {olat})", payload.origin.address,
                f"POINT({dlng} {dlat})", payload.destination.address,
                dep, payload.total_seats, price_per_seat, payload.notes,
                json.dumps(route_geometry_geojson),
                route_distance_km, route_duration_minutes,
                fuel_cost_egp, platform_commission_egp, safety_margin_egp,
            )

            await conn.execute(
                "INSERT INTO ride_history_logs (ride_id, actor_id, action) VALUES ($1, $2, 'created')",
                row["id"], driver_id,
            )

            await create_reservation(conn, wallet["id"], driver_id, row["id"], max_commission)

    return _to_response(dict(row))


# ─────────────────────────────────────────────────────────────────────────────
# List rides
# ─────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

VALID_STATUSES = {"scheduled", "in_progress", "completed", "cancelled"}


async def list_rides(
    driver_id: uuid.UUID,
    status: Optional[str],
    page: int,
    page_size: int,
) -> RideListResponse:
    page_size = min(page_size, 50)
    offset = (page - 1) * page_size
    pool = get_pool()

    async with pool.acquire() as conn:
        where = "WHERE driver_id = $1"
        params: list = [driver_id]

        if status and status in VALID_STATUSES:
            where += " AND status = $2"
            params.append(status)

        rows = await conn.fetch(
            f"SELECT {_RIDE_COLS} FROM rides {where} ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}",
            *params,
        )
        total = await conn.fetchval(f"SELECT COUNT(*) FROM rides {where}", *params)

    return RideListResponse(
        rides=[_to_response(dict(r)) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Get ride detail
# ─────────────────────────────────────────────────────────────────────────────

async def get_ride(ride_id: uuid.UUID, driver_id: uuid.UUID) -> RideDetailResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        ride_row = await _fetch_own_ride(conn, ride_id, driver_id)

        history_rows = await conn.fetch(
            """
            SELECT id, actor_id, action, changed_fields, reason, created_at
            FROM ride_history_logs
            WHERE ride_id = $1
            ORDER BY created_at ASC
            """,
            ride_id,
        )

    return RideDetailResponse(
        ride=_to_response(ride_row),
        history=[
            HistoryEntryResponse(
                id=h["id"],
                actor_id=h["actor_id"],
                action=h["action"],
                changed_fields=h["changed_fields"],
                reason=h["reason"],
                created_at=h["created_at"],
            )
            for h in history_rows
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Edit ride
# ─────────────────────────────────────────────────────────────────────────────

async def edit_ride(
    ride_id: uuid.UUID,
    driver_id: uuid.UUID,
    payload: EditRideRequest,
) -> RideResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            ride = await _fetch_own_ride(conn, ride_id, driver_id)

            if ride["status"] != "scheduled":
                raise RideServiceError("ride_not_editable", "Only scheduled rides can be edited.", 409)

            now = _now()
            sets: list[str] = []
            params: list = []
            changed_fields: dict = {}

            def add_param(val):
                params.append(val)
                return f"${len(params)}"

            if payload.departure_datetime is not None:
                dep = payload.departure_datetime
                if dep.tzinfo is None:
                    dep = dep.replace(tzinfo=timezone.utc)
                if dep <= now:
                    raise RideServiceError("ride_departure_past", "Departure time must be in the future.")
                if dep > now + timedelta(hours=48):
                    raise RideServiceError("ride_departure_too_far", "Rides can only be scheduled up to 48 hours in advance.")
                if dep != ride["departure_datetime"]:
                    changed_fields["departure_datetime"] = {
                        "before": ride["departure_datetime"].isoformat(),
                        "after": dep.isoformat(),
                    }
                    sets.append(f"departure_datetime = {add_param(dep)}")

            if payload.destination is not None:
                if ride.get("price_source") == "system":
                    raise RideServiceError(
                        "destination_not_editable",
                        "Destination cannot be changed for rides with system-calculated pricing. "
                        "Cancel this ride and create a new one with the correct destination.",
                        400,
                    )
                dlat = payload.destination.coordinates.lat
                dlng = payload.destination.coordinates.lng
                changed_fields["destination_address"] = {
                    "before": ride["destination_address"],
                    "after": payload.destination.address,
                }
                sets.append(f"destination_coordinates = ST_GeomFromText({add_param(f'POINT({dlng} {dlat})')}, 4326)::geography")
                sets.append(f"destination_address = {add_param(payload.destination.address)}")

            if payload.total_seats is not None:
                if payload.total_seats < ride["booked_seats"]:
                    raise RideServiceError(
                        "seat_count_invalid",
                        f"Cannot reduce seats below booked count ({ride['booked_seats']}).",
                    )
                if payload.total_seats != ride["total_seats"]:
                    changed_fields["total_seats"] = {"before": ride["total_seats"], "after": payload.total_seats}
                    sets.append(f"total_seats = {add_param(payload.total_seats)}")
                    if ride.get("price_source") == "system" and ride["route_distance_km"] is not None:
                        new_fare = calculate_fare(float(ride["route_distance_km"]), payload.total_seats)
                        new_price = Decimal(str(new_fare.per_seat_price_egp))
                        if new_price != ride["price_per_seat"]:
                            changed_fields["price_per_seat"] = {
                                "before": str(ride["price_per_seat"]),
                                "after": str(new_price),
                            }
                        sets.append(f"price_per_seat = {add_param(new_price)}")
                        sets.append(f"fuel_cost_egp = {add_param(new_fare.fuel_cost_egp)}")
                        sets.append(f"platform_commission_egp = {add_param(new_fare.platform_commission_egp)}")
                        sets.append(f"safety_margin_egp = {add_param(new_fare.safety_margin_egp)}")

            if payload.notes is not None and payload.notes != ride["notes"]:
                changed_fields["notes"] = {"before": ride["notes"], "after": payload.notes}
                sets.append(f"notes = {add_param(payload.notes)}")

            if sets:
                sets.append(f"updated_at = now()")
                id_param = add_param(ride_id)
                row = await conn.fetchrow(
                    f"UPDATE rides SET {', '.join(sets)} WHERE id = {id_param} RETURNING {_RIDE_COLS}",
                    *params,
                )
                if changed_fields:
                    await conn.execute(
                        """
                        INSERT INTO ride_history_logs (ride_id, actor_id, action, changed_fields)
                        VALUES ($1, $2, 'edited', $3)
                        """,
                        ride_id, driver_id, changed_fields,
                    )
            else:
                row = await conn.fetchrow(
                    f"SELECT {_RIDE_COLS} FROM rides WHERE id = $1",
                    ride_id,
                )

    return _to_response(dict(row))


# ─────────────────────────────────────────────────────────────────────────────
# Cancel ride
# ─────────────────────────────────────────────────────────────────────────────

async def cancel_ride(
    ride_id: uuid.UUID,
    driver_id: uuid.UUID,
    reason: str,
    cancellation_source: str = "driver",
    actor_id: Optional[uuid.UUID] = None,
) -> RideResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            ride = await _fetch_own_ride(conn, ride_id, driver_id)

            if ride["status"] != "scheduled":
                raise RideServiceError("ride_not_editable", "Only scheduled rides can be cancelled.", 409)

            if cancellation_source == "driver":
                dep = ride["departure_datetime"]
                if dep.tzinfo is None:
                    dep = dep.replace(tzinfo=timezone.utc)
                if (dep - _now()) < timedelta(hours=4):
                    raise RideServiceError(
                        "cancellation_window_closed",
                        "Rides cannot be cancelled within 4 hours of departure.",
                        409,
                    )

            row = await conn.fetchrow(
                f"""
                UPDATE rides
                SET status = 'cancelled', cancellation_reason = $2,
                    cancellation_source = $3, updated_at = now()
                WHERE id = $1
                RETURNING {_RIDE_COLS}
                """,
                ride_id, reason.strip(), cancellation_source,
            )

            log_actor = actor_id if actor_id is not None else driver_id
            await conn.execute(
                "INSERT INTO ride_history_logs (ride_id, actor_id, action, reason) VALUES ($1, $2, 'cancelled', $3)",
                ride_id, log_actor, reason.strip(),
            )

            # Capture confirmed passengers before cascade changes their status
            confirmed_passengers = await conn.fetch(
                "SELECT id, passenger_id FROM bookings WHERE ride_id = $1 AND status = 'confirmed'",
                ride_id,
            )

            from app.services.booking_service import cancel_all_bookings_for_ride
            await cancel_all_bookings_for_ride(conn, ride_id)

            from app.services.commission_service import release_reservation
            await release_reservation(conn, ride_id, driver_id)

            dep = row["departure_datetime"]
            for b in confirmed_passengers:
                await conn.execute(
                    "INSERT INTO notification_events (recipient_user_id, event_type, payload) VALUES ($1, 'ride_cancelled', $2)",
                    b["passenger_id"],
                    {
                        "ride_id": str(ride_id),
                        "departure_datetime": dep.isoformat() if dep else "",
                        "deep_link": f"/(passenger)/bookings/{b['id']}",
                    },
                )

    return _to_response(dict(row))


# ─────────────────────────────────────────────────────────────────────────────
# Start ride
# ─────────────────────────────────────────────────────────────────────────────

async def start_ride(ride_id: uuid.UUID, driver_id: uuid.UUID) -> RideResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            ride = await _fetch_own_ride(conn, ride_id, driver_id)

            if ride["status"] != "scheduled":
                raise RideServiceError("ride_not_editable", "Only scheduled rides can be started.", 409)

            dep = ride["departure_datetime"]
            if dep.tzinfo is None:
                dep = dep.replace(tzinfo=timezone.utc)
            if _now() < dep:
                raise RideServiceError(
                    "start_too_early",
                    "You can only start this ride at or after its scheduled departure time.",
                    409,
                )

            row = await conn.fetchrow(
                f"UPDATE rides SET status = 'in_progress', started_at = now(), updated_at = now() WHERE id = $1 RETURNING {_RIDE_COLS}",
                ride_id,
            )
            await conn.execute(
                "INSERT INTO ride_history_logs (ride_id, actor_id, action) VALUES ($1, $2, 'started')",
                ride_id, driver_id,
            )

            confirmed_bookings = await conn.fetch(
                "SELECT id, passenger_id FROM bookings WHERE ride_id = $1 AND status = 'confirmed'",
                ride_id,
            )
            for b in confirmed_bookings:
                await conn.execute(
                    "INSERT INTO notification_events (recipient_user_id, event_type, payload) VALUES ($1, 'ride_started', $2)",
                    b["passenger_id"],
                    {
                        "ride_id": str(ride_id),
                        "booking_id": str(b["id"]),
                        "deep_link": f"/(passenger)/rides/{ride_id}/tracking",
                    },
                )

    return _to_response(dict(row))


# ─────────────────────────────────────────────────────────────────────────────
# Complete ride
# ─────────────────────────────────────────────────────────────────────────────

async def complete_ride(ride_id: uuid.UUID, driver_id: uuid.UUID) -> RideResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            ride = await _fetch_own_ride(conn, ride_id, driver_id)

            if ride["status"] != "in_progress":
                raise RideServiceError("ride_not_editable", "Only in-progress rides can be completed.", 409)

            row = await conn.fetchrow(
                f"UPDATE rides SET status = 'completed', completed_at = now(), updated_at = now() WHERE id = $1 RETURNING {_RIDE_COLS}",
                ride_id,
            )
            await conn.execute(
                "INSERT INTO ride_history_logs (ride_id, actor_id, action) VALUES ($1, $2, 'completed')",
                ride_id, driver_id,
            )

            # Capture confirmed bookings before cascade transitions them to completed
            confirmed_bookings = await conn.fetch(
                "SELECT id, passenger_id FROM bookings WHERE ride_id = $1 AND status = 'confirmed'",
                ride_id,
            )

            from app.services.booking_service import complete_ride_bookings
            await complete_ride_bookings(conn, ride_id)

            from app.services.commission_service import deduct_commission, release_reservation
            await deduct_commission(conn, dict(ride), [dict(b) for b in confirmed_bookings])
            await release_reservation(conn, ride_id, driver_id)

            for b in confirmed_bookings:
                await conn.execute(
                    "INSERT INTO notification_events (recipient_user_id, event_type, payload) VALUES ($1, 'ride_completed', $2)",
                    b["passenger_id"],
                    {
                        "ride_id": str(ride_id),
                        "booking_id": str(b["id"]),
                        "deep_link": f"/(passenger)/bookings/{b['id']}",
                    },
                )

    return _to_response(dict(row))
