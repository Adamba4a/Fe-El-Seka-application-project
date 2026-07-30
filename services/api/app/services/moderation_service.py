from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid

from fastapi import HTTPException

from app.core.database import get_pool
from app.services import audit_service, auth_service

logger = logging.getLogger(__name__)

_DEFAULTS: dict[str, float] = {
    "rating_floor": 3.0,
    "rating_window": 10,
    "rating_min_count": 5,
    "report_count_threshold": 3,
    "report_window_days": 30,
}

_config_cache: dict[str, float] = dict(_DEFAULTS)
_config_lock = asyncio.Lock()
_config_loaded: bool = False


async def _refresh_moderation_config() -> None:
    global _config_loaded
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM moderation_config LIMIT 1")
    if row is None:
        logger.warning("moderation_config table is empty — keeping current cache")
        return
    async with _config_lock:
        _config_cache["rating_floor"] = float(row["rating_floor"])
        _config_cache["rating_window"] = int(row["rating_window"])
        _config_cache["rating_min_count"] = int(row["rating_min_count"])
        _config_cache["report_count_threshold"] = int(row["report_count_threshold"])
        _config_cache["report_window_days"] = int(row["report_window_days"])
        _config_loaded = True


async def init_moderation_config() -> None:
    """Best-effort initial load at startup. Falls back to hardcoded defaults if the DB
    table does not exist yet (e.g. migration pending). Background loop retries."""
    try:
        await _refresh_moderation_config()
        logger.info(
            "moderation_config loaded from DB: rating_floor=%.1f rating_window=%d "
            "rating_min_count=%d report_count_threshold=%d report_window_days=%d",
            _config_cache["rating_floor"], _config_cache["rating_window"],
            _config_cache["rating_min_count"], _config_cache["report_count_threshold"],
            _config_cache["report_window_days"],
        )
    except Exception as exc:
        logger.warning(
            "moderation_config unavailable at startup (%s) — using defaults. "
            "Apply migrations and the background loop will sync within 30s.",
            exc,
        )


async def moderation_config_refresh_loop() -> None:
    """Background task: refresh moderation_config cache every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        try:
            await _refresh_moderation_config()
        except Exception as exc:
            logger.error("moderation_config refresh error: %s", exc)


def get_flagging_thresholds() -> dict:
    if not _config_loaded:
        logger.warning("moderation_config not yet loaded from DB — using hardcoded defaults")
    return dict(_config_cache)


async def list_flagged_users(conn) -> list[dict]:
    """Users auto-flagged by rating or report thresholds, advisory-only (FR-019)."""
    thresholds = get_flagging_thresholds()

    low_rating_rows = await conn.fetch(
        """
        WITH ranked AS (
            SELECT ratee_id, stars,
                   ROW_NUMBER() OVER (PARTITION BY ratee_id ORDER BY created_at DESC) AS rn
            FROM ratings
        ),
        windowed AS (
            SELECT ratee_id, AVG(stars)::numeric(3,2) AS avg_recent
            FROM ranked
            WHERE rn <= $1
            GROUP BY ratee_id
        )
        SELECT p.id AS user_id, p.display_name, w.avg_recent
        FROM windowed w
        JOIN profiles p ON p.id = w.ratee_id
        WHERE p.rating_count >= $2 AND w.avg_recent < $3
        """,
        thresholds["rating_window"], thresholds["rating_min_count"], thresholds["rating_floor"],
    )

    report_rows = await conn.fetch(
        """
        SELECT p.id AS user_id, p.display_name, COUNT(r.id) AS recent_report_count
        FROM reports r
        JOIN profiles p ON p.id = r.reported_user_id
        WHERE r.created_at >= now() - make_interval(days => $1::int)
        GROUP BY p.id, p.display_name
        HAVING COUNT(r.id) >= $2
        """,
        thresholds["report_window_days"], thresholds["report_count_threshold"],
    )

    items = [
        {
            "user_id": str(r["user_id"]),
            "display_name": r["display_name"],
            "reason": "low_rating",
            "rating_avg": float(r["avg_recent"]),
            "recent_report_count": None,
        }
        for r in low_rating_rows
    ]
    items += [
        {
            "user_id": str(r["user_id"]),
            "display_name": r["display_name"],
            "reason": "report_count",
            "rating_avg": None,
            "recent_report_count": r["recent_report_count"],
        }
        for r in report_rows
    ]
    return items


async def list_queue(conn, page: int, limit: int) -> tuple[list[dict], int]:
    """Open/under-review reports, newest-first (FR-018)."""
    offset = (page - 1) * limit
    rows = await conn.fetch(
        """
        SELECT r.id, r.category, r.description, r.ride_id, r.status, r.created_at,
               rp.id AS reporter_id, rp.display_name AS reporter_name,
               tp.id AS reported_id, tp.display_name AS reported_name
        FROM reports r
        JOIN profiles rp ON rp.id = r.reporter_id
        JOIN profiles tp ON tp.id = r.reported_user_id
        WHERE r.status IN ('open', 'under_review')
        ORDER BY r.created_at DESC
        LIMIT $1 OFFSET $2
        """,
        limit, offset,
    )
    total = await conn.fetchval(
        "SELECT COUNT(*) FROM reports WHERE status IN ('open', 'under_review')"
    )
    items = [
        {
            "report_id": str(r["id"]),
            "category": r["category"],
            "description": r["description"],
            "reporter": {"user_id": str(r["reporter_id"]), "display_name": r["reporter_name"]},
            "reported_user": {"user_id": str(r["reported_id"]), "display_name": r["reported_name"]},
            "ride_id": str(r["ride_id"]),
            "status": r["status"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]
    return items, total


async def mark_under_review(conn, report_id: uuid.UUID) -> dict:
    """Transition an open report to under_review (FR-020)."""
    row = await conn.fetchrow(
        "UPDATE reports SET status = 'under_review' WHERE id = $1 AND status = 'open' RETURNING id, status",
        report_id,
    )
    if row is None:
        exists = await conn.fetchval("SELECT 1 FROM reports WHERE id = $1", report_id)
        if not exists:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Report not found"})
        raise HTTPException(status_code=409, detail={"error": "conflict", "message": "Report is not open"})
    return {"report_id": str(row["id"]), "status": row["status"]}


async def _enqueue_notification(conn, recipient_user_id, event_type: str, payload: dict) -> None:
    await conn.execute(
        "INSERT INTO notification_events (recipient_user_id, event_type, payload) VALUES ($1, $2, $3)",
        recipient_user_id, event_type, payload,
    )


async def resolve_report(
    conn,
    report_id: uuid.UUID,
    admin_id: uuid.UUID,
    action: str,
    reason: str,
) -> dict:
    """Resolve an open/under-review report with warn/suspend/dismiss (FR-020, FR-021, FR-023, FR-025)."""
    started = time.monotonic()
    if action not in ("warn", "suspend", "dismiss"):
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": "action must be warn, suspend, or dismiss"},
        )
    if not reason or not reason.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": "reason is required"},
        )
    reason = reason.strip()

    async with conn.transaction():
        row = await conn.fetchrow(
            "SELECT id, reported_user_id, status FROM reports WHERE id = $1 FOR UPDATE",
            report_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Report not found"})
        if row["status"] in ("resolved", "dismissed"):
            raise HTTPException(
                status_code=409,
                detail={"error": "conflict", "message": "Report has already been resolved"},
            )

        reported_user_id = row["reported_user_id"]
        new_status = "dismissed" if action == "dismiss" else "resolved"

        await conn.execute(
            """
            UPDATE reports
            SET status = $2, resolution_action = $3, resolution_reason = $4,
                resolved_by = $5, resolved_at = now()
            WHERE id = $1
            """,
            report_id, new_status, action, reason, admin_id,
        )

        if action == "suspend":
            await conn.execute(
                "UPDATE profiles SET verification_status = 'suspended' WHERE id = $1",
                reported_user_id,
            )

        await _enqueue_notification(
            conn, reported_user_id, "moderation_outcome",
            {"action": action, "report_id": str(report_id)},
        )

    if action == "suspend":
        try:
            auth_service.revoke_sessions(str(reported_user_id))
        except Exception as exc:
            logger.warning("Session revocation failed for suspended user %s: %s", reported_user_id, exc)

    # 'dismiss' has no admin_audit_logs entry: the action_type CHECK constraint only
    # permits 'warned'/'suspended' (plus the pre-existing verification values), and the
    # report row's own resolution_action/resolved_by/resolved_at already records it.
    audit_id = None
    if action == "warn":
        audit_id = audit_service.append_log(
            str(admin_id), "warned", str(reported_user_id), reason=reason, report_id=str(report_id),
        )
    elif action == "suspend":
        audit_id = audit_service.append_log(
            str(admin_id), "suspended", str(reported_user_id), reason=reason, report_id=str(report_id),
        )

    logger.info(json.dumps({
        "event": "moderation_action",
        "admin_id": str(admin_id),
        "action_type": action,
        "target_user_id": str(reported_user_id),
        "report_id": str(report_id),
        "reason": reason,
        "duration_ms": round((time.monotonic() - started) * 1000, 1),
    }))

    return {
        "report_id": str(report_id),
        "status": new_status,
        "action": action,
        "audit_log_id": audit_id,
    }


async def reinstate_user(conn, user_id: uuid.UUID, admin_id: uuid.UUID, reason: str) -> dict:
    """Lift a suspension, restoring ride/booking access (FR-022)."""
    started = time.monotonic()
    if not reason or not reason.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": "reason is required"},
        )
    reason = reason.strip()

    async with conn.transaction():
        row = await conn.fetchrow(
            "SELECT verification_status FROM profiles WHERE id = $1 FOR UPDATE",
            user_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "User not found"})
        if row["verification_status"] != "suspended":
            raise HTTPException(
                status_code=409,
                detail={"error": "conflict", "message": "User is not currently suspended"},
            )

        await conn.execute(
            "UPDATE profiles SET verification_status = 'verified' WHERE id = $1",
            user_id,
        )
        await _enqueue_notification(conn, user_id, "moderation_reinstated", {"reason": reason})

    audit_id = audit_service.append_log(str(admin_id), "reinstated", str(user_id), reason=reason)

    logger.info(json.dumps({
        "event": "moderation_action",
        "admin_id": str(admin_id),
        "action_type": "reinstated",
        "target_user_id": str(user_id),
        "report_id": None,
        "reason": reason,
        "duration_ms": round((time.monotonic() - started) * 1000, 1),
    }))

    return {"user_id": str(user_id), "new_status": "verified", "audit_log_id": audit_id}
