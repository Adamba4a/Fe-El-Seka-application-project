from __future__ import annotations

import logging
import time
import uuid
from decimal import ROUND_HALF_UP, Decimal

from app.services import loyalty_service, wallet_service
from app.services.pricing_service import FARE_SPLIT_SEATS

logger = logging.getLogger(__name__)

# Fixed platform commission rate — same constant as pricing_service.PLATFORM_COMMISSION_RATE.
# NOT separately configurable: Phase 5 FR-025 and Phase 8 FR-018.
COMMISSION_RATE = Decimal("0.20")


def compute_per_seat_commission(
    fuel_cost_egp: Decimal,
    distance_fee_egp: Decimal,
    safety_margin_egp: Decimal,
    price_per_seat: Decimal,
    fair_price_per_seat: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """Return (per_seat_commission, per_seat_distance_fee, per_seat_true_commission)
    for one booked seat.

    Split across FARE_SPLIT_SEATS — the SAME fixed divisor pricing_service.calculate_fare()
    uses to quote price_per_seat — rather than the ride's actual total_seats. price_per_seat
    is quoted assuming a 2-way cost split regardless of how many seats the car actually has,
    so commission must be pulled against that same assumption or it silently over/under-charges
    whenever total_seats != FARE_SPLIT_SEATS (e.g. a 1-seat ride was previously charged the
    ride's ENTIRE undivided commission from its single passenger). Every booked seat — including
    seats beyond FARE_SPLIT_SEATS on rides with more capacity — is charged this same per-seat
    rate; extra fill-up seats are pure additional platform/driver revenue, matching the
    "total_collected_egp" fill-up-bonus estimate already shown at quote time.

    This is the single source of truth reused by deduct_commission() below (cash rides, at ride
    completion) and by booking_service.py's sponsored-ride settlement/reversal (which duplicate
    this shape because sponsored rides settle at booking time instead of completion).

    2026-09-02 pricing revision: the 20% commission rate now applies to (fuel_cost + distance_fee)
    instead of fuel_cost alone, and distance_fee itself is still taken from the driver in full —
    unchanged from before, since 100% of it is credited straight back as driver Cash Back points (see
    deduct_commission's call into wallet_service.increment_cash_back_points below). This keeps
    the driver's net commission-debit exactly equal to what pricing_service now quotes the
    passenger (fuel_cost stays the driver's untouched cash share; everything else — distance_fee
    plus the new (fuel+distance)*20% markup — is commission). safety_margin_egp is still added for
    rides created before this revision (their price_per_seat baked in a nonzero safety margin);
    it is always 0.00 for rides created after it, per pricing_service._calc_fee_from_distance.

    2026-09-03 correction: per_seat_commission (above) is what the driver is actually debited —
    it includes distance_fee because that amount is immediately credited straight back to the
    driver as Cash Back, so it must round-trip through the debit for the ledger to balance. But
    it is NOT the platform's real take, so it must not be the basis for passenger points-earned
    (loyalty_service.award_passenger_points/reverse_passenger_points expect true platform
    commission — see that function's docstring). per_seat_true_commission is the platform's
    actual cut: (fuel_cost + distance_fee) * 20%, plus the same markup share as above; it
    deliberately excludes distance_fee_egp and safety_margin_egp, both of which are pass-through
    amounts (Cash Back / legacy quote artifact), not platform revenue.
    """
    markup_commission_per_seat = max(Decimal("0.00"), price_per_seat - fair_price_per_seat) * COMMISSION_RATE
    true_commission_base = (fuel_cost_egp + distance_fee_egp) * COMMISSION_RATE
    per_seat_commission = (
        distance_fee_egp + safety_margin_egp + true_commission_base
    ) / FARE_SPLIT_SEATS + markup_commission_per_seat
    per_seat_distance_fee = distance_fee_egp / FARE_SPLIT_SEATS
    per_seat_true_commission = true_commission_base / FARE_SPLIT_SEATS + markup_commission_per_seat
    return per_seat_commission, per_seat_distance_fee, per_seat_true_commission


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
        per_seat = (distance_fee_egp + safety_margin_egp + (fuel_cost_egp + distance_fee_egp) * 0.20) / FARE_SPLIT_SEATS
                   + (price_per_seat - fair_price_per_seat) * 0.20
        commission for a booking = ROUND(per_seat * booking.seats, 2)
    See compute_per_seat_commission() above for why the divisor is the fixed FARE_SPLIT_SEATS
    constant and not the ride's actual total_seats. Passenger points-earned use a SEPARATE,
    smaller "true commission" figure — (fuel_cost_egp + distance_fee_egp) * 0.20 (plus the same
    markup share) — since distance_fee is pass-through Cash Back, not platform revenue; see
    per_seat_true_commission in compute_per_seat_commission().

    The platform keeps 20% of (fuel_cost + distance_fee) as commission, plus the full
    distance_fee itself (100% platform revenue, credited straight back to the driver as
    Cash Back points — see the increment_cash_back_points call below) and any legacy
    flat safety margin from rides created before the 2026-09-02 pricing revision. When the
    driver has set a final price above the system fair price (Spec 023), the platform also
    takes 20% of that per-seat markup, so commission revenue scales with what the driver
    actually charges (FR-011).

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
    price_per_seat = Decimal(str(ride["price_per_seat"]))
    fair_price_per_seat = (
        Decimal(str(ride["fair_price_per_seat"])) if ride.get("fair_price_per_seat") is not None else price_per_seat
    )
    markup_commission_per_seat = max(Decimal("0.00"), price_per_seat - fair_price_per_seat) * COMMISSION_RATE

    wallet = await wallet_service.get_wallet_with_lock(conn, driver_id)
    wallet_id = wallet["id"]

    has_points_discount = any(
        Decimal(str(b["points_discount_egp"])) > Decimal("0.00")
        for b in confirmed_bookings
        if b.get("points_discount_egp") is not None
    )
    if not confirmed_bookings or (
        fuel_cost == Decimal("0")
        and distance_fee == Decimal("0")
        and safety_margin == Decimal("0")
        and markup_commission_per_seat == Decimal("0")
        and not has_points_discount
    ):
        logger.info(
            "wallet_write operation=COMMISSION_DEBIT driver_id=%s ride_id=%s "
            "bookings=0 amount_egp=0.00 (no confirmed bookings — nothing charged)",
            driver_id,
            ride_id,
        )
        return

    per_seat_commission, per_seat_distance_fee, per_seat_true_commission = compute_per_seat_commission(
        fuel_cost, distance_fee, safety_margin, price_per_seat, fair_price_per_seat
    )

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
        true_commission_amount = (per_seat_true_commission * seats).quantize(
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

        await loyalty_service.award_passenger_points(
            conn, booking["passenger_id"], booking["id"], ride_id, true_commission_amount
        )

        points_discount = (
            Decimal(str(booking["points_discount_egp"]))
            if booking.get("points_discount_egp") is not None
            else Decimal("0")
        )
        if points_discount > Decimal("0.00"):
            await wallet_service.increment_cash_back_points(conn, wallet_id, points_discount)
            await wallet_service.insert_ledger_entry(
                conn,
                wallet_id=wallet_id,
                driver_id=driver_id,
                entry_type="POINTS_DISCOUNT_REIMBURSEMENT",
                amount=points_discount,
                ride_id=ride_id,
                booking_id=booking["id"],
                note="Reimbursement for passenger pay-with-points discount",
            )

    # The distance-fee share of what was just debited is 100% platform revenue,
    # credited straight back to the driver as withdrawable Cash Back (replaces the
    # old loyalty-points/car-maintenance-savings mechanic — post-Spec-028 item 1).
    if total_distance_fee > Decimal("0.00"):
        await wallet_service.increment_cash_back_points(conn, wallet_id, total_distance_fee)
        await wallet_service.insert_ledger_entry(
            conn,
            wallet_id=wallet_id,
            driver_id=driver_id,
            entry_type="CASH_BACK_CREDIT",
            amount=total_distance_fee,
            ride_id=ride_id,
            note="Cash back (distance fee share of commission)",
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


async def update_reservation(
    conn,
    wallet_id: uuid.UUID,
    driver_id: uuid.UUID,
    ride_id: uuid.UUID,
    new_amount: Decimal,
    delta: Decimal,
) -> None:
    """Adjust an existing CommissionReservation's amount and apply the same delta to
    wallet.reserved_egp.

    Used when a driver edits a scheduled ride's price or seat count after creation (Spec 023),
    which changes the expected commission. The caller must compute `delta` (new_amount minus the
    reservation's current amount) and — for a positive delta — have already verified sufficient
    available balance via check_available_balance() before calling this.

    MUST be called inside the edit_ride() transaction, after the wallet row has been locked via
    get_wallet_with_lock(). No-ops (still updates the row, but the wallet call is skipped) when
    delta is exactly zero.
    """
    await conn.execute(
        "UPDATE commission_reservations SET reserved_amount_egp = $2 WHERE ride_id = $1",
        ride_id,
        new_amount,
    )
    if delta > Decimal("0.00"):
        await wallet_service.increment_reserved(conn, wallet_id, delta)
    elif delta < Decimal("0.00"):
        await wallet_service.decrement_reserved(conn, wallet_id, -delta)
    logger.info(
        "event=wallet_write operation=RESERVATION_UPDATE driver_id=%s amount_delta_egp=%s "
        "new_amount_egp=%s ride_id=%s",
        driver_id, delta, new_amount, ride_id,
    )


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
