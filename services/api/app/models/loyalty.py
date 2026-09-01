from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# ── Passenger / driver facing ────────────────────────────────────────────────

class LoyaltyBalanceResponse(BaseModel):
    account_id: UUID
    role: Literal["passenger", "driver"]
    balance: int


class LoyaltyTransactionItem(BaseModel):
    id: UUID
    delta: int
    reason: str
    balance_after: int
    ride_id: Optional[UUID] = None
    booking_id: Optional[UUID] = None
    redemption_request_id: Optional[UUID] = None
    created_at: datetime


class LoyaltyTransactionsResponse(BaseModel):
    items: list[LoyaltyTransactionItem]
    total: int
    page: int


class LoyaltyCatalogItem(BaseModel):
    id: UUID
    type: str
    title: str
    description: str
    point_cost: int
    fulfillment_mode: str


class LoyaltyCatalogResponse(BaseModel):
    items: list[LoyaltyCatalogItem]


class LoyaltyRedeemResponse(BaseModel):
    redemption_request_id: UUID
    status: Literal["fulfilled", "pending"]
    points_spent: int
    balance_after: int


# ── Booking-time inline redemption ──────────────────────────────────────────

class LoyaltyRedemptionResult(BaseModel):
    redemption_request_id: UUID
    points_spent: int
    fare_after_discount_egp: Decimal = Field(max_digits=10, decimal_places=2)


# ── Admin-facing ──────────────────────────────────────────────────────────────

class AdminLoyaltyQueueCatalogRef(BaseModel):
    type: str
    title: str


class AdminLoyaltyQueueItem(BaseModel):
    id: UUID
    user_id: UUID
    user_name: str
    user_email: str
    role: Literal["passenger", "driver"]
    catalog_entry: AdminLoyaltyQueueCatalogRef
    points_spent: int
    created_at: datetime


class AdminLoyaltyQueueResponse(BaseModel):
    total: int
    page: int
    items: list[AdminLoyaltyQueueItem]


class AdminLoyaltyQueueActionResponse(BaseModel):
    id: UUID
    status: str
    fulfilled_by: Optional[UUID] = None
    fulfilled_at: Optional[datetime] = None


class AdminLoyaltyRejectRequest(BaseModel):
    reason: str


class AdminLoyaltyCatalogEntry(BaseModel):
    id: UUID
    type: str
    title: str
    description: str
    audience: str
    point_cost: int
    fulfillment_mode: str
    active: bool
    created_at: datetime
    updated_at: datetime


class AdminLoyaltyCatalogListResponse(BaseModel):
    items: list[AdminLoyaltyCatalogEntry]


class AdminLoyaltyCatalogCreateRequest(BaseModel):
    title: str
    description: str
    audience: Literal["passenger", "driver", "both"]
    point_cost: int = Field(gt=0)
    fulfillment_mode: Literal["instant", "manual"] = "instant"


class AdminLoyaltyCatalogUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    point_cost: Optional[int] = Field(default=None, gt=0)
    fulfillment_mode: Optional[Literal["instant", "manual"]] = None
    active: Optional[bool] = None
    # System entries only (free_ride / discount) — paired platform_settings value.
    loyalty_free_ride_max_fare_egp: Optional[Decimal] = Field(
        default=None, max_digits=10, decimal_places=2
    )
    loyalty_discount_percentage: Optional[int] = Field(default=None, ge=0, le=100)
