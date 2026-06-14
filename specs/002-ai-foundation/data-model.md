# Data Model: AI Foundation

**Feature**: `002-ai-foundation` | **Date**: 2026-06-13

---

## Overview

Phase 2 introduces no new database tables. All persistent data in this phase lives in **Supabase Storage** (model artifacts) and **local files** (pipeline intermediates). The entities below describe the logical data structures used across the dataset pipeline, training pipeline, and AI serving layer.

---

## Entity 1 — CairoZone

Represents a named geographic zone used as origin/destination in synthetic ride generation and as the basis for zone centroid feature encoding.

**Defined in**: `pipelines/dataset/zones.py` (hardcoded list — not a database table)

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Human-readable zone name (e.g., `"Maadi"`, `"Cairo University"`) |
| `zone_type` | `enum` | One of: `district`, `university`, `business_zone` |
| `centroid_lat` | `float` | WGS84 latitude of zone centroid |
| `centroid_lng` | `float` | WGS84 longitude of zone centroid |
| `weight` | `float` | Probability weight for synthetic generation (sum of all weights = 1.0) |

**Constraints**:
- All weights must sum to 1.0
- `centroid_lat` ∈ [29.7, 30.3] (Cairo bounding box)
- `centroid_lng` ∈ [30.8, 31.8] (Cairo bounding box)
- Minimum 18 zones must be defined (see research.md Decision 2 for full list)

---

## Entity 2 — SyntheticRide

A single synthetic ride record produced by the dataset pipeline. Stored as rows in a Parquet file. Forms the primary training corpus.

**Defined in**: `data/raw/rides.parquet` (pipeline output, gitignored)

| Field | Type | Description |
|---|---|---|
| `id` | `UUID` (str) | Unique record identifier |
| `origin_zone` | `str` | Name of the origin CairoZone |
| `destination_zone` | `str` | Name of the destination CairoZone |
| `origin_lat` | `float` | Origin coordinate (zone centroid + Gaussian noise σ=0.008°) |
| `origin_lng` | `float` | Origin coordinate (zone centroid + Gaussian noise σ=0.008°) |
| `destination_lat` | `float` | Destination coordinate (zone centroid + Gaussian noise) |
| `destination_lng` | `float` | Destination coordinate (zone centroid + Gaussian noise) |
| `departure_at` | `datetime` (UTC) | Departure time; bimodal distribution reflecting Cairo peak hours |
| `estimated_distance_km` | `float` | Euclidean distance between origin and destination centroids (km) |
| `is_driver` | `bool` | True = driver ride; False = passenger request |
| `match_label` | `int` | 0 or 1 — synthetic match quality label (see research.md Decision 2) |

**Constraints**:
- Minimum 100,000 records total
- Minimum 1,000 records per zone (as origin or destination)
- No null values in any field
- `match_label` positive rate: 30–40% (enforced by label generation logic)
- `estimated_distance_km` > 0

**Lifecycle**: Created by `pipelines/dataset/generate_rides.py` → consumed by `pipelines/features/engineer.py`

---

## Entity 3 — FeatureVector

The standardized 14-dimensional numerical input to all three ML models. Used identically in offline training (feature pipeline) and online serving (AI service). **This entity must be computed identically in both contexts.**

**Defined in**: `app/services/feature_engineering.py` (single source of truth; imported by training pipeline)

| Field | Index | Type | Description |
|---|---|---|---|
| `passenger_origin_lat` | 0 | `float` | Passenger origin zone centroid latitude |
| `passenger_origin_lng` | 1 | `float` | Passenger origin zone centroid longitude |
| `passenger_dest_lat` | 2 | `float` | Passenger destination zone centroid latitude |
| `passenger_dest_lng` | 3 | `float` | Passenger destination zone centroid longitude |
| `driver_origin_lat` | 4 | `float` | Driver origin zone centroid latitude |
| `driver_origin_lng` | 5 | `float` | Driver origin zone centroid longitude |
| `driver_dest_lat` | 6 | `float` | Driver destination zone centroid latitude |
| `driver_dest_lng` | 7 | `float` | Driver destination zone centroid longitude |
| `overlap_ratio` | 8 | `float` | Estimated route overlap, 0.0–1.0 |
| `pickup_detour_km` | 9 | `float` | Estimated driver detour to reach passenger pickup (km) |
| `dropoff_distance_km` | 10 | `float` | Walk distance from driver dropoff to passenger destination (km) |
| `dest_zone_distance_km` | 11 | `float` | Euclidean distance between passenger and driver destination centroids (km) |
| `departure_hour_sin` | 12 | `float` | sin(2π × departure_hour / 24) |
| `departure_hour_cos` | 13 | `float` | cos(2π × departure_hour / 24) |

**Constraints**:
- Feature order is fixed; any change requires retraining all models
- `overlap_ratio` ∈ [0.0, 1.0] — must be clamped before passing to model if out of range
- `departure_hour` ∈ [0, 23] — must be extracted from UTC datetime before encoding
- All values must be finite (no NaN, no ±∞)
- `feature_engineering.py` is the **single source of truth** — no duplicate implementation

---

## Entity 4 — TrainedModelArtifact

A versioned, serialized model stored in the Supabase Storage model registry. Persisted as two files per version: the joblib model file and a JSON metadata file.

**Stored in**: Supabase Storage bucket `model-registry`

| Field | Type | Source | Description |
|---|---|---|---|
| `model_type` | `enum` | training pipeline | One of: `match_score`, `ride_ranker`, `price_recommender` |
| `version` | `str` | training pipeline | UTC ISO 8601 timestamp of training run completion (e.g., `"2026-06-13T14:30:22Z"`) |
| `training_date` | `str` | training pipeline | Same as `version` (UTC ISO 8601) |
| `dataset_record_count` | `int` | training pipeline | Number of records used in training split |
| `validation_split` | `float` | training pipeline | Fraction held out for validation (0.20) |
| `metrics` | `dict` | training pipeline | Model-specific metrics (see below) |
| `feature_count` | `int` | training pipeline | Number of input features (14) |
| `feature_names` | `list[str]` | training pipeline | Ordered list of feature names (matches FeatureVector field names) |

**Metrics by model type**:

| Model | Metric Key | Type | Gate |
|---|---|---|---|
| `match_score` | `auc_roc` | float | ≥ 0.65 (training run fails if below) |
| `ride_ranker` | `auc_roc` | float | no gate for MVP |
| `price_recommender` | `mae_egp` | float | no gate for MVP |

**Storage paths** (within bucket `model-registry`):

```
{model_type}/{version}/model.joblib
{model_type}/{version}/metadata.json
{model_type}/latest.json                ← {"version": "<UTC ISO 8601>"}
```

**Constraints**:
- Version identifiers are UTC ISO 8601; two runs starting at the same second are not possible in single-machine MVP context
- `latest.json` is written atomically after all model files and metadata are confirmed uploaded
- Old versions are NOT deleted automatically (NFR-005: retain ≥ 2 most recent versions)

---

## Entity 5 — PredictionRequest / PredictionResponse

Runtime Pydantic models used by the AI service HTTP API. Not persisted — exists only in memory during a request lifecycle.

**Defined in**: `app/models/prediction.py`

### MatchScoreRequest

```
passenger_request:
  origin_zone:        str
  destination_zone:   str
  origin_centroid:    {lat: float, lng: float}
  destination_centroid: {lat: float, lng: float}
  departure_at:       datetime (UTC)

candidates: list of:
  ride_id:                UUID (str)
  driver_origin_zone:     str
  driver_destination_zone: str
  driver_origin_centroid:  {lat: float, lng: float}
  driver_dest_centroid:    {lat: float, lng: float}
  driver_departure_at:     datetime (UTC)
  estimated_overlap_ratio: float
  estimated_pickup_detour_km: float
  estimated_dropoff_distance_km: float
```

### MatchScoreResponse

```
model_version:  str (UTC ISO 8601)
model_type:     "match_score"
scores: list of:
  ride_id:      UUID (str)
  match_score:  float (0.0–1.0, clamped)
```

### RankingRequest

```
candidates: list of:
  ride_id:      UUID (str)
  match_score:  float  (optional; if absent, model scores internally)
```

### RankingResponse

```
model_version:  str
model_type:     "ride_ranker"
ranked:         list[str]   (ride_id values, descending match quality)
```

### PriceRequest

```
origin_zone:              str
destination_zone:         str
origin_centroid:          {lat: float, lng: float}
destination_centroid:     {lat: float, lng: float}
estimated_distance_km:    float
departure_at:             datetime (UTC)
```

### PriceResponse

```
model_version:      str
model_type:         "price_recommender"
recommended_fare:
  min_egp:          float  (≥ 10 EGP floor)
  max_egp:          float
  currency:         "EGP"
```

---

## Entity 6 — ErrorResponse

Returned by all endpoints on validation failure or model-not-loaded conditions.

```
error:       str   (machine-readable code, e.g., "model_not_loaded", "invalid_input")
model_type:  str   (which model was missing, if applicable)
message:     str   (human-readable description)
```

HTTP status codes:
- `422` — request validation failure (Pydantic)
- `503` — model not loaded for this endpoint
- `500` — unexpected internal error (logged; generic message to caller)

---

## Entity 7 — HealthResponse

Returned by `GET /health`. Extended from the Phase 1 backend health check format.

```
status:          "ok" | "degraded" | "unavailable"
models_loaded:   int  (0–3)
model_versions:
  match_score:          str | null
  ride_ranker:          str | null
  price_recommender:    str | null
version:         str  (AI service version from config, e.g., "0.1.0")
```

**Status rules**:
- `ok`: all 3 models loaded
- `degraded`: 1 or 2 models loaded (or 0 models but service is running)
- `unavailable`: service is starting up or has crashed (not reachable)

---

## No Database Entities

Phase 2 does not introduce any new Supabase PostgreSQL tables. The database schema established in Phase 1 (`users`, `rides`, `bookings`) is not modified. All AI data lives in Supabase Storage or local files.

Future phases (Phase 9 — AI Application) may introduce a `prediction_logs` table for audit trail; that is out of scope here.
