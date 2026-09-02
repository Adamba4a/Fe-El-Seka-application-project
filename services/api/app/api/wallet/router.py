from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, status

from app.core.database import get_pool
from app.dependencies.roles import get_current_driver
from app.models.wallet import CashBackRedeemRequest, CashBackRedeemResponse
from app.services import wallet_service

router = APIRouter()

_PER_PAGE = 50


@router.get("/wallet")
async def get_my_wallet(
    page: int = 1,
    driver: dict = Depends(get_current_driver),
) -> dict:
    """Return the authenticated driver's wallet summary and paginated ledger."""
    driver_id = uuid.UUID(str(driver["id"]))

    pool = get_pool()
    async with pool.acquire() as conn:
        wallet = await wallet_service.get_or_create_wallet(conn, driver_id)
        entries, total = await wallet_service.get_ledger_page(conn, driver_id, page, _PER_PAGE)

    balance = Decimal(str(wallet["balance_egp"]))
    reserved = Decimal(str(wallet["reserved_egp"]))
    available = balance - reserved
    sponsored_earnings = Decimal(str(wallet["sponsored_earnings_egp"]))
    cash_back_points = Decimal(str(wallet["cash_back_points_egp"]))
    total_pages = max(1, (total + _PER_PAGE - 1) // _PER_PAGE)

    return {
        "balance_egp": str(balance),
        "reserved_egp": str(reserved),
        "available_egp": str(available),
        "sponsored_earnings_egp": str(sponsored_earnings),
        "cash_back_points_egp": str(cash_back_points),
        "entries": [
            {
                "id": str(e["id"]),
                "type": e["type"],
                "amount_egp": str(e["amount_egp"]),
                "ride_id": str(e["ride_id"]) if e["ride_id"] else None,
                "booking_id": str(e["booking_id"]) if e["booking_id"] else None,
                "fuel_cost_egp_snapshot": str(e["fuel_cost_egp_snapshot"]) if e["fuel_cost_egp_snapshot"] else None,
                "note": e["note"],
                "created_at": e["created_at"].isoformat(),
            }
            for e in entries
        ],
        "pagination": {
            "page": page,
            "per_page": _PER_PAGE,
            "total_entries": total,
            "total_pages": total_pages,
        },
    }


@router.post(
    "/wallet/cash-back/redeem",
    response_model=CashBackRedeemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def redeem_cash_back(
    body: CashBackRedeemRequest,
    driver: dict = Depends(get_current_driver),
) -> dict:
    """Move points from cash_back_points_egp into the withdrawable sponsored_earnings_egp pool."""
    driver_id = uuid.UUID(str(driver["id"]))
    pool = get_pool()
    async with pool.acquire() as conn:
        entry = await wallet_service.redeem_cash_back_points(conn, driver_id, body.amount_egp)

    return {
        "id": entry["id"],
        "amount_egp": str(entry["amount_egp"]),
        "cash_back_points_egp": str(entry["cash_back_points_egp"]),
        "sponsored_earnings_egp": str(entry["sponsored_earnings_egp"]),
        "created_at": entry["created_at"],
    }
