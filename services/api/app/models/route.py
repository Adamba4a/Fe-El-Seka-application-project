from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GeoPoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class RouteGeometry(BaseModel):
    distance_km: float
    duration_minutes: int
    geojson_linestring: dict
    is_routable: bool


class CompatibilityResult(BaseModel):
    overlap_pct: float
    pickup_walk_m: float
    dropoff_walk_m: float
    detour_km: float
    detour_minutes: int
    is_compatible: bool

    premium_pickup_available: bool
    premium_pickup_detour_km: float
    premium_pickup_fee_egp: Optional[float] = None

    premium_dropoff_available: bool
    premium_dropoff_detour_km: float
    premium_dropoff_fee_egp: Optional[float] = None

    # No detour required — the driver already ends their route near the
    # passenger's real destination; the passenger arranges their own onward
    # transport from there. Only computed when neither a standard nor a
    # premium dropoff match applies.
    nearby_endpoint_available: bool = False
    nearby_endpoint_distance_km: float = 0.0
    nearby_endpoint_duration_minutes: int = 0


class RideCandidate(BaseModel):
    ride_id: UUID
    driver_id: UUID
    departure_time: datetime
    available_seats: int
    price_per_seat_egp: float
    candidate_type: str
    compatibility: CompatibilityResult
    driver_origin_lat: Optional[float] = None
    driver_origin_lng: Optional[float] = None
    driver_dest_lat: Optional[float] = None
    driver_dest_lng: Optional[float] = None


class CandidateSearchRequest(BaseModel):
    origin: GeoPoint
    destination: GeoPoint
    departure_time: datetime


class CandidateListResponse(BaseModel):
    standard: list[RideCandidate]
    premium: list[RideCandidate]
    nearby: list[RideCandidate] = []
    total_count: int


class FareEstimateRequest(BaseModel):
    origin: GeoPoint
    destination: GeoPoint
    seat_count: int = Field(..., ge=1, le=8)


class FareEstimateResponse(BaseModel):
    distance_km: float
    fuel_price_per_litre_egp: float
    fuel_cost_egp: float
    platform_commission_egp: float
    safety_margin_egp: float
    seat_count: int
    per_seat_price_egp: float
    total_collected_egp: float


class CompatibilityFeaturesRequest(BaseModel):
    ride_id: UUID
    passenger_origin: GeoPoint
    passenger_destination: GeoPoint
    requested_departure_time: datetime


class CompatibilityFeatures(BaseModel):
    ride_id: UUID
    overlap_pct: float
    pickup_walk_m: float
    dropoff_walk_m: float
    detour_km: float
    detour_minutes: int
    passenger_route_km: float
    driver_route_km: float
    available_seats: int
    departure_delta_minutes: int
    price_per_seat_egp: float
    is_compatible: bool
    premium_pickup_available: bool
    premium_dropoff_available: bool
