from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.core.database import get_pool
from app.dependencies.roles import get_current_admin
from app.services import dashboard_service

router = APIRouter()

_VALID_PERIODS = ("today", "7d", "30d", "90d")


@router.get("/overview")
async def get_overview(
    period: str = "7d",
    _admin: dict = Depends(get_current_admin),
) -> dict:
    if period not in _VALID_PERIODS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": f"period must be one of {', '.join(_VALID_PERIODS)}",
            },
        )

    pool = get_pool()
    kpis, rides_trend, commission_trend = await asyncio.gather(
        dashboard_service.get_kpis(pool, period),
        dashboard_service.get_daily_trend(pool, period, "rides_completed"),
        dashboard_service.get_daily_trend(pool, period, "commission_collected_egp"),
    )

    return {
        **kpis,
        "trends": {
            "rides_completed": rides_trend,
            "commission_collected_egp": commission_trend,
        },
    }
