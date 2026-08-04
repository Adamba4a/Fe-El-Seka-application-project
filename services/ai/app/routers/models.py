import logging

import joblib
from fastapi import APIRouter, Request

from app.models.registry import (
    DiscardCandidateRequest,
    DiscardCandidateResponse,
    PromoteRequest,
    PromoteResponse,
    ReloadRequest,
    ReloadResponse,
    ShadowRequest,
    ShadowResponse,
)
from app.services.model_registry import ModelRegistry, RegistryError

router = APIRouter(tags=["models"])
logger = logging.getLogger(__name__)

_ALL_MODEL_TYPES = ["match_score", "ride_ranker"]


@router.post("/shadow", response_model=ShadowResponse)
def activate_shadow(body: ShadowRequest, request: Request) -> ShadowResponse:
    """contracts/ai-service-endpoints.md POST /models/shadow. Called by
    model_lifecycle_service.py's advance_to_shadow() once a candidate has
    passed the promotion-margin gate. Writes candidate.json and loads the
    version into app.state.models[model_type]["candidate"] so the predict
    routers can start producing (never user-facing) shadow scores."""
    registry = ModelRegistry()
    registry.write_candidate(body.model_type, body.storage_version)

    local_path = registry.download_model(body.model_type, body.storage_version)
    obj = joblib.load(local_path)

    model_state: dict = getattr(request.app.state, "models", {})
    model_state.setdefault(body.model_type, {})["candidate"] = {
        "model": obj,
        "version": body.storage_version,
    }
    request.app.state.models = model_state

    logger.info("Activated shadow candidate for %s (version: %s)", body.model_type, body.storage_version)
    return ShadowResponse(status="shadow_active", storage_version=body.storage_version)


@router.post("/promote", response_model=PromoteResponse)
def promote_model(body: PromoteRequest, request: Request) -> PromoteResponse:
    """contracts/ai-service-endpoints.md POST /models/promote. Called by
    model_lifecycle_service.py's advance_to_champion() once a rollout has
    completed all rollout_step_pcts steps. Writes latest.json, clears
    candidate.json, and swaps app.state.models[model_type]["model"] to the
    now-champion version."""
    registry = ModelRegistry()
    registry.write_latest(body.model_type, body.storage_version)
    registry.clear_candidate(body.model_type)

    local_path = registry.download_model(body.model_type, body.storage_version)
    obj = joblib.load(local_path)

    model_state: dict = getattr(request.app.state, "models", {})
    slot = model_state.setdefault(body.model_type, {})
    slot["model"] = obj
    slot["version"] = body.storage_version
    slot.pop("candidate", None)
    request.app.state.models = model_state

    logger.info("Promoted %s to champion (version: %s)", body.model_type, body.storage_version)
    return PromoteResponse(status="promoted", storage_version=body.storage_version)


@router.post("/discard-candidate", response_model=DiscardCandidateResponse)
def discard_candidate(body: DiscardCandidateRequest, request: Request) -> DiscardCandidateResponse:
    """contracts/ai-service-endpoints.md POST /models/discard-candidate.
    Called on rejection, unfavorable shadow burn-in, or rollback cleanup —
    NOT on the critical rollback path itself (FR-012), which is pure
    services/api DB state (rollout_pct -> 0) that takes effect on the next
    rollout-cache refresh with zero call here."""
    registry = ModelRegistry()
    registry.clear_candidate(body.model_type)

    model_state: dict = getattr(request.app.state, "models", {})
    slot = model_state.get(body.model_type)
    if slot is not None:
        slot.pop("candidate", None)
    request.app.state.models = model_state

    logger.info("Discarded candidate for %s", body.model_type)
    return DiscardCandidateResponse(status="candidate_cleared")


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
