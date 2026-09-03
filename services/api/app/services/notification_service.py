from __future__ import annotations

import asyncio
import logging
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import resend

from app.core.config import settings
from app.core.database import get_pool

logger = logging.getLogger(__name__)

_RETRY_DELAYS_MINUTES = [0, 5, 30, 120, 1440]
_FROM_ADDRESS = "noreply@triplyy.net"


def _use_mailpit() -> bool:
    """True when no real Resend key is configured — send via local Mailpit instead."""
    key = settings.resend_api_key.strip()
    return not key or key.startswith("re_your_")


async def enqueue_cancellation_emails(ride_id: uuid.UUID) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        # Insert one email_notifications row per booked passenger
        await conn.execute(
            """
            INSERT INTO email_notifications (ride_id, passenger_id, passenger_email, notification_type, status)
            SELECT
                b.ride_id,
                b.passenger_id,
                p.email,
                'ride_cancelled',
                'pending'
            FROM bookings b
            JOIN profiles p ON p.id = b.passenger_id
            WHERE b.ride_id = $1
              AND b.status = 'confirmed'
            ON CONFLICT DO NOTHING
            """,
            ride_id,
        )


def _build_email_content(notification_type: str, ride_id: uuid.UUID, payload: dict) -> tuple[str, str]:
    """Return (subject, html) for a queued email_notifications row, keyed by its
    notification_type. Every booking-lifecycle event shares the email_notifications
    table/retry pipeline, so the content must be looked up per type here rather than
    assuming every row is a cancellation."""
    if notification_type == "booking_created":
        return (
            "Your booking request was sent",
            f"<p>Your booking request for ride <code>{ride_id}</code> has been sent to the driver "
            f"and is awaiting confirmation.</p>",
        )
    if notification_type == "booking_requested":
        return (
            "New booking request",
            f"<p>A passenger requested to book a seat on your ride <code>{ride_id}</code>. "
            f"Please confirm or decline the request in the app.</p>",
        )
    if notification_type == "booking_confirmed":
        return (
            "Your booking is confirmed",
            f"<p>Good news — your booking for ride <code>{ride_id}</code> has been confirmed by the driver.</p>",
        )
    if notification_type == "booking_rejected":
        return (
            "Your booking request was declined",
            f"<p>The driver declined your booking request for ride <code>{ride_id}</code>. "
            f"Please check the app to find alternative rides.</p>",
        )
    if notification_type == "booking_cancelled_by_driver":
        return (
            "Your booking has been cancelled",
            f"<p>The driver cancelled your booking for ride <code>{ride_id}</code>. "
            f"Please check the app to find alternative rides.</p>",
        )
    if notification_type == "booking_cancelled_by_passenger":
        return (
            "A passenger cancelled their booking",
            f"<p>A passenger cancelled their booking on your ride <code>{ride_id}</code>.</p>",
        )
    if notification_type == "booking_seats_added":
        additional_seats = payload.get("additional_seats")
        seats_html = f" ({additional_seats} additional seat(s))" if additional_seats else ""
        return (
            "A passenger added seats to their booking",
            f"<p>A passenger added seats{seats_html} to their booking on your ride <code>{ride_id}</code>.</p>",
        )
    if notification_type == "booking_expired":
        return (
            "Your booking request expired",
            f"<p>Your booking request for ride <code>{ride_id}</code> expired before the driver responded. "
            f"Please check the app to find alternative rides.</p>",
        )
    # "ride_cancelled" and any unrecognized type fall back to the original cancellation copy.
    return (
        "Your ride has been cancelled",
        f"<p>We're sorry — the ride you booked (ID: <code>{ride_id}</code>) "
        f"has been cancelled. Please check the app to find alternative rides.</p>",
    )


async def _send_via_mailpit(to: str, subject: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = _FROM_ADDRESS
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))

    def _send() -> None:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as s:
            s.sendmail(_FROM_ADDRESS, [to], msg.as_string())

    await asyncio.to_thread(_send)


async def _send_email(to: str, subject: str, html: str) -> None:
    if _use_mailpit():
        logger.info("Sending via Mailpit → %s", to)
        await _send_via_mailpit(to, subject, html)
    else:
        resend.api_key = settings.resend_api_key
        resend.Emails.send({
            "from": _FROM_ADDRESS,
            "to": to,
            "subject": subject,
            "html": html,
        })


async def _send_booking_notification_email(
    recipient_email: str, notification_type: str, ride_id: uuid.UUID, payload: dict
) -> None:
    subject, html = _build_email_content(notification_type, ride_id, payload)
    await _send_email(recipient_email, subject, html)


async def send_verification_decision_email(
    recipient_email: str, approved: bool, rejection_reason: str | None = None
) -> None:
    """Fire-and-forget notification for an admin verification approve/reject
    decision. Not queued via email_notifications — that table's ride_id is
    NOT NULL (Phase 6 design assumed every email was ride-linked), and a
    verification decision has no associated ride. Sent directly from
    BackgroundTasks instead, mirroring verification_service's own
    fire-and-forget AI triage: a transient send failure just logs a warning
    rather than blocking or retrying the admin's already-committed decision.
    """
    if approved:
        subject = "Your identity has been verified"
        html = (
            "<p>Good news — your identity verification was approved."
            " You can now book and take rides on Triplyy.</p>"
        )
    else:
        subject = "Your identity verification was not approved"
        reason_html = (
            f"<p><strong>Reason:</strong> {rejection_reason}</p>" if rejection_reason else ""
        )
        html = (
            "<p>Your identity verification submission was not approved.</p>"
            f"{reason_html}"
            "<p>Please review the details and resubmit your documents in the app.</p>"
        )
    try:
        await _send_email(recipient_email, subject, html)
    except Exception:
        logger.warning(
            "Verification decision email failed to send to %s", recipient_email, exc_info=True
        )


async def send_domain_verification_email(recipient_email: str, code: str) -> None:
    """Sends the group domain-verification OTP. Unlike the fire-and-forget
    verification-decision email above, a send failure here must propagate —
    the caller (group_service.request_domain_verification) has nothing
    useful to tell the user if the code never went out.
    """
    subject = "Your Triplyy domain verification code"
    html = (
        f"<p>Your domain verification code is <strong>{code}</strong>.</p>"
        "<p>This code expires in 5 minutes. If you didn't request this, you can ignore this email.</p>"
    )
    await _send_email(recipient_email, subject, html)


async def _process_pending_emails() -> None:
    pool = get_pool()
    now = datetime.now(timezone.utc)

    # Scan candidates without locking — per-row lock acquired below before each send
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, ride_id, passenger_email, notification_type, payload, retry_count, last_attempted_at
            FROM email_notifications
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 50
            """
        )

    for row in rows:
        retry = row["retry_count"]
        if retry >= len(_RETRY_DELAYS_MINUTES):
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE email_notifications SET status = 'failed_permanent' WHERE id = $1",
                    row["id"],
                )
            continue

        if row["last_attempted_at"] is not None:
            last = row["last_attempted_at"]
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            wait = timedelta(minutes=_RETRY_DELAYS_MINUTES[retry])
            if now < last + wait:
                continue

        # Acquire a per-row lock inside a transaction; SKIP LOCKED means another
        # worker already claimed this row — don't double-send.
        async with pool.acquire() as conn:
            async with conn.transaction():
                locked = await conn.fetchrow(
                    "SELECT id FROM email_notifications WHERE id = $1 AND status = 'pending' FOR UPDATE SKIP LOCKED",
                    row["id"],
                )
                if not locked:
                    continue

                try:
                    await _send_booking_notification_email(
                        row["passenger_email"], row["notification_type"], row["ride_id"], row["payload"] or {}
                    )
                    await conn.execute(
                        "UPDATE email_notifications SET status = 'sent', last_attempted_at = now() WHERE id = $1",
                        row["id"],
                    )
                except Exception as exc:
                    logger.warning("Email send failed for notification %s: %s", row["id"], exc)
                    new_retry = retry + 1
                    new_status = "failed_permanent" if new_retry >= len(_RETRY_DELAYS_MINUTES) else "pending"
                    await conn.execute(
                        """
                        UPDATE email_notifications
                        SET retry_count = $2, status = $3, last_attempted_at = now()
                        WHERE id = $1
                        """,
                        row["id"], new_retry, new_status,
                    )


async def enqueue_booking_notification(
    conn,
    notification_type: str,
    recipient_user_id: uuid.UUID,
    payload_dict: dict,
) -> None:
    """Insert one booking event row into email_notifications with structured payload."""
    row = await conn.fetchrow(
        "SELECT email FROM profiles WHERE id = $1",
        recipient_user_id,
    )
    if row is None:
        logger.warning("enqueue_booking_notification: recipient %s not found", recipient_user_id)
        return

    ride_id = payload_dict.get("ride_id")
    if ride_id is None:
        logger.warning("enqueue_booking_notification: payload missing ride_id for %s", notification_type)
        return

    await conn.execute(
        """
        INSERT INTO email_notifications
            (ride_id, passenger_id, passenger_email, notification_type, status, payload)
        VALUES ($1, $2, $3, $4, 'pending', $5)
        """,
        uuid.UUID(str(ride_id)),
        recipient_user_id,
        row["email"],
        notification_type,
        payload_dict,
    )


async def email_retry_loop() -> None:
    """Background task: poll email_notifications and retry until sent or exhausted."""
    while True:
        try:
            await _process_pending_emails()
        except Exception as exc:
            logger.error("Email retry sweep error: %s", exc)
        await asyncio.sleep(60)
