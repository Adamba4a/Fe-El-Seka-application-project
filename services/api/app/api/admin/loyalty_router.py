from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.core.database import get_pool
from app.dependencies.roles import get_current_admin
from app.models.loyalty import (
    AdminLoyaltyQueueActionResponse,
    AdminLoyaltyQueueResponse,
    AdminLoyaltyRejectRequest,
)
from app.services import loyalty_service

router = APIRouter()


@router.get("/queue", response_model=AdminLoyaltyQueueResponse)
async def get_queue(
    page: int = 1,
    limit: int = 20,
    _admin: dict = Depends(get_current_admin),
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await loyalty_service.list_pending_queue(conn, page, limit)


@router.post("/queue/{redemption_request_id}/fulfill", response_model=AdminLoyaltyQueueActionResponse)
async def fulfill_queue_item(
    redemption_request_id: uuid.UUID,
    admin: dict = Depends(get_current_admin),
) -> dict:
    pool = get_pool()
    admin_id = uuid.UUID(str(admin["id"]))
    async with pool.acquire() as conn:
        return await loyalty_service.fulfill_request(conn, redemption_request_id, admin_id)


@router.post("/queue/{redemption_request_id}/reject", response_model=AdminLoyaltyQueueActionResponse)
async def reject_queue_item(
    redemption_request_id: uuid.UUID,
    body: AdminLoyaltyRejectRequest,
    admin: dict = Depends(get_current_admin),
) -> dict:
    pool = get_pool()
    admin_id = uuid.UUID(str(admin["id"]))
    async with pool.acquire() as conn:
        return await loyalty_service.reject_request(conn, redemption_request_id, admin_id, body.reason)
