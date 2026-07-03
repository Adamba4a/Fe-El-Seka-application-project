from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ZoneCentroid(BaseModel):
    lat: float
    lng: float


class PassengerRequestFeatures(BaseModel):
    origin_zone: str
    destination_zone: str
    origin_centroid: ZoneCentroid
    destination_centroid: ZoneCentroid
    departure_at: datetime


class CandidateFeatures(BaseModel):
    ride_id: str
    driver_origin_zone: str
    driver_destination_zone: str
    driver_origin_centroid: ZoneCentroid
    driver_dest_centroid: ZoneCentroid
    driver_departure_at: datetime
    estimated_overlap_ratio: float = Field(ge=0.0, le=1.0)
    estimated_pickup_detour_km: float = Field(ge=0.0)
    estimated_dropoff_distance_km: float = Field(ge=0.0)


class AIMatchScoreRequest(BaseModel):
    passenger_request: PassengerRequestFeatures
    candidates: list[CandidateFeatures] = Field(min_length=1, max_length=20)


class ScoredCandidate(BaseModel):
    ride_id: str
    match_score: float
    match_score_pct: int


class AIMatchScoreResponse(BaseModel):
    model_version: str
    scores: list[ScoredCandidate]


class AIRankingRequest(BaseModel):
    candidates: list[ScoredCandidate]


class AIRankingResponse(BaseModel):
    model_version: str
    ranked: list[str]


class AIPriceRequest(BaseModel):
    origin_zone: str
    destination_zone: str
    origin_centroid: ZoneCentroid
    destination_centroid: ZoneCentroid
    estimated_distance_km: float = Field(gt=0.0)
    departure_at: datetime


class AIPriceResponse(BaseModel):
    model_version: str
    min_egp: Decimal
    max_egp: Decimal
