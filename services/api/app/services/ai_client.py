from __future__ import annotations

import logging
from decimal import Decimal

import httpx

from app.models.ai import (
    AIMatchScoreRequest,
    AIMatchScoreResponse,
    AIPriceRequest,
    AIPriceResponse,
    AIRankingResponse,
    ScoredCandidate,
)

logger = logging.getLogger(__name__)


class AIServiceUnavailableError(Exception):
    pass


async def score_candidates(
    client: httpx.AsyncClient,
    request: AIMatchScoreRequest,
) -> AIMatchScoreResponse:
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

    data = resp.json()
    scores = [
        ScoredCandidate(
            ride_id=s["ride_id"],
            match_score=s["match_score"],
            match_score_pct=round(s["match_score"] * 100),
        )
        for s in data["scores"]
    ]
    return AIMatchScoreResponse(model_version=data["model_version"], scores=scores)


async def rank_candidates(
    client: httpx.AsyncClient,
    scored: list[ScoredCandidate],
) -> AIRankingResponse:
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

    data = resp.json()
    return AIRankingResponse(model_version=data["model_version"], ranked=data["ranked"])


async def get_fare(
    client: httpx.AsyncClient,
    request: AIPriceRequest,
) -> AIPriceResponse:
    try:
        resp = await client.post(
            "/predict/price-recommendation",
            json=request.model_dump(mode="json"),
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

    data = resp.json()
    fare = data["recommended_fare"]
    return AIPriceResponse(
        model_version=data["model_version"],
        min_egp=Decimal(str(fare["min_egp"])),
        max_egp=Decimal(str(fare["max_egp"])),
    )


async def is_available(client: httpx.AsyncClient) -> bool:
    try:
        resp = await client.get("/health")
        resp.raise_for_status()
        return resp.json().get("status") == "ok"
    except Exception:
        return False
