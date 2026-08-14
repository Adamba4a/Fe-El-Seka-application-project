from __future__ import annotations

import uuid
from decimal import Decimal

import asyncpg
from fastapi import HTTPException, UploadFile

from app.services import storage_service

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
