from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from app.core.database import get_pool
from app.dependencies.roles import get_current_admin
from app.models.wallet import AdjustRequest, AdjustResponse, TopUpRequest, TopUpResponse
from app.services import wallet_service

router = APIRouter()

_PER_PAGE = 50


# ─────────────────────────────────────────────────────────────────────────────
# GET wallet — summary + paginated ledger
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{driver_id}/wallet")
async def get_driver_wallet(
    driver_id: uuid.UUID,
    page: int = 1,
    _admin: dict = Depends(get_current_admin),
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        wallet = await wallet_service.get_or_create_wallet(conn, driver_id)
        entries, total = await wallet_service.get_ledger_page(conn, driver_id, page, _PER_PAGE)

    balance = Decimal(str(wallet["balance_egp"]))
    reserved = Decimal(str(wallet["reserved_egp"]))
    available = balance - reserved
    total_pages = max(1, (total + _PER_PAGE - 1) // _PER_PAGE)

    return {
        "wallet_id": str(wallet["id"]),
        "driver_id": str(driver_id),
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
                "created_by": str(e["created_by"]) if e["created_by"] else None,
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


# ─────────────────────────────────────────────────────────────────────────────
# POST topup — ADMIN_CREDIT
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{driver_id}/wallet/topup", response_model=TopUpResponse)
async def topup_wallet(
    driver_id: uuid.UUID,
    body: TopUpRequest,
    admin: dict = Depends(get_current_admin),
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            wallet = await wallet_service.get_wallet_with_lock(conn, driver_id)
            await wallet_service.increment_balance(conn, wallet["id"], body.amount_egp)
            entry = await wallet_service.insert_ledger_entry(
                conn,
                wallet_id=wallet["id"],
                driver_id=driver_id,
                entry_type="ADMIN_CREDIT",
                amount=body.amount_egp,
                created_by=uuid.UUID(str(admin["id"])),
                note=body.note,
            )

    new_balance = Decimal(str(wallet["balance_egp"])) + body.amount_egp
    return {
        "wallet_id": wallet["id"],
        "driver_id": driver_id,
        "new_balance_egp": str(new_balance),
        "ledger_entry_id": entry["id"],
        "amount_credited_egp": str(body.amount_egp),
        "created_at": entry["created_at"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST adjust — ADMIN_DEBIT (capped at available balance)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{driver_id}/wallet/adjust", response_model=AdjustResponse)
async def adjust_wallet(
    driver_id: uuid.UUID,
    body: AdjustRequest,
    admin: dict = Depends(get_current_admin),
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            wallet = await wallet_service.get_wallet_with_lock(conn, driver_id)

            balance = Decimal(str(wallet["balance_egp"]))
            reserved = Decimal(str(wallet["reserved_egp"]))
            available = balance - reserved

            if body.amount_egp > available:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "DEBIT_EXCEEDS_AVAILABLE_BALANCE",
                        "message": "Debit amount exceeds available balance.",
                        "available_egp": str(available),
                        "balance_egp": str(balance),
                        "reserved_egp": str(reserved),
                    },
                )

            await wallet_service.decrement_balance(conn, wallet["id"], body.amount_egp)
            entry = await wallet_service.insert_ledger_entry(
                conn,
                wallet_id=wallet["id"],
                driver_id=driver_id,
                entry_type="ADMIN_DEBIT",
                amount=body.amount_egp,
                created_by=uuid.UUID(str(admin["id"])),
                note=body.note,
            )

    new_balance = balance - body.amount_egp
    new_available = new_balance - reserved
    return {
        "wallet_id": wallet["id"],
        "driver_id": driver_id,
        "new_balance_egp": str(new_balance),
        "new_available_egp": str(new_available),
        "ledger_entry_id": entry["id"],
        "amount_debited_egp": str(body.amount_egp),
        "created_at": entry["created_at"],
    }
