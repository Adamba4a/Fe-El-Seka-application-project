from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.database import get_pool
from app.dependencies.verification import get_current_verified_passenger
from app.models.ai import CandidateFeatures, PassengerRequestFeatures, ZoneCentroid
from app.models.route import GeoPoint
from app.services import ai_client
from app.services import candidate_service
from app.services import match_logging_service
from app.services import ranking_config_service
from app.services.ai_client import AIServiceUnavailableError
from app.services.route_service import RouteServiceUnavailableError
from app.utils.zone_lookup import nearest_zone

router = APIRouter()
logger = logging.getLogger(__name__)

_AI_CANDIDATE_CAP = 20


# ── Request models ────────────────────────────────────────────────────────────

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
    desired_departure_at: Optional[datetime] = None


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


async def _ai_rank(
    candidates,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    departure_at: datetime,
) -> tuple[list, dict[str, int], Optional[str]]:
    """Return (ranked_candidates, score_map, model_version). Raises AIServiceUnavailableError on failure."""
    # Real coordinates go straight into the AI request — zone snapping is only used
    # here to derive a human-readable label, never to substitute for the actual GPS
    # point sent to the model.
    p_origin_zone, _ = nearest_zone(origin_lat, origin_lng)
    p_dest_zone, _ = nearest_zone(dest_lat, dest_lng)

    passenger_req = PassengerRequestFeatures(
        origin_zone=p_origin_zone,
        destination_zone=p_dest_zone,
        origin_centroid=ZoneCentroid(lat=origin_lat, lng=origin_lng),
        destination_centroid=ZoneCentroid(lat=dest_lat, lng=dest_lng),
        departure_at=departure_at,
    )

    capped = candidates[:_AI_CANDIDATE_CAP]

    ai_features: list[CandidateFeatures] = []
    for c in capped:
        if c.driver_origin_lat is None:
            continue
        d_origin_zone, _ = nearest_zone(c.driver_origin_lat, c.driver_origin_lng)
        d_dest_zone, _ = nearest_zone(c.driver_dest_lat, c.driver_dest_lng)
        ai_features.append(
            CandidateFeatures(
                ride_id=str(c.ride_id),
                driver_origin_zone=d_origin_zone,
                driver_destination_zone=d_dest_zone,
                driver_origin_centroid=ZoneCentroid(lat=c.driver_origin_lat, lng=c.driver_origin_lng),
                driver_dest_centroid=ZoneCentroid(lat=c.driver_dest_lat, lng=c.driver_dest_lng),
                driver_departure_at=c.departure_time,
                estimated_overlap_ratio=max(0.0, min(1.0, c.compatibility.overlap_pct / 100)),
                estimated_pickup_detour_km=max(0.0, c.compatibility.pickup_walk_m / 1000),
                estimated_dropoff_distance_km=max(0.0, c.compatibility.dropoff_walk_m / 1000),
            )
        )

    if not ai_features:
        raise AIServiceUnavailableError("No candidates with coordinates for AI scoring")

    scored, model_version = await ai_client.score_candidates(passenger_req, ai_features)

    if len({s.match_score_pct for s in scored}) == 1:
        raise AIServiceUnavailableError("All AI scores identical — degrading to overlap_pct sort")

    ranked_ids = await ai_client.rank_candidates(passenger_req, ai_features)

    score_lookup = {s.ride_id: s for s in scored}
    ranked_scored = [score_lookup[rid] for rid in ranked_ids if rid in score_lookup]

    # Apply 20% threshold with min-3 guarantee (preserve ranked order)
    above = [s for s in ranked_scored if s.match_score_pct >= 20]
    if len(above) < 3:
        below = [s for s in ranked_scored if s.match_score_pct < 20]
        above = above + below[: max(0, 3 - len(above))]
    final_scored = above

    cand_lookup = {str(c.ride_id): c for c in capped}
    ranked_candidates = [cand_lookup[s.ride_id] for s in final_scored if s.ride_id in cand_lookup]
    score_map = {s.ride_id: s.match_score_pct for s in final_scored}

    return ranked_candidates, score_map, model_version


# ── GET /api/v1/search/nearby ─────────────────────────────────────────────────
# Lightweight dashboard preview — no destination, no AI ranking, no route service
# call. Just the closest scheduled rides with open seats to a pickup point.

@router.get("/nearby")
async def nearby_rides(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    limit: int = Query(2, ge=1, le=5),
    _profile: dict = Depends(get_current_verified_passenger),
) -> JSONResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                r.id, r.departure_datetime, r.available_seats, r.price_per_seat,
                r.origin_address, r.destination_address,
                ST_Y(r.destination_coordinates::geometry) AS destination_lat,
                ST_X(r.destination_coordinates::geometry) AS destination_lng,
                ST_Distance(r.origin_coordinates, ST_SetSRID(ST_MakePoint($2, $1), 4326)::geography) AS distance_m,
                p.display_name, p.profile_photo_path AS avatar_url, p.verification_status
            FROM rides r
            JOIN profiles p ON p.id = r.driver_id
            WHERE r.status = 'scheduled'
              AND r.available_seats > 0
              AND r.departure_datetime > now()
            ORDER BY r.origin_coordinates <-> ST_SetSRID(ST_MakePoint($2, $1), 4326)::geography
            LIMIT $3
            """,
            lat, lng, limit,
        )

    rides_out = [
        {
            "ride_id": str(r["id"]),
            "driver": {
                "display_name": r["display_name"],
                "avatar_url": r["avatar_url"],
                "is_verified": r["verification_status"] == "verified",
            },
            "departure_datetime": r["departure_datetime"].isoformat(),
            "available_seats": r["available_seats"],
            "per_seat_price": f"{float(r['price_per_seat']):.2f}",
            "origin_address": r["origin_address"],
            "destination_address": r["destination_address"],
            "destination_lat": float(r["destination_lat"]),
            "destination_lng": float(r["destination_lng"]),
            "distance_meters": round(float(r["distance_m"])),
        }
        for r in rows
    ]
    return JSONResponse({"rides": rides_out})


# ── POST /api/v1/search/rides ─────────────────────────────────────────────────

@router.post("/rides")
async def search_rides(
    body: SearchRidesRequest,
    background_tasks: BackgroundTasks,
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
        return JSONResponse({"candidates": [], "total": 0, "no_rides_found": True, "ai_ranking_active": False})

    driver_ids = list({c.driver_id for c in all_candidates})
    profiles = await _fetch_driver_profiles(driver_ids)

    departure_at = body.desired_departure_at or datetime.now(timezone.utc)

    ai_active = False
    score_map: dict[str, int] = {}
    model_version: Optional[str] = None

    try:
        all_candidates, score_map, model_version = await _ai_rank(
            all_candidates,
            body.origin.lat,
            body.origin.lng,
            body.destination.lat,
            body.destination.lng,
            departure_at,
        )
        ai_active = True
    except AIServiceUnavailableError as exc:
        logger.warning(json.dumps({
            "event": "ai_search_fallback",
            "reason": "identical_scores" if "identical" in str(exc).lower() else type(exc).__name__,
            "candidate_count": len(all_candidates),
            "fallback": "overlap_pct_desc",
        }))
        all_candidates = sorted(all_candidates, key=lambda c: c.compatibility.overlap_pct, reverse=True)

    # Score stays the primary sort key (already applied above, both paths). Within
    # that order, prefer candidates whose departure time is closest to the
    # passenger's desired time — earlier or later, symmetric — as a secondary
    # signal, most relevant when several candidates share a score.
    if ai_active:
        all_candidates = sorted(
            all_candidates,
            key=lambda c: (
                -score_map.get(str(c.ride_id), 0),
                abs((c.departure_time - departure_at).total_seconds()),
            ),
        )
    else:
        all_candidates = sorted(
            all_candidates,
            key=lambda c: (
                -c.compatibility.overlap_pct,
                abs((c.departure_time - departure_at).total_seconds()),
            ),
        )

    all_candidates, explored_ride_id = ranking_config_service.apply_exploration(all_candidates)
    logger.info(json.dumps({
        "event": "exploration_applied",
        "exploration_triggered": explored_ride_id is not None,
        "candidate_count": len(all_candidates),
        "promoted_ride_id": explored_ride_id,
    }))

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
            "match_score_pct": score_map.get(str(c.ride_id)),
            "compatibility": _shape_compatibility(c.compatibility),
        })

    search_ctx = match_logging_service.SearchContext(
        passenger_id=uuid.UUID(str(_profile["id"])),
        origin_lat=body.origin.lat,
        origin_lng=body.origin.lng,
        destination_lat=body.destination.lat,
        destination_lng=body.destination.lng,
        desired_departure_at=departure_at,
        ai_available=ai_active,
    )
    background_tasks.add_task(
        match_logging_service.persist_match_events,
        search_ctx, all_candidates, score_map, ai_active, model_version, explored_ride_id,
    )

    return JSONResponse({
        "candidates": candidates_out,
        "total": len(candidates_out),
        "no_rides_found": False,
        "ai_ranking_active": ai_active,
    })
