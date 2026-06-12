from typing import Any

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health", response_model=dict[str, Any])
async def health_check() -> dict[str, Any]:
    """
    Service health check per contracts/health-check.md.
    AI service has no database dependency in Phase 1.
    """
    return {
        "status": "ok",
        "database": "connected",
        "version": settings.ai_version,
    }
