from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.core.database import get_pool
from app.dependencies.roles import get_current_admin
from app.models.car_maintenance import (
    AdminCarMaintenanceFulfillResponse,
    AdminCarMaintenanceQueueResponse,
)
from app.services import car_maintenance_service

router = APIRouter()


@router.get("", response_model=AdminCarMaintenanceQueueResponse)
async def get_queue(
    page: int = 1,
    limit: int = 20,
    _admin: dict = Depends(get_current_admin),
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await car_maintenance_service.list_pending_queue(conn, page, limit)


@router.post("/{reward_id}/fulfill", response_model=AdminCarMaintenanceFulfillResponse)
async def fulfill_reward(
    reward_id: uuid.UUID,
    admin: dict = Depends(get_current_admin),
) -> dict:
    pool = get_pool()
    admin_id = uuid.UUID(str(admin["id"]))
    async with pool.acquire() as conn:
        return await car_maintenance_service.fulfill_reward(conn, reward_id, admin_id)
