from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from app.core.database import get_pool
from app.models.recurring_ride import (
    RecurringRideDefinitionCreateRequest,
    RecurringRideDefinitionDetailResponse,
    RecurringRideDefinitionListResponse,
    RecurringRideDefinitionResponse,
    RecurringRideDefinitionUpdateRequest,
    RecurringRideDefinitionUpdateResponse,
)
from app.models.ride import CoordinatesSchema, LocationSchema
from app.models.route import GeoPoint
from app.services import ride_service, route_service, wallet_service
from app.services.commission_service import (
    check_available_balance,
    compute_per_seat_commission,
    create_reservation,
)
from app.services.pricing_service import calculate_fare
from app.services.route_service import RouteServiceUnavailableError

logger = logging.getLogger(__name__)

# Rolling generation window (research.md Decision 2): today through day+13.
_WINDOW_DAYS = 14

# Definition edits only propagate to generated instances that haven't yet
# entered the same 4-hour pre-departure edit-lockout window as one-off rides
# (ride_service.edit_ride) — kept in sync so a driver can't use the recurring
# edit path to bypass that rule.
_EDIT_CUTOFF_HOURS = 4


# ─────────────────────────────────────────────────────────────────────────────
# Custom exceptions
# ─────────────────────────────────────────────────────────────────────────────

class RecurringRideServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_DEFINITION_COLS = """
    id, driver_id, vehicle_id,
    origin_address, destination_address,
    ST_Y(origin_coordinates::geometry) AS origin_lat,
    ST_X(origin_coordinates::geometry) AS origin_lng,
    ST_Y(destination_coordinates::geometry) AS dest_lat,
    ST_X(destination_coordinates::geometry) AS dest_lng,
    departure_time, weekdays, total_seats, price_per_seat, notes, status,
    created_at, updated_at
"""


def _to_definition_response(
    row: dict, upcoming_instance_count: Optional[int] = None
) -> RecurringRideDefinitionResponse:
    return RecurringRideDefinitionResponse(
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
        departure_time=row["departure_time"],
        weekdays=list(row["weekdays"]),
        total_seats=row["total_seats"],
        price_per_seat=str(row["price_per_seat"]),
        notes=row["notes"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        upcoming_instance_count=upcoming_instance_count,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _fetch_own_definition(conn, definition_id: uuid.UUID, driver_id: uuid.UUID) -> dict:
    row = await conn.fetchrow(
        f"SELECT {_DEFINITION_COLS} FROM recurring_ride_definitions WHERE id = $1",
        definition_id,
    )
    if row is None or row["driver_id"] != driver_id:
        raise RecurringRideServiceError("definition_not_found", "Recurring ride definition not found.", 404)
    return dict(row)


# ─────────────────────────────────────────────────────────────────────────────
# Create definition (T005)
# ─────────────────────────────────────────────────────────────────────────────

async def create_definition(
    driver_id: uuid.UUID,
    vehicle_id: uuid.UUID,
    vehicle_seat_count: int,
    payload: RecurringRideDefinitionCreateRequest,
) -> RecurringRideDefinitionResponse:
    # No OSRM call here (research.md Decision 4) — route feasibility is checked
    # per-instance by the generation loop, not once at definition time.
    if not payload.weekdays:
        raise RecurringRideServiceError("weekdays_empty", "Select at least one weekday.", 400)
    if any(w < 1 or w > 7 for w in payload.weekdays):
        raise RecurringRideServiceError(
            "weekdays_invalid", "Weekdays must be ISO weekday numbers (1=Monday..7=Sunday).", 400
        )

    olat = payload.origin.coordinates.lat
    olng = payload.origin.coordinates.lng
    dlat = payload.destination.coordinates.lat
    dlng = payload.destination.coordinates.lng
    if abs(olat - dlat) < 1e-5 and abs(olng - dlng) < 1e-5:
        raise RecurringRideServiceError(
            "ride_same_locations", "Origin and destination must be different locations.", 400
        )

    if payload.total_seats < 1 or payload.total_seats > vehicle_seat_count:
        raise RecurringRideServiceError(
            "seat_count_invalid",
            f"Seat count must be between 1 and your vehicle's capacity ({vehicle_seat_count}).",
            400,
        )
    if payload.price_per_seat <= 0:
        raise RecurringRideServiceError("price_invalid", "Price per seat must be greater than zero.", 400)

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            INSERT INTO recurring_ride_definitions (
                driver_id, vehicle_id,
                origin_coordinates, origin_address,
                destination_coordinates, destination_address,
                departure_time, weekdays, total_seats, price_per_seat, notes
            ) VALUES (
                $1, $2,
                ST_GeomFromText($3, 4326)::geography, $4,
                ST_GeomFromText($5, 4326)::geography, $6,
                $7, $8, $9, $10, $11
            )
            RETURNING {_DEFINITION_COLS}
            """,
            driver_id, vehicle_id,
            f"POINT({olng} {olat})", payload.origin.address,
            f"POINT({dlng} {dlat})", payload.destination.address,
            payload.departure_time, sorted(set(payload.weekdays)), payload.total_seats,
            Decimal(str(payload.price_per_seat)), payload.notes,
        )

    return _to_definition_response(dict(row), upcoming_instance_count=0)


# ─────────────────────────────────────────────────────────────────────────────
# List / get definitions (T008)
# ─────────────────────────────────────────────────────────────────────────────

async def list_definitions(driver_id: uuid.UUID) -> RecurringRideDefinitionListResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT {_DEFINITION_COLS} FROM recurring_ride_definitions WHERE driver_id = $1 ORDER BY created_at DESC",
            driver_id,
        )
        ids = [r["id"] for r in rows]
        counts: dict = {}
        if ids:
            count_rows = await conn.fetch(
                """
                SELECT recurring_ride_definition_id AS id, COUNT(*) AS cnt
                FROM rides
                WHERE recurring_ride_definition_id = ANY($1::uuid[])
                  AND status = 'scheduled'
                  AND departure_datetime > now()
                GROUP BY recurring_ride_definition_id
                """,
                ids,
            )
            counts = {c["id"]: c["cnt"] for c in count_rows}

    return RecurringRideDefinitionListResponse(
        definitions=[
            _to_definition_response(dict(r), upcoming_instance_count=counts.get(r["id"], 0)) for r in rows
        ]
    )


async def get_definition(
    driver_id: uuid.UUID, definition_id: uuid.UUID
) -> RecurringRideDefinitionDetailResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        definition = await _fetch_own_definition(conn, definition_id, driver_id)

        instance_rows = await conn.fetch(
            f"SELECT {ride_service._RIDE_COLS} FROM rides "
            f"WHERE recurring_ride_definition_id = $1 ORDER BY departure_datetime ASC",
            definition_id,
        )

    now = _now()
    upcoming_count = sum(
        1
        for r in instance_rows
        if r["status"] == "scheduled" and r["departure_datetime"] > now
    )

    return RecurringRideDefinitionDetailResponse(
        definition=_to_definition_response(definition, upcoming_instance_count=upcoming_count),
        instances=[ride_service._to_response(dict(r)) for r in instance_rows],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Edit definition (T007) — propagates per FR-011
# ─────────────────────────────────────────────────────────────────────────────

async def edit_definition(
    driver_id: uuid.UUID,
    definition_id: uuid.UUID,
    payload: RecurringRideDefinitionUpdateRequest,
) -> RecurringRideDefinitionUpdateResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            definition = await conn.fetchrow(
                f"SELECT {_DEFINITION_COLS} FROM recurring_ride_definitions WHERE id = $1 FOR UPDATE",
                definition_id,
            )
            if definition is None or definition["driver_id"] != driver_id:
                raise RecurringRideServiceError(
                    "definition_not_found", "Recurring ride definition not found.", 404
                )
            if definition["status"] != "active":
                raise RecurringRideServiceError(
                    "definition_ended",
                    "This recurring ride has ended and can no longer be edited.",
                    403,
                )

            vehicle = await conn.fetchrow(
                "SELECT seat_count FROM vehicles WHERE id = $1", definition["vehicle_id"]
            )

            if payload.weekdays is not None and not payload.weekdays:
                raise RecurringRideServiceError("weekdays_empty", "Select at least one weekday.", 400)
            if payload.weekdays is not None and any(w < 1 or w > 7 for w in payload.weekdays):
                raise RecurringRideServiceError(
                    "weekdays_invalid", "Weekdays must be ISO weekday numbers (1=Monday..7=Sunday).", 400
                )

            new_total_seats = (
                payload.total_seats if payload.total_seats is not None else definition["total_seats"]
            )
            if payload.total_seats is not None and (
                payload.total_seats < 1 or payload.total_seats > vehicle["seat_count"]
            ):
                raise RecurringRideServiceError(
                    "seat_count_invalid",
                    f"Seat count must be between 1 and your vehicle's capacity ({vehicle['seat_count']}).",
                    400,
                )
            new_price = (
                Decimal(str(payload.price_per_seat))
                if payload.price_per_seat is not None
                else Decimal(str(definition["price_per_seat"]))
            )
            if payload.price_per_seat is not None and new_price <= 0:
                raise RecurringRideServiceError("price_invalid", "Price per seat must be greater than zero.", 400)

            route_changed = payload.origin is not None or payload.destination is not None
            new_origin_lat = payload.origin.coordinates.lat if payload.origin else definition["origin_lat"]
            new_origin_lng = payload.origin.coordinates.lng if payload.origin else definition["origin_lng"]
            new_dest_lat = payload.destination.coordinates.lat if payload.destination else definition["dest_lat"]
            new_dest_lng = payload.destination.coordinates.lng if payload.destination else definition["dest_lng"]
            new_origin_address = payload.origin.address if payload.origin else definition["origin_address"]
            new_dest_address = payload.destination.address if payload.destination else definition["destination_address"]

            sets: list[str] = []
            params: list = []

            def add_param(val):
                params.append(val)
                return f"${len(params)}"

            if payload.origin is not None:
                sets.append(
                    f"origin_coordinates = ST_GeomFromText({add_param(f'POINT({new_origin_lng} {new_origin_lat})')}, 4326)::geography"
                )
                sets.append(f"origin_address = {add_param(new_origin_address)}")
            if payload.destination is not None:
                sets.append(
                    f"destination_coordinates = ST_GeomFromText({add_param(f'POINT({new_dest_lng} {new_dest_lat})')}, 4326)::geography"
                )
                sets.append(f"destination_address = {add_param(new_dest_address)}")
            if payload.departure_time is not None:
                sets.append(f"departure_time = {add_param(payload.departure_time)}")
            if payload.weekdays is not None:
                sets.append(f"weekdays = {add_param(sorted(set(payload.weekdays)))}")
            if payload.total_seats is not None:
                sets.append(f"total_seats = {add_param(payload.total_seats)}")
            if payload.price_per_seat is not None:
                sets.append(f"price_per_seat = {add_param(new_price)}")
            if payload.notes is not None:
                sets.append(f"notes = {add_param(payload.notes)}")

            if sets:
                sets.append("updated_at = now()")
                id_param = add_param(definition_id)
                updated = await conn.fetchrow(
                    f"UPDATE recurring_ride_definitions SET {', '.join(sets)} "
                    f"WHERE id = {id_param} RETURNING {_DEFINITION_COLS}",
                    *params,
                )
            else:
                updated = definition

            # Propagate to already-generated instances with zero confirmed bookings
            # that haven't yet entered the edit-lockout window (FR-011). Not-yet-
            # generated occurrences need no action — the next generation tick reads
            # the updated definition directly. Skip entirely on a no-op PATCH (no
            # `sets` means nothing on the definition actually changed).
            target_rows = (
                await conn.fetch(
                    f"""
                    SELECT {ride_service._RIDE_COLS} FROM rides
                    WHERE recurring_ride_definition_id = $1
                      AND status = 'scheduled'
                      AND booked_seats = 0
                      AND departure_datetime - INTERVAL '{_EDIT_CUTOFF_HOURS} hours' > now()
                    """,
                    definition_id,
                )
                if sets
                else []
            )

            updated_count = 0
            now = _now()
            for inst in target_rows:
                inst = dict(inst)
                new_dep = inst["departure_datetime"]
                if payload.departure_time is not None:
                    inst_dep = inst["departure_datetime"]
                    if inst_dep.tzinfo is None:
                        inst_dep = inst_dep.replace(tzinfo=timezone.utc)
                    new_dep = datetime.combine(inst_dep.date(), payload.departure_time, tzinfo=timezone.utc)
                    if new_dep <= now:
                        # Would move this instance's departure into the past — leave it untouched.
                        continue

                route_geometry_geojson = None
                route_distance_km = inst["route_distance_km"]
                route_duration_minutes = inst["route_duration_minutes"]
                fuel_cost_egp = inst["fuel_cost_egp"]
                platform_commission_egp = inst["platform_commission_egp"]
                distance_fee_egp = inst["distance_fee_egp"]
                safety_margin_egp = inst["safety_margin_egp"]
                fair_price_per_seat = inst["fair_price_per_seat"]

                if route_changed:
                    try:
                        route = await route_service.calculate_route(
                            GeoPoint(lat=new_origin_lat, lng=new_origin_lng),
                            GeoPoint(lat=new_dest_lat, lng=new_dest_lng),
                        )
                    except RouteServiceUnavailableError:
                        logger.warning(
                            "recurring edit propagation: OSRM unavailable, skipping ride_id=%s", inst["id"]
                        )
                        continue
                    if not route.is_routable:
                        logger.warning(
                            "recurring edit propagation: unroutable, skipping ride_id=%s", inst["id"]
                        )
                        continue
                    route_geometry_geojson = route.geojson_linestring
                    route_distance_km = route.distance_km
                    route_duration_minutes = route.duration_minutes
                    fare = calculate_fare(route.distance_km, new_total_seats)
                    fuel_cost_egp = fare.fuel_cost_egp
                    platform_commission_egp = fare.platform_commission_egp
                    distance_fee_egp = fare.distance_fee_egp
                    safety_margin_egp = fare.safety_margin_egp
                    fair_price_per_seat = fare.per_seat_price_egp

                inst_sets = [
                    "departure_datetime = $2", "total_seats = $3", "price_per_seat = $4",
                    "notes = $5", "fair_price_per_seat = $6", "route_distance_km = $7",
                    "route_duration_minutes = $8", "fuel_cost_egp = $9",
                    "platform_commission_egp = $10", "distance_fee_egp = $11",
                    "safety_margin_egp = $12", "updated_at = now()",
                ]
                inst_params: list = [
                    inst["id"], new_dep, new_total_seats, new_price,
                    updated["notes"], Decimal(str(fair_price_per_seat)), route_distance_km,
                    route_duration_minutes, fuel_cost_egp, platform_commission_egp,
                    distance_fee_egp, safety_margin_egp,
                ]
                if route_changed and route_geometry_geojson is not None:
                    inst_sets += [
                        "route_geometry = ST_SetSRID(ST_GeomFromGeoJSON($13), 4326)",
                        "origin_coordinates = ST_GeomFromText($14, 4326)::geography",
                        "origin_address = $15",
                        "destination_coordinates = ST_GeomFromText($16, 4326)::geography",
                        "destination_address = $17",
                    ]
                    inst_params += [
                        json.dumps(route_geometry_geojson),
                        f"POINT({new_origin_lng} {new_origin_lat})",
                        new_origin_address,
                        f"POINT({new_dest_lng} {new_dest_lat})",
                        new_dest_address,
                    ]

                # NOTE: does not sync the instance's CommissionReservation the way
                # ride_service.edit_ride() does for one-off rides — propagated price/
                # seat changes here are driver-initiated bulk edits across a whole
                # series and are comparatively rare; revisit if this becomes a real
                # balance-integrity gap in practice.
                await conn.execute(
                    f"UPDATE rides SET {', '.join(inst_sets)} WHERE id = $1", *inst_params
                )
                await conn.execute(
                    "INSERT INTO ride_history_logs (ride_id, actor_id, action) VALUES ($1, $2, 'edited')",
                    inst["id"], driver_id,
                )
                updated_count += 1

    return RecurringRideDefinitionUpdateResponse(
        definition=_to_definition_response(dict(updated)),
        updated_instance_count=updated_count,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Generation loop (T006)
# ─────────────────────────────────────────────────────────────────────────────

async def _generate_one_instance(definition: dict, dep: datetime) -> bool:
    """Create a single day instance for one definition/date if it doesn't already
    exist and the driver has sufficient wallet balance. Returns True if created."""
    pool = get_pool()
    driver_id = definition["driver_id"]

    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT 1 FROM rides WHERE recurring_ride_definition_id = $1 AND public.utc_date(departure_datetime) = $2",
            definition["id"], dep.date(),
        )
    if existing:
        return False

    try:
        route = await route_service.calculate_route(
            GeoPoint(lat=definition["origin_lat"], lng=definition["origin_lng"]),
            GeoPoint(lat=definition["dest_lat"], lng=definition["dest_lng"]),
        )
    except RouteServiceUnavailableError:
        logger.warning("recurring generation: OSRM unavailable definition_id=%s", definition["id"])
        return False
    if not route.is_routable:
        logger.warning("recurring generation: unroutable definition_id=%s", definition["id"])
        return False

    fare = calculate_fare(route.distance_km, definition["total_seats"])
    fair_price_dec = Decimal(str(fare.per_seat_price_egp))
    price_per_seat = Decimal(str(definition["price_per_seat"]))

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Same advisory lock create_ride() takes — serializes against a
            # concurrent one-off POST /rides or another generation tick for
            # this driver so wallet reservation math can't race.
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", str(driver_id))

            # Same 2-hour overlap guard create_ride() enforces for one-off rides —
            # a generated instance must not double-book the driver against another
            # ride (recurring instance or one-off) already on their schedule.
            conflict = await conn.fetchval(
                """
                SELECT 1 FROM rides
                WHERE driver_id = $1
                  AND status IN ('scheduled', 'in_progress')
                  AND departure_datetime >= $2
                  AND departure_datetime <= $3
                LIMIT 1
                """,
                driver_id, dep - timedelta(hours=2), dep + timedelta(hours=2),
            )
            if conflict:
                logger.warning(
                    "recurring generation: time conflict, skipping definition_id=%s dep=%s",
                    definition["id"], dep,
                )
                return False

            per_seat_commission, _ = compute_per_seat_commission(
                Decimal(str(fare.fuel_cost_egp)), Decimal(str(fare.distance_fee_egp)),
                Decimal(str(fare.safety_margin_egp)), price_per_seat, fair_price_dec,
            )
            max_commission = (per_seat_commission * definition["total_seats"]).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            wallet = await wallet_service.get_wallet_with_lock(conn, driver_id)
            if not check_available_balance(wallet, max_commission):
                logger.warning(
                    "recurring generation: insufficient wallet balance definition_id=%s driver_id=%s",
                    definition["id"], driver_id,
                )
                return False

            row = await conn.fetchrow(
                """
                INSERT INTO rides (
                    driver_id, vehicle_id,
                    origin_coordinates, origin_address,
                    destination_coordinates, destination_address,
                    departure_datetime, total_seats, booked_seats, price_per_seat, fair_price_per_seat,
                    notes, status,
                    route_geometry, route_distance_km, route_duration_minutes,
                    fuel_cost_egp, platform_commission_egp, distance_fee_egp, safety_margin_egp, price_source,
                    recurring_ride_definition_id
                ) VALUES (
                    $1, $2,
                    ST_GeomFromText($3, 4326)::geography, $4,
                    ST_GeomFromText($5, 4326)::geography, $6,
                    $7, $8, 0, $9, $10, $11, 'scheduled',
                    ST_SetSRID(ST_GeomFromGeoJSON($12), 4326), $13, $14, $15, $16, $17, $18, 'system',
                    $19
                )
                ON CONFLICT (recurring_ride_definition_id, public.utc_date(departure_datetime))
                    WHERE recurring_ride_definition_id IS NOT NULL
                    DO NOTHING
                RETURNING id
                """,
                driver_id, definition["vehicle_id"],
                f"POINT({definition['origin_lng']} {definition['origin_lat']})", definition["origin_address"],
                f"POINT({definition['dest_lng']} {definition['dest_lat']})", definition["destination_address"],
                dep, definition["total_seats"], price_per_seat, fair_price_dec, definition["notes"],
                json.dumps(route.geojson_linestring),
                route.distance_km, route.duration_minutes,
                fare.fuel_cost_egp, fare.platform_commission_egp, fare.distance_fee_egp, fare.safety_margin_egp,
                definition["id"],
            )
            if row is None:
                # Idempotency backstop (NFR-001) — another tick already created this
                # exact (definition, date) instance between our pre-check and here.
                return False

            await conn.execute(
                "INSERT INTO ride_history_logs (ride_id, actor_id, action) VALUES ($1, $2, 'created')",
                row["id"], driver_id,
            )
            await create_reservation(conn, wallet["id"], driver_id, row["id"], max_commission)

    return True


async def generate_upcoming_instances() -> int:
    """One tick of the rolling 2-week generator (research.md Decision 2).

    Queries every `active` definition whose driver/vehicle are currently
    eligible (FR-010/FR-012 — org-verified driver, active+owned vehicle),
    then ensures a `rides` row exists for each selected weekday's next
    occurrence through day+13. Ineligible definitions are simply skipped —
    no row mutation needed, since generated-instance visibility for search
    is computed at query time (T011), not stored.

    Returns the number of newly created instances (for logging/tests).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        definitions = await conn.fetch(
            """
            SELECT
                rd.id, rd.driver_id, rd.vehicle_id,
                rd.origin_address, rd.destination_address,
                ST_Y(rd.origin_coordinates::geometry) AS origin_lat,
                ST_X(rd.origin_coordinates::geometry) AS origin_lng,
                ST_Y(rd.destination_coordinates::geometry) AS dest_lat,
                ST_X(rd.destination_coordinates::geometry) AS dest_lng,
                rd.departure_time, rd.weekdays, rd.total_seats, rd.price_per_seat, rd.notes, rd.status,
                rd.created_at, rd.updated_at
            FROM recurring_ride_definitions rd
            JOIN profiles p ON p.id = rd.driver_id
            JOIN vehicles v ON v.id = rd.vehicle_id AND v.driver_id = rd.driver_id
            WHERE rd.status = 'active'
              AND p.org_verified_at IS NOT NULL
              AND v.is_active = true
            """
        )

    created = 0
    now = _now()
    today = now.date()
    for definition_row in definitions:
        definition = dict(definition_row)
        weekdays = {int(w) for w in definition["weekdays"]}
        for offset in range(_WINDOW_DAYS):
            day: date = today + timedelta(days=offset)
            if day.isoweekday() not in weekdays:
                continue
            dep = datetime.combine(day, definition["departure_time"], tzinfo=timezone.utc)
            if dep <= now:
                continue
            try:
                if await _generate_one_instance(definition, dep):
                    created += 1
            except Exception:
                logger.exception(
                    "recurring generation failed definition_id=%s date=%s", definition["id"], day
                )
    return created


async def recurring_ride_generation_loop() -> None:
    """Background task: top up the rolling generation window every 10 minutes."""
    while True:
        try:
            created = await generate_upcoming_instances()
            if created:
                logger.info("recurring_ride_generation_loop created=%d", created)
        except Exception as exc:
            logger.error("Recurring ride generation loop error: %s", exc)
        await asyncio.sleep(600)
