from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Any, Optional

import asyncpg
from fastapi import HTTPException

from app.core.database import get_pool
from app.services import match_logging_service, ride_service
from app.services.notification_service import enqueue_booking_notification

logger = logging.getLogger(__name__)


async def _enqueue_fcm_notification(
    conn,
    event_type: str,
    recipient_user_id: uuid.UUID,
    payload: dict,
) -> None:
    await conn.execute(
        "INSERT INTO notification_events (recipient_user_id, event_type, payload) VALUES ($1, $2, $3)",
        recipient_user_id,
        event_type,
        payload,
    )


async def get_booking_or_404(conn, booking_id: uuid.UUID, caller_id: uuid.UUID) -> dict:
    """Fetch a booking by ID and verify the caller has access (passenger or ride driver)."""
    row = await conn.fetchrow(
        """
        SELECT b.*, r.driver_id
        FROM bookings b
        JOIN rides r ON r.id = b.ride_id
        WHERE b.id = $1
        """,
        booking_id,
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Booking not found"},
        )
    booking = dict(row)
    if booking["passenger_id"] != caller_id and booking["driver_id"] != caller_id:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "Access denied"},
        )
    return booking


async def _assert_ride_owner(conn, ride_id: uuid.UUID, driver_id: uuid.UUID) -> None:
    """Raise HTTP 403 if driver_id does not own the ride."""
    row = await conn.fetchrow(
        "SELECT driver_id FROM rides WHERE id = $1",
        ride_id,
    )
    if row is None or row["driver_id"] != driver_id:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "You do not own this ride"},
        )


async def create_booking(
    conn,
    ride_id: uuid.UUID,
    passenger_id: uuid.UUID,
    boarding_lat: float,
    boarding_lng: float,
    alighting_lat: float,
    alighting_lng: float,
    premium_pickup: bool,
    premium_dropoff: bool,
    premium_pickup_fee: Optional[float],
    premium_dropoff_fee: Optional[float],
    seats: int = 1,
    loyalty_redemption_catalog_entry_id: Optional[uuid.UUID] = None,
) -> dict:
    """Atomically reserve `seats` seats and create a pending booking. Must be called with a pool conn."""
    from app.services import loyalty_service

    async with conn.transaction():
        # 1. Lock the ride row to prevent concurrent seat races
        ride = await conn.fetchrow(
            """
            SELECT id, status, departure_datetime, price_per_seat, booked_seats, total_seats, driver_id, group_id,
                   fuel_cost_egp, distance_fee_egp, safety_margin_egp, fair_price_per_seat,
                   vehicle_id, recurring_ride_definition_id
            FROM rides WHERE id = $1 FOR UPDATE
            """,
            ride_id,
        )
        if ride is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Ride not found"})

        if ride["driver_id"] == passenger_id:
            raise HTTPException(
                status_code=403,
                detail={"error": "cannot_book_own_ride", "message": "You cannot book a seat on your own ride"},
            )

        if ride["status"] != "scheduled":
            raise HTTPException(
                status_code=422,
                detail={"error": "ride_not_schedulable", "message": "Ride is not accepting bookings"},
            )

        # A general (non-sponsored) group's rides are open to anyone — they surface in
        # normal search and need no membership check. Only a SPONSORED group's rides
        # are membership-gated, since booking one can draw on the group's funded
        # balance (see the payment_source branch below).
        membership_row = None
        is_sponsored_group = False
        if ride["group_id"] is not None:
            is_sponsored_group = bool(
                await conn.fetchval("SELECT is_sponsored FROM groups WHERE id = $1", ride["group_id"])
            )
            if is_sponsored_group:
                membership_row = await conn.fetchrow(
                    "SELECT domain_verification_id FROM group_memberships WHERE group_id = $1 AND user_id = $2",
                    ride["group_id"], passenger_id,
                )
                if membership_row is None:
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "error": "group_membership_required",
                            "message": "You must be a member of this group to book this ride.",
                        },
                    )

        dep = ride["departure_datetime"]
        if dep.tzinfo is None:
            dep = dep.replace(tzinfo=timezone.utc)
        if dep <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=422,
                detail={"error": "ride_departed", "message": "Ride has already departed"},
            )

        # FR-012 (Spec 027): a generated recurring instance with zero confirmed
        # bookings becomes unbookable the moment its driver/vehicle goes
        # ineligible (unverified org email, deactivated vehicle) — mirrors the
        # visibility rule applied in search (ride_service.recurring_instance_visibility_sql).
        # An instance that already has a confirmed booking is exempt.
        if ride["recurring_ride_definition_id"] is not None and ride["booked_seats"] == 0:
            eligible = await ride_service.is_driver_vehicle_eligible(
                conn, ride["driver_id"], ride["vehicle_id"]
            )
            if not eligible:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "ride_not_schedulable",
                        "message": "Ride is not accepting bookings",
                    },
                )

        # Spec 026 (redesigned 2026-08-31): a sponsored-group booking only settles —
        # debits the group's funded balance and credits the driver — once the driver
        # actually CONFIRMS it (see confirm_booking). At creation time we only mark
        # the booking as SPONSORED and enforce the 1-seat cap; no money moves yet, so
        # a later rejection never has to reverse anything (see reject_booking).
        # Redesign: since group membership is now open to everyone (no domain gate at
        # join time), only a member who has separately domain-verified their
        # eligibility for THIS sponsored group (group_memberships.domain_verification_id)
        # draws on its funded balance — any other member of the same group still rides,
        # just pays cash.
        payment_source = "CASH"
        if is_sponsored_group and membership_row["domain_verification_id"] is not None:
            if seats > 1:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "sponsored_ride_seat_limit",
                        "message": "Sponsored rides are limited to 1 seat per booking.",
                    },
                )
            payment_source = "SPONSORED"

        # 2. Atomic seat claim — zero rows means not enough seats remain
        claimed = await conn.fetchrow(
            """
            UPDATE rides SET booked_seats = booked_seats + $2
            WHERE id = $1 AND booked_seats + $2 <= total_seats
            RETURNING id
            """,
            ride_id,
            seats,
        )
        if claimed is None:
            raise HTTPException(
                status_code=409,
                detail={"error": "no_seats_available", "message": "No seats available on this ride"},
            )

        # 3. Compute pricing
        per_seat = Decimal(str(ride["price_per_seat"]))
        pu_fee = Decimal(str(premium_pickup_fee)) if premium_pickup and premium_pickup_fee else Decimal("0")
        do_fee = Decimal(str(premium_dropoff_fee)) if premium_dropoff and premium_dropoff_fee else Decimal("0")
        total = per_seat * seats + pu_fee + do_fee

        # 3a. Inline free_ride/discount loyalty redemption (Spec 028, FR-004/FR-005).
        # Must run before the booking row is inserted (it deducts points and needs the
        # final fare), and can't combine with a sponsored-group discount (FR-005a).
        loyalty_redemption = None
        if loyalty_redemption_catalog_entry_id is not None:
            if payment_source == "SPONSORED":
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "loyalty_redemption_conflict",
                        "message": "Loyalty redemption cannot be combined with a sponsored-group ride.",
                    },
                )
            loyalty_redemption = await loyalty_service.redeem_for_booking(
                conn, passenger_id, loyalty_redemption_catalog_entry_id, ride_id, total
            )
            total = loyalty_redemption["fare_after_discount_egp"]

        # 4. Insert booking — unique index raises UniqueViolation on duplicate active booking
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO bookings (
                    ride_id, passenger_id, per_seat_price, total_price, seats,
                    passenger_pickup_point, passenger_dropoff_point,
                    premium_pickup_requested, premium_dropoff_requested,
                    premium_pickup_fee, premium_dropoff_fee, payment_source
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    ST_SetSRID(ST_MakePoint($6, $7), 4326),
                    ST_SetSRID(ST_MakePoint($8, $9), 4326),
                    $10, $11, $12, $13, $14
                ) RETURNING id, status, per_seat_price, total_price, seats,
                           premium_pickup_requested, premium_dropoff_requested,
                           premium_pickup_fee, premium_dropoff_fee, created_at
                """,
                ride_id, passenger_id, per_seat, total, seats,
                boarding_lng, boarding_lat,      # MakePoint(lng, lat)
                alighting_lng, alighting_lat,
                premium_pickup, premium_dropoff,
                pu_fee if premium_pickup else None,
                do_fee if premium_dropoff else None,
                payment_source,
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "duplicate_booking",
                    "message": "You already have an active booking for this ride",
                },
            )

        booking = dict(row)
        booking_id = booking["id"]

        if loyalty_redemption is not None:
            await loyalty_service.attach_booking_to_redemption(
                conn, loyalty_redemption["redemption_request_id"], booking_id
            )
        booking["loyalty_redemption"] = loyalty_redemption

        # 5. Audit log
        await _insert_audit_log(conn, booking_id, "created", passenger_id, "passenger", None, "pending")
        await match_logging_service.record_outcome(
            conn, ride_id, passenger_id, "requested", {"booking_id": str(booking_id)},
        )

        # 6. Notifications
        driver_id = ride["driver_id"]
        await enqueue_booking_notification(
            conn,
            "booking_created",
            passenger_id,
            {"ride_id": str(ride_id), "booking_id": str(booking_id)},
        )

        passenger_profile = await conn.fetchrow(
            "SELECT display_name FROM profiles WHERE id = $1",
            passenger_id,
        )
        dep = ride["departure_datetime"]
        await _enqueue_fcm_notification(
            conn,
            "booking_received",
            driver_id,
            {
                "ride_id": str(ride_id),
                "booking_id": str(booking_id),
                "passenger_name": passenger_profile["display_name"] if passenger_profile else "",
                "departure_datetime": dep.isoformat() if dep else "",
                "deep_link": f"/(driver)/rides/{ride_id}/bookings",
            },
        )

        return booking


async def _settle_sponsored_booking(
    conn,
    *,
    booking_id: uuid.UUID,
    ride_id: uuid.UUID,
    driver_id: uuid.UUID,
    group_id: uuid.UUID,
    per_seat_price,
    seats: int,
    fuel_cost_egp,
    distance_fee_egp,
    safety_margin_egp,
    fair_price_per_seat,
) -> None:
    """Debit the group's funded balance and credit the driver for a sponsored booking
    that is about to become confirmed. Shared by confirm_booking and reject_booking's
    premium-pickup fallback path (which also confirms a booking directly). Must be
    called from within the caller's transaction, with the booking row already locked.
    """
    from app.services import loyalty_service, wallet_service
    from app.services.commission_service import compute_per_seat_commission

    total_seat_price = Decimal(str(per_seat_price)) * seats
    fuel_cost_egp = Decimal(str(fuel_cost_egp or 0))
    distance_fee_egp = Decimal(str(distance_fee_egp or 0))
    safety_margin_egp = Decimal(str(safety_margin_egp or 0))
    fair_price_per_seat = Decimal(str(fair_price_per_seat))
    price_per_seat = Decimal(str(per_seat_price))

    per_seat_commission, per_seat_distance_fee = compute_per_seat_commission(
        fuel_cost_egp, distance_fee_egp, safety_margin_egp, price_per_seat, fair_price_per_seat
    )
    commission_for_booking = (per_seat_commission * seats).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    net_credit = total_seat_price - commission_for_booking
    distance_fee_amount = (per_seat_distance_fee * seats).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    group_row = await conn.fetchrow(
        "SELECT id, funded_balance_egp FROM groups WHERE id = $1 FOR UPDATE",
        group_id,
    )
    if Decimal(str(group_row["funded_balance_egp"])) < total_seat_price:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "insufficient_funded_balance",
                "message": "This group's funded balance can no longer cover this booking.",
            },
        )
    await conn.execute(
        "UPDATE groups SET funded_balance_egp = funded_balance_egp - $2 WHERE id = $1",
        group_row["id"], total_seat_price,
    )

    driver_wallet = await wallet_service.get_wallet_with_lock(conn, driver_id)
    await wallet_service.increment_sponsored_earnings(conn, driver_wallet["id"], net_credit)
    await wallet_service.insert_ledger_entry(
        conn,
        driver_wallet["id"],
        driver_id,
        "SPONSORED_RIDE_CREDIT",
        net_credit,
        ride_id=ride_id,
        booking_id=booking_id,
        note="Sponsored group booking settlement",
    )
    await loyalty_service.award_driver_points(
        conn, driver_id, driver_wallet["id"], distance_fee_amount
    )


async def confirm_booking(
    conn,
    booking_id: uuid.UUID,
    ride_id: uuid.UUID,
    driver_id: uuid.UUID,
) -> dict:
    """Transition a pending booking to confirmed. Must be called with a pool conn."""
    await _assert_ride_owner(conn, ride_id, driver_id)

    async with conn.transaction():
        row = await conn.fetchrow(
            """
            SELECT b.id, b.status, b.ride_id, b.passenger_id, b.seats, b.per_seat_price, b.payment_source,
                   r.group_id, r.fuel_cost_egp, r.distance_fee_egp, r.safety_margin_egp, r.fair_price_per_seat
            FROM bookings b
            JOIN rides r ON r.id = b.ride_id
            WHERE b.id = $1
            FOR UPDATE OF b
            """,
            booking_id,
        )
        if row is None or row["ride_id"] != ride_id:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Booking not found"})
        if row["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail={"error": "booking_not_pending", "message": "Booking is not in pending status"},
            )

        # Spec 026 (redesigned 2026-08-31): a sponsored booking settles — draws from
        # the group's funded balance and credits the driver — only once it's actually
        # confirmed here, using the price the passenger locked in at booking time
        # (per_seat_price), not the ride's current price. This is deliberate: it means
        # a rejected sponsored booking never touched the group's money and needs no
        # reversal (see reject_booking), and the sponsorship dashboard's activity feed
        # — driven entirely by SPONSORED_RIDE_CREDIT/REVERSAL ledger entries — only
        # ever shows rides that were actually confirmed.
        if row["payment_source"] == "SPONSORED":
            await _settle_sponsored_booking(
                conn,
                booking_id=booking_id,
                ride_id=ride_id,
                driver_id=driver_id,
                group_id=row["group_id"],
                per_seat_price=row["per_seat_price"],
                seats=row["seats"],
                fuel_cost_egp=row["fuel_cost_egp"],
                distance_fee_egp=row["distance_fee_egp"],
                safety_margin_egp=row["safety_margin_egp"],
                fair_price_per_seat=row["fair_price_per_seat"],
            )

        updated = await conn.fetchrow(
            """
            UPDATE bookings SET status = 'confirmed', confirmed_at = now()
            WHERE id = $1 RETURNING id, status, confirmed_at
            """,
            booking_id,
        )

        await _insert_audit_log(conn, booking_id, "confirmed", driver_id, "driver", "pending", "confirmed")
        await match_logging_service.record_outcome(
            conn, ride_id, row["passenger_id"], "accepted", {"booking_id": str(booking_id)},
        )

        await enqueue_booking_notification(
            conn,
            "booking_confirmed",
            row["passenger_id"],
            {"ride_id": str(ride_id), "booking_id": str(booking_id)},
        )

        info = await conn.fetchrow(
            """
            SELECT r.departure_datetime, p.display_name AS driver_name
            FROM rides r JOIN profiles p ON p.id = r.driver_id
            WHERE r.id = $1
            """,
            ride_id,
        )
        await _enqueue_fcm_notification(
            conn,
            "booking_confirmed",
            row["passenger_id"],
            {
                "ride_id": str(ride_id),
                "booking_id": str(booking_id),
                "driver_name": info["driver_name"] if info else "",
                "departure_datetime": info["departure_datetime"].isoformat() if info else "",
                "deep_link": f"/(passenger)/bookings/{booking_id}",
            },
        )

    return dict(updated)


async def reject_booking(
    conn,
    booking_id: uuid.UUID,
    ride_id: uuid.UUID,
    driver_id: uuid.UUID,
    reason: Optional[str] = None,
) -> dict:
    """Reject a pending booking, applying premium fallback rule (FR-021) when applicable."""
    await _assert_ride_owner(conn, ride_id, driver_id)

    async with conn.transaction():
        row = await conn.fetchrow(
            """
            SELECT b.id, b.status, b.ride_id, b.passenger_id, b.seats,
                   b.premium_pickup_requested, b.per_seat_price, b.payment_source,
                   r.departure_datetime, r.group_id, r.fuel_cost_egp, r.distance_fee_egp,
                   r.safety_margin_egp, r.fair_price_per_seat
            FROM bookings b
            JOIN rides r ON r.id = b.ride_id
            WHERE b.id = $1
            FOR UPDATE OF b
            """,
            booking_id,
        )
        if row is None or row["ride_id"] != ride_id:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Booking not found"})
        if row["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail={"error": "booking_not_pending", "message": "Booking is not in pending status"},
            )

        if row["premium_pickup_requested"]:
            walk_m = await conn.fetchval(
                """
                SELECT ST_Distance(
                    b.passenger_pickup_point::geography,
                    ST_ClosestPoint(r.route_geometry::geometry, b.passenger_pickup_point::geometry)::geography
                )
                FROM bookings b
                JOIN rides r ON r.id = b.ride_id
                WHERE b.id = $1
                """,
                booking_id,
            )
            if walk_m is not None and walk_m <= 500:
                # This fallback confirms the booking directly (bypassing confirm_booking),
                # so a sponsored booking must settle here too — otherwise it would become
                # confirmed without ever debiting the group / crediting the driver.
                if row["payment_source"] == "SPONSORED":
                    await _settle_sponsored_booking(
                        conn,
                        booking_id=booking_id,
                        ride_id=ride_id,
                        driver_id=driver_id,
                        group_id=row["group_id"],
                        per_seat_price=row["per_seat_price"],
                        seats=row["seats"],
                        fuel_cost_egp=row["fuel_cost_egp"],
                        distance_fee_egp=row["distance_fee_egp"],
                        safety_margin_egp=row["safety_margin_egp"],
                        fair_price_per_seat=row["fair_price_per_seat"],
                    )

                # Fallback: remove only the pickup premium; preserve any dropoff premium
                await conn.execute(
                    """
                    UPDATE bookings
                    SET status = 'confirmed',
                        confirmed_at = now(),
                        premium_pickup_requested = false,
                        premium_pickup_fee = null,
                        total_price = total_price - COALESCE(premium_pickup_fee, 0)
                    WHERE id = $1
                    """,
                    booking_id,
                )
                await _insert_audit_log(
                    conn, booking_id, "confirmed", driver_id, "driver", "pending", "confirmed",
                    {"fallback_applied": True, "reason": reason},
                )
                await enqueue_booking_notification(
                    conn,
                    "booking_confirmed",
                    row["passenger_id"],
                    {"ride_id": str(ride_id), "booking_id": str(booking_id), "fallback_applied": True},
                )
                await _enqueue_fcm_notification(
                    conn,
                    "booking_confirmed",
                    row["passenger_id"],
                    {
                        "ride_id": str(ride_id),
                        "booking_id": str(booking_id),
                        "departure_datetime": (
                            row["departure_datetime"].isoformat() if row["departure_datetime"] else ""
                        ),
                        "deep_link": f"/(passenger)/bookings/{booking_id}",
                    },
                )
                await match_logging_service.record_outcome(
                    conn, ride_id, row["passenger_id"], "accepted",
                    {"booking_id": str(booking_id), "fallback_applied": True},
                )
                return {"id": booking_id, "status": "confirmed", "cancelled_by": None, "fallback_applied": True}

        # No fallback — cancel the booking and release the seats
        await conn.execute(
            "UPDATE rides SET booked_seats = GREATEST(booked_seats - $2, 0) WHERE id = $1",
            ride_id,
            row["seats"],
        )
        updated = await conn.fetchrow(
            """
            UPDATE bookings
            SET status = 'cancelled',
                cancelled_by = 'driver',
                cancellation_reason = $2,
                cancelled_at = now()
            WHERE id = $1
            RETURNING id, status, cancelled_by
            """,
            booking_id,
            reason,
        )

        await _insert_audit_log(
            conn, booking_id, "rejected", driver_id, "driver", "pending", "cancelled", {"reason": reason}
        )
        await match_logging_service.record_outcome(
            conn, ride_id, row["passenger_id"], "rejected",
            {"booking_id": str(booking_id), "reason": reason},
        )

        await enqueue_booking_notification(
            conn,
            "booking_rejected",
            row["passenger_id"],
            {"ride_id": str(ride_id), "booking_id": str(booking_id)},
        )
        await _enqueue_fcm_notification(
            conn,
            "booking_rejected",
            row["passenger_id"],
            {
                "ride_id": str(ride_id),
                "booking_id": str(booking_id),
                "departure_datetime": row["departure_datetime"].isoformat() if row["departure_datetime"] else "",
                "deep_link": "/(passenger)/rides",
            },
        )

    result = dict(updated)
    result["fallback_applied"] = False
    return result


async def cancel_booking(
    conn,
    booking_id: uuid.UUID,
    caller_id: Optional[uuid.UUID],
    caller_role: str,  # 'passenger', 'driver', 'system'
    reason: Optional[str] = None,
) -> dict:
    """Cancel a booking, release the seat, and enqueue the appropriate notification."""
    async with conn.transaction():
        row = await conn.fetchrow(
            """
            SELECT b.id, b.status, b.ride_id, b.passenger_id, b.seats, b.payment_source, b.per_seat_price,
                   r.driver_id, r.departure_datetime, r.group_id, r.price_per_seat, r.total_seats,
                   r.fuel_cost_egp, r.distance_fee_egp, r.safety_margin_egp, r.fair_price_per_seat
            FROM bookings b
            JOIN rides r ON r.id = b.ride_id
            WHERE b.id = $1
            FOR UPDATE OF b
            """,
            booking_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Booking not found"})

        if caller_role == "passenger" and row["passenger_id"] != caller_id:
            raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Access denied"})
        if caller_role == "driver" and row["driver_id"] != caller_id:
            raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Access denied"})

        if row["status"] in ("cancelled", "completed"):
            raise HTTPException(
                status_code=409,
                detail={"error": "booking_terminal", "message": "Booking is already cancelled or completed"},
            )

        dep = row["departure_datetime"]
        if dep.tzinfo is None:
            dep = dep.replace(tzinfo=timezone.utc)
        time_until_dep = dep - datetime.now(timezone.utc)
        if caller_role == "passenger" and time_until_dep < timedelta(hours=2):
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "cancellation_window_closed",
                    "message": "Bookings cannot be cancelled within 2 hours of departure.",
                },
            )
        if caller_role == "driver" and time_until_dep < timedelta(hours=2):
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "cancellation_window_closed",
                    "message": "Passenger bookings cannot be cancelled within 2 hours of departure.",
                },
            )
        late_cancellation = time_until_dep < timedelta(hours=2)

        # Spec 026 (redesigned 2026-08-31): a sponsored booking now only settles once
        # CONFIRMED (see confirm_booking / _settle_sponsored_booking) — a still-pending
        # sponsored booking never touched the group's money, so cancelling it needs no
        # reversal at all. Only reverse a booking that was actually confirmed, using the
        # price the passenger locked in (per_seat_price), which is exactly what was
        # credited at settlement time — not the ride's current (possibly since-edited) price.
        if row["payment_source"] == "SPONSORED" and row["status"] == "confirmed":
            from app.services import loyalty_service, wallet_service
            from app.services.commission_service import compute_per_seat_commission

            total_seat_price = Decimal(str(row["per_seat_price"])) * row["seats"]
            fuel_cost_egp = Decimal(str(row["fuel_cost_egp"] or 0))
            distance_fee_egp = Decimal(str(row["distance_fee_egp"] or 0))
            safety_margin_egp = Decimal(str(row["safety_margin_egp"] or 0))
            fair_price_per_seat = Decimal(str(row["fair_price_per_seat"]))
            price_per_seat = Decimal(str(row["per_seat_price"]))

            per_seat_commission, per_seat_distance_fee = compute_per_seat_commission(
                fuel_cost_egp, distance_fee_egp, safety_margin_egp, price_per_seat, fair_price_per_seat
            )
            commission_for_booking = (per_seat_commission * row["seats"]).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            net_credit = total_seat_price - commission_for_booking
            # Mirrors the accumulation applied at booking creation — claw it back so a
            # cancelled sponsored booking doesn't leave phantom progress toward the
            # car-maintenance reward (see create_booking's SPONSORED branch).
            distance_fee_amount = (per_seat_distance_fee * row["seats"]).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            await conn.fetchrow("SELECT id FROM groups WHERE id = $1 FOR UPDATE", row["group_id"])
            await conn.execute(
                "UPDATE groups SET funded_balance_egp = funded_balance_egp + $2 WHERE id = $1",
                row["group_id"], total_seat_price,
            )
            driver_wallet = await wallet_service.get_wallet_with_lock(conn, row["driver_id"])
            await wallet_service.decrement_sponsored_earnings(conn, driver_wallet["id"], net_credit)
            await wallet_service.insert_ledger_entry(
                conn,
                driver_wallet["id"],
                row["driver_id"],
                "SPONSORED_RIDE_REVERSAL",
                net_credit,
                ride_id=row["ride_id"],
                booking_id=booking_id,
                note="Sponsored group booking cancellation reversal",
            )
            # Mirror the fractional-carry pool reversal (award_driver_points may have
            # cashed part of this contribution into points already — GREATEST(...,0)
            # in decrement_car_maintenance_savings protects the pool floor). Separately
            # claw back whole points via reverse_points: since a single booking's
            # distance fee is almost always < 1 EGP, this is 0 in the common case (no
            # point was ever minted from this booking alone) and a conservative
            # (never-over-claws) floor otherwise — the driver keeps any point that
            # required pooling with other bookings' fractional remainders.
            await wallet_service.decrement_car_maintenance_savings(
                conn, driver_wallet["id"], distance_fee_amount
            )
            points_to_reverse = int(distance_fee_amount.to_integral_value(rounding=ROUND_FLOOR))
            if points_to_reverse > 0:
                await loyalty_service.reverse_points(
                    conn, row["driver_id"], points_to_reverse,
                    ride_id=row["ride_id"], booking_id=booking_id,
                )

        await conn.execute(
            "UPDATE rides SET booked_seats = GREATEST(booked_seats - $2, 0) WHERE id = $1",
            row["ride_id"],
            row["seats"],
        )

        cancelled_by_val = caller_role if caller_role in ("passenger", "driver") else "system"
        updated = await conn.fetchrow(
            """
            UPDATE bookings
            SET status = 'cancelled',
                cancelled_by = $2,
                cancellation_reason = $3,
                late_cancellation = $4,
                cancelled_at = now()
            WHERE id = $1
            RETURNING id, status, cancelled_by, late_cancellation, cancelled_at
            """,
            booking_id,
            cancelled_by_val,
            reason,
            late_cancellation,
        )

        prev_status = row["status"]
        await _insert_audit_log(
            conn, booking_id, "cancelled", caller_id, caller_role,
            prev_status, "cancelled", {"reason": reason},
        )
        await match_logging_service.record_outcome(
            conn, row["ride_id"], row["passenger_id"], "cancelled",
            {"booking_id": str(booking_id), "cancelled_by": cancelled_by_val, "reason": reason},
        )

        if caller_role == "passenger":
            notif_type = "booking_cancelled_by_passenger"
            recipient = row["driver_id"]
        elif caller_role == "driver":
            notif_type = "booking_cancelled_by_driver"
            recipient = row["passenger_id"]
        else:
            notif_type = "ride_cancelled"
            recipient = row["passenger_id"]

        await enqueue_booking_notification(
            conn,
            notif_type,
            recipient,
            {"ride_id": str(row["ride_id"]), "booking_id": str(booking_id)},
        )

        dep_str = row["departure_datetime"].isoformat() if row["departure_datetime"] else ""
        if caller_role == "passenger":
            await _enqueue_fcm_notification(
                conn,
                "booking_cancelled",
                row["driver_id"],
                {
                    "ride_id": str(row["ride_id"]),
                    "booking_id": str(booking_id),
                    "cancelled_by": "passenger",
                    "departure_datetime": dep_str,
                    "deep_link": f"/(driver)/rides/{row['ride_id']}/bookings",
                },
            )
        elif caller_role == "driver":
            await _enqueue_fcm_notification(
                conn,
                "booking_cancelled",
                row["passenger_id"],
                {
                    "ride_id": str(row["ride_id"]),
                    "booking_id": str(booking_id),
                    "cancelled_by": "driver",
                    "departure_datetime": dep_str,
                    "deep_link": f"/(passenger)/bookings/{booking_id}",
                },
            )
        # system: ride_cancelled FCM events are emitted by cancel_ride() directly

    return dict(updated)


async def add_booking_seats(
    conn,
    booking_id: uuid.UUID,
    passenger_id: uuid.UUID,
    additional_seats: int,
) -> dict:
    """Increase the seat count on an existing pending/confirmed booking. Must be called with a pool conn."""
    async with conn.transaction():
        row = await conn.fetchrow(
            """
            SELECT b.id, b.status, b.ride_id, b.passenger_id, b.seats, b.per_seat_price, b.payment_source,
                   r.driver_id, r.departure_datetime
            FROM bookings b
            JOIN rides r ON r.id = b.ride_id
            WHERE b.id = $1
            FOR UPDATE OF b
            """,
            booking_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Booking not found"})
        if row["passenger_id"] != passenger_id:
            raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Access denied"})
        if row["status"] not in ("pending", "confirmed"):
            raise HTTPException(
                status_code=409,
                detail={"error": "booking_terminal", "message": "Booking is not active"},
            )
        if row["payment_source"] == "SPONSORED":
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "sponsored_ride_seat_limit",
                    "message": "Sponsored rides are limited to 1 seat per booking.",
                },
            )

        dep = row["departure_datetime"]
        if dep.tzinfo is None:
            dep = dep.replace(tzinfo=timezone.utc)
        if dep <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=422,
                detail={"error": "ride_departed", "message": "Ride has already departed"},
            )

        claimed = await conn.fetchrow(
            """
            UPDATE rides SET booked_seats = booked_seats + $2
            WHERE id = $1 AND booked_seats + $2 <= total_seats
            RETURNING id
            """,
            row["ride_id"],
            additional_seats,
        )
        if claimed is None:
            raise HTTPException(
                status_code=409,
                detail={"error": "no_seats_available", "message": "No seats available on this ride"},
            )

        per_seat = Decimal(str(row["per_seat_price"]))
        extra_cost = per_seat * additional_seats
        updated = await conn.fetchrow(
            """
            UPDATE bookings
            SET seats = seats + $2, total_price = total_price + $3
            WHERE id = $1
            RETURNING id, status, seats, total_price
            """,
            booking_id,
            additional_seats,
            extra_cost,
        )

        await _insert_audit_log(
            conn, booking_id, "seats_added", passenger_id, "passenger",
            row["status"], row["status"], {"additional_seats": additional_seats},
        )

        await enqueue_booking_notification(
            conn,
            "booking_seats_added",
            row["driver_id"],
            {"ride_id": str(row["ride_id"]), "booking_id": str(booking_id), "additional_seats": additional_seats},
        )
        await _enqueue_fcm_notification(
            conn,
            "booking_seats_added",
            row["driver_id"],
            {
                "ride_id": str(row["ride_id"]),
                "booking_id": str(booking_id),
                "additional_seats": additional_seats,
                "departure_datetime": row["departure_datetime"].isoformat() if row["departure_datetime"] else "",
                "deep_link": f"/(driver)/rides/{row['ride_id']}/bookings",
            },
        )

    return dict(updated)


async def cancel_all_bookings_for_ride(conn, ride_id: uuid.UUID) -> int:
    """Cancel all pending and confirmed bookings for a ride. Used by ride cascade. Returns count."""
    rows = await conn.fetch(
        "SELECT id FROM bookings WHERE ride_id = $1 AND status IN ('pending', 'confirmed')",
        ride_id,
    )
    for row in rows:
        await cancel_booking(
            conn,
            row["id"],
            caller_id=None,
            caller_role="system",
            reason="ride_cancelled_by_driver",
        )
    return len(rows)


async def expire_one_pending_booking(conn, booking_id: uuid.UUID) -> bool:
    """Cancel one still-pending booking: release its seat, mark it cancelled,
    and notify the passenger. No-ops if the booking is no longer pending
    (already handled concurrently, or the driver acted on it first).

    Shared by the periodic staleness sweep and by ride-status transitions
    (start/complete) that must not leave a request pending once the driver
    can no longer act on it.
    """
    locked = await conn.fetchrow(
        """
        SELECT b.id, b.passenger_id, b.ride_id, b.seats, r.departure_datetime
        FROM bookings b
        JOIN rides r ON r.id = b.ride_id
        WHERE b.id = $1 AND b.status = 'pending'
        FOR UPDATE OF b SKIP LOCKED
        """,
        booking_id,
    )
    if locked is None:
        return False  # Concurrently processed or already non-pending

    await conn.execute(
        """
        UPDATE bookings
        SET status = 'cancelled',
            cancelled_by = 'system',
            cancellation_reason = 'booking_expired',
            cancelled_at = now()
        WHERE id = $1
        """,
        locked["id"],
    )

    await conn.execute(
        "UPDATE rides SET booked_seats = GREATEST(booked_seats - $2, 0) WHERE id = $1",
        locked["ride_id"],
        locked["seats"],
    )

    await _insert_audit_log(
        conn, locked["id"], "expired", None, "system", "pending", "cancelled"
    )
    await match_logging_service.record_outcome(
        conn, locked["ride_id"], locked["passenger_id"], "cancelled",
        {"booking_id": str(locked["id"]), "cancelled_by": "system", "reason": "booking_expired"},
    )

    await enqueue_booking_notification(
        conn,
        "booking_expired",
        locked["passenger_id"],
        {"ride_id": str(locked["ride_id"]), "booking_id": str(locked["id"])},
    )
    await _enqueue_fcm_notification(
        conn,
        "booking_expired",
        locked["passenger_id"],
        {
            "ride_id": str(locked["ride_id"]),
            "booking_id": str(locked["id"]),
            "departure_datetime": (
                locked["departure_datetime"].isoformat() if locked["departure_datetime"] else ""
            ),
            "deep_link": "/(passenger)/rides",
        },
    )
    return True


async def _expire_pending_bookings(pool) -> None:
    """Sweep stale pending bookings and cancel them (max 500 per run): either
    older than 24 hours, or whose ride already moved past 'scheduled' (started,
    completed, or cancelled) while the driver never responded — which would
    otherwise leave the booking stuck showing "pending" forever.
    """
    async with pool.acquire() as conn:
        candidates = await conn.fetch(
            """
            SELECT b.id
            FROM bookings b
            JOIN rides r ON r.id = b.ride_id
            WHERE b.status = 'pending'
              AND (b.created_at < NOW() - INTERVAL '24 hours' OR r.status != 'scheduled')
            LIMIT 500
            """
        )

    for row in candidates:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await expire_one_pending_booking(conn, row["id"])


async def booking_expiry_loop() -> None:
    """Background task: cancel unresponded pending bookings every 10 minutes."""
    pool = get_pool()
    while True:
        try:
            await _expire_pending_bookings(pool)
        except Exception as exc:
            logger.error("Booking expiry sweep error: %s", exc)
        await asyncio.sleep(600)


async def complete_ride_bookings(conn, ride_id: uuid.UUID) -> int:
    """Transition all confirmed bookings for a ride to completed. Idempotent."""
    from app.services import loyalty_service

    rows = await conn.fetch(
        """
        UPDATE bookings b
        SET status = 'completed'
        FROM rides r
        WHERE b.ride_id = $1 AND b.status = 'confirmed' AND r.id = b.ride_id
        RETURNING b.id, b.passenger_id, b.total_price, r.driver_id
        """,
        ride_id,
    )
    for row in rows:
        await _insert_audit_log(
            conn, row["id"], "completed", None, "system", "confirmed", "completed"
        )
        # FR-001 (Spec 028): passengers earn loyalty points on completed bookings,
        # proportional to what they actually paid (already net of any inline
        # free_ride/discount redemption applied at booking creation).
        await loyalty_service.award_passenger_points(
            conn, row["passenger_id"], row["id"], ride_id, Decimal(str(row["total_price"]))
        )
        await match_logging_service.record_outcome(
            conn, ride_id, row["passenger_id"], "completed", {"booking_id": str(row["id"])},
        )
        await _enqueue_fcm_notification(
            conn,
            "rating_prompt",
            row["passenger_id"],
            {
                "ride_id": str(ride_id),
                "booking_id": str(row["id"]),
                "deep_link": f"/(passenger)/ratings/{row['id']}",
            },
        )
        await _enqueue_fcm_notification(
            conn,
            "rating_prompt",
            row["driver_id"],
            {
                "ride_id": str(ride_id),
                "booking_id": str(row["id"]),
                "deep_link": f"/(driver)/ratings/{row['id']}",
            },
        )
    return len(rows)


async def _insert_audit_log(
    conn,
    booking_id: uuid.UUID,
    event_type: str,
    actor_id: Optional[uuid.UUID],
    actor_role: str,
    prev_status: Optional[str],
    new_status: str,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Append one immutable row to booking_audit_log."""
    await conn.execute(
        """
        INSERT INTO booking_audit_log
            (booking_id, event_type, actor_id, actor_role, previous_status, new_status, metadata)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        booking_id,
        event_type,
        actor_id,
        actor_role,
        prev_status,
        new_status,
        metadata or {},
    )
