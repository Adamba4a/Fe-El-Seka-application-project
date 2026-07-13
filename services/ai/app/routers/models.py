import logging

import joblib
from fastapi import APIRouter, Request

from app.models.registry import ReloadRequest, ReloadResponse
from app.services.model_registry import ModelRegistry, RegistryError

router = APIRouter(tags=["models"])
logger = logging.getLogger(__name__)

_ALL_MODEL_TYPES = ["match_score", "ride_ranker"]


@router.post("/reload", response_model=ReloadResponse)
def reload_models(body: ReloadRequest, request: Request) -> ReloadResponse:
    registry = ModelRegistry()

    targets = [body.model_type] if body.model_type else _ALL_MODEL_TYPES
    reloaded: list[str] = []
    skipped: list[str] = []
    errors: dict[str, str] = {}

    model_state: dict = getattr(request.app.state, "models", {})

    for model_type in targets:
        if model_type not in _ALL_MODEL_TYPES:
            skipped.append(model_type)
            continue
        try:
            version = registry.get_latest_version(model_type)
            local_path = registry.download_model(model_type, version)
            obj = joblib.load(local_path)
            model_state[model_type] = {"model": obj, "version": version}
            reloaded.append(model_type)
            logger.info("Reloaded %s (version: %s)", model_type, version)
        except RegistryError as exc:
            errors[model_type] = str(exc)
            logger.warning("Failed to reload %s: %s", model_type, exc)
        except Exception as exc:
            errors[model_type] = str(exc)
            logger.warning("Unexpected error reloading %s: %s", model_type, exc)

    request.app.state.models = model_state
    return ReloadResponse(reloaded=reloaded, skipped=skipped, errors=errors)
