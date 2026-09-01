from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.database import get_pool
from app.dependencies.auth import get_current_user
from app.models.loyalty import (
    LoyaltyBalanceResponse,
    LoyaltyCatalogResponse,
    LoyaltyRedeemResponse,
    LoyaltyTransactionsResponse,
)
from app.services import loyalty_service

router = APIRouter()

_PER_PAGE = 50


async def _current_passenger_or_driver(profile: dict = Depends(get_current_user)) -> dict:
    """Loyalty accounts exist per passenger/driver role — admins have neither."""
    if profile.get("role") not in ("passenger", "driver"):
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "Passenger or driver role required"},
        )
    return profile


@router.get("/balance", response_model=LoyaltyBalanceResponse)
async def get_balance(profile: dict = Depends(_current_passenger_or_driver)) -> dict:
    user_id = uuid.UUID(str(profile["id"]))
    role = profile["role"]
    pool = get_pool()
    async with pool.acquire() as conn:
        account = await loyalty_service.get_balance(conn, user_id, role)
    return {"account_id": account["id"], "role": account["role"], "balance": account["balance"]}


@router.get("/transactions", response_model=LoyaltyTransactionsResponse)
async def get_transactions(
    page: int = Query(1, ge=1),
    profile: dict = Depends(_current_passenger_or_driver),
) -> dict:
    user_id = uuid.UUID(str(profile["id"]))
    role = profile["role"]
    pool = get_pool()
    async with pool.acquire() as conn:
        account = await loyalty_service.get_balance(conn, user_id, role)
        entries, total = await loyalty_service.get_ledger_page(conn, account["id"], page, _PER_PAGE)
    return {"items": entries, "total": total, "page": page}


@router.get("/catalog", response_model=LoyaltyCatalogResponse)
async def get_catalog(profile: dict = Depends(_current_passenger_or_driver)) -> dict:
    role = profile["role"]
    pool = get_pool()
    async with pool.acquire() as conn:
        items = await loyalty_service.list_catalog(conn, role)
    return {"items": items}


@router.post("/catalog/{catalog_entry_id}/redeem", response_model=LoyaltyRedeemResponse)
async def redeem_catalog_entry(
    catalog_entry_id: uuid.UUID,
    profile: dict = Depends(_current_passenger_or_driver),
) -> dict:
    user_id = uuid.UUID(str(profile["id"]))
    role = profile["role"]
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await loyalty_service.redeem_catalog_entry(conn, user_id, role, catalog_entry_id)
    return result
