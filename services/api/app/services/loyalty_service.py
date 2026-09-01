from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import ROUND_FLOOR, Decimal
from typing import Literal, Optional

from fastapi import HTTPException

from app.services import audit_service, wallet_service

Role = Literal["passenger", "driver"]

_ADMIN_PAGE_SIZE = 20

# ─────────────────────────────────────────────────────────────────────────────
# Account / ledger primitives (mirrors wallet_service.get_wallet_with_lock)
# ─────────────────────────────────────────────────────────────────────────────

_ACCOUNT_COLS = "id, user_id, role, balance, created_at, updated_at"


async def get_or_create_account(conn, user_id: uuid.UUID, role: Role) -> dict:
    await conn.execute(
        "INSERT INTO loyalty_points_accounts (user_id, role) VALUES ($1, $2::loyalty_account_role) "
        "ON CONFLICT (user_id, role) DO NOTHING",
        user_id,
        role,
    )
    row = await conn.fetchrow(
        f"SELECT {_ACCOUNT_COLS} FROM loyalty_points_accounts WHERE user_id = $1 AND role = $2::loyalty_account_role",
        user_id,
        role,
    )
    return dict(row)


async def get_account_with_lock(conn, user_id: uuid.UUID, role: Role) -> dict:
    """Return the user's role-scoped points account under SELECT ... FOR UPDATE.

    Creates the row first if absent, then locks it. MUST be called inside an active
    transaction — the lock is released on commit/rollback. Use for all balance-mutating
    operations (earn, redeem, refund, reversal).
    """
    await conn.execute(
        "INSERT INTO loyalty_points_accounts (user_id, role) VALUES ($1, $2::loyalty_account_role) "
        "ON CONFLICT (user_id, role) DO NOTHING",
        user_id,
        role,
    )
    row = await conn.fetchrow(
        f"SELECT {_ACCOUNT_COLS} FROM loyalty_points_accounts WHERE user_id = $1 AND role = $2::loyalty_account_role "
        "FOR UPDATE",
        user_id,
        role,
    )
    return dict(row)


async def _get_setting(conn, key: str) -> str:
    value = await conn.fetchval("SELECT value FROM platform_settings WHERE key = $1", key)
    if value is None:
        raise RuntimeError(f"Missing required platform_settings key: {key}")
    return value


async def _record_transaction(
    conn,
    account_id: uuid.UUID,
    delta: int,
    reason: str,
    *,
    ride_id: Optional[uuid.UUID] = None,
    booking_id: Optional[uuid.UUID] = None,
    redemption_request_id: Optional[uuid.UUID] = None,
) -> dict:
    """Apply delta to the account's balance and append an immutable ledger entry.

    The caller MUST already hold the account row lock via get_account_with_lock() in
    the same transaction. Positive delta = earn/refund, negative = redeem/reversal.
    Relies on the loyalty_points_accounts.balance >= 0 CHECK constraint as a last-resort
    guard — callers that can go negative (redemption spend, reversal) MUST pre-validate
    or floor the delta themselves (see redeem_catalog_entry / reverse_points).
    """
    updated = await conn.fetchrow(
        "UPDATE loyalty_points_accounts SET balance = balance + $2, updated_at = now() "
        "WHERE id = $1 RETURNING balance",
        account_id,
        delta,
    )
    new_balance = updated["balance"]
    row = await conn.fetchrow(
        """
        INSERT INTO loyalty_points_transactions
            (account_id, delta, reason, ride_id, booking_id, redemption_request_id, balance_after)
        VALUES ($1, $2, $3::loyalty_transaction_reason, $4, $5, $6, $7)
        RETURNING id, account_id, delta, reason, ride_id, booking_id, redemption_request_id,
                  balance_after, created_at
        """,
        account_id,
        delta,
        reason,
        ride_id,
        booking_id,
        redemption_request_id,
        new_balance,
    )
    return dict(row)


async def get_balance(conn, user_id: uuid.UUID, role: Role) -> dict:
    return await get_or_create_account(conn, user_id, role)


async def get_ledger_page(
    conn, account_id: uuid.UUID, page: int, per_page: int = 50
) -> tuple[list[dict], int]:
    """Return (entries, total_count) for the account's ledger, newest-first, paginated."""
    per_page = min(per_page, 50)
    offset = (page - 1) * per_page
    rows = await conn.fetch(
        """
        SELECT id, delta, reason, ride_id, booking_id, redemption_request_id, balance_after, created_at
        FROM loyalty_points_transactions
        WHERE account_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        account_id,
        per_page,
        offset,
    )
    total = await conn.fetchval(
        "SELECT COUNT(*) FROM loyalty_points_transactions WHERE account_id = $1", account_id
    )
    return [dict(r) for r in rows], int(total)


# ─────────────────────────────────────────────────────────────────────────────
# Earning (FR-001, FR-002)
# ─────────────────────────────────────────────────────────────────────────────

async def award_passenger_points(
    conn,
    passenger_id: uuid.UUID,
    booking_id: uuid.UUID,
    ride_id: uuid.UUID,
    fare_paid_egp: Decimal,
) -> None:
    """Credit floor(fare_paid_egp * loyalty_passenger_earn_points_per_egp_fare) points.

    MUST be called inside the same transaction as the booking completion update
    (booking_service.complete_ride_bookings), per booking. FR-001.
    """
    if fare_paid_egp <= Decimal("0"):
        return
    rate = Decimal(await _get_setting(conn, "loyalty_passenger_earn_points_per_egp_fare"))
    points = int((fare_paid_egp * rate).to_integral_value(rounding=ROUND_FLOOR))
    if points <= 0:
        return
    account = await get_account_with_lock(conn, passenger_id, "passenger")
    await _record_transaction(
        conn, account["id"], points, "ride_completed_earn", ride_id=ride_id, booking_id=booking_id
    )
    await conn.execute(
        "INSERT INTO notification_events (recipient_user_id, event_type, payload) VALUES ($1, $2, $3)",
        passenger_id,
        "loyalty_points_earned",
        {"points": points, "ride_id": str(ride_id), "booking_id": str(booking_id)},
    )


async def award_driver_points(
    conn,
    driver_id: uuid.UUID,
    wallet_id: uuid.UUID,
    distance_fee_amount: Decimal,
) -> None:
    """Replaces car_maintenance_service.accumulate_and_maybe_grant(). Credits 1 point per
    whole EGP of accumulated distance fee (research.md Decision 6, 1:1 with the retired
    CAR_MAINTENANCE_THRESHOLD_EGP mechanism).

    driver_wallets.car_maintenance_savings_egp is reused purely as a fractional-EGP carry
    buffer (NOT a user-facing balance anymore — loyalty_points_accounts is): each call adds
    distance_fee_amount to it, then "cashes out" every whole EGP crossed as 1 point,
    leaving the sub-EGP remainder for the next ride. This preserves the exact precision the
    old car-maintenance mechanism had; flooring distance_fee_amount per-ride instead (most
    rides fund < 1 EGP of distance fee) would silently lose most of a driver's earnings.

    MUST be called inside the same transaction as the wallet debit, with the wallet row
    already locked via wallet_service.get_wallet_with_lock() (commission_service.deduct_commission
    and booking_service._settle_sponsored_booking both do this before calling here).
    """
    if distance_fee_amount <= Decimal("0"):
        return

    new_total = await wallet_service.increment_car_maintenance_savings(
        conn, wallet_id, distance_fee_amount
    )
    points = int(new_total.to_integral_value(rounding=ROUND_FLOOR))
    if points <= 0:
        return

    await wallet_service.decrement_car_maintenance_savings(conn, wallet_id, Decimal(points))
    account = await get_account_with_lock(conn, driver_id, "driver")
    await _record_transaction(conn, account["id"], points, "ride_completed_earn")


async def reverse_points(
    conn,
    driver_id: uuid.UUID,
    points: int,
    *,
    ride_id: Optional[uuid.UUID] = None,
    booking_id: Optional[uuid.UUID] = None,
) -> None:
    """Claw back up to `points` driver points, floored at the account's current balance
    (never negative). FR-014.

    Used when a sponsored booking that already settled (credited driver points at
    confirmation time, see booking_service._settle_sponsored_booking) is cancelled before
    the ride completes — booking_service.cancel_booking's sponsored-reversal branch calls
    this instead of decrementing driver_wallets directly, since driver points now live in
    loyalty_points_accounts, not car_maintenance_savings_egp.
    """
    if points <= 0:
        return
    account = await get_account_with_lock(conn, driver_id, "driver")
    clawback = min(points, account["balance"])
    if clawback <= 0:
        return
    await _record_transaction(
        conn, account["id"], -clawback, "ride_reversal_clawback", ride_id=ride_id, booking_id=booking_id
    )


# ─────────────────────────────────────────────────────────────────────────────
# Redemption — catalog browse + generic redeem (voucher / car_maintenance)
# ─────────────────────────────────────────────────────────────────────────────

async def list_catalog(conn, role: Role) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT id, type, title, description, point_cost, fulfillment_mode
        FROM loyalty_reward_catalog
        WHERE active = true AND (audience = $1::loyalty_audience OR audience = 'both')
        ORDER BY point_cost ASC
        """,
        role,
    )
    return [dict(r) for r in rows]


async def redeem_catalog_entry(
    conn, user_id: uuid.UUID, role: Role, catalog_entry_id: uuid.UUID
) -> dict:
    """Redeem a voucher or car_maintenance catalog entry. free_ride/discount are rejected
    here — they redeem inline at booking creation via redeem_for_booking(). FR-011."""
    account = await get_account_with_lock(conn, user_id, role)
    entry = await conn.fetchrow(
        "SELECT id, type, point_cost, fulfillment_mode, active FROM loyalty_reward_catalog "
        "WHERE id = $1 FOR UPDATE",
        catalog_entry_id,
    )
    if entry is None or not entry["active"]:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Catalog entry not found"})
    if entry["type"] in ("free_ride", "discount"):
        raise HTTPException(
            status_code=409,
            detail={"error": "invalid_redemption_type", "message": "Use booking creation to redeem this reward"},
        )
    if account["balance"] < entry["point_cost"]:
        raise HTTPException(status_code=409, detail={"error": "insufficient_points", "message": "Not enough points"})

    status = "fulfilled" if entry["fulfillment_mode"] == "instant" else "pending"
    fulfilled_at = datetime.now(timezone.utc) if status == "fulfilled" else None
    request = await conn.fetchrow(
        """
        INSERT INTO loyalty_redemption_requests
            (account_id, catalog_entry_id, points_spent, fulfillment_mode, status, fulfilled_at)
        VALUES ($1, $2, $3, $4::loyalty_fulfillment_mode, $5::loyalty_redemption_status, $6)
        RETURNING id, status
        """,
        account["id"],
        entry["id"],
        entry["point_cost"],
        entry["fulfillment_mode"],
        status,
        fulfilled_at,
    )
    tx = await _record_transaction(
        conn, account["id"], -entry["point_cost"], "redemption_spend", redemption_request_id=request["id"]
    )
    return {
        "redemption_request_id": request["id"],
        "status": request["status"],
        "points_spent": entry["point_cost"],
        "balance_after": tx["balance_after"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Redemption — inline free_ride / discount at booking creation (FR-004/FR-005/FR-005a)
# ─────────────────────────────────────────────────────────────────────────────

async def redeem_for_booking(
    conn,
    passenger_id: uuid.UUID,
    catalog_entry_id: uuid.UUID,
    ride_id: uuid.UUID,
    fare_egp: Decimal,
) -> dict:
    """Validate + deduct points for an inline free_ride/discount redemption. MUST be
    called inside the same transaction as booking creation, before the bookings row is
    inserted (booking_id is unknown yet — call attach_booking_to_redemption() once it is).
    Returns {"redemption_request_id", "points_spent", "fare_after_discount_egp"}.
    """
    account = await get_account_with_lock(conn, passenger_id, "passenger")
    entry = await conn.fetchrow(
        "SELECT id, type, point_cost, active, audience FROM loyalty_reward_catalog WHERE id = $1 FOR UPDATE",
        catalog_entry_id,
    )
    if (
        entry is None
        or not entry["active"]
        or entry["type"] not in ("free_ride", "discount")
        or entry["audience"] not in ("passenger", "both")
    ):
        raise HTTPException(
            status_code=409,
            detail={"error": "loyalty_redemption_conflict", "message": "Not a valid free-ride/discount reward"},
        )
    if account["balance"] < entry["point_cost"]:
        raise HTTPException(status_code=409, detail={"error": "insufficient_points", "message": "Not enough points"})

    if entry["type"] == "free_ride":
        max_fare = Decimal(await _get_setting(conn, "loyalty_free_ride_max_fare_egp"))
        fare_after = max(fare_egp - max_fare, Decimal("0.00"))
    else:
        pct = Decimal(await _get_setting(conn, "loyalty_discount_percentage"))
        fare_after = (fare_egp * (Decimal("100") - pct) / Decimal("100")).quantize(Decimal("0.01"))

    request = await conn.fetchrow(
        """
        INSERT INTO loyalty_redemption_requests
            (account_id, catalog_entry_id, points_spent, fulfillment_mode, status, ride_id, fulfilled_at)
        VALUES ($1, $2, $3, 'instant'::loyalty_fulfillment_mode, 'fulfilled'::loyalty_redemption_status, $4, now())
        RETURNING id
        """,
        account["id"],
        entry["id"],
        entry["point_cost"],
        ride_id,
    )
    await _record_transaction(
        conn, account["id"], -entry["point_cost"], "redemption_spend",
        ride_id=ride_id, redemption_request_id=request["id"],
    )
    return {
        "redemption_request_id": request["id"],
        "points_spent": entry["point_cost"],
        "fare_after_discount_egp": fare_after,
    }


async def attach_booking_to_redemption(conn, redemption_request_id: uuid.UUID, booking_id: uuid.UUID) -> None:
    await conn.execute(
        "UPDATE loyalty_redemption_requests SET booking_id = $2 WHERE id = $1",
        redemption_request_id,
        booking_id,
    )
    await conn.execute(
        "UPDATE loyalty_points_transactions SET booking_id = $2 WHERE redemption_request_id = $1",
        redemption_request_id,
        booking_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Admin-facing: manual-fulfillment queue (generalizes car_maintenance_service)
# ─────────────────────────────────────────────────────────────────────────────

async def list_pending_queue(conn, page: int, limit: int = _ADMIN_PAGE_SIZE) -> dict:
    offset = (page - 1) * limit
    rows = await conn.fetch(
        """
        SELECT rr.id, a.user_id, a.role, p.display_name AS user_name, p.email AS user_email,
               c.type AS catalog_type, c.title AS catalog_title, rr.points_spent, rr.created_at
        FROM loyalty_redemption_requests rr
        JOIN loyalty_points_accounts a ON a.id = rr.account_id
        JOIN profiles p ON p.id = a.user_id
        JOIN loyalty_reward_catalog c ON c.id = rr.catalog_entry_id
        WHERE rr.status = 'pending'
        ORDER BY rr.created_at ASC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )
    total = await conn.fetchval("SELECT count(*) FROM loyalty_redemption_requests WHERE status = 'pending'")
    items = [
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "user_name": row["user_name"],
            "user_email": row["user_email"],
            "role": row["role"],
            "catalog_entry": {"type": row["catalog_type"], "title": row["catalog_title"]},
            "points_spent": row["points_spent"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return {"total": int(total), "page": page, "items": items}


async def fulfill_request(conn, redemption_request_id: uuid.UUID, admin_id: uuid.UUID) -> dict:
    """No balance mutation — points were already deducted at submission (FR-011)."""
    async with conn.transaction():
        row = await conn.fetchrow(
            "SELECT id, status FROM loyalty_redemption_requests WHERE id = $1 FOR UPDATE",
            redemption_request_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Request not found"})
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail={"error": "conflict", "message": "Request already resolved"})

        updated = await conn.fetchrow(
            """
            UPDATE loyalty_redemption_requests
            SET status = 'fulfilled', fulfilled_by = $2, fulfilled_at = now()
            WHERE id = $1
            RETURNING id, status, fulfilled_by, fulfilled_at
            """,
            redemption_request_id,
            admin_id,
        )
        user_id = await conn.fetchval(
            "SELECT a.user_id FROM loyalty_points_accounts a "
            "JOIN loyalty_redemption_requests rr ON rr.account_id = a.id WHERE rr.id = $1",
            redemption_request_id,
        )
        await conn.execute(
            "INSERT INTO notification_events (recipient_user_id, event_type, payload) VALUES ($1, $2, $3)",
            user_id,
            "loyalty_redemption_fulfilled",
            {"redemption_request_id": str(redemption_request_id)},
        )

    audit_service.append_log(
        str(admin_id), "approved", str(user_id), redemption_request_id=str(redemption_request_id)
    )

    return {
        "id": updated["id"],
        "status": updated["status"],
        "fulfilled_by": updated["fulfilled_by"],
        "fulfilled_at": updated["fulfilled_at"],
    }


async def reject_request(conn, redemption_request_id: uuid.UUID, admin_id: uuid.UUID, reason: str) -> dict:
    """Refunds points_spent back to the account via a redemption_refund transaction (FR-012)."""
    async with conn.transaction():
        row = await conn.fetchrow(
            "SELECT id, status, account_id, points_spent FROM loyalty_redemption_requests WHERE id = $1 FOR UPDATE",
            redemption_request_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Request not found"})
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail={"error": "conflict", "message": "Request already resolved"})

        updated = await conn.fetchrow(
            """
            UPDATE loyalty_redemption_requests
            SET status = 'rejected', fulfilled_by = $2, fulfilled_at = now(), rejection_reason = $3
            WHERE id = $1
            RETURNING id, status, fulfilled_by, fulfilled_at
            """,
            redemption_request_id,
            admin_id,
            reason,
        )
        account = await conn.fetchrow(
            f"SELECT {_ACCOUNT_COLS} FROM loyalty_points_accounts WHERE id = $1 FOR UPDATE", row["account_id"]
        )
        await _record_transaction(
            conn, account["id"], row["points_spent"], "redemption_refund",
            redemption_request_id=redemption_request_id,
        )
        await conn.execute(
            "INSERT INTO notification_events (recipient_user_id, event_type, payload) VALUES ($1, $2, $3)",
            account["user_id"],
            "loyalty_redemption_rejected",
            {"redemption_request_id": str(redemption_request_id), "reason": reason},
        )

    audit_service.append_log(
        str(admin_id), "rejected", str(account["user_id"]),
        reason=reason, redemption_request_id=str(redemption_request_id),
    )

    return {
        "id": updated["id"],
        "status": updated["status"],
        "fulfilled_by": updated["fulfilled_by"],
        "fulfilled_at": updated["fulfilled_at"],
    }
