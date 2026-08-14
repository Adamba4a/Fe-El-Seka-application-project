from __future__ import annotations

import uuid
from decimal import Decimal

import asyncpg
from fastapi import HTTPException, UploadFile

from app.services import audit_service, storage_service, wallet_service

_DEFAULT_VODAFONE_CASH_NUMBER = "VODAFONE_CASH_NUMBER_NOT_CONFIGURED"
_DEFAULT_SUPPORT_EMAIL = "support@felseka.com"

_ALLOWED_TYPES = {"image/jpeg", "image/png"}
_MAX_SCREENSHOT_BYTES = 10 * 1024 * 1024  # 10 MB
# wallet_topup_requests.amount_egp is NUMERIC(12,2) — 10 digits before the
# decimal point, 2 after. Enforced in app code so an oversized amount comes
# back as a clean 422 instead of an unhandled Postgres numeric overflow 500.
_MAX_AMOUNT_EGP = Decimal("9999999999.99")


async def _get_vodafone_cash_number(conn) -> str:
    """Return the platform's Vodafone Cash number from platform_settings.

    Mirrors verification_service._get_support_email(): same table, same
    fallback-if-missing behavior.
    """
    row = await conn.fetchrow(
        "SELECT value FROM platform_settings WHERE key = $1",
        "vodafone_cash_number",
    )
    return row["value"] if row else _DEFAULT_VODAFONE_CASH_NUMBER


async def _get_support_email(conn) -> str:
    row = await conn.fetchrow(
        "SELECT value FROM platform_settings WHERE key = $1",
        "support_email",
    )
    return row["value"] if row else _DEFAULT_SUPPORT_EMAIL


async def _is_topup_locked(conn, driver_id: uuid.UUID) -> bool:
    row = await conn.fetchrow(
        "SELECT is_topup_locked FROM profiles WHERE id = $1",
        driver_id,
    )
    return bool(row["is_topup_locked"]) if row else False


async def _rejected_count_since_reset(conn, driver_id: uuid.UUID) -> int:
    """Count REJECTED requests since the driver's last topup_lock_reset_at
    (or since account creation, if never reset) — see research.md §5."""
    count = await conn.fetchval(
        """
        SELECT count(*)
        FROM wallet_topup_requests
        WHERE driver_id = $1
          AND status = 'REJECTED'
          AND created_at > COALESCE(
              (SELECT topup_lock_reset_at FROM profiles WHERE id = $1),
              '-infinity'
          )
        """,
        driver_id,
    )
    return int(count)


async def get_settings(conn, driver_id: uuid.UUID) -> dict:
    """T011: settings for the top-up request form.

    Returns is_locked/support_email alongside the Vodafone Cash number so the
    frontend can gate the form before the driver picks a screenshot, not only
    after a full submission (post-review fix, see data-model.md §4).
    """
    vodafone_cash_number = await _get_vodafone_cash_number(conn)
    is_locked = await _is_topup_locked(conn, driver_id)
    support_email = await _get_support_email(conn) if is_locked else None
    return {
        "vodafone_cash_number": vodafone_cash_number,
        "is_locked": is_locked,
        "support_email": support_email,
    }


async def _validate_and_read_screenshot(file: UploadFile) -> bytes:
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "message": "Screenshot must be JPEG or PNG",
            },
        )
    data = await file.read()
    if len(data) > _MAX_SCREENSHOT_BYTES:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "message": "Screenshot must be under 10 MB",
            },
        )
    if not data:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "message": "Screenshot file is empty",
            },
        )
    return data


async def submit_request(
    conn,
    driver_id: uuid.UUID,
    amount_egp,
    payment_reference: str,
    screenshot_file: UploadFile,
) -> dict:
    """T012: create a PENDING top-up request (FR-002/FR-003/FR-004/FR-005).

    Unlike verification_service.submit_documents, storage upload happens
    BEFORE the DB insert here: a REJECTED wallet_topup_requests row counts
    against the driver's 3-attempt submission-lock cap (FR-014/FR-015), so a
    PENDING row created before a failed upload would leave the driver with a
    broken/missing screenshot that an admin will likely reject through no
    fault of the driver's — unfairly burning one of their 3 attempts. A
    storage failure with no DB row yet is comparatively harmless (at worst an
    orphaned object with no corresponding row) and simply surfaces as a clean
    error the driver can retry.
    """
    if amount_egp is None or amount_egp <= 0:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "message": "amount_egp must be greater than 0.00 EGP",
            },
        )
    if amount_egp > _MAX_AMOUNT_EGP:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "message": f"amount_egp must not exceed {_MAX_AMOUNT_EGP} EGP",
            },
        )
    if not payment_reference or not payment_reference.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "message": "payment_reference is required",
            },
        )

    if await _is_topup_locked(conn, driver_id):
        support_email = await _get_support_email(conn)
        raise HTTPException(
            status_code=403,
            detail={
                "error": "submission_locked",
                "message": (
                    "You have exhausted all top-up attempts."
                    f" Please contact us at {support_email} for a manual review."
                ),
                "support_email": support_email,
            },
        )

    existing_pending = await conn.fetchrow(
        """
        SELECT id, amount_egp FROM wallet_topup_requests
        WHERE driver_id = $1 AND status = 'PENDING'
        """,
        driver_id,
    )
    if existing_pending:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "pending_request_exists",
                "message": "You already have a top-up request awaiting review.",
                "id": str(existing_pending["id"]),
                "amount_egp": str(existing_pending["amount_egp"]),
            },
        )

    screenshot_data = await _validate_and_read_screenshot(screenshot_file)

    request_id = uuid.uuid4()
    ext = "jpg" if screenshot_file.content_type == "image/jpeg" else "png"
    screenshot_path = f"{driver_id}/{request_id}.{ext}"

    # Upload before inserting the row (see docstring): a storage failure here
    # leaves at most an orphaned object, never a PENDING row with a broken
    # screenshot that would unfairly cost the driver a rejection-cap attempt.
    storage_service.upload_file(
        "topup-proofs",
        screenshot_path,
        screenshot_data,
        screenshot_file.content_type,
    )

    try:
        row = await conn.fetchrow(
            """
            INSERT INTO wallet_topup_requests
                (id, driver_id, amount_egp, payment_reference, screenshot_path, status)
            VALUES ($1, $2, $3, $4, $5, 'PENDING')
            RETURNING id, status, amount_egp, payment_reference, created_at
            """,
            request_id,
            driver_id,
            amount_egp,
            payment_reference.strip(),
            screenshot_path,
        )
    except asyncpg.UniqueViolationError as exc:
        constraint = getattr(exc, "constraint_name", "") or ""
        if constraint == "uq_topup_reference_active":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "duplicate_payment_reference",
                    "error_code": "DUPLICATE_PAYMENT_REFERENCE",
                    "message": "This payment reference has already been submitted.",
                },
            ) from exc
        raise HTTPException(
            status_code=409,
            detail={
                "error": "pending_request_exists",
                "message": "You already have a top-up request awaiting review.",
            },
        ) from exc

    return {
        "id": row["id"],
        "status": row["status"],
        "amount_egp": row["amount_egp"],
        "payment_reference": row["payment_reference"],
        "created_at": row["created_at"],
    }


# ── Admin-facing (US2) ─────────────────────────────────────────────────────
#
# `profiles` has no phone-number column (its original `phone_number` column
# was renamed to `email` in migration 20260616000001, before this feature was
# designed) — contracts/api.md and tasks.md T018/T024/T025 describe a
# `driver_phone` field that doesn't exist in the schema. Every other admin
# queue in this codebase (verification_router's AdminQueueResponse) already
# identifies drivers by `email`, so AdminTopupQueueItem/AdminTopupHistoryItem
# use `driver_email` here instead — same deviation pattern as T014's `/api`
# routing prefix fix.

_ADMIN_PAGE_SIZE = 20


async def _enqueue_notification(conn, recipient_user_id: uuid.UUID, event_type: str, payload: dict) -> None:
    """Queue a push notification for async dispatch (mirrors moderation_service's
    helper). MUST be called inside the same conn.transaction() as the state
    change it announces: a direct `await fcm_service.send_push_notifications(...)`
    after commit would let a Firebase/network failure turn an already-successful
    approve/reject into a 500 for the admin, who'd then hit 409 on retry — this
    row-insert is a local, non-network write that commits atomically with the
    approval/rejection, and notification_dispatcher_loop (already running as a
    background task, see main.py) delivers and retries it independently."""
    await conn.execute(
        "INSERT INTO notification_events (recipient_user_id, event_type, payload) VALUES ($1, $2, $3)",
        recipient_user_id,
        event_type,
        payload,
    )


async def list_pending_queue(conn, page: int, limit: int = _ADMIN_PAGE_SIZE) -> dict:
    """T018: PENDING requests oldest-first (FR-008), joined with driver identity,
    with a signed screenshot URL per item."""
    offset = (page - 1) * limit
    rows = await conn.fetch(
        """
        SELECT r.id, r.driver_id, p.display_name AS driver_name, p.email AS driver_email,
               r.amount_egp, r.payment_reference, r.screenshot_path, r.created_at
        FROM wallet_topup_requests r
        JOIN profiles p ON p.id = r.driver_id
        WHERE r.status = 'PENDING'
        ORDER BY r.created_at ASC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )
    total = await conn.fetchval("SELECT count(*) FROM wallet_topup_requests WHERE status = 'PENDING'")
    items = [
        {
            "id": row["id"],
            "driver_id": row["driver_id"],
            "driver_name": row["driver_name"],
            "driver_email": row["driver_email"],
            "amount_egp": row["amount_egp"],
            "payment_reference": row["payment_reference"],
            "screenshot_url": storage_service.generate_signed_url("topup-proofs", row["screenshot_path"]) or "",
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return {"total": int(total), "page": page, "items": items}


async def approve_request(conn, request_id: uuid.UUID, admin_id: uuid.UUID) -> dict:
    """T019: approve a PENDING request, crediting the wallet exactly once via the
    same wallet_service calls api/admin/wallet_router.py's topup_wallet uses
    (FR-009, NFR-006), and resetting the driver's rejection cycle (FR-014)."""
    async with conn.transaction():
        row = await conn.fetchrow(
            "SELECT id, driver_id, amount_egp, status FROM wallet_topup_requests WHERE id = $1 FOR UPDATE",
            request_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Top-up request not found"})
        if row["status"] != "PENDING":
            raise HTTPException(status_code=409, detail={"error": "conflict", "message": "Request already reviewed"})

        driver_id = row["driver_id"]
        amount = row["amount_egp"]

        wallet = await wallet_service.get_wallet_with_lock(conn, driver_id)
        await wallet_service.increment_balance(conn, wallet["id"], amount)
        entry = await wallet_service.insert_ledger_entry(
            conn,
            wallet_id=wallet["id"],
            driver_id=driver_id,
            entry_type="ADMIN_CREDIT",
            amount=amount,
            created_by=admin_id,
            note=f"wallet_topup_request:{request_id}",
        )

        reviewed = await conn.fetchrow(
            """
            UPDATE wallet_topup_requests
            SET status = 'APPROVED', reviewed_by = $2, reviewed_at = now(), ledger_entry_id = $3
            WHERE id = $1
            RETURNING id, status, reviewed_by, reviewed_at
            """,
            request_id,
            admin_id,
            entry["id"],
        )
        await conn.execute(
            "UPDATE profiles SET topup_lock_reset_at = now() WHERE id = $1",
            driver_id,
        )
        await _enqueue_notification(
            conn,
            driver_id,
            "wallet_topup_approved",
            {"request_id": str(request_id), "amount_egp": str(amount)},
        )

    new_balance_egp = Decimal(str(wallet["balance_egp"])) + Decimal(str(amount))

    audit_service.append_log(
        str(admin_id), "approved", str(driver_id), topup_request_id=str(request_id)
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
    """T020: reject a PENDING request with a mandatory reason (FR-010); locks the
    driver out of resubmission on their 3rd rejection since the last reset (FR-014)."""
    if not reason or not reason.strip():
        raise HTTPException(status_code=422, detail={"error": "validation_error", "message": "reason is required"})
    reason = reason.strip()

    driver_locked = False
    async with conn.transaction():
        row = await conn.fetchrow(
            "SELECT id, driver_id, status FROM wallet_topup_requests WHERE id = $1 FOR UPDATE",
            request_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Top-up request not found"})
        if row["status"] != "PENDING":
            raise HTTPException(status_code=409, detail={"error": "conflict", "message": "Request already reviewed"})

        driver_id = row["driver_id"]

        reviewed = await conn.fetchrow(
            """
            UPDATE wallet_topup_requests
            SET status = 'REJECTED', rejection_reason = $2, reviewed_by = $3, reviewed_at = now()
            WHERE id = $1
            RETURNING id, status, rejection_reason, reviewed_by, reviewed_at
            """,
            request_id,
            reason,
            admin_id,
        )

        rejected_count = await _rejected_count_since_reset(conn, driver_id)
        if rejected_count >= 3:
            driver_locked = True
            await conn.execute("UPDATE profiles SET is_topup_locked = TRUE WHERE id = $1", driver_id)

        await _enqueue_notification(
            conn,
            driver_id,
            "wallet_topup_rejected",
            {"request_id": str(request_id), "reason": reason},
        )

    audit_service.append_log(
        str(admin_id), "rejected", str(driver_id), topup_request_id=str(request_id), reason=reason
    )

    return {
        "id": reviewed["id"],
        "status": reviewed["status"],
        "rejection_reason": reviewed["rejection_reason"],
        "reviewed_by": reviewed["reviewed_by"],
        "reviewed_at": reviewed["reviewed_at"],
        "driver_locked": driver_locked,
    }


async def list_review_history(
    conn, page: int, outcome: str | None = None, q: str | None = None, limit: int = _ADMIN_PAGE_SIZE
) -> dict:
    """T021: reviewed (APPROVED/REJECTED) requests, newest-first, with optional
    outcome/name-or-email filters."""
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
        FROM wallet_topup_requests r
        JOIN profiles p ON p.id = r.driver_id
        WHERE {where_clause}
        """,
        *params,
    )

    params_with_paging = [*params, limit, offset]
    rows = await conn.fetch(
        f"""
        SELECT r.id, r.driver_id, p.display_name AS driver_name, r.amount_egp, r.status,
               r.rejection_reason, r.reviewed_by, r.reviewed_at, p.is_topup_locked AS driver_is_locked
        FROM wallet_topup_requests r
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
            "driver_is_locked": bool(row["driver_is_locked"]),
        }
        for row in rows
    ]
    return {"total": int(total), "page": page, "items": items}


async def unlock_driver(conn, driver_id: uuid.UUID, admin_id: uuid.UUID) -> dict:
    """T021: clear a driver's 3-rejection submission lock (FR-016) and reset
    their rejection cycle so past REJECTED rows stop counting toward the cap."""
    row = await conn.fetchrow("SELECT is_topup_locked FROM profiles WHERE id = $1", driver_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Driver not found"})
    if not row["is_topup_locked"]:
        raise HTTPException(status_code=409, detail={"error": "conflict", "message": "Driver is not locked"})

    await conn.execute(
        "UPDATE profiles SET is_topup_locked = FALSE, topup_lock_reset_at = now() WHERE id = $1",
        driver_id,
    )
    audit_service.append_log(str(admin_id), "unlocked", str(driver_id))

    return {"driver_id": driver_id, "is_topup_locked": False}
