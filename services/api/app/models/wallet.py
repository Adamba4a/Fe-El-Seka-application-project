from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator


class LedgerEntryType(str, Enum):
    COMMISSION_DEBIT = "COMMISSION_DEBIT"
    ADMIN_CREDIT = "ADMIN_CREDIT"
    ADMIN_DEBIT = "ADMIN_DEBIT"
    SPONSORED_RIDE_CREDIT = "SPONSORED_RIDE_CREDIT"
    SPONSORED_RIDE_REVERSAL = "SPONSORED_RIDE_REVERSAL"
    WITHDRAWAL_DEBIT = "WITHDRAWAL_DEBIT"
    CASH_BACK_CREDIT = "CASH_BACK_CREDIT"
    CASH_BACK_REVERSAL = "CASH_BACK_REVERSAL"
    POINTS_DISCOUNT_REIMBURSEMENT = "POINTS_DISCOUNT_REIMBURSEMENT"
    CASH_BACK_REDEEMED = "CASH_BACK_REDEEMED"


# ── Response schemas ─────────────────────────────────────────────────────────

class LedgerEntryResponse(BaseModel):
    id: UUID
    type: LedgerEntryType
    amount_egp: str
    ride_id: Optional[UUID]
    booking_id: Optional[UUID]
    fuel_cost_egp_snapshot: Optional[str]
    created_by: Optional[UUID]
    note: Optional[str]
    created_at: datetime


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total_entries: int
    total_pages: int


class WalletPageResponse(BaseModel):
    balance_egp: str
    reserved_egp: str
    available_egp: str
    sponsored_earnings_egp: str
    cash_back_points_egp: str
    entries: list[LedgerEntryResponse]
    pagination: PaginationMeta


# ── Cash Back redeem schemas ─────────────────────────────────────────────────

class CashBackRedeemRequest(BaseModel):
    amount_egp: Decimal

    @field_validator("amount_egp")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount_egp must be greater than 0.00 EGP")
        return v


class CashBackRedeemResponse(BaseModel):
    id: UUID
    amount_egp: str
    cash_back_points_egp: str
    sponsored_earnings_egp: str
    created_at: datetime


# ── Admin request / response schemas ─────────────────────────────────────────

class TopUpRequest(BaseModel):
    amount_egp: Decimal
    note: Optional[str] = None

    @field_validator("amount_egp")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount_egp must be greater than 0.00 EGP")
        return v


class TopUpResponse(BaseModel):
    wallet_id: UUID
    driver_id: UUID
    new_balance_egp: str
    ledger_entry_id: UUID
    amount_credited_egp: str
    created_at: datetime


class AdjustRequest(BaseModel):
    amount_egp: Decimal
    note: Optional[str] = None

    @field_validator("amount_egp")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount_egp must be greater than 0.00 EGP")
        return v


class AdjustResponse(BaseModel):
    wallet_id: UUID
    driver_id: UUID
    new_balance_egp: str
    new_available_egp: str
    ledger_entry_id: UUID
    amount_debited_egp: str
    created_at: datetime
