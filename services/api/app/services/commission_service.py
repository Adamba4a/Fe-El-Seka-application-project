from __future__ import annotations

import logging
import time
import uuid
from decimal import ROUND_HALF_UP, Decimal

from app.services import car_maintenance_service, wallet_service

logger = logging.getLogger(__name__)

# Fixed platform commission rate — same constant as pricing_service.PLATFORM_COMMISSION_RATE.
# NOT separately configurable: Phase 5 FR-025 and Phase 8 FR-018.
COMMISSION_RATE = Decimal("0.20")


# ─────────────────────────────────────────────────────────────────────────────
# Ride completion — deduct proportional commission
# ─────────────────────────────────────────────────────────────────────────────

async def deduct_commission(
    conn,
    ride: dict,
    confirmed_bookings: list[dict],
) -> None:
    """Deduct proportional commission for each confirmed booking that just completed.

    Commission is charged per seat, not per booking row — a single booking can reserve
    more than one seat (see the multi-seat booking feature), and each of those seats
    must be charged its share:
        per_seat = (fuel_cost_egp * 0.20 + distance_fee_egp + safety_margin_egp) / total_seats
        commission for a booking = ROUND(per_seat * booking.seats, 2)

    The platform keeps the 20% fuel-cost commission plus the flat safety margin and the
    per-km distance fee in full — both are platform revenue, not a driver buffer.

    Does NOT release the CommissionReservation — the caller (complete_ride) must call
    release_reservation() separately after this function returns.

    MUST be called inside the complete_ride() transaction, after bookings have been
    transitioned to 'completed' by complete_ride_bookings(). The wallet row is locked
    inside this function via get_wallet_with_lock().
    """
    driver_id = ride["driver_id"]
    ride_id = ride["id"]
    fuel_cost = (
        Decimal(str(ride["fuel_cost_egp"]))
        if ride.get("fuel_cost_egp") is not None
        else Decimal("0")
    )
    distance_fee = (
        Decimal(str(ride["distance_fee_egp"]))
        if ride.get("distance_fee_egp") is not None
        else Decimal("0")
    )
    safety_margin = (
        Decimal(str(ride["safety_margin_egp"]))
        if ride.get("safety_margin_egp") is not None
        else Decimal("0")
    )
    total_seats = int(ride["total_seats"])

    wallet = await wallet_service.get_wallet_with_lock(conn, driver_id)
    wallet_id = wallet["id"]

    if not confirmed_bookings or total_seats == 0 or (
        fuel_cost == Decimal("0") and distance_fee == Decimal("0") and safety_margin == Decimal("0")
    ):
        logger.info(
            "wallet_write operation=COMMISSION_DEBIT driver_id=%s ride_id=%s "
            "bookings=0 amount_egp=0.00 (no confirmed bookings — nothing charged)",
            driver_id,
            ride_id,
        )
        return

    per_seat_commission = (fuel_cost * COMMISSION_RATE + distance_fee + safety_margin) / total_seats
    per_seat_distance_fee = distance_fee / total_seats

    total_deducted = Decimal("0.00")
    total_distance_fee = Decimal("0.00")
    for booking in confirmed_bookings:
        seats = int(booking.get("seats", 1))
        commission_amount = (per_seat_commission * seats).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        distance_fee_amount = (per_seat_distance_fee * seats).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        await wallet_service.insert_ledger_entry(
            conn,
            wallet_id=wallet_id,
            driver_id=driver_id,
            entry_type="COMMISSION_DEBIT",
            amount=commission_amount,
            ride_id=ride_id,
            booking_id=booking["id"],
            fuel_cost_egp_snapshot=fuel_cost,
        )
        await wallet_service.decrement_balance(conn, wallet_id, commission_amount)
        total_deducted += commission_amount
        total_distance_fee += distance_fee_amount

    # The distance-fee share of what was just debited funds the driver's free
    # car-maintenance savings counter (100% platform revenue, credited back as a
    # driver benefit once CAR_MAINTENANCE_THRESHOLD_EGP is reached).
    await car_maintenance_service.accumulate_and_maybe_grant(
        conn, driver_id, wallet_id, total_distance_fee
    )

    logger.info(
        "wallet_write operation=COMMISSION_DEBIT driver_id=%s ride_id=%s "
        "bookings=%d total_deducted_egp=%s",
        driver_id,
        ride_id,
        len(confirmed_bookings),
        total_deducted,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Ride cancellation — release commission reservation
# ─────────────────────────────────────────────────────────────────────────────

async def release_reservation(conn, ride_id: uuid.UUID, driver_id: uuid.UUID) -> None:
    """Release the CommissionReservation for a cancelled ride.

    Deletes the reservation row and decrements wallet.reserved_egp by the same amount.
    No ledger entry is created — the reservation was virtual and nothing was charged.

    Safe to call even if no reservation exists (idempotent no-op).

    MUST be called inside the ride cancellation transaction.
    """
    wallet = await wallet_service.get_wallet_with_lock(conn, driver_id)

    reservation = await conn.fetchrow(
        "DELETE FROM commission_reservations WHERE ride_id = $1 RETURNING reserved_amount_egp",
        ride_id,
    )
    if reservation is None:
        logger.debug(
            "release_reservation: no reservation for ride_id=%s (already released or never created)",
            ride_id,
        )
        return

    released = Decimal(str(reservation["reserved_amount_egp"]))
    _start = time.monotonic()
    await wallet_service.decrement_reserved(conn, wallet["id"], released)
    _ms = round((time.monotonic() - _start) * 1000)
    logger.info(
        "event=wallet_write operation=RESERVATION_RELEASE driver_id=%s amount_egp=%s "
        "ride_id=%s booking_id=null admin_actor_id=null duration_ms=%d error=null",
        driver_id, released, ride_id, _ms,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Ride creation — balance enforcement and reservation
# ─────────────────────────────────────────────────────────────────────────────

def check_available_balance(wallet: dict, max_commission: Decimal) -> bool:
    """Return True if the driver's available balance covers max_commission.

    available_egp = balance_egp − reserved_egp (never stored, always derived)
    """
    balance = Decimal(str(wallet["balance_egp"]))
    reserved = Decimal(str(wallet["reserved_egp"]))
    return (balance - reserved) >= max_commission


async def create_reservation(
    conn,
    wallet_id: uuid.UUID,
    driver_id: uuid.UUID,
    ride_id: uuid.UUID,
    reserved_amount: Decimal,
) -> None:
    """Insert a CommissionReservation row and increment wallet.reserved_egp.

    MUST be called inside the create_ride() transaction, after the ride row is inserted
    (ride_id FK must already exist). The wallet row must already be locked via
    get_wallet_with_lock().
    """
    await conn.execute(
        """
        INSERT INTO commission_reservations (wallet_id, driver_id, ride_id, reserved_amount_egp)
        VALUES ($1, $2, $3, $4)
        """,
        wallet_id,
        driver_id,
        ride_id,
        reserved_amount,
    )
    _start = time.monotonic()
    await wallet_service.increment_reserved(conn, wallet_id, reserved_amount)
    _ms = round((time.monotonic() - _start) * 1000)
    logger.info(
        "event=wallet_write operation=RESERVATION_CREATE driver_id=%s amount_egp=%s "
        "ride_id=%s booking_id=null admin_actor_id=null duration_ms=%d error=null",
        driver_id, reserved_amount, ride_id, _ms,
    )
