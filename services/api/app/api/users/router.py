from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.core.database import get_pool
from app.dependencies.auth import get_current_user
from app.models.device_token import DeviceTokenRequest, DeviceTokenResponse

router = APIRouter()


@router.post("/me/device-tokens", response_model=DeviceTokenResponse)
async def register_device_token(
    body: DeviceTokenRequest,
    profile: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(profile["id"]))
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO user_device_tokens (user_id, token, platform)
            VALUES ($1, $2, $3)
            ON CONFLICT (token) DO UPDATE SET
                user_id      = EXCLUDED.user_id,
                last_seen_at = now()
            RETURNING id, user_id, platform, last_seen_at
            """,
            user_id,
            body.token,
            body.platform,
        )
    return DeviceTokenResponse(
        token_id=row["id"],
        user_id=row["user_id"],
        platform=row["platform"],
        last_seen_at=row["last_seen_at"],
    )
