from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.database import get_pool
from app.models.org_access import (
    OrgAccessConfirm,
    OrgAccessConfirmResponse,
    OrgAccessRequest,
    OrgAccessRequestResponse,
)
from app.services import notification_service
from app.services.domain_verification_service import (
    _check_domain_otp_resend_rate,
    _generate_otp,
    _get_domain_blocklist,
    _hash_otp,
)

# ── T009 support: request an org-email verification OTP (no group intent) ──

async def request_verification(profile: dict, payload: OrgAccessRequest) -> OrgAccessRequestResponse:
    user_id = uuid.UUID(str(profile["id"]))

    email = payload.email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_email", "message": "Enter a valid email address."},
        )
    domain = email.rsplit("@", 1)[1]

    pool = get_pool()
    async with pool.acquire() as conn:
        blocklist = await _get_domain_blocklist(conn)
        if domain in blocklist:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "blocklisted_domain",
                    "message": "Please use your work or school email, not a personal email address.",
                },
            )

        _check_domain_otp_resend_rate(email)

        code = _generate_otp()
        salt = secrets.token_hex(16)
        otp_hash = f"{salt}${_hash_otp(code, salt)}"

        row = await conn.fetchrow(
            """
            INSERT INTO domain_verifications
                (user_id, email, domain, requested_group_type, otp_code_hash, otp_expires_at, is_first_for_domain)
            VALUES ($1, $2, $3, NULL, $4, now() + interval '5 minutes', false)
            RETURNING id
            """,
            user_id, email, domain, otp_hash,
        )

    try:
        await notification_service.send_domain_verification_email(email, code)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "otp_send_failed",
                "message": "Could not send the verification code. Try again.",
            },
        )

    return OrgAccessRequestResponse(verification_id=str(row["id"]), expires_in_seconds=300)


# ── T009 support: confirm the OTP and set profiles.org_verified_at ─────────

async def confirm_verification(profile: dict, payload: OrgAccessConfirm) -> OrgAccessConfirmResponse:
    user_id = uuid.UUID(str(profile["id"]))
    try:
        verification_id = uuid.UUID(payload.verification_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error": "otp_invalid", "message": "Incorrect code."},
        )

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            verification = await conn.fetchrow(
                """
                SELECT id, email, domain, otp_code_hash, otp_expires_at, verified_at
                FROM domain_verifications
                WHERE id = $1 AND user_id = $2
                FOR UPDATE
                """,
                verification_id, user_id,
            )
            if verification is None:
                raise HTTPException(
                    status_code=400,
                    detail={"error": "otp_invalid", "message": "Incorrect code."},
                )

            if verification["verified_at"] is not None:
                # Single-use: once confirmed, it must not be replayable.
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "otp_already_used",
                        "message": "This code has already been used. Request a new one.",
                    },
                )

            if verification["otp_expires_at"] < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=410,
                    detail={
                        "error": "otp_expired",
                        "message": "Code has expired. Request a new one.",
                    },
                )

            salt, _, expected_hash = verification["otp_code_hash"].partition("$")
            if _hash_otp(payload.code.strip(), salt) != expected_hash:
                raise HTTPException(
                    status_code=400,
                    detail={"error": "otp_invalid", "message": "Incorrect code."},
                )

            email = verification["email"]
            domain = verification["domain"]

            # FR-010: only enforced here, at confirm-time — the request step
            # (Scenario 7) always succeeds even for an email another account
            # has already claimed.
            conflict = await conn.fetchval(
                """
                SELECT 1
                FROM profiles p
                JOIN domain_verifications dv ON dv.user_id = p.id
                WHERE dv.email = $1
                  AND dv.verified_at IS NOT NULL
                  AND p.org_verified_at IS NOT NULL
                  AND p.id != $2
                LIMIT 1
                """,
                email, user_id,
            )
            if conflict:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "email_already_verified_elsewhere",
                        "message": "This email is already org-verified on a different account.",
                    },
                )

            await conn.execute(
                "UPDATE domain_verifications SET verified_at = now() WHERE id = $1",
                verification_id,
            )

            row = await conn.fetchrow(
                """
                UPDATE profiles
                SET org_verified_at = now(),
                    org_verified_domain = $2
                WHERE id = $1
                RETURNING org_verified_at, org_verified_domain
                """,
                user_id, domain,
            )

    return OrgAccessConfirmResponse(
        org_verified_at=row["org_verified_at"].isoformat(),
        org_verified_domain=row["org_verified_domain"],
    )
