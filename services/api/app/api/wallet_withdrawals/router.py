from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.core.database import get_pool
from app.dependencies.roles import get_current_driver
from app.models.withdrawal import (
    WithdrawalHistoryResponse,
    WithdrawalSubmitRequest,
    WithdrawalSubmitResponse,
)
from app.services import withdrawal_service

router = APIRouter()


@router.post("", response_model=WithdrawalSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_request(
    body: WithdrawalSubmitRequest,
    driver: dict = Depends(get_current_driver),
) -> dict:
    driver_id = uuid.UUID(str(driver["id"]))
    pool = get_pool()
    async with pool.acquire() as conn:
        return await withdrawal_service.submit_request(
            conn, driver_id, body.amount_egp, body.payout_reference,
        )


@router.get("", response_model=WithdrawalHistoryResponse)
async def get_history(
    page: int = 1,
    per_page: int = 20,
    driver: dict = Depends(get_current_driver),
) -> dict:
    driver_id = uuid.UUID(str(driver["id"]))
    pool = get_pool()
    async with pool.acquire() as conn:
        return await withdrawal_service.list_driver_history(conn, driver_id, page, per_page)
