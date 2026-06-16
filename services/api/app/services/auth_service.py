import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock

from fastapi import HTTPException
from supabase import create_client

from app.core.config import settings

logger = logging.getLogger(__name__)

# In-memory rate limiter keyed by email
_resend_tracker: dict[str, list[float]] = defaultdict(list)
_resend_lock = Lock()

_RESEND_WINDOW_SECONDS = 900  # 15 minutes
_RESEND_MAX = 3


def _check_resend_rate(email: str) -> None:
    now = time.time()
    with _resend_lock:
        timestamps = [
            t for t in _resend_tracker[email]
            if now - t < _RESEND_WINDOW_SECONDS
        ]
        if len(timestamps) >= _RESEND_MAX:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "otp_rate_limited",
                    "message": "Too many OTP requests. Try again in 15 minutes.",
                    "retry_after_seconds": _RESEND_WINDOW_SECONDS,
                },
            )
        timestamps.append(now)
        _resend_tracker[email] = timestamps


def _supabase():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def request_otp(email: str) -> dict:
    _check_resend_rate(email)
    sb = _supabase()
    try:
        sb.auth.sign_in_with_otp({"email": email})
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": "otp_send_failed", "message": str(exc)},
        )
    return {"message": "OTP sent", "expires_in_seconds": 300}


def verify_otp(email: str, otp: str) -> dict:
    sb = _supabase()
    try:
        resp = sb.auth.verify_otp({"email": email, "token": otp, "type": "email"})
    except Exception as exc:
        error_str = str(exc).lower()
        if "expired" in error_str:
            raise HTTPException(
                status_code=410,
                detail={
                    "error": "otp_expired",
                    "message": "Code has expired. Request a new one.",
                },
            )
        raise HTTPException(
            status_code=400,
            detail={"error": "otp_invalid", "message": "Incorrect code."},
        )

    if not resp.session or not resp.user:
        raise HTTPException(
            status_code=400,
            detail={"error": "otp_invalid", "message": "Verification failed"},
        )

    session = resp.session
    user = resp.user

    profile_resp = sb.table("profiles").select("id").eq("id", user.id).execute()
    is_new_user = not bool(profile_resp.data)

    if not is_new_user:
        (
            sb.table("profiles")
            .update({"last_login_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", user.id)
            .execute()
        )

    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_in": session.expires_in or 3600,
        "user": {
            "id": user.id,
            "email": user.email or email,
            "is_new_user": is_new_user,
        },
    }


def refresh_session(refresh_token: str) -> dict:
    sb = _supabase()
    try:
        resp = sb.auth.refresh_session(refresh_token)
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": str(exc)},
        )
    if not resp.session:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Session could not be refreshed",
            },
        )
    return {
        "access_token": resp.session.access_token,
        "expires_in": resp.session.expires_in or 3600,
    }


def sign_out(user_id: str, token: str) -> None:
    sb = _supabase()
    try:
        sb.auth.admin.sign_out(user_id)
    except Exception:
        pass


def revoke_sessions(user_id: str) -> None:
    """Used by admin suspend action to immediately cut off the user."""
    sb = _supabase()
    try:
        sb.auth.admin.sign_out(user_id)
    except Exception as exc:
        logger.error("Failed to revoke sessions for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=502,
            detail={
                "error": "revocation_failed",
                "message": "User suspended in DB but session revocation"
                " failed. Retry the suspend action.",
            },
        )
