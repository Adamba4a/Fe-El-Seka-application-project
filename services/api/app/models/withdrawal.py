from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.wallet import PaginationMeta

# ── Driver-facing schemas ─────────────────────────────────────────────────────

class WithdrawalSubmitRequest(BaseModel):
    amount_egp: Decimal = Field(max_digits=12, decimal_places=2)
    payout_reference: str


class WithdrawalSubmitResponse(BaseModel):
    id: UUID
    status: str
    amount_egp: Decimal = Field(max_digits=12, decimal_places=2)
    payout_reference: str
    created_at: datetime


class WithdrawalHistoryItem(BaseModel):
    id: UUID
    amount_egp: Decimal = Field(max_digits=12, decimal_places=2)
    payout_reference: str
    status: str
    rejection_reason: Optional[str]
    created_at: datetime
    reviewed_at: Optional[datetime]


class WithdrawalHistoryResponse(BaseModel):
    items: list[WithdrawalHistoryItem]
    pagination: PaginationMeta


# ── Admin request / response schemas ─────────────────────────────────────────

class AdminWithdrawalQueueItem(BaseModel):
    id: UUID
    driver_id: UUID
    driver_name: str
    driver_email: str
    amount_egp: Decimal = Field(max_digits=12, decimal_places=2)
    payout_reference: str
    created_at: datetime


class AdminWithdrawalQueueResponse(BaseModel):
    total: int
    page: int
    items: list[AdminWithdrawalQueueItem]


class AdminWithdrawalApproveResponse(BaseModel):
    id: UUID
    status: str
    ledger_entry_id: UUID
    new_balance_egp: Decimal = Field(max_digits=12, decimal_places=2)
    reviewed_by: UUID
    reviewed_at: datetime


class AdminWithdrawalRejectRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_must_be_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reason must not be empty")
        return v


class AdminWithdrawalRejectResponse(BaseModel):
    id: UUID
    status: str
    rejection_reason: str
    reviewed_by: UUID
    reviewed_at: datetime


class AdminWithdrawalHistoryItem(BaseModel):
    request_id: UUID
    driver_id: UUID
    driver_name: str
    amount_egp: Decimal = Field(max_digits=12, decimal_places=2)
    status: str
    rejection_reason: Optional[str]
    reviewed_by: Optional[UUID]
    reviewed_at: Optional[datetime]


class AdminWithdrawalHistoryResponse(BaseModel):
    total: int
    page: int
    items: list[AdminWithdrawalHistoryItem]
