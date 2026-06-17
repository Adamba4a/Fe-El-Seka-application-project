from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import resend
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.ride import EmailNotification, EmailNotificationStatus

logger = logging.getLogger(__name__)

BACKOFF_MINUTES = [0, 5, 30, 120, 1440]  # 0m, 5m, 30m, 2h, 24h


def _init_resend() -> None:
    api_key = os.getenv("RESEND_API_KEY", "")
    if api_key:
        resend.api_key = api_key


# ─────────────────────────────────────────────────────────────────────────────
# Enqueue emails for a cancelled ride (T036)
# ─────────────────────────────────────────────────────────────────────────────

async def enqueue_cancellation_emails(db: AsyncSession, ride_id: uuid.UUID) -> int:
    """Queue cancellation emails for all booked passengers on the ride.

    Until Phase 6 bookings exist, this queries email_notifications for any
    manually pre-loaded rows and returns 0 for new rides.
    """
    # Phase 6 will add: query bookings table → INSERT email_notifications rows
    # For now this is a no-op returning 0
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# Send a single email (T052)
# ─────────────────────────────────────────────────────────────────────────────

async def send_cancellation_email(db: AsyncSession, notification_id: uuid.UUID) -> None:
    result = await db.execute(
        select(EmailNotification).where(EmailNotification.id == notification_id)
    )
    notif = result.scalar_one_or_none()
    if not notif:
        return

    _init_resend()
    try:
        params: resend.Emails.SendParams = {
            "from": "Fe El Seka <no-reply@felseka.com>",
            "to": [notif.passenger_email],
            "subject": "Your ride has been cancelled",
            "html": (
                "<p>We're sorry to inform you that the ride you booked has been cancelled.</p>"
                "<p>If you have any questions, please contact us.</p>"
                "<p>— The Fe El Seka Team</p>"
            ),
        }
        resend.Emails.send(params)
        notif.status = EmailNotificationStatus.sent
        notif.last_attempted_at = datetime.now(timezone.utc)
    except Exception as exc:
        logger.warning("Failed to send cancellation email %s: %s", notification_id, exc)
        notif.retry_count = (notif.retry_count or 0) + 1
        notif.last_attempted_at = datetime.now(timezone.utc)
        if notif.retry_count >= 5:
            notif.status = EmailNotificationStatus.failed_permanent
        else:
            notif.status = EmailNotificationStatus.failed

    await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Retry sweep (T053)
# ─────────────────────────────────────────────────────────────────────────────

async def retry_pending_emails(db: AsyncSession) -> None:
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(EmailNotification).where(
            EmailNotification.status.in_([EmailNotificationStatus.pending, EmailNotificationStatus.failed]),
            EmailNotification.retry_count < 5,
        )
    )
    notifications = result.scalars().all()

    for notif in notifications:
        backoff = BACKOFF_MINUTES[min(notif.retry_count, len(BACKOFF_MINUTES) - 1)]
        if notif.last_attempted_at is None:
            should_send = True
        else:
            last = notif.last_attempted_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            should_send = now >= last + timedelta(minutes=backoff)

        if should_send:
            await send_cancellation_email(db, notif.id)


# ─────────────────────────────────────────────────────────────────────────────
# Background sweep loop (started on FastAPI startup — T056)
# ─────────────────────────────────────────────────────────────────────────────

async def email_retry_loop() -> None:
    from ..database import AsyncSessionLocal
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await retry_pending_emails(db)
        except Exception as exc:
            logger.error("Email retry sweep error: %s", exc)
        await asyncio.sleep(300)  # 5 minutes
