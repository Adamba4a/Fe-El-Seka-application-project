from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

# ── Admin-facing schemas ──────────────────────────────────────────────────────

class AdminCarMaintenanceQueueItem(BaseModel):
    id: UUID
    driver_id: UUID
    driver_name: str
    driver_email: str
    amount_egp: Decimal = Field(max_digits=10, decimal_places=2)
    reached_at: datetime


class AdminCarMaintenanceQueueResponse(BaseModel):
    total: int
    page: int
    items: list[AdminCarMaintenanceQueueItem]


class AdminCarMaintenanceFulfillResponse(BaseModel):
    id: UUID
    status: str
    fulfilled_by: UUID
    fulfilled_at: datetime
