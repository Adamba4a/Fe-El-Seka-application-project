import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.config import get_settings
from app.routers import health, models, predict, verification

logger = logging.getLogger(__name__)

WEIGHTS_DIR = Path(__file__).resolve().parent / "models" / "weights"


def _load_models(app: FastAPI) -> None:
    from app.services.model_registry import ModelRegistry, RegistryError

    registry = ModelRegistry()

    model_state: dict[str, dict | None] = {
        "match_score": None,
        "ride_ranker": None,
    }

    for model_type in model_state:
        try:
            import joblib

            version = registry.get_latest_version(model_type)
            local_path = registry.download_model(model_type, version)
            obj = joblib.load(local_path)
            model_state[model_type] = {"model": obj, "version": version}
            logger.info("Loaded %s (version: %s)", model_type, version)
        except RegistryError as exc:
            logger.warning("Could not load %s — serving will return 503: %s", model_type, exc)
        except Exception as exc:
            logger.warning("Unexpected error loading %s: %s", model_type, exc)

    app.state.models = model_state


def _load_face_models(app: FastAPI) -> None:
    from app.services.face_service import load_face_models

    try:
        detector, recognizer = load_face_models(WEIGHTS_DIR)
        app.state.face_models = {"detector": detector, "recognizer": recognizer}
        logger.info("Loaded face-match models from %s", WEIGHTS_DIR)
    except Exception as exc:
        app.state.face_models = None
        logger.warning("Could not load face-match models — /verify/identity face match will be unavailable: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AI service starting — loading models...")
    _load_models(app)
    _load_face_models(app)
    yield
    logger.info("AI service shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Triplyy AI Service",
        version=settings.ai_version,
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(health.router, prefix="/ai")
    app.include_router(predict.router, prefix="/predict")
    app.include_router(models.router, prefix="/models")
    app.include_router(verification.router, prefix="/verify")
    return app


app = create_app()
