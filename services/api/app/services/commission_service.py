from __future__ import annotations

import logging
import time
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import HTTPException

from app.services import wallet_service

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

    For each confirmed booking:
        commission = ROUND((fuel_cost_egp * 0.20 + safety_margin_egp) / total_seats, 2)

    The platform keeps both the 20% fuel-cost commission and the flat safety margin —
    the safety margin is platform revenue, not a driver buffer.

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
    safety_margin = (
        Decimal(str(ride["safety_margin_egp"]))
        if ride.get("safety_margin_egp") is not None
        else Decimal("0")
    )
    total_seats = int(ride["total_seats"])

    wallet = await wallet_service.get_wallet_with_lock(conn, driver_id)
    wallet_id = wallet["id"]

    if not confirmed_bookings or total_seats == 0 or (fuel_cost == Decimal("0") and safety_margin == Decimal("0")):
        logger.info(
            "wallet_write operation=COMMISSION_DEBIT driver_id=%s ride_id=%s "
            "bookings=0 amount_egp=0.00 (no confirmed bookings — nothing charged)",
            driver_id,
            ride_id,
        )
        return

    commission_per_booking = ((fuel_cost * COMMISSION_RATE + safety_margin) / total_seats).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    for booking in confirmed_bookings:
        await wallet_service.insert_ledger_entry(
            conn,
            wallet_id=wallet_id,
            driver_id=driver_id,
            entry_type="COMMISSION_DEBIT",
            amount=commission_per_booking,
            ride_id=ride_id,
            booking_id=booking["id"],
            fuel_cost_egp_snapshot=fuel_cost,
        )
        await wallet_service.decrement_balance(conn, wallet_id, commission_per_booking)

    total_deducted = commission_per_booking * len(confirmed_bookings)
    logger.info(
        "wallet_write operation=COMMISSION_DEBIT driver_id=%s ride_id=%s "
        "bookings=%d per_booking_egp=%s total_deducted_egp=%s",
        driver_id,
        ride_id,
        len(confirmed_bookings),
        commission_per_booking,
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
