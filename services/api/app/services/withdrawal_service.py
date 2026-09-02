from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException

from app.services import audit_service, wallet_service

# withdrawal_requests.amount_egp is NUMERIC(12,2) — same overflow guard
# wallet_topup_service uses for the mirror-image column.
_MAX_AMOUNT_EGP = Decimal("9999999999.99")

# Cash Back must accumulate to this threshold before any withdrawal is allowed
# (post-Spec-028 item 1 — mirrors the retired CAR_MAINTENANCE_THRESHOLD_EGP mechanic,
# now applied to real withdrawable EGP instead of loyalty points).
_MIN_WITHDRAWABLE_BALANCE_EGP = Decimal("1000.00")

_DRIVER_PAGE_SIZE = 20
_ADMIN_PAGE_SIZE = 20


async def _available_balance(conn, driver_id: uuid.UUID) -> Decimal:
    """Withdrawals draw exclusively from sponsored_earnings_egp — never balance_egp,
    which holds the driver's own top-ups (including the promotional free-ride credit)
    and must not be withdrawable."""
    wallet = await wallet_service.get_or_create_wallet(conn, driver_id)
    return Decimal(str(wallet["sponsored_earnings_egp"]))


async def _enqueue_notification(conn, recipient_user_id: uuid.UUID, event_type: str, payload: dict) -> None:
    """Queue a push notification for async dispatch — mirrors
    wallet_topup_service._enqueue_notification (see its docstring for why this
    is a same-transaction row insert rather than a direct send)."""
    await conn.execute(
        "INSERT INTO notification_events (recipient_user_id, event_type, payload) VALUES ($1, $2, $3)",
        recipient_user_id,
        event_type,
        payload,
    )


async def submit_request(
    conn,
    driver_id: uuid.UUID,
    amount_egp,
    payout_reference: str,
) -> dict:
    """T018: create a PENDING withdrawal request (FR-011/FR-012/FR-013)."""
    if amount_egp is None or amount_egp <= 0:
        raise HTTPException(
            status_code=422,
            detail={"error": "validation_error", "message": "amount_egp must be greater than 0.00 EGP"},
        )
    if amount_egp > _MAX_AMOUNT_EGP:
        raise HTTPException(
            status_code=422,
            detail={"error": "validation_error", "message": f"amount_egp must not exceed {_MAX_AMOUNT_EGP} EGP"},
        )
    if not payout_reference or not payout_reference.strip():
        raise HTTPException(
            status_code=422,
            detail={"error": "validation_error", "message": "payout_reference is required"},
        )

    available = await _available_balance(conn, driver_id)
    if available < _MIN_WITHDRAWABLE_BALANCE_EGP:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "below_minimum_threshold",
                "message": (
                    f"You need at least {_MIN_WITHDRAWABLE_BALANCE_EGP} EGP in Cash Back "
                    "before you can withdraw."
                ),
                "minimum_egp": str(_MIN_WITHDRAWABLE_BALANCE_EGP),
            },
        )
    if amount_egp > available:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "insufficient_balance",
                "message": "amount_egp exceeds your available wallet balance",
            },
        )

    existing_pending = await conn.fetchrow(
        """
        SELECT id, amount_egp FROM withdrawal_requests
        WHERE driver_id = $1 AND status = 'PENDING'
        """,
        driver_id,
    )
    if existing_pending:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "pending_request_exists",
                "message": "You already have a withdrawal request awaiting review.",
                "id": str(existing_pending["id"]),
                "amount_egp": str(existing_pending["amount_egp"]),
            },
        )

    row = await conn.fetchrow(
        """
        INSERT INTO withdrawal_requests (driver_id, amount_egp, payout_reference, status)
        VALUES ($1, $2, $3, 'PENDING')
        RETURNING id, status, amount_egp, payout_reference, created_at
        """,
        driver_id,
        amount_egp,
        payout_reference.strip(),
    )

    return {
        "id": row["id"],
        "status": row["status"],
        "amount_egp": row["amount_egp"],
        "payout_reference": row["payout_reference"],
        "created_at": row["created_at"],
    }


async def list_driver_history(conn, driver_id: uuid.UUID, page: int, per_page: int = _DRIVER_PAGE_SIZE) -> dict:
    """T018: the driver's own withdrawal requests (any status), newest-first."""
    per_page = min(per_page, 50)
    offset = (page - 1) * per_page

    rows = await conn.fetch(
        """
        SELECT id, amount_egp, payout_reference, status, rejection_reason, created_at, reviewed_at
        FROM withdrawal_requests
        WHERE driver_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        driver_id,
        per_page,
        offset,
    )
    total = await conn.fetchval(
        "SELECT count(*) FROM withdrawal_requests WHERE driver_id = $1", driver_id
    )
    total = int(total)
    total_pages = max(1, (total + per_page - 1) // per_page)

    items = [
        {
            "id": row["id"],
            "amount_egp": row["amount_egp"],
            "payout_reference": row["payout_reference"],
            "status": row["status"],
            "rejection_reason": row["rejection_reason"],
            "created_at": row["created_at"],
            "reviewed_at": row["reviewed_at"],
        }
        for row in rows
    ]
    return {
        "items": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_entries": total,
            "total_pages": total_pages,
        },
    }


# ── Admin-facing ─────────────────────────────────────────────────────────────

async def list_pending_queue(conn, page: int, limit: int = _ADMIN_PAGE_SIZE) -> dict:
    """T018: PENDING requests oldest-first (FR-016), joined with driver identity."""
    offset = (page - 1) * limit
    rows = await conn.fetch(
        """
        SELECT r.id, r.driver_id, p.display_name AS driver_name, p.email AS driver_email,
               r.amount_egp, r.payout_reference, r.created_at
        FROM withdrawal_requests r
        JOIN profiles p ON p.id = r.driver_id
        WHERE r.status = 'PENDING'
        ORDER BY r.created_at ASC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )
    total = await conn.fetchval("SELECT count(*) FROM withdrawal_requests WHERE status = 'PENDING'")
    items = [
        {
            "id": row["id"],
            "driver_id": row["driver_id"],
            "driver_name": row["driver_name"],
            "driver_email": row["driver_email"],
            "amount_egp": row["amount_egp"],
            "payout_reference": row["payout_reference"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return {"total": int(total), "page": page, "items": items}


async def approve_request(conn, request_id: uuid.UUID, admin_id: uuid.UUID) -> dict:
    """T018: approve a PENDING request — re-validates available balance under the
    wallet's row lock at approval time (research.md §10, FR-014); `409
    insufficient_balance_at_approval` if it no longer covers the amount."""
    async with conn.transaction():
        row = await conn.fetchrow(
            "SELECT id, driver_id, amount_egp, status FROM withdrawal_requests WHERE id = $1 FOR UPDATE",
            request_id,
        )
        if row is None:
            raise HTTPException(
                status_code=404, detail={"error": "not_found", "message": "Withdrawal request not found"}
            )
        if row["status"] != "PENDING":
            raise HTTPException(status_code=409, detail={"error": "conflict", "message": "Request already reviewed"})

        driver_id = row["driver_id"]
        amount = row["amount_egp"]

        wallet = await wallet_service.get_wallet_with_lock(conn, driver_id)
        available = Decimal(str(wallet["sponsored_earnings_egp"]))
        if Decimal(str(amount)) > available:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "insufficient_balance_at_approval",
                    "message": "The driver's available sponsored earnings no longer cover this withdrawal.",
                },
            )

        await wallet_service.decrement_sponsored_earnings(conn, wallet["id"], amount)
        entry = await wallet_service.insert_ledger_entry(
            conn,
            wallet_id=wallet["id"],
            driver_id=driver_id,
            entry_type="WITHDRAWAL_DEBIT",
            amount=amount,
            created_by=admin_id,
            note=f"withdrawal_request:{request_id}",
        )

        reviewed = await conn.fetchrow(
            """
            UPDATE withdrawal_requests
            SET status = 'APPROVED', reviewed_by = $2, reviewed_at = now(), ledger_entry_id = $3
            WHERE id = $1
            RETURNING id, status, reviewed_by, reviewed_at
            """,
            request_id,
            admin_id,
            entry["id"],
        )
        await _enqueue_notification(
            conn,
            driver_id,
            "withdrawal_approved",
            {"request_id": str(request_id), "amount_egp": str(amount)},
        )

    new_balance_egp = Decimal(str(wallet["sponsored_earnings_egp"])) - Decimal(str(amount))

    audit_service.append_log(
        str(admin_id), "approved", str(driver_id), withdrawal_request_id=str(request_id)
    )

    return {
        "id": reviewed["id"],
        "status": reviewed["status"],
        "ledger_entry_id": entry["id"],
        "new_balance_egp": new_balance_egp,
        "reviewed_by": reviewed["reviewed_by"],
        "reviewed_at": reviewed["reviewed_at"],
    }


async def reject_request(conn, request_id: uuid.UUID, admin_id: uuid.UUID, reason: str) -> dict:
    """T018: reject a PENDING request with a mandatory reason (FR-014)."""
    if not reason or not reason.strip():
        raise HTTPException(status_code=422, detail={"error": "validation_error", "message": "reason is required"})
    reason = reason.strip()

    async with conn.transaction():
        row = await conn.fetchrow(
            "SELECT id, driver_id, status FROM withdrawal_requests WHERE id = $1 FOR UPDATE",
            request_id,
        )
        if row is None:
            raise HTTPException(
                status_code=404, detail={"error": "not_found", "message": "Withdrawal request not found"}
            )
        if row["status"] != "PENDING":
            raise HTTPException(status_code=409, detail={"error": "conflict", "message": "Request already reviewed"})

        driver_id = row["driver_id"]

        reviewed = await conn.fetchrow(
            """
            UPDATE withdrawal_requests
            SET status = 'REJECTED', rejection_reason = $2, reviewed_by = $3, reviewed_at = now()
            WHERE id = $1
            RETURNING id, status, rejection_reason, reviewed_by, reviewed_at
            """,
            request_id,
            reason,
            admin_id,
        )

        await _enqueue_notification(
            conn,
            driver_id,
            "withdrawal_rejected",
            {"request_id": str(request_id), "reason": reason},
        )

    audit_service.append_log(
        str(admin_id), "rejected", str(driver_id), withdrawal_request_id=str(request_id), reason=reason
    )

    return {
        "id": reviewed["id"],
        "status": reviewed["status"],
        "rejection_reason": reviewed["rejection_reason"],
        "reviewed_by": reviewed["reviewed_by"],
        "reviewed_at": reviewed["reviewed_at"],
    }


async def list_review_history(
    conn, page: int, outcome: str | None = None, q: str | None = None, limit: int = _ADMIN_PAGE_SIZE
) -> dict:
    """T018: reviewed (APPROVED/REJECTED) requests, newest-first, with optional
    outcome/name-or-email filters — mirrors wallet_topup_service.list_review_history."""
    if outcome is not None and outcome not in ("APPROVED", "REJECTED"):
        raise HTTPException(
            status_code=422,
            detail={"error": "validation_error", "message": "outcome must be APPROVED or REJECTED"},
        )

    offset = (page - 1) * limit
    conditions = ["r.status IN ('APPROVED', 'REJECTED')"]
    params: list = []

    if outcome:
        params.append(outcome)
        conditions.append(f"r.status = ${len(params)}")
    if q:
        params.append(f"%{q}%")
        conditions.append(f"(p.display_name ILIKE ${len(params)} OR p.email ILIKE ${len(params)})")

    where_clause = " AND ".join(conditions)

    total = await conn.fetchval(
        f"""
        SELECT count(*)
        FROM withdrawal_requests r
        JOIN profiles p ON p.id = r.driver_id
        WHERE {where_clause}
        """,
        *params,
    )

    params_with_paging = [*params, limit, offset]
    rows = await conn.fetch(
        f"""
        SELECT r.id, r.driver_id, p.display_name AS driver_name, r.amount_egp, r.status,
               r.rejection_reason, r.reviewed_by, r.reviewed_at
        FROM withdrawal_requests r
        JOIN profiles p ON p.id = r.driver_id
        WHERE {where_clause}
        ORDER BY r.reviewed_at DESC
        LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
        """,
        *params_with_paging,
    )

    items = [
        {
            "request_id": row["id"],
            "driver_id": row["driver_id"],
            "driver_name": row["driver_name"],
            "amount_egp": row["amount_egp"],
            "status": row["status"],
            "rejection_reason": row["rejection_reason"],
            "reviewed_by": row["reviewed_by"],
            "reviewed_at": row["reviewed_at"],
        }
        for row in rows
    ]
    return {"total": int(total), "page": page, "items": items}
