from pydantic import BaseModel


class RetrainRequest(BaseModel):
    model_type: str
    dataset_storage_path: str
    dataset_snapshot_id: str


class RetrainResponse(BaseModel):
    status: str  # "trained" | "gate_failed"
    storage_version: str | None = None
    evaluation_score: float | None = None
    auc_roc: float | None = None
    expected_calibration_error: float | None = None
    reason: str | None = None
