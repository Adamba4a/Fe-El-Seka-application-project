from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.core.database import get_pool
from app.dependencies.roles import get_current_admin
from app.models.withdrawal import (
    AdminWithdrawalApproveResponse,
    AdminWithdrawalHistoryResponse,
    AdminWithdrawalQueueResponse,
    AdminWithdrawalRejectRequest,
    AdminWithdrawalRejectResponse,
)
from app.services import withdrawal_service

router = APIRouter()


@router.get("", response_model=AdminWithdrawalQueueResponse)
async def get_queue(
    page: int = 1,
    limit: int = 20,
    _admin: dict = Depends(get_current_admin),
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await withdrawal_service.list_pending_queue(conn, page, limit)


@router.get("/history", response_model=AdminWithdrawalHistoryResponse)
async def get_history(
    page: int = 1,
    outcome: str | None = None,
    q: str | None = None,
    _admin: dict = Depends(get_current_admin),
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await withdrawal_service.list_review_history(conn, page, outcome, q)


@router.post("/{request_id}/approve", response_model=AdminWithdrawalApproveResponse)
async def approve_request(
    request_id: uuid.UUID,
    admin: dict = Depends(get_current_admin),
) -> dict:
    pool = get_pool()
    admin_id = uuid.UUID(str(admin["id"]))
    async with pool.acquire() as conn:
        return await withdrawal_service.approve_request(conn, request_id, admin_id)


@router.post("/{request_id}/reject", response_model=AdminWithdrawalRejectResponse)
async def reject_request(
    request_id: uuid.UUID,
    body: AdminWithdrawalRejectRequest,
    admin: dict = Depends(get_current_admin),
) -> dict:
    pool = get_pool()
    admin_id = uuid.UUID(str(admin["id"]))
    async with pool.acquire() as conn:
        return await withdrawal_service.reject_request(conn, request_id, admin_id, body.reason)
