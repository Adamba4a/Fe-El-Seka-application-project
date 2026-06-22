from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.core.config import settings

router = APIRouter()


def _require_internal_secret(x_internal_secret: Optional[str] = Header(None)) -> None:
    if not settings.internal_secret or x_internal_secret != settings.internal_secret:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "Invalid or missing internal secret."},
        )


@router.post("/compatibility", include_in_schema=False)
async def compatibility_features(
    x_internal_secret: Optional[str] = Header(None),
) -> dict:
    _require_internal_secret(x_internal_secret)
    raise HTTPException(
        status_code=501,
        detail={"error": "not_implemented", "message": "Compatibility endpoint not yet implemented."},
    )
