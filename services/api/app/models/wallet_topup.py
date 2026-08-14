from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.wallet import PaginationMeta


# ── Driver-facing schemas ─────────────────────────────────────────────────────

class TopupSettingsResponse(BaseModel):
    vodafone_cash_number: str
    is_locked: bool
    support_email: Optional[str] = None


class TopupSubmitResponse(BaseModel):
    id: UUID
    status: str
    amount_egp: Decimal = Field(max_digits=12, decimal_places=2)
    payment_reference: str
    created_at: datetime


class TopupHistoryItem(BaseModel):
    id: UUID
    amount_egp: Decimal = Field(max_digits=12, decimal_places=2)
    payment_reference: str
    status: str
    rejection_reason: Optional[str]
    created_at: datetime
    reviewed_at: Optional[datetime]


class TopupHistoryResponse(BaseModel):
    items: list[TopupHistoryItem]
    pagination: PaginationMeta
    is_locked: bool


class TopupCancelResponse(BaseModel):
    id: UUID
    status: str


# ── Admin request / response schemas ─────────────────────────────────────────

class AdminTopupQueueItem(BaseModel):
    id: UUID
    driver_id: UUID
    driver_name: str
    driver_phone: str
    amount_egp: Decimal = Field(max_digits=12, decimal_places=2)
    payment_reference: str
    screenshot_url: str
    created_at: datetime


class AdminTopupQueueResponse(BaseModel):
    total: int
    page: int
    items: list[AdminTopupQueueItem]


class AdminTopupApproveResponse(BaseModel):
    id: UUID
    status: str
    ledger_entry_id: UUID
    new_balance_egp: Decimal = Field(max_digits=12, decimal_places=2)
    reviewed_by: UUID
    reviewed_at: datetime


class AdminTopupRejectRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_must_be_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reason must not be empty")
        return v


class AdminTopupRejectResponse(BaseModel):
    id: UUID
    status: str
    rejection_reason: str
    reviewed_by: UUID
    reviewed_at: datetime
    driver_locked: bool


class AdminTopupHistoryItem(BaseModel):
    request_id: UUID
    driver_id: UUID
    driver_name: str
    amount_egp: Decimal = Field(max_digits=12, decimal_places=2)
    status: str
    rejection_reason: Optional[str]
    reviewed_by: Optional[UUID]
    reviewed_at: Optional[datetime]
    driver_is_locked: bool


class AdminTopupHistoryResponse(BaseModel):
    total: int
    page: int
    items: list[AdminTopupHistoryItem]


class AdminTopupUnlockResponse(BaseModel):
    driver_id: UUID
    is_topup_locked: bool
