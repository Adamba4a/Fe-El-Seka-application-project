from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.database import get_pool
from app.dependencies.roles import get_current_driver
from app.models.wallet_topup import TopupSettingsResponse, TopupSubmitResponse
from app.services import wallet_topup_service

router = APIRouter()


@router.get("/settings", response_model=TopupSettingsResponse)
async def get_settings(driver: dict = Depends(get_current_driver)) -> dict:
    driver_id = uuid.UUID(str(driver["id"]))
    pool = get_pool()
    async with pool.acquire() as conn:
        return await wallet_topup_service.get_settings(conn, driver_id)


@router.post("", response_model=TopupSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_request(
    amount_egp: str = Form(...),
    payment_reference: str = Form(...),
    screenshot: UploadFile = File(...),
    driver: dict = Depends(get_current_driver),
) -> dict:
    try:
        amount = Decimal(amount_egp)
    except InvalidOperation as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "validation_error", "message": "amount_egp must be a valid number"},
        ) from exc

    driver_id = uuid.UUID(str(driver["id"]))
    pool = get_pool()
    async with pool.acquire() as conn:
        return await wallet_topup_service.submit_request(
            conn, driver_id, amount, payment_reference, screenshot,
        )
