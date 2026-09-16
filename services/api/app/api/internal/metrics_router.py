from __future__ import annotations

import hmac
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import settings
from app.core.request_metrics import request_metrics

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request, x_internal_secret: Optional[str] = Header(None)) -> dict:
    if (
        not settings.internal_secret
        or not x_internal_secret
        or not hmac.compare_digest(x_internal_secret, settings.internal_secret)
    ):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Invalid internal secret."})
    return request_metrics.snapshot(getattr(request.app.state, "pool", None))
