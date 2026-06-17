from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from app.core.database import get_pool
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
    notes, created_at, updated_at
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
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


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

            row = await conn.fetchrow(
                f"""
                INSERT INTO rides (
                    driver_id, vehicle_id,
                    origin_coordinates, origin_address,
                    destination_coordinates, destination_address,
                    departure_datetime, total_seats, booked_seats, price_per_seat, notes, status
                ) VALUES (
                    $1, $2,
                    ST_GeomFromText($3, 4326)::geography, $4,
                    ST_GeomFromText($5, 4326)::geography, $6,
                    $7, $8, 0, $9, $10, 'scheduled'
                )
                RETURNING {_RIDE_COLS}
                """,
                driver_id, vehicle_id,
                f"POINT({olng} {olat})", payload.origin.address,
                f"POINT({dlng} {dlat})", payload.destination.address,
                dep, payload.total_seats, Decimal(payload.price_per_seat), payload.notes,
            )

            await conn.execute(
                "INSERT INTO ride_history_logs (ride_id, actor_id, action) VALUES ($1, $2, 'created')",
                row["id"], driver_id,
            )

    return _to_response(dict(row))


# ─────────────────────────────────────────────────────────────────────────────
# List rides
# ─────────────────────────────────────────────────────────────────────────────

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

            if payload.price_per_seat is not None:
                new_price = Decimal(payload.price_per_seat)
                if new_price != ride["price_per_seat"]:
                    changed_fields["price_per_seat"] = {
                        "before": str(ride["price_per_seat"]),
                        "after": str(new_price),
                    }
                    sets.append(f"price_per_seat = {add_param(new_price)}")

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
                        ride_id, driver_id, json.dumps(changed_fields),
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

    from app.services.notification_service import enqueue_cancellation_emails
    await enqueue_cancellation_emails(ride_id)

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
                f"UPDATE rides SET status = 'in_progress', updated_at = now() WHERE id = $1 RETURNING {_RIDE_COLS}",
                ride_id,
            )
            await conn.execute(
                "INSERT INTO ride_history_logs (ride_id, actor_id, action) VALUES ($1, $2, 'started')",
                ride_id, driver_id,
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
                f"UPDATE rides SET status = 'completed', updated_at = now() WHERE id = $1 RETURNING {_RIDE_COLS}",
                ride_id,
            )
            await conn.execute(
                "INSERT INTO ride_history_logs (ride_id, actor_id, action) VALUES ($1, $2, 'completed')",
                ride_id, driver_id,
            )

    return _to_response(dict(row))
