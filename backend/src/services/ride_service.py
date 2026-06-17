from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from geoalchemy2.elements import WKTElement
from sqlalchemy import select, update, text, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.ride import (
    Ride,
    RideHistoryLog,
    RideStatus,
    RideAction,
    CreateRideRequest,
    EditRideRequest,
    ride_to_response,
    RideResponse,
    RideDetailResponse,
    RideListResponse,
    HistoryEntryResponse,
)

# ─────────────────────────────────────────────────────────────────────────────
# Status transition table (T018)
# ─────────────────────────────────────────────────────────────────────────────

VALID_TRANSITIONS: dict[tuple[RideStatus, str], RideStatus] = {
    (RideStatus.scheduled, "start"): RideStatus.in_progress,
    (RideStatus.scheduled, "cancel"): RideStatus.cancelled,
    (RideStatus.scheduled, "edit"): RideStatus.scheduled,
    (RideStatus.in_progress, "complete"): RideStatus.completed,
}


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

def _make_point(lat: float, lng: float) -> WKTElement:
    return WKTElement(f"POINT({lng} {lat})", srid=4326)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def _fetch_own_ride(db: AsyncSession, ride_id: uuid.UUID, driver_id: uuid.UUID) -> Ride:
    result = await db.execute(select(Ride).where(Ride.id == ride_id))
    ride = result.scalar_one_or_none()
    if ride is None or ride.driver_id != driver_id:
        raise RideServiceError("ride_not_found", "Ride not found.", 404)
    return ride


async def _log_action(
    db: AsyncSession,
    ride_id: uuid.UUID,
    actor_id: Optional[uuid.UUID],
    action: RideAction,
    changed_fields: Optional[dict] = None,
    reason: Optional[str] = None,
) -> None:
    log = RideHistoryLog(
        ride_id=ride_id,
        actor_id=actor_id,
        action=action,
        changed_fields=changed_fields,
        reason=reason,
    )
    db.add(log)


# ─────────────────────────────────────────────────────────────────────────────
# Create ride (T026)
# ─────────────────────────────────────────────────────────────────────────────

async def create_ride(
    db: AsyncSession,
    driver_id: uuid.UUID,
    vehicle_id: uuid.UUID,
    vehicle_seat_count: int,
    payload: CreateRideRequest,
) -> RideResponse:
    origin_lat = payload.origin.coordinates.lat
    origin_lng = payload.origin.coordinates.lng
    dest_lat = payload.destination.coordinates.lat
    dest_lng = payload.destination.coordinates.lng

    if abs(origin_lat - dest_lat) < 1e-5 and abs(origin_lng - dest_lng) < 1e-5:
        raise RideServiceError("ride_same_locations", "Origin and destination must be different locations.")

    now = _now_utc()
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

    # Advisory lock prevents concurrent rides from the same driver passing the overlap check simultaneously
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:driver_id))"), {"driver_id": str(driver_id)})

    window_start = dep - timedelta(hours=2)
    window_end = dep + timedelta(hours=2)

    conflict = await db.execute(
        select(Ride).where(
            Ride.driver_id == driver_id,
            Ride.status.in_([RideStatus.scheduled, RideStatus.in_progress]),
            Ride.departure_datetime >= window_start,
            Ride.departure_datetime <= window_end,
        )
    )
    if conflict.scalar_one_or_none():
        raise RideServiceError("ride_time_conflict", "You already have a ride within 2 hours of this departure time.", 409)

    ride = Ride(
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        origin_coordinates=_make_point(origin_lat, origin_lng),
        origin_address=payload.origin.address,
        destination_coordinates=_make_point(dest_lat, dest_lng),
        destination_address=payload.destination.address,
        departure_datetime=dep,
        total_seats=payload.total_seats,
        booked_seats=0,
        price_per_seat=Decimal(payload.price_per_seat),
        notes=payload.notes,
        status=RideStatus.scheduled,
    )
    db.add(ride)
    await db.flush()

    await _log_action(db, ride.id, driver_id, RideAction.created)
    await db.commit()
    await db.refresh(ride)

    return ride_to_response(ride)


# ─────────────────────────────────────────────────────────────────────────────
# List rides (T043)
# ─────────────────────────────────────────────────────────────────────────────

async def list_rides(
    db: AsyncSession,
    driver_id: uuid.UUID,
    status: Optional[str],
    page: int,
    page_size: int,
) -> RideListResponse:
    page_size = min(page_size, 50)
    offset = (page - 1) * page_size

    q = select(Ride).where(Ride.driver_id == driver_id)
    count_q = select(func.count()).select_from(Ride).where(Ride.driver_id == driver_id)

    if status:
        try:
            status_enum = RideStatus(status)
            q = q.where(Ride.status == status_enum)
            count_q = count_q.where(Ride.status == status_enum)
        except ValueError:
            pass

    q = q.order_by(Ride.created_at.desc()).offset(offset).limit(page_size)

    rows = await db.execute(q)
    rides = rows.scalars().all()

    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    return RideListResponse(
        rides=[ride_to_response(r) for r in rides],
        total=total,
        page=page,
        page_size=page_size,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Get ride detail (T044)
# ─────────────────────────────────────────────────────────────────────────────

async def get_ride(db: AsyncSession, ride_id: uuid.UUID, driver_id: uuid.UUID) -> RideDetailResponse:
    ride = await _fetch_own_ride(db, ride_id, driver_id)

    history_result = await db.execute(
        select(RideHistoryLog)
        .where(RideHistoryLog.ride_id == ride_id)
        .order_by(RideHistoryLog.created_at.asc())
    )
    history = history_result.scalars().all()

    return RideDetailResponse(
        ride=ride_to_response(ride),
        history=[
            HistoryEntryResponse(
                id=h.id,
                actor_id=h.actor_id,
                action=h.action.value if hasattr(h.action, "value") else h.action,
                changed_fields=h.changed_fields,
                reason=h.reason,
                created_at=h.created_at,
            )
            for h in history
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Edit ride (T028, T039)
# ─────────────────────────────────────────────────────────────────────────────

async def edit_ride(
    db: AsyncSession,
    ride_id: uuid.UUID,
    driver_id: uuid.UUID,
    payload: EditRideRequest,
) -> RideResponse:
    ride = await _fetch_own_ride(db, ride_id, driver_id)

    if ride.status != RideStatus.scheduled:
        raise RideServiceError("ride_not_editable", "Only scheduled rides can be edited.", 409)

    changed_fields: dict = {}
    now = _now_utc()

    if payload.departure_datetime is not None:
        dep = payload.departure_datetime
        if dep.tzinfo is None:
            dep = dep.replace(tzinfo=timezone.utc)
        if dep <= now:
            raise RideServiceError("ride_departure_past", "Departure time must be in the future.")
        if dep > now + timedelta(hours=48):
            raise RideServiceError("ride_departure_too_far", "Rides can only be scheduled up to 48 hours in advance.")
        if dep != ride.departure_datetime:
            changed_fields["departure_datetime"] = {
                "before": ride.departure_datetime.isoformat(),
                "after": dep.isoformat(),
            }
            ride.departure_datetime = dep

    if payload.destination is not None:
        dest_lat = payload.destination.coordinates.lat
        dest_lng = payload.destination.coordinates.lng
        changed_fields["destination_address"] = {
            "before": ride.destination_address,
            "after": payload.destination.address,
        }
        ride.destination_coordinates = _make_point(dest_lat, dest_lng)
        ride.destination_address = payload.destination.address

    if payload.total_seats is not None:
        if payload.total_seats < ride.booked_seats:
            raise RideServiceError(
                "seat_count_invalid",
                f"Cannot reduce seats below booked count ({ride.booked_seats}).",
            )
        if payload.total_seats != ride.total_seats:
            changed_fields["total_seats"] = {"before": ride.total_seats, "after": payload.total_seats}
            ride.total_seats = payload.total_seats

    if payload.price_per_seat is not None:
        new_price = Decimal(payload.price_per_seat)
        if new_price != ride.price_per_seat:
            changed_fields["price_per_seat"] = {
                "before": str(ride.price_per_seat),
                "after": str(new_price),
            }
            ride.price_per_seat = new_price

    if payload.notes is not None and payload.notes != ride.notes:
        changed_fields["notes"] = {"before": ride.notes, "after": payload.notes}
        ride.notes = payload.notes

    if changed_fields:
        await _log_action(db, ride.id, driver_id, RideAction.edited, changed_fields=changed_fields)

    await db.commit()
    await db.refresh(ride)

    return ride_to_response(ride)


# ─────────────────────────────────────────────────────────────────────────────
# Cancel ride (T032)
# ─────────────────────────────────────────────────────────────────────────────

async def cancel_ride(
    db: AsyncSession,
    ride_id: uuid.UUID,
    driver_id: uuid.UUID,
    reason: str,
    cancellation_source: str = "driver",
    actor_id: Optional[uuid.UUID] = None,
) -> RideResponse:
    ride = await _fetch_own_ride(db, ride_id, driver_id)

    if ride.status != RideStatus.scheduled:
        raise RideServiceError("ride_not_editable", "Only scheduled rides can be cancelled.", 409)

    if not reason or not reason.strip():
        raise RideServiceError("reason_required", "A cancellation reason is required.")

    ride.status = RideStatus.cancelled
    ride.cancellation_reason = reason.strip()
    ride.cancellation_source = cancellation_source

    log_actor = actor_id if actor_id is not None else driver_id
    await _log_action(db, ride.id, log_actor, RideAction.cancelled, reason=reason.strip())

    from ..services.notification_service import enqueue_cancellation_emails
    await enqueue_cancellation_emails(db, ride_id)

    await db.commit()
    await db.refresh(ride)

    return ride_to_response(ride)


# ─────────────────────────────────────────────────────────────────────────────
# Start ride (T059)
# ─────────────────────────────────────────────────────────────────────────────

async def start_ride(db: AsyncSession, ride_id: uuid.UUID, driver_id: uuid.UUID) -> RideResponse:
    ride = await _fetch_own_ride(db, ride_id, driver_id)

    if ride.status != RideStatus.scheduled:
        raise RideServiceError("ride_not_editable", "Only scheduled rides can be started.", 409)

    dep = ride.departure_datetime
    if dep.tzinfo is None:
        dep = dep.replace(tzinfo=timezone.utc)

    if _now_utc() < dep:
        raise RideServiceError("start_too_early", "You can only start this ride at or after its scheduled departure time.", 409)

    ride.status = RideStatus.in_progress
    await _log_action(db, ride.id, driver_id, RideAction.started)

    await db.commit()
    await db.refresh(ride)

    return ride_to_response(ride)


# ─────────────────────────────────────────────────────────────────────────────
# Complete ride (T060)
# ─────────────────────────────────────────────────────────────────────────────

async def complete_ride(db: AsyncSession, ride_id: uuid.UUID, driver_id: uuid.UUID) -> RideResponse:
    ride = await _fetch_own_ride(db, ride_id, driver_id)

    if ride.status != RideStatus.in_progress:
        raise RideServiceError("ride_not_editable", "Only in-progress rides can be completed.", 409)

    ride.status = RideStatus.completed
    await _log_action(db, ride.id, driver_id, RideAction.completed)

    await db.commit()
    await db.refresh(ride)

    return ride_to_response(ride)
