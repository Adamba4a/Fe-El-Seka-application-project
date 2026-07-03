from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class GeoPointSchema(BaseModel):
    lat: float
    lng: float


# ── Request schemas ─────────────────────────────────────────────────────────

class BookingCreateRequest(BaseModel):
    ride_id: UUID
    boarding_point: GeoPointSchema
    alighting_point: GeoPointSchema
    premium_pickup_requested: bool = False
    premium_dropoff_requested: bool = False
    # Fees displayed to the passenger on the detail screen; stored verbatim at booking time
    premium_pickup_fee: Optional[float] = None
    premium_dropoff_fee: Optional[float] = None


class BookingCancelRequest(BaseModel):
    reason: Optional[str] = None


# ── Response schemas ─────────────────────────────────────────────────────────

class BookingResponse(BaseModel):
    booking_id: UUID
    ride_id: UUID
    status: str
    per_seat_price: str
    total_price: str
    premium_pickup_requested: bool
    premium_dropoff_requested: bool
    premium_pickup_fee: Optional[str]
    premium_dropoff_fee: Optional[str]
    created_at: datetime


class BookingListItem(BaseModel):
    booking_id: UUID
    ride_id: UUID
    status: str
    driver_display_name: Optional[str]
    departure_datetime: Optional[datetime]
    per_seat_price: str
    total_price: str
    premium_pickup_requested: bool
    premium_dropoff_requested: bool
    premium_pickup_fee: Optional[str]
    premium_dropoff_fee: Optional[str]
    created_at: datetime
    confirmed_at: Optional[datetime]
    cancelled_at: Optional[datetime]


class BookingListResponse(BaseModel):
    bookings: list[BookingListItem]
    total: int
    page: int
    page_size: int


# ── Driver schemas ───────────────────────────────────────────────────────────

class PassengerSummary(BaseModel):
    display_name: Optional[str]
    avatar_url: Optional[str]


class DriverBookingItem(BaseModel):
    booking_id: UUID
    passenger: PassengerSummary
    status: str
    per_seat_price: str
    total_price: str
    boarding_point: GeoPointSchema
    alighting_point: GeoPointSchema
    premium_pickup_requested: bool
    premium_pickup_fee: Optional[str]
    premium_dropoff_requested: bool
    premium_dropoff_fee: Optional[str]
    created_at: datetime


class DriverBookingListResponse(BaseModel):
    bookings: list[DriverBookingItem]
    total: int


class DriverConfirmResponse(BaseModel):
    booking_id: UUID
    status: str
    confirmed_at: Optional[datetime]


class DriverRejectResponse(BaseModel):
    booking_id: UUID
    status: str
    cancelled_by: Optional[str]
    fallback_applied: bool
