from __future__ import annotations

import hashlib
import secrets
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException

# In-memory rate limiter keyed by email, mirroring auth_service's
# resend-rate-limit shape. Shared across every caller of this module
# (Groups domain-verification and the org-only-access gate) since both
# gate the same underlying email-OTP flow.
_domain_otp_resend_tracker: dict[str, list[float]] = defaultdict(list)
_domain_otp_resend_lock = Lock()
_RESEND_WINDOW_SECONDS = 900  # 15 minutes
_RESEND_MAX = 3


def _check_domain_otp_resend_rate(email: str) -> None:
    now = time.time()
    with _domain_otp_resend_lock:
        timestamps = [
            t for t in _domain_otp_resend_tracker[email]
            if now - t < _RESEND_WINDOW_SECONDS
        ]
        if len(timestamps) >= _RESEND_MAX:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "otp_rate_limited",
                    "message": "Too many verification requests. Try again in 15 minutes.",
                    "retry_after_seconds": _RESEND_WINDOW_SECONDS,
                },
            )
        timestamps.append(now)
        _domain_otp_resend_tracker[email] = timestamps


def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_otp(code: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{code}".encode()).hexdigest()


async def _get_platform_setting(conn, key: str, default: str) -> str:
    value = await conn.fetchval("SELECT value FROM platform_settings WHERE key = $1", key)
    return value if value is not None else default


async def _get_domain_blocklist(conn) -> set[str]:
    raw = await _get_platform_setting(
        conn,
        "group_domain_blocklist",
        "gmail.com,yahoo.com,outlook.com,hotmail.com,icloud.com,protonmail.com",
    )
    return {d.strip().lower() for d in raw.split(",") if d.strip()}
