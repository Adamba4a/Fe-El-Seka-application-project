import numpy as np
import pandas as pd
import pytest

from app.services.feature_engineering import FEATURE_NAMES
from pipelines.training import train_from_real_data as train_from_real_data_module
from pipelines.training.train_from_real_data import TrainingGateError, train_from_real_data


def _synthetic_dataset_df(n_groups: int = 60, candidates_per_group: int = 6, seed: int = 7) -> pd.DataFrame:
    """Builds a dataset_df shaped like a real dataset-snapshot Parquet (the raw
    coordinate/ratio columns _build_features_df expects), with the "chosen"
    candidate in each search group deliberately the one with the highest
    overlap_ratio and lowest detour/distance — the same monotone direction
    train_from_real_data.py's MATCH_QUALITY_MONOTONE_CONSTRAINTS enforces —
    so a model fit on it should comfortably clear the AUC/ECE gates."""
    rng = np.random.default_rng(seed)
    base_departure = pd.Timestamp("2026-06-01T08:00:00+00:00")
    rows = []
    for g in range(n_groups):
        passenger_origin_lat = 30.0 + rng.uniform(-0.05, 0.05)
        passenger_origin_lng = 31.2 + rng.uniform(-0.05, 0.05)
        passenger_dest_lat = 30.05 + rng.uniform(-0.05, 0.05)
        passenger_dest_lng = 31.3 + rng.uniform(-0.05, 0.05)
        overlaps = rng.uniform(0.1, 1.0, size=candidates_per_group)
        detours = rng.uniform(0.1, 5.0, size=candidates_per_group)
        distances = rng.uniform(0.1, 5.0, size=candidates_per_group)
        combined = overlaps - 0.1 * detours - 0.1 * distances
        chosen_idx = int(np.argmax(combined))
        for c in range(candidates_per_group):
            label = 1 if c == chosen_idx else 0
            rows.append({
                "search_id": f"search-{g}",
                "passenger_origin_lat": passenger_origin_lat,
                "passenger_origin_lng": passenger_origin_lng,
                "passenger_dest_lat": passenger_dest_lat,
                "passenger_dest_lng": passenger_dest_lng,
                "driver_origin_lat": passenger_origin_lat + rng.uniform(-0.01, 0.01),
                "driver_origin_lng": passenger_origin_lng + rng.uniform(-0.01, 0.01),
                "driver_dest_lat": passenger_dest_lat + rng.uniform(-0.01, 0.01),
                "driver_dest_lng": passenger_dest_lng + rng.uniform(-0.01, 0.01),
                "overlap_ratio": float(overlaps[c]),
                "pickup_detour_km": float(detours[c]),
                "dropoff_distance_km": float(distances[c]),
                "departure_at_utc": base_departure.isoformat(),
                "match_prob": 0.99 if label == 1 else 0.01,
                "match_label": label,
            })
    return pd.DataFrame(rows)


def test_train_from_real_data_passes_gate_and_returns_metadata():
    df = _synthetic_dataset_df()
    result = train_from_real_data(df, model_type="match_score", version="v-test")

    assert result["auc_roc"] >= train_from_real_data_module._AUC_GATE
    assert result["expected_calibration_error"] <= train_from_real_data_module._ECE_GATE
    assert 0.0 <= result["evaluation_score"] <= 1.0

    metadata = result["metadata"]
    assert metadata["model_type"] == "match_score"
    assert metadata["version"] == "v-test"
    assert metadata["feature_count"] == len(FEATURE_NAMES)
    assert metadata["feature_names"] == FEATURE_NAMES
    assert metadata["metrics"]["gate_passed"] is True
    assert metadata["dataset_record_count"] == len(df)
    assert metadata["training_record_count"] + metadata["validation_record_count"] == len(df)


def test_train_from_real_data_raises_training_gate_error_when_auc_gate_unreachable(monkeypatch):
    """Forcing the gate to an unreachable threshold (rather than trying to craft
    data that reliably scores low, which would be flaky) deterministically
    exercises the TrainingGateError path and its auc_roc/ece attributes."""
    df = _synthetic_dataset_df()
    monkeypatch.setattr(train_from_real_data_module, "_AUC_GATE", 1.1)

    with pytest.raises(TrainingGateError) as exc_info:
        train_from_real_data(df, model_type="match_score", version="v-test")

    assert exc_info.value.auc_roc < 1.1
    assert exc_info.value.expected_calibration_error >= 0.0
