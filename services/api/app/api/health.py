from typing import Any

from fastapi import APIRouter, Request

from app.core.config import settings
from app.core.database import ping

router = APIRouter()


@router.get("/health", response_model=dict[str, Any])
async def health_check(request: Request) -> dict[str, Any]:
    """
    Service health check per contracts/health-check.md.
    Returns status, database connectivity, and service version.
    Always returns HTTP 200 — degraded means the service is up but a dependency is not.
    """
    pool = getattr(request.app.state, "pool", None)

    db_status = "disconnected"
    overall_status = "degraded"

    if pool is not None and await ping(pool):
        db_status = "connected"
        overall_status = "ok"

    return {
        "status": overall_status,
        "database": db_status,
        "version": settings.api_version,
    }
