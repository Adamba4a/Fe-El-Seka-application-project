from __future__ import annotations

import logging
import time
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Wallet read / upsert
# ─────────────────────────────────────────────────────────────────────────────

_WALLET_COLS = (
    "id, driver_id, balance_egp, reserved_egp, sponsored_earnings_egp, "
    "cash_back_points_egp, car_maintenance_savings_egp, created_at, updated_at"
)


async def get_or_create_wallet(conn, driver_id: uuid.UUID) -> dict:
    """Return the driver's wallet row, creating it (balance 0.00) if absent."""
    await conn.execute(
        "INSERT INTO driver_wallets (driver_id) VALUES ($1) ON CONFLICT (driver_id) DO NOTHING",
        driver_id,
    )
    row = await conn.fetchrow(
        f"SELECT {_WALLET_COLS} FROM driver_wallets WHERE driver_id = $1",
        driver_id,
    )
    return dict(row)


async def get_wallet_with_lock(conn, driver_id: uuid.UUID) -> dict:
    """Return the driver's wallet row under SELECT ... FOR UPDATE.

    Creates the row first if absent, then locks it.
    MUST be called inside an active transaction — the lock is released on commit/rollback.
    Use for all balance-mutating operations (commission deduction, reservation, admin writes).
    """
    await conn.execute(
        "INSERT INTO driver_wallets (driver_id) VALUES ($1) ON CONFLICT (driver_id) DO NOTHING",
        driver_id,
    )
    row = await conn.fetchrow(
        f"SELECT {_WALLET_COLS} FROM driver_wallets WHERE driver_id = $1 FOR UPDATE",
        driver_id,
    )
    return dict(row)


# ─────────────────────────────────────────────────────────────────────────────
# Balance mutations
# All functions below MUST be called inside an active transaction with the
# wallet row already locked via get_wallet_with_lock().
# ─────────────────────────────────────────────────────────────────────────────

async def increment_balance(conn, wallet_id: uuid.UUID, amount: Decimal) -> None:
    await conn.execute(
        "UPDATE driver_wallets SET balance_egp = balance_egp + $2, updated_at = now() WHERE id = $1",
        wallet_id,
        amount,
    )


async def decrement_balance(conn, wallet_id: uuid.UUID, amount: Decimal) -> None:
    """Subtract amount from balance_egp. Balance may go negative (FR-009 — balance enforcement
    only gates ride creation, not ride completion)."""
    await conn.execute(
        "UPDATE driver_wallets SET balance_egp = balance_egp - $2, updated_at = now() WHERE id = $1",
        wallet_id,
        amount,
    )


async def increment_reserved(conn, wallet_id: uuid.UUID, amount: Decimal) -> None:
    await conn.execute(
        "UPDATE driver_wallets SET reserved_egp = reserved_egp + $2, updated_at = now() WHERE id = $1",
        wallet_id,
        amount,
    )


async def decrement_reserved(conn, wallet_id: uuid.UUID, amount: Decimal) -> None:
    """Subtract amount from reserved_egp. GREATEST(..., 0) guards the DB CHECK constraint
    against floating-point drift — commission_service should always pass the exact amount."""
    await conn.execute(
        "UPDATE driver_wallets SET reserved_egp = GREATEST(reserved_egp - $2, 0), updated_at = now() WHERE id = $1",
        wallet_id,
        amount,
    )


async def increment_sponsored_earnings(conn, wallet_id: uuid.UUID, amount: Decimal) -> None:
    """Credit sponsored_earnings_egp — the ONLY pool withdrawal requests may draw from.
    Kept separate from balance_egp so a driver can never withdraw self-funded top-ups
    (including the promotional free-ride credit). Only touched by redeem_cash_back_points
    and withdrawal approval — all Cash Back earning events credit cash_back_points_egp
    instead (see increment_cash_back_points)."""
    await conn.execute(
        "UPDATE driver_wallets SET sponsored_earnings_egp = sponsored_earnings_egp + $2, "
        "updated_at = now() WHERE id = $1",
        wallet_id,
        amount,
    )


async def decrement_sponsored_earnings(conn, wallet_id: uuid.UUID, amount: Decimal) -> None:
    """Subtract amount from sponsored_earnings_egp. GREATEST(..., 0) guards the DB CHECK
    constraint against floating-point drift on booking-cancellation reversals."""
    await conn.execute(
        "UPDATE driver_wallets SET sponsored_earnings_egp = GREATEST(sponsored_earnings_egp - $2, 0), "
        "updated_at = now() WHERE id = $1",
        wallet_id,
        amount,
    )


async def increment_cash_back_points(conn, wallet_id: uuid.UUID, amount: Decimal) -> None:
    """Credit cash_back_points_egp (1 pt = 1 EGP) — every Cash Back earning event
    (sponsored ride settlement, distance-fee share, points-discount reimbursement)
    lands here first. Not withdrawable until redeemed into sponsored_earnings_egp
    via redeem_cash_back_points."""
    await conn.execute(
        "UPDATE driver_wallets SET cash_back_points_egp = cash_back_points_egp + $2, "
        "updated_at = now() WHERE id = $1",
        wallet_id,
        amount,
    )


async def decrement_cash_back_points(conn, wallet_id: uuid.UUID, amount: Decimal) -> None:
    """Subtract amount from cash_back_points_egp. GREATEST(..., 0) guards the DB CHECK
    constraint — a driver may have already redeemed some of the points being clawed
    back on a booking-cancellation reversal."""
    await conn.execute(
        "UPDATE driver_wallets SET cash_back_points_egp = GREATEST(cash_back_points_egp - $2, 0), "
        "updated_at = now() WHERE id = $1",
        wallet_id,
        amount,
    )


async def redeem_cash_back_points(conn, driver_id: uuid.UUID, amount: Decimal) -> dict:
    """Move `amount` from cash_back_points_egp into the withdrawable sponsored_earnings_egp
    pool, logging a single CASH_BACK_REDEEMED ledger entry. Must be called outside any
    caller-held transaction — opens its own so the wallet lock scope stays minimal."""
    async with conn.transaction():
        wallet = await get_wallet_with_lock(conn, driver_id)
        available = Decimal(str(wallet["cash_back_points_egp"]))
        if amount <= 0:
            raise HTTPException(
                status_code=422,
                detail={"error": "validation_error", "message": "amount must be greater than 0.00"},
            )
        if amount > available:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "insufficient_points",
                    "message": "amount exceeds your available Cash Back points balance",
                },
            )
        await decrement_cash_back_points(conn, wallet["id"], amount)
        await increment_sponsored_earnings(conn, wallet["id"], amount)
        entry = await insert_ledger_entry(
            conn,
            wallet["id"],
            driver_id,
            "CASH_BACK_REDEEMED",
            amount,
            note="Redeemed Cash Back points to withdrawable cash",
        )
        entry["cash_back_points_egp"] = available - amount
        entry["sponsored_earnings_egp"] = Decimal(str(wallet["sponsored_earnings_egp"])) + amount
    return entry


# ─────────────────────────────────────────────────────────────────────────────
# Ledger
# ─────────────────────────────────────────────────────────────────────────────

async def insert_ledger_entry(
    conn,
    wallet_id: uuid.UUID,
    driver_id: uuid.UUID,
    entry_type: str,
    amount: Decimal,
    *,
    ride_id: Optional[uuid.UUID] = None,
    booking_id: Optional[uuid.UUID] = None,
    fuel_cost_egp_snapshot: Optional[Decimal] = None,
    created_by: Optional[uuid.UUID] = None,
    note: Optional[str] = None,
) -> dict:
    """Insert an immutable COMMISSION_DEBIT, ADMIN_CREDIT, or ADMIN_DEBIT entry.
    Returns the created row as a dict."""
    _start = time.monotonic()
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO driver_ledger_entries
                (wallet_id, driver_id, type, amount_egp, ride_id, booking_id,
                 fuel_cost_egp_snapshot, created_by, note)
            VALUES ($1, $2, $3::ledger_entry_type, $4, $5, $6, $7, $8, $9)
            RETURNING id, wallet_id, driver_id, type, amount_egp, ride_id, booking_id,
                      fuel_cost_egp_snapshot, created_by, note, created_at
            """,
            wallet_id,
            driver_id,
            entry_type,
            amount,
            ride_id,
            booking_id,
            fuel_cost_egp_snapshot,
            created_by,
            note,
        )
    except Exception as exc:
        _ms = round((time.monotonic() - _start) * 1000)
        logger.error(
            "event=wallet_write operation=%s driver_id=%s amount_egp=%s "
            "ride_id=%s booking_id=%s admin_actor_id=%s duration_ms=%d error=%s",
            entry_type, driver_id, amount, ride_id, booking_id, created_by, _ms, exc,
        )
        raise
    _ms = round((time.monotonic() - _start) * 1000)
    logger.info(
        "event=wallet_write operation=%s driver_id=%s amount_egp=%s "
        "ride_id=%s booking_id=%s admin_actor_id=%s duration_ms=%d error=null",
        entry_type, driver_id, amount, ride_id, booking_id, created_by, _ms,
    )
    return dict(row)


async def get_ledger_page(
    conn,
    driver_id: uuid.UUID,
    page: int,
    per_page: int = 50,
) -> tuple[list[dict], int]:
    """Return (entries, total_count) for the driver's ledger, newest-first, paginated."""
    per_page = min(per_page, 50)
    offset = (page - 1) * per_page

    rows = await conn.fetch(
        """
        SELECT id, type, amount_egp, ride_id, booking_id,
               fuel_cost_egp_snapshot, created_by, note, created_at
        FROM driver_ledger_entries
        WHERE driver_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        driver_id,
        per_page,
        offset,
    )
    total = await conn.fetchval(
        "SELECT COUNT(*) FROM driver_ledger_entries WHERE driver_id = $1",
        driver_id,
    )
    return [dict(r) for r in rows], int(total)
