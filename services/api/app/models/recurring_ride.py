from __future__ import annotations

from datetime import datetime, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.ride import LocationSchema, RideResponse


class RecurringRideDefinitionCreateRequest(BaseModel):
    vehicle_id: UUID
    origin: LocationSchema
    destination: LocationSchema
    departure_time: time
    weekdays: list[int]
    total_seats: int
    price_per_seat: float
    notes: Optional[str] = None


class RecurringRideDefinitionUpdateRequest(BaseModel):
    origin: Optional[LocationSchema] = None
    destination: Optional[LocationSchema] = None
    departure_time: Optional[time] = None
    weekdays: Optional[list[int]] = None
    total_seats: Optional[int] = None
    price_per_seat: Optional[float] = None
    notes: Optional[str] = None


class RecurringRideDefinitionResponse(BaseModel):
    id: UUID
    driver_id: UUID
    vehicle_id: UUID
    origin: LocationSchema
    destination: LocationSchema
    departure_time: time
    weekdays: list[int]
    total_seats: int
    price_per_seat: str
    notes: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    upcoming_instance_count: Optional[int] = None


class RecurringRideDefinitionListResponse(BaseModel):
    definitions: list[RecurringRideDefinitionResponse]


class RecurringRideDefinitionDetailResponse(BaseModel):
    definition: RecurringRideDefinitionResponse
    instances: list[RideResponse]


class RecurringRideDefinitionUpdateResponse(BaseModel):
    definition: RecurringRideDefinitionResponse
    updated_instance_count: int
