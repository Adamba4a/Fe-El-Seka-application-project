from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.core.database import get_pool
from app.dependencies.roles import get_current_admin
from app.models.loyalty import (
    AdminLoyaltyCatalogCreateRequest,
    AdminLoyaltyCatalogEntry,
    AdminLoyaltyCatalogListResponse,
    AdminLoyaltyCatalogUpdateRequest,
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


@router.get("/catalog", response_model=AdminLoyaltyCatalogListResponse)
async def get_admin_catalog(_admin: dict = Depends(get_current_admin)) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        items = await loyalty_service.list_admin_catalog(conn)
    return {"items": items}


@router.post("/catalog", response_model=AdminLoyaltyCatalogEntry)
async def create_catalog_voucher(
    body: AdminLoyaltyCatalogCreateRequest,
    admin: dict = Depends(get_current_admin),
) -> dict:
    pool = get_pool()
    admin_id = uuid.UUID(str(admin["id"]))
    async with pool.acquire() as conn:
        return await loyalty_service.create_voucher(
            conn, admin_id, body.title, body.description, body.audience, body.point_cost, body.fulfillment_mode
        )


@router.patch("/catalog/{catalog_entry_id}", response_model=AdminLoyaltyCatalogEntry)
async def update_catalog_entry(
    catalog_entry_id: uuid.UUID,
    body: AdminLoyaltyCatalogUpdateRequest,
    _admin: dict = Depends(get_current_admin),
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await loyalty_service.update_catalog_entry(conn, catalog_entry_id, body.model_dump(exclude_none=True))


@router.delete("/catalog/{catalog_entry_id}", response_model=AdminLoyaltyCatalogEntry)
async def retire_catalog_entry(
    catalog_entry_id: uuid.UUID,
    _admin: dict = Depends(get_current_admin),
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await loyalty_service.retire_catalog_entry(conn, catalog_entry_id)
