from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.auth import get_current_user
from app.models.route import (
    CandidateListResponse,
    CandidateSearchRequest,
    FareEstimateRequest,
    FareEstimateResponse,
)
from app.services import candidate_service, route_service
from app.services.pricing_service import calculate_fare
from app.services.route_service import RouteServiceUnavailableError

router = APIRouter()


@router.post("/fare", response_model=FareEstimateResponse)
async def fare_estimate(body: FareEstimateRequest) -> FareEstimateResponse:
    try:
        route = await route_service.calculate_route(body.origin, body.destination)
    except RouteServiceUnavailableError:
        raise HTTPException(
            status_code=503,
            detail={"error": "route_intelligence_unavailable"},
        )
    if not route.is_routable:
        raise HTTPException(
            status_code=422,
            detail={"error": "unroutable"},
        )
    return calculate_fare(route.distance_km, body.seat_count)


@router.post("/candidates", response_model=CandidateListResponse)
async def find_candidates(
    body: CandidateSearchRequest,
    _user: dict = Depends(get_current_user),
) -> CandidateListResponse:
    try:
        return await candidate_service.generate_candidates(
            body.origin, body.destination, body.departure_time
        )
    except RouteServiceUnavailableError:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "route_intelligence_unavailable",
                "message": "Route intelligence temporarily unavailable. Please try again shortly.",
            },
        )
