from fastapi import APIRouter, Request

from app.config import get_settings
from app.models.health import HealthResponse, ModelVersions

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health(request: Request) -> HealthResponse:
    settings = get_settings()
    model_state: dict = getattr(request.app.state, "models", {})

    def version_of(key: str) -> str | None:
        slot = model_state.get(key)
        return slot["version"] if slot else None

    loaded = sum(1 for v in model_state.values() if v is not None)
    total = len(model_state)

    if total == 0 or loaded == 0:
        status = "unavailable"
    elif loaded < total:
        status = "degraded"
    else:
        status = "ok"

    return HealthResponse(
        status=status,
        ai_version=settings.ai_version,
        models=ModelVersions(
            match_score=version_of("match_score"),
            ride_ranker=version_of("ride_ranker"),
            price_recommender=version_of("price_recommender"),
        ),
    )
