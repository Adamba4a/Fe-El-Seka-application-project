from datetime import datetime

from pydantic import BaseModel, Field


class ZoneCoords(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class MatchScoreRequest(BaseModel):
    passenger_origin: ZoneCoords
    passenger_destination: ZoneCoords
    driver_origin: ZoneCoords
    driver_destination: ZoneCoords
    overlap_ratio: float = Field(..., ge=0.0, le=1.0)
    pickup_detour_km: float = Field(..., ge=0.0)
    dropoff_distance_km: float = Field(..., ge=0.0)
    departure_at: datetime


class MatchScoreItem(BaseModel):
    candidate_id: str
    score: float = Field(..., ge=0.0, le=1.0)


class MatchScoreResponse(BaseModel):
    scores: list[MatchScoreItem]
    model_version: str


class MatchScoreBatchRequest(BaseModel):
    candidates: list[MatchScoreRequest] = Field(..., min_length=1, max_length=200)


class RideRankingRequest(BaseModel):
    candidate_id: str
    passenger_origin: ZoneCoords
    passenger_destination: ZoneCoords
    driver_origin: ZoneCoords
    driver_destination: ZoneCoords
    overlap_ratio: float = Field(..., ge=0.0, le=1.0)
    pickup_detour_km: float = Field(..., ge=0.0)
    dropoff_distance_km: float = Field(..., ge=0.0)
    departure_at: datetime


class RideRankingBatchRequest(BaseModel):
    candidates: list[RideRankingRequest] = Field(..., min_length=1, max_length=200)


class RankedRide(BaseModel):
    candidate_id: str
    rank: int
    score: float = Field(..., ge=0.0, le=1.0)


class RideRankingResponse(BaseModel):
    ranked: list[RankedRide]
    model_version: str
