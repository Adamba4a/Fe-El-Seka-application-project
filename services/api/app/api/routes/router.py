from __future__ import annotations

import logging
import time

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
logger = logging.getLogger(__name__)


@router.post("/fare", response_model=FareEstimateResponse)
async def fare_estimate(body: FareEstimateRequest) -> FareEstimateResponse:
    t0 = time.monotonic()
    status_code = 200
    try:
        try:
            route = await route_service.calculate_route(body.origin, body.destination)
        except RouteServiceUnavailableError:
            status_code = 503
            raise HTTPException(
                status_code=503,
                detail={"error": "route_intelligence_unavailable"},
            )
        if not route.is_routable:
            status_code = 422
            raise HTTPException(
                status_code=422,
                detail={"error": "unroutable"},
            )
        return calculate_fare(route.distance_km, body.seat_count)
    finally:
        logger.info(
            "endpoint=POST /api/routes/fare status=%d duration_ms=%d",
            status_code,
            round((time.monotonic() - t0) * 1000),
        )


@router.post("/candidates", response_model=CandidateListResponse)
async def find_candidates(
    body: CandidateSearchRequest,
    _user: dict = Depends(get_current_user),
) -> CandidateListResponse:
    t0 = time.monotonic()
    status_code = 200
    try:
        try:
            return await candidate_service.generate_candidates(
                body.origin, body.destination, body.departure_time
            )
        except RouteServiceUnavailableError:
            status_code = 503
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "route_intelligence_unavailable",
                    "message": "Route intelligence temporarily unavailable. Please try again shortly.",
                },
            )
    finally:
        logger.info(
            "endpoint=POST /api/routes/candidates status=%d duration_ms=%d",
            status_code,
            round((time.monotonic() - t0) * 1000),
        )
