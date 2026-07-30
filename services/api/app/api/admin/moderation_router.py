from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.core.database import get_pool
from app.dependencies.roles import get_current_admin
from app.models.moderation import ReinstateUserRequest, ResolveReportRequest
from app.services import moderation_service

router = APIRouter()


# ── GET /admin/moderation/queue ──────────────────────────────────────────────

@router.get("/queue")
async def get_queue(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    admin: dict = Depends(get_current_admin),
):
    pool = get_pool()
    async with pool.acquire() as conn:
        items, total = await moderation_service.list_queue(conn, page, limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


# ── GET /admin/moderation/flagged ────────────────────────────────────────────

@router.get("/flagged")
async def get_flagged(admin: dict = Depends(get_current_admin)):
    pool = get_pool()
    async with pool.acquire() as conn:
        items = await moderation_service.list_flagged_users(conn)
    return {"items": items}


# ── POST /admin/moderation/reports/{report_id}/review ────────────────────────

@router.post("/reports/{report_id}/review")
async def review_report(
    report_id: uuid.UUID,
    admin: dict = Depends(get_current_admin),
):
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await moderation_service.mark_under_review(conn, report_id)
    return result


# ── POST /admin/moderation/reports/{report_id}/resolve ───────────────────────

@router.post("/reports/{report_id}/resolve")
async def resolve_report(
    report_id: uuid.UUID,
    body: ResolveReportRequest,
    admin: dict = Depends(get_current_admin),
):
    admin_id = uuid.UUID(str(admin["id"]))
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await moderation_service.resolve_report(
            conn, report_id, admin_id, body.action, body.reason,
        )
    return result


# ── POST /admin/moderation/users/{user_id}/reinstate ─────────────────────────

@router.post("/users/{user_id}/reinstate")
async def reinstate_user(
    user_id: uuid.UUID,
    body: ReinstateUserRequest,
    admin: dict = Depends(get_current_admin),
):
    admin_id = uuid.UUID(str(admin["id"]))
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await moderation_service.reinstate_user(conn, user_id, admin_id, body.reason)
    return result
