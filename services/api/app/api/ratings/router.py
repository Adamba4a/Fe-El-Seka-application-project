from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.core.database import get_pool
from app.dependencies.auth import get_current_user
from app.models.rating import RatingCreateRequest
from app.services import rating_service

router = APIRouter()


# ── POST /api/v1/ratings ─────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_rating(
    body: RatingCreateRequest,
    profile: dict = Depends(get_current_user),
):
    rater_id = uuid.UUID(str(profile["id"]))

    pool = get_pool()
    async with pool.acquire() as conn:
        result = await rating_service.submit_rating(
            conn, body.booking_id, rater_id, body.stars, body.comment,
        )

    return JSONResponse(
        status_code=201,
        content={
            "rating_id": str(result["rating_id"]),
            "booking_id": str(result["booking_id"]),
            "revealed": result["revealed"],
        },
    )
