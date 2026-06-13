# Quickstart & Validation Guide: AI Foundation

**Feature**: `002-ai-foundation` | **Date**: 2026-06-13

This guide validates Phase 2 end-to-end: from raw data ingestion to trained models to live prediction API.
Run steps in order. Each step has a verification check before proceeding to the next.

---

## Prerequisites

- Phase 1 complete: `services/ai` scaffold exists with `pyproject.toml`
- Supabase running locally: `supabase start` (confirms `http://127.0.0.1:54321` is up)
- Inside `services/ai/` for all commands below
- Python 3.11+, `uv` installed

**Install dependencies**:
```bash
cd services/ai
uv sync
```

**Verify install**:
```bash
uv run python -c "import xgboost, sklearn, osmnx, joblib, pandas; print('OK')"
# Expected: OK
```

---

## Step 1 — Dataset Pipeline

**Run**:
```bash
uv run python -m pipelines.dataset.run
```

**What it does**:
1. Downloads Cairo road network via OSM (may take 1–3 minutes on first run; cached after)
2. Generates 100,000+ synthetic ride records with zone-weighted, peak-time-distributed parameters
3. Writes `data/raw/rides.parquet`

**Verify** (SC-001, SC-002):
```bash
uv run python -c "
import pandas as pd
df = pd.read_parquet('data/raw/rides.parquet')
print(f'Records: {len(df)}')
print(f'Zones (origin): {df.origin_zone.nunique()}')
print(f'Zones (destination): {df.destination_zone.nunique()}')
print(f'Match label rate: {df.match_label.mean():.2%}')
print(f'Null count: {df.isnull().sum().sum()}')
"
# Expected:
# Records: 100000+
# Zones (origin): 18+
# Zones (destination): 18+
# Match label rate: 30% – 40%
# Null count: 0
```

---

## Step 2 — Feature Engineering Pipeline

**Run**:
```bash
uv run python -m pipelines.features.run
```

**What it does**:
1. Loads `data/raw/rides.parquet`
2. Applies the shared feature engineering module (`app/services/feature_engineering.py`)
3. Writes `data/features/features.parquet` with 14-column feature matrix + labels

**Verify** (FR-011 — determinism):
```bash
uv run python -c "
import pandas as pd
df = pd.read_parquet('data/features/features.parquet')
print(f'Feature columns: {len(df.columns)}')
print(f'Any NaN: {df.isnull().any().any()}')
print(f'Any Inf: {(df == float(\"inf\")).any().any()}')
print(df.dtypes)
"
# Expected:
# Feature columns: 15 (14 features + match_label)
# Any NaN: False
# Any Inf: False
# All columns: float64 or int64
```

---

## Step 3 — Training Pipeline

**Run**:
```bash
uv run python -m pipelines.training.run
```

**What it does**:
1. Loads `data/features/features.parquet`
2. Trains match score model (XGBoost) → validates AUC-ROC ≥ 0.65 gate
3. Trains ride ranker model (XGBoost)
4. Trains price recommendation model (Scikit-Learn Ridge)
5. Writes `.joblib` + `metadata.json` files to `data/models/`
6. Uploads all artifacts to Supabase Storage `model-registry` bucket
7. Writes `latest.json` for each model type after all uploads succeed

**Verify** (SC-003, FR-016, FR-017):
```bash
# Check local artifacts
ls data/models/
# Expected: match_score.joblib, match_score_metadata.json,
#           ride_ranker.joblib, ride_ranker_metadata.json,
#           price_recommender.joblib, price_recommender_metadata.json

# Check AUC-ROC gate passed
uv run python -c "
import json
with open('data/models/match_score_metadata.json') as f:
    m = json.load(f)
print(f'AUC-ROC: {m[\"metrics\"][\"auc_roc\"]:.4f}')
print(f'Gate passed: {m[\"metrics\"][\"gate_passed\"]}')
"
# Expected:
# AUC-ROC: 0.65+
# Gate passed: True
```

**Verify Supabase Storage upload** (SC-007, FR-017):
```bash
uv run python -c "
from supabase import create_client
import os
url = os.environ['SUPABASE_URL']
key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
sb = create_client(url, key)
for model in ['match_score', 'ride_ranker', 'price_recommender']:
    latest = sb.storage.from_('model-registry').download(f'{model}/latest.json')
    print(f'{model}: {latest.decode()}')
"
# Expected (one line per model):
# match_score: {"version": "2026-06-13T...Z"}
# ride_ranker: {"version": "2026-06-13T...Z"}
# price_recommender: {"version": "2026-06-13T...Z"}
```

---

## Step 4 — Start the AI Service

**Run** (in a separate terminal):
```bash
cd services/ai
uv run uvicorn app.main:app --port 8001 --reload
```

**Verify health** (SC-006, FR-001):
```bash
curl http://localhost:8001/health
```
Expected response:
```json
{
  "status": "ok",
  "models_loaded": 3,
  "model_versions": {
    "match_score": "2026-06-13T...",
    "ride_ranker": "2026-06-13T...",
    "price_recommender": "2026-06-13T..."
  },
  "version": "0.1.0"
}
```

**Verify startup time** (SC-006): service must reach `"status": "ok"` within 30 seconds of launch.

---

## Step 5 — Validate Prediction Endpoints

**Match score** (SC-004, FR-019):
```bash
curl -X POST http://localhost:8001/predict/match-score \
  -H "Content-Type: application/json" \
  -d '{
    "passenger_request": {
      "origin_zone": "Downtown Cairo",
      "destination_zone": "Maadi",
      "origin_centroid": {"lat": 30.0444, "lng": 31.2357},
      "destination_centroid": {"lat": 30.0131, "lng": 31.2089},
      "departure_at": "2026-06-13T08:00:00Z"
    },
    "candidates": [
      {
        "ride_id": "550e8400-e29b-41d4-a716-446655440000",
        "driver_origin_zone": "Downtown Cairo",
        "driver_destination_zone": "Maadi",
        "driver_origin_centroid": {"lat": 30.0500, "lng": 31.2400},
        "driver_dest_centroid": {"lat": 30.0100, "lng": 31.2100},
        "driver_departure_at": "2026-06-13T07:55:00Z",
        "estimated_overlap_ratio": 0.78,
        "estimated_pickup_detour_km": 0.5,
        "estimated_dropoff_distance_km": 0.3
      }
    ]
  }'
```
Expected: `"match_score"` ∈ [0.0, 1.0], response within 500ms.

**Price recommendation** (SC-005, FR-021):
```bash
curl -X POST http://localhost:8001/predict/price-recommendation \
  -H "Content-Type: application/json" \
  -d '{
    "origin_zone": "Downtown Cairo",
    "destination_zone": "Maadi",
    "origin_centroid": {"lat": 30.0444, "lng": 31.2357},
    "destination_centroid": {"lat": 30.0131, "lng": 31.2089},
    "estimated_distance_km": 12.5,
    "departure_at": "2026-06-13T08:00:00Z"
  }'
```
Expected: `min_egp` ≥ 10.0, `max_egp` > `min_egp`, `currency` = `"EGP"`, response within 200ms.

---

## Step 6 — Validate Partial Model Availability (FR-002a)

Stop the service. Edit `app/services/model_registry.py` to skip loading `price_recommender`. Restart the service.

```bash
curl http://localhost:8001/health
# Expected: "status": "degraded", "models_loaded": 2

curl -X POST http://localhost:8001/predict/price-recommendation -d '{...}'
# Expected: HTTP 503
# Body: {"error": "model_not_loaded", "model_type": "price_recommender", ...}

curl -X POST http://localhost:8001/predict/match-score -d '{...}'
# Expected: HTTP 200 (match score still works)
```

---

## Step 7 — Validate Hot Reload (FR-023)

With service running and all 3 models loaded:
```bash
curl -X POST http://localhost:8001/models/reload -H "Content-Type: application/json" -d '{}'
```
Expected:
```json
{
  "reloaded": ["match_score", "ride_ranker", "price_recommender"],
  "versions": { ... }
}
```
Confirm service continued serving during reload (send a prediction request concurrently).

---

## Step 8 — Run Unit & Integration Tests

```bash
cd services/ai
uv run pytest tests/ -v
```

Key tests:
- `test_feature_engineering.py` — determinism: same input → same feature vector (FR-011)
- `test_match_scorer.py` — clamping: raw score > 1.0 is clamped to 1.0 (FR-024)
- `test_health_endpoint.py` — degraded status when models missing
- `test_prediction_endpoints.py` — 503 when model not loaded; 422 on bad input

---

## Reference

- API contracts: [contracts/prediction-api.md](contracts/prediction-api.md)
- Storage layout: [contracts/model-registry.md](contracts/model-registry.md)
- Data model: [data-model.md](data-model.md)
- Feature vector spec: data-model.md § Entity 3 — FeatureVector
