import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

from app.services.feature_engineering import FEATURE_NAMES, MATCH_QUALITY_MONOTONE_CONSTRAINTS
from pipelines.training.evaluate import auc_roc_score, build_metadata, expected_calibration_error

logger = logging.getLogger(__name__)

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "models"


def train_ride_ranker(features_df: pd.DataFrame, version: str) -> tuple:
    X = features_df[FEATURE_NAMES].values
    y_soft = features_df["match_prob"].values
    y_hard = features_df["match_label"].values

    X_train, X_val, y_train_soft, y_val_soft, y_train_hard, y_val_hard = train_test_split(
        X, y_soft, y_hard, test_size=0.20, random_state=42, stratify=y_hard
    )

    # Same soft-label + monotonic-constraint approach as match_score (see
    # train_match_score.py) — the ranker shared the identical training bug
    # (fit to Bernoulli-sampled coin-flips) and its score is exposed to users
    # via RankedRide.score, so it needs the same calibration fix.
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
    model.fit(
        X_train, y_train_soft,
        eval_set=[(X_val, y_val_soft)],
        verbose=False,
    )

    y_pred_proba = np.clip(model.predict(X_val), 0.0, 1.0)
    auc = auc_roc_score(y_val_hard, y_pred_proba)
    ece = expected_calibration_error(y_val_hard, y_pred_proba)
    logger.info("Ride ranker AUC-ROC: %.4f", auc)
    logger.info("Ride ranker calibration error (ECE): %.4f", ece)

    metadata = build_metadata(
        model_type="ride_ranker",
        version=version,
        dataset_record_count=len(features_df),
        train_count=len(X_train),
        val_count=len(X_val),
        metrics={"auc_roc": round(auc, 4), "expected_calibration_error": round(ece, 4)},
        feature_names=FEATURE_NAMES,
    )

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, _OUTPUT_DIR / "ride_ranker.joblib")
    (_OUTPUT_DIR / "ride_ranker_metadata.json").write_text(json.dumps(metadata, indent=2))
    logger.info("Saved ride_ranker model and metadata")

    return model, metadata
