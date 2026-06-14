# Research: AI Foundation

**Feature**: `002-ai-foundation` | **Date**: 2026-06-13

---

## Decision 1 — Cairo Road Network Ingestion

**Decision**: Use `osmnx` to download the Cairo road network from OpenStreetMap.

**Rationale**: osmnx wraps the Overpass API and returns the road network as a NetworkX graph with node geometries (lat/lng per intersection). This gives Cairo zone centroids from real road nodes, and the graph structure allows validating that synthetic ride pairs are connected by real road corridors. Cairo's OSM coverage is extensive; the drive network graph for Greater Cairo is downloadable in under 2 minutes.

**How to use**:
```python
import osmnx as ox
G = ox.graph_from_place("Cairo, Egypt", network_type="drive")
nodes, edges = ox.graph_to_gdfs(G)
# nodes has geometry (Point), osmid, x (lng), y (lat)
```

**Alternatives considered**:
- Raw Overpass API: More control, but verbose; osmnx is a purpose-built wrapper — no benefit to raw API for this use case.
- Pre-downloaded PBF file + osmium: Faster for continent-scale extracts; overkill for Cairo alone.
- Kaggle transportation datasets: No suitably scoped Cairo carpooling dataset found on Kaggle. General taxi datasets (e.g., New York taxi) are not geographically transferable. OSM is the correct primary source.

---

## Decision 2 — Synthetic Ride Generation Strategy

**Decision**: Generate synthetic rides by sampling weighted origin/destination zone pairs, adding Gaussian noise to zone centroids for coordinate variation, and sampling departure times from a bimodal distribution reflecting Cairo peak hours.

**Cairo Zone Definitions** (hardcoded in `pipelines/dataset/zones.py`):

| Zone | Type | Centroid (approx.) | Weight |
|---|---|---|---|
| Downtown Cairo | district | 30.0444, 31.2357 | 0.10 |
| Maadi | district | 30.0131, 31.2089 | 0.09 |
| Zamalek | district | 30.0598, 31.2214 | 0.05 |
| Heliopolis | district | 30.0912, 31.3217 | 0.08 |
| Nasr City | district | 30.0626, 31.3462 | 0.09 |
| New Cairo | district | 30.0274, 31.4745 | 0.08 |
| 6th of October | district | 29.9602, 30.9304 | 0.06 |
| Giza | district | 29.9870, 31.2118 | 0.07 |
| Mohandessin | district | 30.0594, 31.2024 | 0.05 |
| Dokki | district | 30.0381, 31.2124 | 0.04 |
| Shubra | district | 30.1100, 31.2480 | 0.05 |
| Ain Shams | district | 30.1191, 31.3272 | 0.04 |
| Cairo University | university | 30.0260, 31.2097 | 0.06 |
| AUC New Cairo | university | 30.0209, 31.4997 | 0.04 |
| Ain Shams University | university | 30.1199, 31.3220 | 0.03 |
| Helwan University | university | 29.8421, 31.3340 | 0.02 |
| Smart Village | business_zone | 30.0730, 30.9710 | 0.05 |
| New Admin Capital | business_zone | 30.0130, 31.6990 | 0.03 |

**Departure time distribution**: Bimodal — 40% morning peak (7–9am, normally distributed μ=8h, σ=0.5h), 40% evening peak (4–7pm, μ=17h, σ=0.75h), 20% off-peak (uniform across remaining hours).

**Coordinate noise**: Gaussian noise with σ=0.008° (~900m) applied to zone centroids for origin/destination coordinates to simulate real pickup/dropoff variation within a zone.

**Minimum zone representation**: Every zone must appear as origin or destination in at least 1,000 records to prevent model bias.

**Label generation for match score training**:
A synthetic pair (passenger request, candidate driver ride) is labelled `1` (good match) when all three conditions hold:
1. Destination zones are the same or adjacent (within 5km centroid distance)
2. Departure times are within 30 minutes of each other
3. Driver's origin is in the same or adjacent zone as passenger's origin

Otherwise labelled `0`. This produces a realistic ~30–40% positive rate consistent with carpooling match scarcity.

**Alternatives considered**:
- Random uniform origin/destination: No geographic realism; model learns nothing about Cairo commute patterns.
- Real taxi trip datasets: No freely available Cairo taxi dataset with sufficient volume and coverage.
- Manual route scripting: Too labour-intensive for 100k records; zone-based generation is scalable.

---

## Decision 3 — Intermediate Data Format

**Decision**: Apache Parquet via `pandas` + `pyarrow`.

**Rationale**: Columnar format compresses synthetic ride records ~5–10× vs CSV. Read performance for feature engineering (loading 100k rows of floats) is significantly faster than CSV. Parquet preserves data types (floats, datetime) without parsing overhead. Standard format in ML pipelines; pandas reads it natively.

**Alternatives considered**:
- CSV: Simple but large (~50MB for 100k rows uncompressed) and slow to parse. No type safety.
- JSON: Not suitable for tabular data; ~3× larger than Parquet.
- HDF5/Feather: Also good; Parquet preferred for broader ecosystem compatibility.

---

## Decision 4 — Feature Vector Design

**Decision**: 14-dimensional feature vector, zone encoding via lat/lng centroid pairs (decided in `/speckit-clarify`).

| Feature | Description | Encoding |
|---|---|---|
| `passenger_origin_lat` | Passenger origin zone centroid latitude | float |
| `passenger_origin_lng` | Passenger origin zone centroid longitude | float |
| `passenger_dest_lat` | Passenger destination zone centroid latitude | float |
| `passenger_dest_lng` | Passenger destination zone centroid longitude | float |
| `driver_origin_lat` | Driver origin zone centroid latitude | float |
| `driver_origin_lng` | Driver origin zone centroid longitude | float |
| `driver_dest_lat` | Driver destination zone centroid latitude | float |
| `driver_dest_lng` | Driver destination zone centroid longitude | float |
| `overlap_ratio` | Estimated route overlap (0.0–1.0) | float |
| `pickup_detour_km` | Estimated driver detour to pickup passenger (km) | float |
| `dropoff_distance_km` | Walk distance from driver dropoff to passenger destination (km) | float |
| `dest_zone_distance_km` | Euclidean distance between passenger and driver destination centroids (km) | float |
| `departure_hour_sin` | Cyclical encoding: sin(2π × hour / 24) | float |
| `departure_hour_cos` | Cyclical encoding: cos(2π × hour / 24) | float |

**Cyclical time encoding rationale**: Preserves that 23:00 is close to 01:00. Tree models (XGBoost) do not inherently learn cyclical relationships from raw hour integers — sine/cosine encoding surfaces this directly as two continuous features.

**Feature module sharing**: `app/services/feature_engineering.py` is the single source of truth, imported by both the training pipeline and the serving layer. This guarantees training/serving consistency (the highest-risk area identified in the spec).

---

## Decision 5 — Model Architectures

### Match Score Model (XGBoost binary classifier)
- **Target**: Binary label (1 = good match, 0 = poor match) — generated synthetically
- **Algorithm**: `XGBClassifier` with `objective='binary:logistic'`, `eval_metric='auc'`
- **Hyperparameters** (baseline, no tuning for MVP): `n_estimators=200`, `max_depth=6`, `learning_rate=0.1`, `subsample=0.8`, `colsample_bytree=0.8`
- **Split**: 80% train / 20% validation (stratified on label)
- **Gate**: AUC-ROC ≥ 0.65 on validation set (from clarification Q4)
- **Output**: `predict_proba()[:, 1]` → float score 0.0–1.0, clamped at serving layer

### Ride Ranking Model (XGBoost pointwise ranker)
- **Target**: Same binary label as match score; pointwise ranking approach (train classifier, use scores for ranking)
- **Rationale**: A separate ranker trained on the same labels adds a calibration step tuned for ordering rather than raw probability. For MVP with synthetic data, pointwise is sufficient; pairwise LambdaRank deferred post-competition.
- **Algorithm**: `XGBClassifier` with `objective='binary:logistic'` (same architecture, different train split weighting to emphasize rank-relevant pairs)
- **Output**: Sorted ride IDs descending by predicted score

### Price Recommendation Model (Scikit-Learn Ridge Regression)
- **Target**: Synthetic fare (EGP) computed as: `fare = base_fare + per_km_rate × distance_km + peak_surcharge`
  - `base_fare = 15 EGP`, `per_km_rate = 3.5 EGP/km`, `peak_surcharge = 10 EGP if peak else 0`
  - Gaussian noise σ=5 EGP added to simulate real driver pricing variation
- **Algorithm**: `Ridge(alpha=1.0)` — linear model appropriate for a synthetically generated linear target
- **Features used**: `passenger_origin_lat`, `passenger_origin_lng`, `passenger_dest_lat`, `passenger_dest_lng`, `dest_zone_distance_km`, `departure_hour_sin`, `departure_hour_cos` (7 features)
- **Output**: Point estimate; served as `min_egp = max(10, estimate × 0.8)`, `max_egp = estimate × 1.2`
- **Metric**: Mean Absolute Error (MAE) in EGP; no minimum threshold enforced for MVP

---

## Decision 6 — Model Registry Layout (Supabase Storage)

**Decision**: Bucket `model-registry`, version-isolated paths, with a `latest.json` pointer per model type.

```
model-registry/                        (Supabase Storage bucket)
├── match_score/
│   ├── 2026-06-13T14:30:22Z/
│   │   ├── model.joblib               (serialized XGBClassifier)
│   │   └── metadata.json              (version, date, record_count, metrics)
│   └── latest.json                    ({"version": "2026-06-13T14:30:22Z"})
├── ride_ranker/
│   ├── 2026-06-13T14:30:22Z/
│   │   ├── model.joblib
│   │   └── metadata.json
│   └── latest.json
└── price_recommender/
    ├── 2026-06-13T14:30:22Z/
    │   ├── model.joblib
    │   └── metadata.json
    └── latest.json
```

**metadata.json structure**:
```json
{
  "version": "2026-06-13T14:30:22Z",
  "model_type": "match_score",
  "training_date": "2026-06-13T14:30:22Z",
  "dataset_record_count": 100000,
  "validation_split": 0.2,
  "metrics": {
    "auc_roc": 0.72,
    "threshold_gate": "auc_roc >= 0.65",
    "gate_passed": true
  },
  "feature_count": 14,
  "feature_names": ["passenger_origin_lat", "passenger_origin_lng", "..."]
}
```

**Rationale**: `latest.json` avoids listing bucket contents on every startup (O(1) lookup vs O(n) list). Version-isolated paths prevent overwrites. Metadata JSON keeps the registry self-describing without a database dependency.

**Alternatives considered**:
- Database table for registry metadata: Adds DB dependency at AI service startup — breaks NFR-002 (independent deployability).
- Version in filename (flat bucket): Hard to manage, no natural grouping per model type.
- MLflow model registry: Heavyweight external dependency; not in approved stack.

---

## Decision 7 — FastAPI Model Loading Pattern

**Decision**: Use FastAPI `@asynccontextmanager` lifespan for startup loading; store loaded models in `app.state.models`; reload endpoint downloads latest from Supabase Storage and replaces in-memory instance.

**Lifespan pattern**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.models = await load_all_models()   # download from Storage
    yield
    app.state.models = {}

app = FastAPI(lifespan=lifespan)
```

**Rationale**: Lifespan is the recommended FastAPI pattern since v0.111 (replaces deprecated `@app.on_event`). `app.state` avoids module-level globals, making endpoints testable by injecting mock models via `app.state`. Per-endpoint independence (FR-002a) is implemented by storing each model separately in the state dict and checking presence before serving.

**Alternatives considered**:
- Global variables: Anti-pattern; breaks testability and thread safety.
- Dependency injection loading per request: Re-downloads/loads model on every request — unacceptable latency.
- `@app.on_event("startup")`: Deprecated in FastAPI 0.111+.

---

## Decision 8 — Fallback Contract Implementation Note

The AI service does not implement fallback logic — that belongs to the main backend (Phase 9). The AI service's responsibility is:
1. Health endpoint responds within timeout (1 second) even under degraded conditions
2. Each prediction endpoint returns HTTP 503 with a structured body when its model is not loaded
3. All error responses use a consistent JSON structure: `{"error": "model_not_loaded", "model_type": "match_score", "message": "..."}`

This allows the backend (Phase 9) to implement fallback by catching HTTP 503 or connection timeout on any prediction call.
