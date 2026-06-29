from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends

from app.core.database import get_pool
from app.dependencies.roles import get_current_driver
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
    total_pages = max(1, (total + _PER_PAGE - 1) // _PER_PAGE)

    return {
        "balance_egp": str(balance),
        "reserved_egp": str(reserved),
        "available_egp": str(available),
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
