from __future__ import annotations

import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

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
        commission = ROUND(fuel_cost_egp * 0.20 / total_seats, 2)

    Also deletes the ride's CommissionReservation (even if no confirmed bookings exist —
    empty-seat reservations are silently released).

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
    total_seats = int(ride["total_seats"])

    wallet = await wallet_service.get_wallet_with_lock(conn, driver_id)
    wallet_id = wallet["id"]

    # Always delete the reservation — release unused seat reservation for empty rides too
    reservation = await conn.fetchrow(
        "DELETE FROM commission_reservations WHERE ride_id = $1 RETURNING reserved_amount_egp",
        ride_id,
    )
    if reservation is not None:
        await wallet_service.decrement_reserved(
            conn, wallet_id, Decimal(str(reservation["reserved_amount_egp"]))
        )

    if not confirmed_bookings or total_seats == 0 or fuel_cost == Decimal("0"):
        logger.info(
            "wallet_write operation=COMMISSION_DEBIT driver_id=%s ride_id=%s "
            "bookings=0 amount_egp=0.00 (no confirmed bookings — nothing charged)",
            driver_id,
            ride_id,
        )
        return

    commission_per_booking = (fuel_cost * COMMISSION_RATE / total_seats).quantize(
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
    await wallet_service.decrement_reserved(conn, wallet["id"], released)

    logger.info(
        "wallet_write operation=RESERVATION_RELEASE driver_id=%s ride_id=%s released_egp=%s",
        driver_id,
        ride_id,
        released,
    )
