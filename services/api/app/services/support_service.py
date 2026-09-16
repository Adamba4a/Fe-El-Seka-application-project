import asyncio
import hashlib
import hmac
import logging
from html import escape

from fastapi import HTTPException

from app.core.config import settings
from app.core.database import get_pool
from app.models.support import SupportRequest
from app.services.notification_service import _send_email

logger = logging.getLogger(__name__)
RETRY_SECONDS = [60, 300, 1800, 7200]


async def submit_report(body: SupportRequest, client_ip: str):
    if body.website:
        raise HTTPException(422, detail={"error": "invalid_submission"})
    fingerprint = hmac.new(settings.supabase_service_role_key.encode(), client_ip.encode(), hashlib.sha256).hexdigest()
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            # A dedicated, short-held lock protects both limits and idempotency
            # across API workers. No external calls occur under this lock.
            await conn.execute("SELECT pg_advisory_xact_lock(320032)")
            if await conn.fetchval("SELECT id FROM support_requests WHERE id = $1", body.id):
                return {"id": body.id}
            counts = await conn.fetchrow(
                """SELECT count(*) FILTER (WHERE email = $1) AS email_count,
                          count(*) FILTER (WHERE client_fingerprint = $2) AS client_count
                   FROM support_requests WHERE created_at > now() - interval '1 hour'
                   AND (email = $1 OR client_fingerprint = $2)""",
                body.email,
                fingerprint,
            )
            if counts["email_count"] >= 3 or counts["client_count"] >= 10:
                raise HTTPException(429, detail={"error": "rate_limited"}, headers={"Retry-After": "3600"})
            await conn.execute(
                """INSERT INTO support_requests (id, email, description, locale, client_fingerprint)
                   VALUES ($1, $2, $3, $4, $5)""",
                body.id,
                body.email,
                body.description,
                body.locale,
                fingerprint,
            )
    return {"id": body.id}


async def list_reports(status, page):
    async with get_pool().acquire() as conn:
        total = await conn.fetchval(
            "SELECT count(*) FROM support_requests WHERE ($1::text IS NULL OR status = $1)",
            status,
        )
        rows = await conn.fetch(
            """SELECT id, email, description, locale, status, email_status, created_at, updated_at
               FROM support_requests WHERE ($1::text IS NULL OR status = $1)
               ORDER BY created_at DESC, id DESC LIMIT 20 OFFSET $2""",
            status,
            (page - 1) * 20,
        )
    return {"items": [dict(row) for row in rows], "total": total, "page": page}


async def update_status(report_id, status, admin_id):
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            old = await conn.fetchval("SELECT status FROM support_requests WHERE id = $1 FOR UPDATE", report_id)
            if old is None:
                raise HTTPException(404, detail={"error": "not_found"})
            if old != status:
                await conn.execute(
                    "UPDATE support_requests SET status = $2, updated_at = now() WHERE id = $1", report_id, status
                )
                await conn.execute(
                    "INSERT INTO support_status_history (request_id, admin_id, old_status, new_status) "
                    "VALUES ($1,$2,$3,$4)",
                    report_id,
                    admin_id,
                    old,
                    status,
                )
    return {"id": report_id, "status": status}


def email_content(row):
    return (
        f"Triplyy support request {row['id']}",
        f"<p>Contact: {escape(row['email'])}</p>"
        f"<p>Language: {escape(row['locale'])}</p>"
        f"<div dir='auto' style='white-space:pre-wrap'>{escape(row['description'])}</div>",
    )


async def process_support_emails():
    # Bound work per sweep; locks prevent concurrent workers sending the same row.
    for _ in range(20):
        async with get_pool().acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """SELECT id, email, description, locale, email_attempts FROM support_requests
                       WHERE email_status = 'pending' AND next_email_attempt_at <= now()
                       ORDER BY next_email_attempt_at LIMIT 1 FOR UPDATE SKIP LOCKED""",
                )
                if row is None:
                    return
                attempts = row["email_attempts"] + 1
                try:
                    subject, html = email_content(row)
                    await asyncio.wait_for(_send_email(settings.support_email, subject, html), timeout=20)
                except Exception:
                    # Do not log the exception: provider errors can contain contact data.
                    logger.warning("Support notification failed for report %s", row["id"])
                    status = "failed" if attempts >= 5 else "pending"
                    delay = RETRY_SECONDS[min(attempts - 1, 3)]
                    await conn.execute(
                        """UPDATE support_requests SET email_status=$2, email_attempts=$3,
                           next_email_attempt_at=now() + $4 * interval '1 second' WHERE id=$1""",
                        row["id"],
                        status,
                        attempts,
                        delay,
                    )
                else:
                    await conn.execute(
                        "UPDATE support_requests SET email_status='sent', email_attempts=$2 WHERE id=$1",
                        row["id"],
                        attempts,
                    )


async def support_email_loop():
    while True:
        try:
            await process_support_emails()
        except Exception:
            logger.warning("Support email sweep failed")
        await asyncio.sleep(60)
