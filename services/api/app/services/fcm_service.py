from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging

from app.core.config import settings
from app.core.database import get_pool

logger = logging.getLogger(__name__)

_app: Optional[firebase_admin.App] = None

_NOTIFICATION_TEMPLATES: dict[str, tuple[str, str]] = {
    "booking_received": (
        "New Booking Request",
        "A passenger wants to join your ride.",
    ),
    "booking_reminder": (
        "Pending Booking Request",
        "You have a pending booking request waiting for your response.",
    ),
    "booking_confirmed": (
        "Booking Confirmed",
        "Your ride booking has been confirmed!",
    ),
    "booking_rejected": (
        "Booking Not Accepted",
        "Your booking request was not accepted.",
    ),
    "booking_cancelled": (
        "Booking Cancelled",
        "A booking on your ride has been cancelled.",
    ),
    "booking_expired": (
        "Booking Expired",
        "Your booking request has expired.",
    ),
    "ride_cancelled": (
        "Ride Cancelled",
        "Your upcoming ride has been cancelled.",
    ),
    "ride_started": (
        "Ride Started",
        "Your driver has started the ride. Track their location now.",
    ),
    "ride_completed": (
        "Ride Completed",
        "Your ride is complete. Thank you for using Triplyy!",
    ),
}

# FCM error codes that mark a token as permanently invalid (should be deregistered)
_INVALID_TOKEN_CODES = frozenset({
    "registration-token-not-registered",
    "invalid-registration-token",
    "messaging/registration-token-not-registered",
    "messaging/invalid-registration-token",
})


async def initialize_fcm() -> None:
    """Load Firebase credentials from Supabase Vault and initialize the Firebase app.

    Called once during FastAPI lifespan startup, after the connection pool is ready.
    Raises RuntimeError if the Vault secret is missing — treat as a startup failure.
    """
    global _app
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = $1",
            settings.firebase_service_account_secret_name,
        )
    if row is None:
        raise RuntimeError(
            f"Firebase service account secret '{settings.firebase_service_account_secret_name}' "
            "not found in Supabase Vault. Store it via the Supabase dashboard before starting the API."
        )
    cred_dict = json.loads(row["decrypted_secret"])
    cred = credentials.Certificate(cred_dict)
    _app = firebase_admin.initialize_app(cred)
    logger.info("FCM credentials loaded from Vault (project: %s)", cred_dict.get("project_id", "unknown"))


async def send_push_notifications(
    conn,
    recipient_user_id: uuid.UUID,
    event_type: str,
    data_payload: dict,
) -> int:
    """Send FCM push notifications to all active device tokens for a user.

    Deregisters permanently invalid tokens. Returns count of successful sends.
    No-ops silently if FCM is not initialized or the user has no registered tokens.
    """
    if _app is None:
        logger.warning("FCM not initialized — skipping push for user %s event %s", recipient_user_id, event_type)
        return 0

    rows = await conn.fetch(
        "SELECT id, token FROM user_device_tokens WHERE user_id = $1",
        recipient_user_id,
    )
    if not rows:
        return 0

    tokens = [r["token"] for r in rows]
    token_to_id: dict[str, uuid.UUID] = {r["token"]: r["id"] for r in rows}

    title, body = _NOTIFICATION_TEMPLATES.get(
        event_type,
        ("Triplyy", "You have a new notification."),
    )

    multicast_msg = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in data_payload.items() if v is not None},
    )

    response = await asyncio.to_thread(messaging.send_each_for_multicast, multicast_msg)

    invalid_ids = [
        token_to_id[tokens[i]]
        for i, result in enumerate(response.responses)
        if not result.success
        and getattr(result.exception, "code", None) in _INVALID_TOKEN_CODES
    ]
    if invalid_ids:
        await conn.execute(
            "DELETE FROM user_device_tokens WHERE id = ANY($1::uuid[])",
            invalid_ids,
        )
        logger.info(
            "Deregistered %d invalid FCM token(s) for user %s",
            len(invalid_ids),
            recipient_user_id,
        )

    return response.success_count
