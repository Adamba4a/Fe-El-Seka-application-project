from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException

from app.services import audit_service, wallet_service

# Once a driver's accumulated car_maintenance_savings_egp (funded entirely by the
# 0.3 EGP/km distance fee — see commission_service.py) reaches this threshold, a
# car_maintenance_rewards row is created and the counter resets to 0.00.
CAR_MAINTENANCE_THRESHOLD_EGP = Decimal("3000.00")


async def accumulate_and_maybe_grant(
    conn,
    driver_id: uuid.UUID,
    wallet_id: uuid.UUID,
    distance_fee_amount: Decimal,
) -> None:
    """Add distance_fee_amount to the driver's savings counter; grant a reward and
    reset to 0.00 for each threshold crossed.

    MUST be called inside the same transaction as the wallet debit, with the wallet
    row already locked via get_wallet_with_lock() (commission_service.deduct_commission
    does both before calling this).
    """
    if distance_fee_amount <= Decimal("0"):
        return

    new_total = await wallet_service.increment_car_maintenance_savings(
        conn, wallet_id, distance_fee_amount
    )

    while new_total >= CAR_MAINTENANCE_THRESHOLD_EGP:
        reward = await conn.fetchrow(
            """
            INSERT INTO car_maintenance_rewards (driver_id, wallet_id, amount_egp)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            driver_id,
            wallet_id,
            CAR_MAINTENANCE_THRESHOLD_EGP,
        )
        await wallet_service.reset_car_maintenance_savings(conn, wallet_id)
        new_total = new_total - CAR_MAINTENANCE_THRESHOLD_EGP
        await conn.execute(
            "INSERT INTO notification_events (recipient_user_id, event_type, payload) VALUES ($1, $2, $3)",
            driver_id,
            "car_maintenance_earned",
            {"reward_id": str(reward["id"]), "amount_egp": str(CAR_MAINTENANCE_THRESHOLD_EGP)},
        )


# ── Admin-facing ────────────────────────────────────────────────────────────

_ADMIN_PAGE_SIZE = 20


async def list_pending_queue(conn, page: int, limit: int = _ADMIN_PAGE_SIZE) -> dict:
    """PENDING rewards oldest-first, joined with driver identity."""
    offset = (page - 1) * limit
    rows = await conn.fetch(
        """
        SELECT r.id, r.driver_id, p.display_name AS driver_name, p.email AS driver_email,
               r.amount_egp, r.reached_at
        FROM car_maintenance_rewards r
        JOIN profiles p ON p.id = r.driver_id
        WHERE r.status = 'PENDING'
        ORDER BY r.reached_at ASC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )
    total = await conn.fetchval("SELECT count(*) FROM car_maintenance_rewards WHERE status = 'PENDING'")
    items = [
        {
            "id": row["id"],
            "driver_id": row["driver_id"],
            "driver_name": row["driver_name"],
            "driver_email": row["driver_email"],
            "amount_egp": row["amount_egp"],
            "reached_at": row["reached_at"],
        }
        for row in rows
    ]
    return {"total": int(total), "page": page, "items": items}


async def fulfill_reward(conn, reward_id: uuid.UUID, admin_id: uuid.UUID) -> dict:
    """Mark a PENDING reward FULFILLED after the admin has arranged the free car
    maintenance offline. No wallet or ledger mutation — the driver was never
    credited money for this, it's a service, not a payout."""
    async with conn.transaction():
        row = await conn.fetchrow(
            "SELECT id, driver_id, status FROM car_maintenance_rewards WHERE id = $1 FOR UPDATE",
            reward_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Reward not found"})
        if row["status"] != "PENDING":
            raise HTTPException(status_code=409, detail={"error": "conflict", "message": "Reward already fulfilled"})

        driver_id = row["driver_id"]

        updated = await conn.fetchrow(
            """
            UPDATE car_maintenance_rewards
            SET status = 'FULFILLED', fulfilled_by = $2, fulfilled_at = now()
            WHERE id = $1
            RETURNING id, status, fulfilled_by, fulfilled_at
            """,
            reward_id,
            admin_id,
        )

    audit_service.append_log(
        str(admin_id), "approved", str(driver_id), car_maintenance_reward_id=str(reward_id)
    )

    return {
        "id": updated["id"],
        "status": updated["status"],
        "fulfilled_by": updated["fulfilled_by"],
        "fulfilled_at": updated["fulfilled_at"],
    }
