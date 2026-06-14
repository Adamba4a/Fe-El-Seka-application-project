import json
import logging
from pathlib import Path

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from app.services.feature_engineering import FEATURE_NAMES
from pipelines.training.evaluate import auc_roc_score, build_metadata

logger = logging.getLogger(__name__)

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "models"
_AUC_GATE = 0.65


class TrainingGateError(Exception):
    pass


def train_match_score(features_df: pd.DataFrame, version: str) -> tuple:
    X = features_df[FEATURE_NAMES].values
    y = features_df["match_label"].values

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    model = XGBClassifier(
        objective="binary:logistic",
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="auc",
        random_state=42,
        verbosity=0,
    )
    model.fit(X_train, y_train)

    y_pred_proba = model.predict_proba(X_val)[:, 1]
    auc = auc_roc_score(y_val, y_pred_proba)
    gate_passed = auc >= _AUC_GATE

    logger.info("Match score model AUC-ROC: %.4f (gate: %.2f — %s)",
                auc, _AUC_GATE, "PASS" if gate_passed else "FAIL")

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
