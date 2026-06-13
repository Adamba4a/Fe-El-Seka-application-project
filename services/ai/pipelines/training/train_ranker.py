import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from app.services.feature_engineering import FEATURE_NAMES
from pipelines.training.evaluate import auc_roc_score, build_metadata

logger = logging.getLogger(__name__)

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "models"


def train_ride_ranker(features_df: pd.DataFrame, version: str) -> tuple:
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
    logger.info("Ride ranker AUC-ROC: %.4f", auc)

    metadata = build_metadata(
        model_type="ride_ranker",
        version=version,
        dataset_record_count=len(features_df),
        train_count=len(X_train),
        val_count=len(X_val),
        metrics={"auc_roc": round(auc, 4)},
        feature_names=FEATURE_NAMES,
    )

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, _OUTPUT_DIR / "ride_ranker.joblib")
    (_OUTPUT_DIR / "ride_ranker_metadata.json").write_text(json.dumps(metadata, indent=2))
    logger.info("Saved ride_ranker model and metadata")

    return model, metadata
