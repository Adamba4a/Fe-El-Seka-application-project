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
    journey_type: str = "one_way"
    is_women_only: bool = False
    return_departure_time: Optional[time] = None
    return_total_seats: Optional[int] = None
    return_price_per_seat: Optional[float] = None


class RecurringRideDefinitionUpdateRequest(BaseModel):
    origin: Optional[LocationSchema] = None
    destination: Optional[LocationSchema] = None
    departure_time: Optional[time] = None
    weekdays: Optional[list[int]] = None
    total_seats: Optional[int] = None
    price_per_seat: Optional[float] = None
    notes: Optional[str] = None
    journey_type: Optional[str] = None
    is_women_only: Optional[bool] = None
    return_departure_time: Optional[time] = None
    return_total_seats: Optional[int] = None
    return_price_per_seat: Optional[float] = None


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
    journey_type: str = "one_way"
    is_women_only: bool = False
    return_departure_time: Optional[time] = None
    return_total_seats: Optional[int] = None
    return_price_per_seat: Optional[str] = None


class RecurringRideDefinitionListResponse(BaseModel):
    definitions: list[RecurringRideDefinitionResponse]


class RecurringRideDefinitionDetailResponse(BaseModel):
    definition: RecurringRideDefinitionResponse
    instances: list[RideResponse]


class RecurringRideDefinitionUpdateResponse(BaseModel):
    definition: RecurringRideDefinitionResponse
    updated_instance_count: int


class RecurringOccurrenceOverrideRequest(BaseModel):
    outbound_departure_datetime: datetime
    return_departure_datetime: datetime
