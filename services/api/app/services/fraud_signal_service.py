from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from typing import Optional

from app.core.config import settings
from app.core.database import get_pool

logger = logging.getLogger(__name__)


def _hash_value(value: str) -> str:
    """Deterministic, one-way HMAC-SHA256 digest keyed by the server-side
    pepper (never derivable from the input alone, FR-008) — the same raw
    value always hashes identically, which is what makes device/IP graph
    linking possible (FR-002, SC-004)."""
    return hmac.new(
        settings.fraud_signal_hmac_secret.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def record_signal(
    event_type: str,
    user_id: Optional[uuid.UUID],
    device_id: Optional[str],
    ip_address: Optional[str],
) -> None:
    """Fire-and-forget entry point: persist one fraud_signals row. Called via
    FastAPI BackgroundTasks from each of the four instrumented handlers
    (signup, login, ride_posted, booking_created) — must never raise, since
    the request's response has already been (or is about to be) sent
    regardless of this task's outcome (FR-005, FR-006, NFR-001, NFR-002).
    device_id is optional (absent header → NULL hashed_device_id, per spec
    Edge Cases); ip_address should never be None in production (every HTTP
    request has a source IP) but is guarded defensively since hashed_ip is
    NOT NULL and there is nothing meaningful to store without it."""
    try:
        if not ip_address:
            logger.error(json.dumps({
                "event": "fraud_signal_persist_skipped_no_ip",
                "event_type": event_type,
            }))
            return

        hashed_device_id = _hash_value(device_id) if device_id else None
        hashed_ip = _hash_value(ip_address)

        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO fraud_signals (user_id, event_type, hashed_device_id, hashed_ip)
                VALUES ($1, $2, $3, $4)
                """,
                user_id,
                event_type,
                hashed_device_id,
                hashed_ip,
            )
    except Exception as exc:
        logger.error(json.dumps({
            "event": "fraud_signal_persist_failure",
            "event_type": event_type,
            "error": str(exc),
        }))
