from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies.auth import get_current_user
from app.services.geocode_service import GeocodeServiceUnavailableError, reverse_geocode, search_address

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/reverse")
async def reverse(
    lat: float = Query(...),
    lng: float = Query(...),
    _user: dict = Depends(get_current_user),
) -> dict:
    t0 = time.monotonic()
    status_code = 200
    try:
        try:
            return await reverse_geocode(lat, lng)
        except GeocodeServiceUnavailableError:
            status_code = 503
            raise HTTPException(
                status_code=503,
                detail={"error": "geocode_unavailable", "message": "Address lookup temporarily unavailable"},
            )
    finally:
        logger.info(
            "endpoint=GET /api/geocode/reverse status=%d duration_ms=%d",
            status_code,
            round((time.monotonic() - t0) * 1000),
        )


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    _user: dict = Depends(get_current_user),
) -> dict:
    t0 = time.monotonic()
    status_code = 200
    try:
        try:
            result = await search_address(q)
        except GeocodeServiceUnavailableError:
            status_code = 503
            raise HTTPException(
                status_code=503,
                detail={"error": "geocode_unavailable", "message": "Address lookup temporarily unavailable"},
            )
        if result is None:
            status_code = 404
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "No matching address"})
        return result
    finally:
        logger.info(
            "endpoint=GET /api/geocode/search status=%d duration_ms=%d",
            status_code,
            round((time.monotonic() - t0) * 1000),
        )
