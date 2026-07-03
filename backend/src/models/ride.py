from __future__ import annotations

import uuid
import enum
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from geoalchemy2 import Geography
from geoalchemy2.shape import to_shape
from pydantic import BaseModel
from sqlalchemy import (
    Computed,
    Enum as SAEnum,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, NUMERIC, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


# ─────────────────────────────────────────────────────────────────────────────
# Python enums (mirror the PostgreSQL types)
# ─────────────────────────────────────────────────────────────────────────────

class RideStatus(str, enum.Enum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class RideAction(str, enum.Enum):
    created = "created"
    edited = "edited"
    cancelled = "cancelled"
    started = "started"
    completed = "completed"


class EmailNotificationStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"
    failed_permanent = "failed_permanent"


# ─────────────────────────────────────────────────────────────────────────────
# SQLAlchemy ORM models
# ─────────────────────────────────────────────────────────────────────────────

class Ride(Base):
    __tablename__ = "rides"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    driver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)

    origin_coordinates: Mapped[Any] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    origin_address: Mapped[str] = mapped_column(Text, nullable=False)

    destination_coordinates: Mapped[Any] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    destination_address: Mapped[str] = mapped_column(Text, nullable=False)

    departure_datetime: Mapped[datetime] = mapped_column(nullable=False)

    total_seats: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    booked_seats: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    available_seats: Mapped[int] = mapped_column(SmallInteger, Computed("total_seats - booked_seats", persisted=True), init=False)

    price_per_seat: Mapped[Decimal] = mapped_column(NUMERIC(10, 2), nullable=False)

    status: Mapped[RideStatus] = mapped_column(
        SAEnum(RideStatus, name="ride_status", create_type=False),
        nullable=False,
        default=RideStatus.scheduled,
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancellation_source: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(), onupdate=func.now())


class RideHistoryLog(Base):
    __tablename__ = "ride_history_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ride_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rides.id"), nullable=False)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=True)
    action: Mapped[RideAction] = mapped_column(
        SAEnum(RideAction, name="ride_action", create_type=False),
        nullable=False,
    )
    changed_fields: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class EmailNotification(Base):
    __tablename__ = "email_notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ride_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rides.id"), nullable=False)
    passenger_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    passenger_email: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(Text, nullable=False, default="ride_cancelled")
    status: Mapped[EmailNotificationStatus] = mapped_column(
        SAEnum(EmailNotificationStatus, name="email_notification_status", create_type=False),
        nullable=False,
        default=EmailNotificationStatus.pending,
    )
    retry_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    last_attempted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

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
    price_per_seat: str
    notes: Optional[str] = None


class EditRideRequest(BaseModel):
    destination: Optional[LocationSchema] = None
    departure_datetime: Optional[datetime] = None
    total_seats: Optional[int] = None
    price_per_seat: Optional[str] = None
    notes: Optional[str] = None


class CancelRideRequest(BaseModel):
    reason: str


class HistoryEntryResponse(BaseModel):
    id: uuid.UUID
    actor_id: Optional[uuid.UUID]
    action: str
    changed_fields: Optional[dict]
    reason: Optional[str]
    created_at: datetime


class RideResponse(BaseModel):
    id: uuid.UUID
    driver_id: uuid.UUID
    vehicle_id: uuid.UUID
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


class RideDetailResponse(BaseModel):
    ride: RideResponse
    history: list[HistoryEntryResponse]


class RideListResponse(BaseModel):
    rides: list[RideResponse]
    total: int
    page: int
    page_size: int


def ride_to_response(ride: Ride) -> RideResponse:
    origin_point = to_shape(ride.origin_coordinates)
    dest_point = to_shape(ride.destination_coordinates)
    return RideResponse(
        id=ride.id,
        driver_id=ride.driver_id,
        vehicle_id=ride.vehicle_id,
        origin=LocationSchema(
            coordinates=CoordinatesSchema(lat=origin_point.y, lng=origin_point.x),
            address=ride.origin_address,
        ),
        destination=LocationSchema(
            coordinates=CoordinatesSchema(lat=dest_point.y, lng=dest_point.x),
            address=ride.destination_address,
        ),
        departure_datetime=ride.departure_datetime,
        total_seats=ride.total_seats,
        booked_seats=ride.booked_seats,
        available_seats=ride.available_seats,
        price_per_seat=str(ride.price_per_seat),
        status=ride.status.value if isinstance(ride.status, RideStatus) else ride.status,
        cancellation_reason=ride.cancellation_reason,
        cancellation_source=ride.cancellation_source,
        notes=ride.notes,
        created_at=ride.created_at,
        updated_at=ride.updated_at,
    )
