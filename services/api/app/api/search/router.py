from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.database import get_pool
from app.dependencies.verification import get_current_verified_passenger
from app.models.route import GeoPoint
from app.services import candidate_service
from app.services.route_service import RouteServiceUnavailableError

router = APIRouter()


# ── Request / Response models ────────────────────────────────────────────────

class _LatLng(BaseModel):
    lat: float
    lng: float


class _Bbox(BaseModel):
    south: float
    north: float
    west: float
    east: float


class SearchRidesRequest(BaseModel):
    origin: _LatLng
    destination: _LatLng
    dest_bbox: Optional[_Bbox] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _fetch_driver_profiles(driver_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    if not driver_ids:
        return {}
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, display_name, profile_photo_path AS avatar_url, verification_status
            FROM profiles
            WHERE id = ANY($1::uuid[])
            """,
            driver_ids,
        )
    return {row["id"]: dict(row) for row in rows}


def _shape_compatibility(c) -> dict:
    return {
        "overlap_percentage": c.overlap_pct,
        "pickup_walk_meters": c.pickup_walk_m,
        "dropoff_walk_meters": c.dropoff_walk_m,
        "driver_detour_km": c.detour_km,
        "driver_detour_minutes": c.detour_minutes,
        "is_compatible": c.is_compatible,
        "premium_pickup_available": c.premium_pickup_available,
        "premium_pickup_fee": c.premium_pickup_fee_egp,
        "premium_dropoff_available": c.premium_dropoff_available,
        "premium_dropoff_fee": c.premium_dropoff_fee_egp,
    }


# ── POST /api/v1/search/rides ─────────────────────────────────────────────────

@router.post("/rides")
async def search_rides(
    body: SearchRidesRequest,
    _profile: dict = Depends(get_current_verified_passenger),
) -> JSONResponse:
    origin = GeoPoint(lat=body.origin.lat, lng=body.origin.lng)
    destination = GeoPoint(lat=body.destination.lat, lng=body.destination.lng)

    dest_bbox = dict(body.dest_bbox) if body.dest_bbox else None

    try:
        result = await candidate_service.generate_candidates(
            origin=origin,
            destination=destination,
            dest_bbox=dest_bbox,
        )
    except RouteServiceUnavailableError:
        return JSONResponse(
            status_code=503,
            content={"error": "routing_unavailable", "message": "Route service unavailable — please try again shortly"},
        )

    all_candidates = list(result.standard) + list(result.premium)

    if not all_candidates:
        return JSONResponse({"candidates": [], "total": 0, "no_rides_found": True})

    driver_ids = list({c.driver_id for c in all_candidates})
    profiles = await _fetch_driver_profiles(driver_ids)

    candidates_out = []
    for c in all_candidates:
        prof = profiles.get(c.driver_id, {})
        candidates_out.append({
            "ride_id": str(c.ride_id),
            "driver": {
                "display_name": prof.get("display_name"),
                "avatar_url": prof.get("avatar_url"),
                "is_verified": prof.get("verification_status") == "verified",
            },
            "departure_datetime": c.departure_time.isoformat(),
            "available_seats": c.available_seats,
            "per_seat_price": f"{c.price_per_seat_egp:.2f}",
            "candidate_type": c.candidate_type,
            "compatibility": _shape_compatibility(c.compatibility),
        })

    return JSONResponse({
        "candidates": candidates_out,
        "total": len(candidates_out),
        "no_rides_found": False,
    })
