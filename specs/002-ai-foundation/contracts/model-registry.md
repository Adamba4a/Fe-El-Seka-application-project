# Contract: Model Registry (Supabase Storage)

**Service**: `services/ai` pipelines + AI serving layer | **Feature**: `002-ai-foundation` | **Date**: 2026-06-13

> **Superseded (2026-07-04)**: `price_recommender` was removed — see `contracts/prediction-api.md` for rationale. Only `match_score` and `ride_ranker` are registered, trained, and served now. References to `price_recommender` below are historical.

---

## Storage Bucket

**Bucket name**: `model-registry`
**Access**: private (service role key required — `SUPABASE_SERVICE_ROLE_KEY`)
**Provider**: Supabase Storage

---

## Path Layout

```
model-registry/                            (bucket root)
├── match_score/
│   ├── {version}/
│   │   ├── model.joblib                   (serialized XGBClassifier)
│   │   └── metadata.json                  (training metadata)
│   └── latest.json                        (pointer to current production version)
└── ride_ranker/
    ├── {version}/
    │   ├── model.joblib
    │   └── metadata.json
    └── latest.json
```
*(A third `price_recommender/` directory existed before that model was removed 2026-07-04.)*

**`{version}`** is a UTC ISO 8601 datetime string with colons replaced by hyphens for path safety:
- Original: `2026-06-13T14:30:22Z`
- Path form: `2026-06-13T14-30-22Z`

---

## File Schemas

### `model.joblib`

A joblib-serialized Python object. Contents by model type:

| Model Type | Serialized Object |
|---|---|
| `match_score` | `xgboost.XGBClassifier` instance (fitted) |
| `ride_ranker` | `xgboost.XGBClassifier` instance (fitted) |
| ~~`price_recommender`~~ | ~~`sklearn.linear_model.Ridge` instance (fitted)~~ — removed 2026-07-04 |

Loaded via: `joblib.load(local_path)` after downloading from Storage.

---

### `metadata.json`

```json
{
  "version": "2026-06-13T14:30:22Z",
  "model_type": "match_score",
  "training_date": "2026-06-13T14:30:22Z",
  "dataset_record_count": 100000,
  "training_record_count": 80000,
  "validation_record_count": 20000,
  "validation_split": 0.20,
  "metrics": {
    "auc_roc": 0.72,
    "threshold_gate": "auc_roc >= 0.65",
    "gate_passed": true
  },
  "feature_count": 14,
  "feature_names": [
    "passenger_origin_lat",
    "passenger_origin_lng",
    "passenger_dest_lat",
    "passenger_dest_lng",
    "driver_origin_lat",
    "driver_origin_lng",
    "driver_dest_lat",
    "driver_dest_lng",
    "overlap_ratio",
    "pickup_detour_km",
    "dropoff_distance_km",
    "dest_zone_distance_km",
    "departure_hour_sin",
    "departure_hour_cos"
  ]
}
```

---

### `latest.json`

```json
{
  "version": "2026-06-13T14:30:22Z"
}
```

Written atomically **after** all other files for a version are confirmed uploaded. The AI service reads this file at startup and on reload to determine which version to download. Writing `latest.json` last is the consistency guarantee — a partial upload will not have `latest.json` pointing to it.

---

## Upload Sequence (training pipeline)

The training pipeline MUST follow this exact sequence when uploading a new model version:

```
1. Complete training + validation for both models
2. If AUC-ROC < 0.65 for match_score → abort, do NOT upload anything
3. For each model_type in [match_score, ride_ranker]:
   a. Serialize model to local data/models/{model_type}.joblib
   b. Write local data/models/{model_type}_metadata.json
   c. Upload model.joblib → model-registry/{model_type}/{version_path}/model.joblib
   d. Upload metadata.json → model-registry/{model_type}/{version_path}/metadata.json
4. For each model_type (only after all uploads in step 3 succeed):
   a. Write latest.json → model-registry/{model_type}/latest.json
```
*(Originally "all three models" / `[match_score, ride_ranker, price_recommender]` — `price_recommender` removed 2026-07-04.)*

If any upload in step 3 fails, the sequence aborts. `latest.json` files are NOT updated for any model type. This prevents a partial upload from being served.

---

## Download Sequence (AI service startup / reload)

```
1. For each model_type in [match_score, ride_ranker]:
   a. Download model-registry/{model_type}/latest.json
   b. Parse {"version": "<version>"} → resolve version_path
   c. Download model-registry/{model_type}/{version_path}/model.joblib to temp file
   d. joblib.load(temp_file) → model object
   e. Store in app.state.models[model_type] = {"model": obj, "version": version}
   f. On any failure: app.state.models[model_type] = None
      Log warning; health reports "degraded"; endpoint returns 503
2. Health endpoint reflects loaded count from app.state.models
```

---

## Retention Policy

- Old model versions are NOT automatically deleted (NFR-005)
- At least the two most recent versions MUST be retained at all times
- Manual cleanup of older versions is permitted via the Supabase Storage dashboard
- A cleanup script is out of scope for the competition MVP

---

## Environment Variables Required

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Supabase project URL (e.g., `http://127.0.0.1:54321` for local) |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key with Storage write access |
| `MODEL_REGISTRY_BUCKET` | Bucket name (default: `model-registry`) |
