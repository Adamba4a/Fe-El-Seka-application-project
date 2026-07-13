import logging
import time

from fastapi import APIRouter, HTTPException, Request

from app.models.prediction import (
    MatchScoreBatchRequest,
    MatchScoreResponse,
    RideRankingBatchRequest,
    RideRankingResponse,
)

router = APIRouter(tags=["predict"])
logger = logging.getLogger(__name__)


def _get_model(request: Request, model_type: str) -> dict:
    model_state: dict = getattr(request.app.state, "models", {})
    slot = model_state.get(model_type)
    if slot is None:
        raise HTTPException(
            status_code=503,
            detail=f"Model '{model_type}' is not available. Retry later or use fallback scoring.",
        )
    return slot


@router.post("/match-score", response_model=MatchScoreResponse)
def predict_match_score(body: MatchScoreBatchRequest, request: Request) -> MatchScoreResponse:
    slot = _get_model(request, "match_score")
    t0 = time.perf_counter()
    from app.services.match_scorer import predict_scores
    result = predict_scores(body, slot)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "endpoint=match_score model_version=%s batch_size=%d response_time_ms=%.1f",
        result.model_version, len(body.candidates), elapsed_ms,
    )
    return result


@router.post("/ride-ranking", response_model=RideRankingResponse)
def predict_ride_ranking(body: RideRankingBatchRequest, request: Request) -> RideRankingResponse:
    slot = _get_model(request, "ride_ranker")
    t0 = time.perf_counter()
    from app.services.ride_ranker import rank_candidates
    result = rank_candidates(body, slot)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "endpoint=ride_ranking model_version=%s batch_size=%d response_time_ms=%.1f",
        result.model_version, len(body.candidates), elapsed_ms,
    )
    return result
