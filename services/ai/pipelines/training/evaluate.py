import numpy as np
from sklearn.metrics import mean_absolute_error, roc_auc_score


def auc_roc_score(y_true, y_pred_proba) -> float:
    return float(roc_auc_score(y_true, y_pred_proba))


def mae_score(y_true, y_pred) -> float:
    return float(mean_absolute_error(y_true, y_pred))


def expected_calibration_error(y_true, y_pred_proba, n_bins: int = 10) -> float:
    """Mean absolute gap between predicted probability and empirical hit-rate,
    bucketed into n_bins and weighted by bucket size (standard ECE). AUC alone
    only checks ranking order — this catches a model that ranks correctly but
    is systematically over/under-confident (see research.md, 2026-07-04
    calibration bug: AUC 0.98 while real-world scores were ~10x too low)."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred_proba = np.asarray(y_pred_proba, dtype=float)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.clip(np.digitize(y_pred_proba, bin_edges[1:-1]), 0, n_bins - 1)

    ece = 0.0
    n = len(y_true)
    for b in range(n_bins):
        mask = bin_idx == b
        count = int(mask.sum())
        if count == 0:
            continue
        avg_pred = float(y_pred_proba[mask].mean())
        avg_actual = float(y_true[mask].mean())
        ece += (count / n) * abs(avg_pred - avg_actual)
    return float(ece)


def build_metadata(
    model_type: str,
    version: str,
    dataset_record_count: int,
    train_count: int,
    val_count: int,
    metrics: dict,
    feature_names: list[str],
) -> dict:
    return {
        "version": version,
        "model_type": model_type,
        "training_date": version,
        "dataset_record_count": dataset_record_count,
        "training_record_count": train_count,
        "validation_record_count": val_count,
        "validation_split": round(val_count / dataset_record_count, 2),
        "metrics": metrics,
        "feature_count": len(feature_names),
        "feature_names": feature_names,
    }
