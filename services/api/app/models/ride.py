from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CoordinatesSchema(BaseModel):
    lat: float
    lng: float


class LocationSchema(BaseModel):
    coordinates: CoordinatesSchema
    address: str


class CreateRideRequest(BaseModel):
    origin: LocationSchema
    destination: LocationSchema
    departure_datetime: datetime
    total_seats: int
    notes: Optional[str] = None


class EditRideRequest(BaseModel):
    destination: Optional[LocationSchema] = None
    departure_datetime: Optional[datetime] = None
    total_seats: Optional[int] = None
    notes: Optional[str] = None


class CancelRideRequest(BaseModel):
    reason: str


class RevocationPayload(BaseModel):
    driver_id: UUID
    revocation_type: str


class HistoryEntryResponse(BaseModel):
    id: UUID
    actor_id: Optional[UUID]
    action: str
    changed_fields: Optional[dict]
    reason: Optional[str]
    created_at: datetime


class RideResponse(BaseModel):
    id: UUID
    driver_id: UUID
    vehicle_id: UUID
    origin: LocationSchema
    destination: LocationSchema
    departure_datetime: datetime
    total_seats: int
    booked_seats: int
    available_seats: int
    price_per_seat: str
    status: str
    cancellation_reason: Optional[str]
    cancellation_source: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    route_distance_km: Optional[float] = None
    route_duration_minutes: Optional[int] = None
    fuel_cost_egp: Optional[float] = None
    platform_commission_egp: Optional[float] = None
    safety_margin_egp: Optional[float] = None
    price_source: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class RideDetailResponse(BaseModel):
    ride: RideResponse
    history: list[HistoryEntryResponse]


class RideListResponse(BaseModel):
    rides: list[RideResponse]
    total: int
    page: int
    page_size: int
