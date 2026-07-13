from __future__ import annotations

import json
import logging
import time

import httpx

from app.models.ai import (
    CandidateFeatures,
    PassengerRequestFeatures,
    ScoredCandidate,
)

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


class AIServiceUnavailableError(Exception):
    pass


async def init(base_url: str) -> httpx.AsyncClient:
    global _client
    # Stateless: auto-reconnects on next request after AI service restart — no manual reset needed
    _client = httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(1.0))
    return _client


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _get() -> httpx.AsyncClient:
    if _client is None:
        raise AIServiceUnavailableError("AI client not initialized")
    return _client


def _candidate_route_payload(
    passenger_req: PassengerRequestFeatures,
    c: CandidateFeatures,
) -> dict:
    return {
        "passenger_origin": passenger_req.origin_centroid.model_dump(mode="json"),
        "passenger_destination": passenger_req.destination_centroid.model_dump(mode="json"),
        "driver_origin": c.driver_origin_centroid.model_dump(mode="json"),
        "driver_destination": c.driver_dest_centroid.model_dump(mode="json"),
        "overlap_ratio": c.estimated_overlap_ratio,
        "pickup_detour_km": c.estimated_pickup_detour_km,
        "dropoff_distance_km": c.estimated_dropoff_distance_km,
        "departure_at": c.driver_departure_at.isoformat(),
    }


async def score_candidates(
    passenger_req: PassengerRequestFeatures,
    candidates: list[CandidateFeatures],
) -> list[ScoredCandidate]:
    client = _get()
    payload = {
        "candidates": [_candidate_route_payload(passenger_req, c) for c in candidates]
    }
    _t0 = time.monotonic()
    _fallback = False
    _model_ver = None
    resp_json: dict | None = None
    try:
        resp = await client.post(
            "/predict/match-score",
            json=payload,
        )
        resp.raise_for_status()
        resp_json = resp.json()
        _model_ver = resp_json.get("model_version")
    except httpx.TimeoutException as exc:
        _fallback = True
        logger.warning("AI match-score timed out")
        raise AIServiceUnavailableError("AI service timed out") from exc
    except httpx.RequestError as exc:
        _fallback = True
        logger.warning("AI match-score unreachable: %s", exc)
        raise AIServiceUnavailableError("AI service unreachable") from exc
    except httpx.HTTPStatusError as exc:
        _fallback = True
        logger.warning("AI match-score returned %d", exc.response.status_code)
        raise AIServiceUnavailableError(f"AI service error {exc.response.status_code}") from exc
    finally:
        logger.info(json.dumps({
            "event": "ai_prediction_call",
            "endpoint": "/predict/match-score",
            "input_shape": len(candidates),
            "model_version": _model_ver,
            "latency_ms": round((time.monotonic() - _t0) * 1000),
            "fallback_triggered": _fallback,
        }))

    results: list[ScoredCandidate] = []
    for i, s in enumerate(resp_json["scores"]):
        clamped = max(0.0, min(1.0, s["score"]))
        results.append(
            ScoredCandidate(
                ride_id=candidates[i].ride_id,
                match_score=clamped,
                match_score_pct=round(clamped * 100),
            )
        )
    return results


async def rank_candidates(
    passenger_req: PassengerRequestFeatures,
    candidates: list[CandidateFeatures],
) -> list[str]:
    client = _get()
    payload = {
        "candidates": [
            {"candidate_id": c.ride_id, **_candidate_route_payload(passenger_req, c)}
            for c in candidates
        ]
    }
    _t0 = time.monotonic()
    _fallback = False
    _model_ver = None
    resp_json: dict | None = None
    try:
        resp = await client.post("/predict/ride-ranking", json=payload)
        resp.raise_for_status()
        resp_json = resp.json()
        _model_ver = resp_json.get("model_version")
    except httpx.TimeoutException as exc:
        _fallback = True
        logger.warning("AI ride-ranking timed out")
        raise AIServiceUnavailableError("AI service timed out") from exc
    except httpx.RequestError as exc:
        _fallback = True
        logger.warning("AI ride-ranking unreachable: %s", exc)
        raise AIServiceUnavailableError("AI service unreachable") from exc
    except httpx.HTTPStatusError as exc:
        _fallback = True
        logger.warning("AI ride-ranking returned %d", exc.response.status_code)
        raise AIServiceUnavailableError(f"AI service error {exc.response.status_code}") from exc
    finally:
        logger.info(json.dumps({
            "event": "ai_prediction_call",
            "endpoint": "/predict/ride-ranking",
            "input_shape": len(candidates),
            "model_version": _model_ver,
            "latency_ms": round((time.monotonic() - _t0) * 1000),
            "fallback_triggered": _fallback,
        }))

    return [r["candidate_id"] for r in resp_json["ranked"]]


async def is_available() -> bool:
    try:
        client = _get()
        resp = await client.get("/health")
        resp.raise_for_status()
        return resp.json().get("status") in ("ok", "degraded")
    except Exception:
        return False
