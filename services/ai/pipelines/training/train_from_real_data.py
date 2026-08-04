import logging

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from xgboost import XGBRegressor

from app.services.feature_engineering import (
    FEATURE_NAMES,
    MATCH_QUALITY_MONOTONE_CONSTRAINTS,
    build_feature_vector_from_coords,
)
from pipelines.training.evaluate import (
    auc_roc_score,
    expected_calibration_error,
    ranking_quality_score,
)

logger = logging.getLogger(__name__)

_AUC_GATE = 0.65
# Real-data retraining hard-gates on calibration too (unlike the synthetic
# pipeline, where ECE is log-only) — research.md R5.
_ECE_GATE = 0.10


class TrainingGateError(Exception):
    def __init__(self, message: str, auc_roc: float, expected_calibration_error: float):
        super().__init__(message)
        self.auc_roc = auc_roc
        self.expected_calibration_error = expected_calibration_error


def _build_features_df(dataset_df: pd.DataFrame) -> pd.DataFrame:
    """Reconstructs the full FEATURE_NAMES vector from the raw coordinate/ratio
    columns stored in a dataset snapshot Parquet — match_events.feature_vector
    does not itself carry the model's 14-dim vector (dataset_pipeline_service.py
    stores raw inputs instead, so a future feature_engineering change doesn't
    require re-deriving historical datasets)."""
    vectors = [
        build_feature_vector_from_coords(
            row.passenger_origin_lat, row.passenger_origin_lng,
            row.passenger_dest_lat, row.passenger_dest_lng,
            row.driver_origin_lat, row.driver_origin_lng,
            row.driver_dest_lat, row.driver_dest_lng,
            row.overlap_ratio, row.pickup_detour_km, row.dropoff_distance_km,
            pd.Timestamp(row.departure_at_utc).to_pydatetime(),
        )
        for row in dataset_df.itertuples()
    ]
    features_df = pd.DataFrame(vectors, columns=FEATURE_NAMES)
    features_df["search_id"] = dataset_df["search_id"].values
    features_df["match_prob"] = dataset_df["match_prob"].values
    features_df["match_label"] = dataset_df["match_label"].values
    return features_df


def train_from_real_data(dataset_df: pd.DataFrame, model_type: str, version: str) -> dict:
    """Trains model_type on a real-data dataset snapshot (contrast with
    pipelines/dataset's synthetic generator). Reuses the same XGBRegressor
    config and monotone constraints as train_match_score.py/train_ranker.py
    (research.md R5), and gates on AUC-ROC + ECE exactly like the synthetic
    pipeline, plus the FR-007 ranking-quality metric which becomes the
    model_versions.evaluation_score used for champion-vs-challenger comparison."""
    features_df = _build_features_df(dataset_df)

    X = features_df[FEATURE_NAMES].values
    y_soft = features_df["match_prob"].values
    y_hard = features_df["match_label"].values
    groups = features_df["search_id"].values

    # GroupShuffleSplit (not train_test_split) so every candidate row from the
    # same passenger search lands entirely in train or entirely in validation —
    # a plain row-level split would leak same-search context across the split
    # and make ranking_quality_score meaningless (it needs a search's full
    # candidate set together to know whether the top pick was correct).
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    train_idx, val_idx = next(splitter.split(X, y_hard, groups=groups))

    X_train, X_val = X[train_idx], X[val_idx]
    y_train_soft, y_val_soft = y_soft[train_idx], y_soft[val_idx]
    y_val_hard = y_hard[val_idx]
    groups_val = groups[val_idx]

    model = XGBRegressor(
        objective="reg:logistic",
        n_estimators=300,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        reg_lambda=2.0,
        monotone_constraints=MATCH_QUALITY_MONOTONE_CONSTRAINTS,
        eval_metric="logloss",
        early_stopping_rounds=20,
        random_state=42,
        verbosity=0,
    )
    model.fit(X_train, y_train_soft, eval_set=[(X_val, y_val_soft)], verbose=False)

    y_pred_proba = np.clip(model.predict(X_val), 0.0, 1.0)
    auc = auc_roc_score(y_val_hard, y_pred_proba)
    ece = expected_calibration_error(y_val_hard, y_pred_proba)
    ranking_quality = ranking_quality_score(groups_val, y_val_hard, y_pred_proba)

    gate_passed = auc >= _AUC_GATE and ece <= _ECE_GATE

    logger.info(
        "Real-data %s: AUC-ROC=%.4f (gate %.2f) ECE=%.4f (gate <=%.2f) ranking_quality=%.4f — %s",
        model_type, auc, _AUC_GATE, ece, _ECE_GATE, ranking_quality,
        "PASS" if gate_passed else "FAIL",
    )

    if not gate_passed:
        raise TrainingGateError(
            f"{model_type} real-data retrain failed gate: AUC-ROC {auc:.4f} "
            f"(>= {_AUC_GATE} required), ECE {ece:.4f} (<= {_ECE_GATE} required)",
            auc_roc=auc,
            expected_calibration_error=ece,
        )

    metadata = {
        "version": version,
        "model_type": model_type,
        "training_date": version,
        "dataset_record_count": len(features_df),
        "training_record_count": len(X_train),
        "validation_record_count": len(X_val),
        "metrics": {
            "auc_roc": round(auc, 4),
            "expected_calibration_error": round(ece, 4),
            "ranking_quality_score": round(ranking_quality, 4),
            "threshold_gate": f"auc_roc >= {_AUC_GATE} and ece <= {_ECE_GATE}",
            "gate_passed": True,
        },
        "feature_count": len(FEATURE_NAMES),
        "feature_names": FEATURE_NAMES,
    }

    return {
        "model": model,
        "metadata": metadata,
        "auc_roc": auc,
        "expected_calibration_error": ece,
        "evaluation_score": ranking_quality,
    }
