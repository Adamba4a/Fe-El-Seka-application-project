from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal

import httpx

from app.models.ai import (
    AIMatchScoreRequest,
    AIPriceRequest,
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


async def score_candidates(
    passenger_req: PassengerRequestFeatures,
    candidates: list[CandidateFeatures],
) -> list[ScoredCandidate]:
    client = _get()
    request = AIMatchScoreRequest(passenger_request=passenger_req, candidates=candidates)
    try:
        resp = await client.post(
            "/predict/match-score",
            json=request.model_dump(mode="json"),
        )
        resp.raise_for_status()
    except httpx.TimeoutException as exc:
        logger.warning("AI match-score timed out")
        raise AIServiceUnavailableError("AI service timed out") from exc
    except httpx.RequestError as exc:
        logger.warning("AI match-score unreachable: %s", exc)
        raise AIServiceUnavailableError("AI service unreachable") from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("AI match-score returned %d", exc.response.status_code)
        raise AIServiceUnavailableError(f"AI service error {exc.response.status_code}") from exc

    results: list[ScoredCandidate] = []
    for s in resp.json()["scores"]:
        clamped = max(0.0, min(1.0, s["match_score"]))
        results.append(
            ScoredCandidate(
                ride_id=s["ride_id"],
                match_score=clamped,
                match_score_pct=round(clamped * 100),
            )
        )
    return results


async def rank_candidates(scored: list[ScoredCandidate]) -> list[str]:
    client = _get()
    payload = {
        "candidates": [
            {"ride_id": s.ride_id, "match_score": s.match_score}
            for s in scored
        ]
    }
    try:
        resp = await client.post("/predict/ride-ranking", json=payload)
        resp.raise_for_status()
    except httpx.TimeoutException as exc:
        logger.warning("AI ride-ranking timed out")
        raise AIServiceUnavailableError("AI service timed out") from exc
    except httpx.RequestError as exc:
        logger.warning("AI ride-ranking unreachable: %s", exc)
        raise AIServiceUnavailableError("AI service unreachable") from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("AI ride-ranking returned %d", exc.response.status_code)
        raise AIServiceUnavailableError(f"AI service error {exc.response.status_code}") from exc

    return resp.json()["ranked"]


async def get_fare(req: AIPriceRequest) -> Decimal:
    client = _get()
    try:
        resp = await client.post(
            "/predict/price-recommendation",
            json=req.model_dump(mode="json"),
        )
        resp.raise_for_status()
    except httpx.TimeoutException as exc:
        logger.warning("AI price-recommendation timed out")
        raise AIServiceUnavailableError("AI service timed out") from exc
    except httpx.RequestError as exc:
        logger.warning("AI price-recommendation unreachable: %s", exc)
        raise AIServiceUnavailableError("AI service unreachable") from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("AI price-recommendation returned %d", exc.response.status_code)
        raise AIServiceUnavailableError(f"AI service error {exc.response.status_code}") from exc

    fare = resp.json()["recommended_fare"]
    min_egp = Decimal(str(fare["min_egp"]))
    max_egp = Decimal(str(fare["max_egp"]))
    result = ((min_egp + max_egp) / 2).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if result <= 0:
        raise AIServiceUnavailableError("AI service returned invalid fare (≤ 0)")
    return result


async def is_available() -> bool:
    try:
        client = _get()
        resp = await client.get("/health")
        resp.raise_for_status()
        return resp.json().get("status") in ("ok", "degraded")
    except Exception:
        return False
