from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.core.config import settings
from app.models.ride import RevocationPayload
from app.services import revocation_service

router = APIRouter()


@router.post("/driver-revocation", include_in_schema=False)
async def driver_revocation_webhook(
    payload: RevocationPayload,
    x_webhook_secret: Optional[str] = Header(None),
) -> dict:
    if not settings.webhook_secret or x_webhook_secret != settings.webhook_secret:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Invalid webhook secret."},
        )
    return await revocation_service.handle_driver_revocation(
        driver_id=payload.driver_id,
        revocation_type=payload.revocation_type,
    )
