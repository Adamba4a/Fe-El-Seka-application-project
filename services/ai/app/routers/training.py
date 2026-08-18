import io
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from fastapi import APIRouter

from app.config import get_settings
from app.core.r2_client import get_r2_client
from app.models.training import RetrainRequest, RetrainResponse
from app.services.model_registry import ModelRegistry
from pipelines.training.train_from_real_data import TrainingGateError, train_from_real_data

router = APIRouter(tags=["training"])
logger = logging.getLogger(__name__)

_AUC_GATE = 0.65


def _make_version() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _download_dataset(storage_path: str) -> pd.DataFrame:
    s = get_settings()
    data = get_r2_client().get_object(
        Bucket=s.training_datasets_bucket, Key=storage_path
    )["Body"].read()
    return pd.read_parquet(io.BytesIO(data))


@router.post("/retrain", response_model=RetrainResponse)
def retrain(body: RetrainRequest) -> RetrainResponse:
    """contracts/ai-service-endpoints.md POST /training/retrain. Trains
    model_type on the real-data dataset snapshot at dataset_storage_path.
    On success, uploads model.joblib/metadata.json under the new
    storage_version but never touches latest.json or candidate.json — that's
    services/api's job (model_lifecycle_service.py decides promotion, then
    calls POST /models/shadow to activate a candidate)."""
    dataset_df = _download_dataset(body.dataset_storage_path)
    version = _make_version()

    try:
        result = train_from_real_data(dataset_df, body.model_type, version)
    except TrainingGateError as exc:
        logger.warning("Real-data retrain gate failed for %s: %s", body.model_type, exc)
        reason = (
            "auc_roc_below_threshold" if exc.auc_roc < _AUC_GATE else "calibration_error_above_threshold"
        )
        return RetrainResponse(
            status="gate_failed",
            reason=reason,
            auc_roc=round(exc.auc_roc, 4),
            expected_calibration_error=round(exc.expected_calibration_error, 4),
        )

    registry = ModelRegistry()
    with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as tmp:
        joblib.dump(result["model"], tmp.name)
        tmp_path = Path(tmp.name)
    registry.upload_model(body.model_type, version, tmp_path)
    registry.upload_metadata(body.model_type, version, result["metadata"])
    logger.info("Trained and uploaded %s candidate artifact (version: %s)", body.model_type, version)

    return RetrainResponse(
        status="trained",
        storage_version=version,
        evaluation_score=round(result["evaluation_score"], 4),
        auc_roc=round(result["auc_roc"], 4),
        expected_calibration_error=round(result["expected_calibration_error"], 4),
    )
