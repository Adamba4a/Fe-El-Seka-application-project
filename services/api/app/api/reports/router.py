from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.core.database import get_pool
from app.dependencies.auth import get_current_user
from app.models.report import ReportCreateRequest
from app.services import report_service

router = APIRouter()


# ── POST /api/v1/reports ─────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_report(
    body: ReportCreateRequest,
    profile: dict = Depends(get_current_user),
):
    reporter_id = uuid.UUID(str(profile["id"]))

    pool = get_pool()
    async with pool.acquire() as conn:
        result = await report_service.submit_report(
            conn,
            body.ride_id,
            body.booking_id,
            reporter_id,
            body.reported_user_id,
            body.category,
            body.description,
        )

    return JSONResponse(
        status_code=201,
        content={"report_id": str(result["report_id"]), "status": result["status"]},
    )


# ── GET /api/v1/reports/mine ─────────────────────────────────────────────────

@router.get("/mine")
async def list_my_reports(
    profile: dict = Depends(get_current_user),
):
    reporter_id = uuid.UUID(str(profile["id"]))

    pool = get_pool()
    async with pool.acquire() as conn:
        items = await report_service.get_own_reports(conn, reporter_id)

    return {
        "items": [
            {
                "report_id": str(item["report_id"]),
                "category": item["category"],
                "status": item["status"],
                "created_at": item["created_at"].isoformat(),
            }
            for item in items
        ]
    }
