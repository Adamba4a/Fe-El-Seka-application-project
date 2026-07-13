from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import asyncpg

from app.core.database import get_pool

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchContext:
    passenger_id: uuid.UUID
    origin_lat: float
    origin_lng: float
    destination_lat: float
    destination_lng: float
    desired_departure_at: datetime
    ai_available: bool


def _build_feature_vector(candidate: Any, predicted_score_pct: Optional[int]) -> dict[str, Any]:
    """Feature values available for this candidate at the point it was shown —
    the same compatibility metrics driving both the AI request and the
    overlap_pct fallback sort, so the shape is identical regardless of
    ai_scored."""
    c = candidate.compatibility
    return {
        "overlap_pct": c.overlap_pct,
        "pickup_walk_m": c.pickup_walk_m,
        "dropoff_walk_m": c.dropoff_walk_m,
        "driver_detour_km": c.detour_km,
        "driver_detour_minutes": c.detour_minutes,
        "candidate_type": candidate.candidate_type,
        "price_per_seat_egp": float(candidate.price_per_seat_egp),
        "predicted_score_pct": predicted_score_pct,
    }


async def persist_match_events(
    search_ctx: SearchContext,
    ranked_candidates: list,
    score_map: dict[str, int],
    ai_scored: bool,
    model_version: Optional[str],
) -> None:
    """Fire-and-forget entry point: persist one search_sessions row and one
    match_events row per shown candidate. Called via asyncio.create_task from
    the search request path — must never raise, since the search response has
    already been (or is about to be) sent regardless of this task's outcome
    (NFR-001)."""
    if not ranked_candidates:
        return
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                search_id = await conn.fetchval(
                    """
                    INSERT INTO search_sessions
                        (passenger_id, origin_point, destination_point, desired_departure_at, ai_available)
                    VALUES (
                        $1,
                        ST_SetSRID(ST_MakePoint($2, $3), 4326),
                        ST_SetSRID(ST_MakePoint($4, $5), 4326),
                        $6, $7
                    )
                    RETURNING id
                    """,
                    search_ctx.passenger_id,
                    search_ctx.origin_lng,
                    search_ctx.origin_lat,
                    search_ctx.destination_lng,
                    search_ctx.destination_lat,
                    search_ctx.desired_departure_at,
                    search_ctx.ai_available,
                )

                rows = []
                for idx, candidate in enumerate(ranked_candidates, start=1):
                    predicted_score_pct = score_map.get(str(candidate.ride_id))
                    predicted_score = (
                        round(predicted_score_pct / 100, 4)
                        if (ai_scored and predicted_score_pct is not None)
                        else None
                    )
                    rows.append((
                        search_id,
                        search_ctx.passenger_id,
                        candidate.ride_id,
                        _build_feature_vector(candidate, predicted_score_pct),
                        predicted_score,
                        idx,
                        False,  # exploration_selected — set by ranking_config_service (User Story 2)
                        ai_scored,
                        model_version if ai_scored else None,
                    ))

                await conn.executemany(
                    """
                    INSERT INTO match_events
                        (search_id, passenger_id, candidate_ride_id, feature_vector,
                         predicted_score, rank_position, exploration_selected,
                         ai_scored, model_version)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    rows,
                )
        logger.info(json.dumps({
            "event": "match_events_persisted",
            "search_id": str(search_id),
            "candidate_count": len(ranked_candidates),
            "ai_scored": ai_scored,
        }))
    except Exception as exc:
        logger.error(json.dumps({
            "event": "match_event_persist_failure",
            "error": str(exc),
        }))


async def record_outcome(
    conn: asyncpg.Connection,  # type: ignore[type-arg]
    ride_id: uuid.UUID,
    passenger_id: uuid.UUID,
    transition_type: str,
    metadata: dict[str, Any],
) -> None:
    """Durable, synchronous outcome recording — called inside an existing
    booking transaction, never fire-and-forget (Match Outcome writes are not
    best-effort). Correlates back to the most recent match_events row for this
    (ride, passenger) pair. No-ops if no matching search-time event exists
    (e.g. a booking that did not originate from a logged search) — outcomes
    are never backfilled retroactively."""
    match_event_id = await conn.fetchval(
        """
        SELECT id FROM match_events
        WHERE candidate_ride_id = $1 AND passenger_id = $2
        ORDER BY created_at DESC
        LIMIT 1
        """,
        ride_id,
        passenger_id,
    )
    if match_event_id is None:
        logger.info(json.dumps({
            "event": "match_outcome_skipped_no_match_event",
            "ride_id": str(ride_id),
            "passenger_id": str(passenger_id),
            "transition_type": transition_type,
        }))
        return

    await conn.execute(
        """
        INSERT INTO match_outcomes (match_event_id, transition_type, metadata)
        VALUES ($1, $2, $3)
        """,
        match_event_id,
        transition_type,
        metadata,
    )
