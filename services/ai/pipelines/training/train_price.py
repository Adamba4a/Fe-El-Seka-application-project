import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split

from pipelines.training.evaluate import build_metadata, mae_score

logger = logging.getLogger(__name__)

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "models"

_PRICE_FEATURES = [
    "passenger_origin_lat",
    "passenger_origin_lng",
    "passenger_dest_lat",
    "passenger_dest_lng",
    "dest_zone_distance_km",
    "departure_hour_sin",
    "departure_hour_cos",
]

_BASE_FARE = 15.0
_PER_KM_RATE = 3.5
_PEAK_SURCHARGE = 10.0


def _generate_fare_labels(features_df: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    dist = features_df["dest_zone_distance_km"].values
    hour_sin = features_df["departure_hour_sin"].values
    # Reconstruct hour from sin (approximate) to detect peak
    hour_approx = np.arcsin(np.clip(hour_sin, -1, 1)) * 24 / (2 * np.pi)
    hour_approx = np.where(hour_approx < 0, hour_approx + 24, hour_approx)
    is_peak = (
        ((hour_approx >= 7) & (hour_approx <= 9))
        | ((hour_approx >= 16) & (hour_approx <= 19))
    )
    noise = rng.normal(0, 5, size=len(dist))
    fare = _BASE_FARE + _PER_KM_RATE * dist + _PEAK_SURCHARGE * is_peak.astype(float) + noise
    return np.maximum(fare, 10.0)


def train_price_recommender(features_df: pd.DataFrame, version: str) -> tuple:
    rng = np.random.default_rng(42)
    X = features_df[_PRICE_FEATURES].values
    y = _generate_fare_labels(features_df, rng)

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.20, random_state=42)

    model = Ridge(alpha=1.0)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_val)
    mae = mae_score(y_val, y_pred)
    logger.info("Price recommender MAE: %.2f EGP", mae)

    metadata = build_metadata(
        model_type="price_recommender",
        version=version,
        dataset_record_count=len(features_df),
        train_count=len(X_train),
        val_count=len(X_val),
        metrics={"mae_egp": round(mae, 2)},
        feature_names=_PRICE_FEATURES,
    )

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, _OUTPUT_DIR / "price_recommender.joblib")
    (_OUTPUT_DIR / "price_recommender_metadata.json").write_text(json.dumps(metadata, indent=2))
    logger.info("Saved price_recommender model and metadata")

    return model, metadata
