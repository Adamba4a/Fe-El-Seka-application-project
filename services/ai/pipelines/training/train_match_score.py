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
_AUC_GATE = 0.65


class TrainingGateError(Exception):
    pass


def train_match_score(features_df: pd.DataFrame, version: str) -> tuple:
    X = features_df[FEATURE_NAMES].values
    y_soft = features_df["match_prob"].values
    y_hard = features_df["match_label"].values

    X_train, X_val, y_train_soft, y_val_soft, y_train_hard, y_val_hard = train_test_split(
        X, y_soft, y_hard, test_size=0.20, random_state=42, stratify=y_hard
    )

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
    # Trained on the continuous match_prob (soft label), not the Bernoulli-sampled
    # match_label — the coin-flip only exists to give AUC something binary to
    # evaluate against below. Fitting the raw coin-flips taught previous versions
    # of this model to reproduce sampling noise instead of the underlying
    # probability (see research.md, 2026-07-04 calibration fix).
    model.fit(
        X_train, y_train_soft,
        eval_set=[(X_val, y_val_soft)],
        verbose=False,
    )

    y_pred_proba = np.clip(model.predict(X_val), 0.0, 1.0)
    auc = auc_roc_score(y_val_hard, y_pred_proba)
    ece = expected_calibration_error(y_val_hard, y_pred_proba)
    gate_passed = auc >= _AUC_GATE

    logger.info("Match score model AUC-ROC: %.4f (gate: %.2f — %s)",
                auc, _AUC_GATE, "PASS" if gate_passed else "FAIL")
    logger.info("Match score model calibration error (ECE): %.4f", ece)

    if not gate_passed:
        raise TrainingGateError(
            f"Match score AUC-ROC {auc:.4f} < gate {_AUC_GATE}. "
            "Aborting — check feature engineering and dataset quality."
        )

    metadata = build_metadata(
        model_type="match_score",
        version=version,
        dataset_record_count=len(features_df),
        train_count=len(X_train),
        val_count=len(X_val),
        metrics={
            "auc_roc": round(auc, 4),
            "expected_calibration_error": round(ece, 4),
            "threshold_gate": f"auc_roc >= {_AUC_GATE}",
            "gate_passed": True,
        },
        feature_names=FEATURE_NAMES,
    )

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, _OUTPUT_DIR / "match_score.joblib")
    (_OUTPUT_DIR / "match_score_metadata.json").write_text(json.dumps(metadata, indent=2))
    logger.info("Saved match_score model and metadata")

    return model, metadata
