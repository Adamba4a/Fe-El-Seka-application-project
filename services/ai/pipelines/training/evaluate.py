from sklearn.metrics import mean_absolute_error, roc_auc_score


def auc_roc_score(y_true, y_pred_proba) -> float:
    return float(roc_auc_score(y_true, y_pred_proba))


def mae_score(y_true, y_pred) -> float:
    return float(mean_absolute_error(y_true, y_pred))


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
