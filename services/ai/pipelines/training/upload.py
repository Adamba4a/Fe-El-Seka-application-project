import logging
from pathlib import Path

from app.services.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).parent.parent.parent / "data" / "models"

_MODEL_FILES = {
    "match_score": ("match_score.joblib", "match_score_metadata.json"),
    "ride_ranker": ("ride_ranker.joblib", "ride_ranker_metadata.json"),
    "price_recommender": ("price_recommender.joblib", "price_recommender_metadata.json"),
}


def upload_all_models(version: str) -> None:
    """Upload all three model artifacts; write latest.json only after all succeed."""
    registry = ModelRegistry()

    uploaded: list[str] = []

    for model_type, (model_file, meta_file) in _MODEL_FILES.items():
        model_path = _MODELS_DIR / model_file
        meta_path = _MODELS_DIR / meta_file

        if not model_path.exists():
            raise FileNotFoundError(f"Model artifact missing: {model_path}")
        if not meta_path.exists():
            raise FileNotFoundError(f"Metadata missing: {meta_path}")

        import json
        metadata = json.loads(meta_path.read_text())

        logger.info("Uploading %s (version %s)...", model_type, version)
        registry.upload_model(model_type, version, model_path)
        registry.upload_metadata(model_type, version, metadata)
        uploaded.append(model_type)
        logger.info("Uploaded %s", model_type)

    # Write latest.json pointers ONLY after all three uploads succeed
    for model_type in uploaded:
        registry.write_latest(model_type, version)
        logger.info("Set latest for %s → %s", model_type, version)

    logger.info("All models uploaded successfully (version: %s)", version)
