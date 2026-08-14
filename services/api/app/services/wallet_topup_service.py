from __future__ import annotations

import uuid

_DEFAULT_VODAFONE_CASH_NUMBER = "VODAFONE_CASH_NUMBER_NOT_CONFIGURED"


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
