from __future__ import annotations

import logging
import time
import uuid
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Wallet read / upsert
# ─────────────────────────────────────────────────────────────────────────────

_WALLET_COLS = "id, driver_id, balance_egp, reserved_egp, created_at, updated_at"


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
