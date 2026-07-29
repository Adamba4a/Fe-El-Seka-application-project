from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ReportCategory = Literal[
    "unsafe_driving", "harassment", "no_show", "fraud_or_scam", "vehicle_mismatch", "other",
]


class ReportCreateRequest(BaseModel):
    ride_id: UUID
    booking_id: UUID
    reported_user_id: UUID
    category: ReportCategory
    description: str = Field(min_length=1, max_length=1000)


class ReportCreateResponse(BaseModel):
    report_id: UUID
    status: str


class ReportListItem(BaseModel):
    report_id: UUID
    category: str
    status: str
    created_at: datetime


class ReportListResponse(BaseModel):
    items: list[ReportListItem]
