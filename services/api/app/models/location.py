from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class LocationUpdateRequest(BaseModel):
    lat: float
    lng: float
    bearing: Optional[int] = None
    speed_kmh: Optional[float] = None
    client_timestamp: datetime


class LocationUpdateResponse(BaseModel):
    location_id: UUID
    ride_id: UUID
    updated_at: datetime


class LocationResponse(BaseModel):
    ride_id: UUID
    lat: float
    lng: float
    bearing: Optional[int]
    client_timestamp: datetime
    updated_at: datetime
