from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RatingCreateRequest(BaseModel):
    booking_id: UUID
    stars: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=500)


class RatingCreateResponse(BaseModel):
    rating_id: UUID
    booking_id: UUID
    revealed: bool


class RatingCommentItem(BaseModel):
    comment: str
    created_at: datetime


class RatingSummaryResponse(BaseModel):
    rating_avg: Optional[float]
    rating_count: int
    comments: list[RatingCommentItem]
