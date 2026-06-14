# Implementation Plan: AI Foundation

**Branch**: `002-ai-foundation` | **Date**: 2026-06-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-ai-foundation/spec.md`

---

## Summary

Build the Fe El Seka AI service from the ground up: a standalone FastAPI prediction server (`services/ai`), an offline dataset pipeline that ingests Cairo road network data and generates 100,000+ synthetic rides, an offline training pipeline that produces three versioned joblib model artifacts (match score, ride ranking, price recommendation), and a Supabase Storage model registry — so that AI predictions are available to the main backend before any real user data exists. The AI service exposes per-endpoint prediction APIs; models are loaded at startup from the registry and can be hot-reloaded without a restart.

---

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**:
- Runtime: `fastapi>=0.111`, `uvicorn[standard]`, `pydantic-settings>=2.2`, `joblib`, `numpy`, `supabase`
- ML: `xgboost>=2.0`, `scikit-learn>=1.4`, `pandas`, `pyarrow`
- Pipeline: `osmnx>=1.9` (OSM Cairo road network ingestion)
- Dev: `ruff>=0.4`, `pytest>=8.0`, `pytest-asyncio>=0.23`, `httpx` (FastAPI test client)

**Storage**: Supabase Storage bucket `model-registry` (versioned model artifacts + metadata); local `data/` directory for pipeline intermediates (gitignored)

**Testing**: pytest + pytest-asyncio for unit and integration tests; httpx for FastAPI endpoint testing

**Target Platform**: Linux/Windows development machine (local for competition MVP)

**Project Type**: Python AI service (FastAPI) + offline pipeline scripts

**Performance Goals**:
- Match score batch (20 candidates): ≤ 500ms p95
- Price recommendation: ≤ 200ms p95
- Model load on startup: ≤ 30s

**Constraints**:
- Model artifacts serialized as joblib (`.joblib`)
- Model versions identified by UTC ISO 8601 timestamp (e.g., `2026-06-13T14:30:22Z`)
- Match score model must achieve AUC-ROC ≥ 0.65 on held-out validation split
- Zone encoding uses lat/lng centroid coordinates (not ordinal or one-hot)
- 50 concurrent prediction requests without latency degradation

**Scale/Scope**: 3 trained models, 100k+ training records, ~24 Cairo zones, 8–14 feature dimensions per input

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle / Standard | Requirement | Status |
|---|---|---|
| Principle IV — AI-Augmented Transportation | AI capabilities MUST exist as dedicated, independently deployable services | ✅ PASS — `services/ai` is a standalone FastAPI service; NFR-002 mandates independent deployability |
| Principle IV — Explainability & Auditability | AI systems MUST remain explainable and auditable | ✅ PASS — XGBoost feature importance is available; all predictions logged per NFR-006; model versions tracked in registry |
| Principle IV — Continuous Improvement | Architecture MUST support model updates without major redesign | ✅ PASS — versioned registry + hot-reload endpoint (FR-023) support iterative model updates |
| Principle VI — Modular Domain-Driven | Spec covers a single business capability | ✅ PASS — AI service only; no auth, no ride management, no frontend |
| Principle VII — Shared Foundations, Independent Applications | AI service independently deployable | ✅ PASS — NFR-002 explicitly requires this |
| Architecture Standards — Dedicated AI services | AI MUST NOT be embedded in the main backend | ✅ PASS — `services/ai` is a separate process and deployment unit |
| Data Standards — UUID primary keys | All entities must use UUID PKs | ✅ PASS — Model artifacts are Storage objects, not database entities; no new DB tables introduced in this phase |
| Security Standards — Secrets via env vars | No credentials in version control | ✅ PASS — Supabase credentials via `.env` (established in Phase 1) |

**Gate result: PASS — no violations. Proceed to Phase 0.**

---

## Project Structure

### Documentation (this feature)

```text
specs/002-ai-foundation/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   ├── prediction-api.md    ← Phase 1 output (prediction endpoints)
│   └── model-registry.md    ← Phase 1 output (storage layout)
├── checklists/
│   └── requirements.md
└── tasks.md             ← Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code

```text
services/ai/
├── app/
│   ├── main.py                      # FastAPI app entry point + lifespan (model loading)
│   ├── config.py                    # pydantic-settings: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, etc.
│   ├── models/                      # Pydantic request/response schemas
│   │   ├── health.py                # HealthResponse schema
│   │   ├── prediction.py            # MatchScoreRequest/Response, RankingRequest/Response, PriceRequest/Response
│   │   └── registry.py              # ReloadRequest/Response, ModelVersionInfo
│   ├── routers/                     # FastAPI route handlers
│   │   ├── health.py                # GET /health
│   │   ├── predict.py               # POST /predict/match-score, /predict/ride-ranking, /predict/price-recommendation
│   │   └── models.py                # POST /models/reload
│   └── services/                    # Business logic (pure functions, no HTTP dependencies)
│       ├── feature_engineering.py   # Zone centroid lookup + feature vector construction (shared: training & serving)
│       ├── match_scorer.py          # Load + call match score XGBoost model
│       ├── ride_ranker.py           # Load + call ride ranking XGBoost model
│       ├── price_recommender.py     # Load + call price Scikit-Learn model
│       └── model_registry.py        # Supabase Storage: upload, download, get-latest, reload
├── pipelines/
│   ├── dataset/
│   │   ├── zones.py                 # Cairo zone definitions: name, type, centroid_lat, centroid_lng, weight
│   │   ├── ingest_osm.py            # Download Cairo road graph via osmnx; extract zone node data
│   │   ├── generate_rides.py        # Synthetic ride generator: 100k+ records, peak-weighted, zone-distributed
│   │   └── run.py                   # Entry point: python -m pipelines.dataset.run
│   ├── features/
│   │   ├── engineer.py              # Feature engineering (imports from app/services/feature_engineering.py)
│   │   └── run.py                   # Entry point: python -m pipelines.features.run
│   └── training/
│       ├── train_match_score.py     # XGBoost binary classifier; AUC-ROC ≥ 0.65 gate
│       ├── train_ranker.py          # XGBoost ranker (LambdaRank or pointwise on match scores)
│       ├── train_price.py           # Scikit-Learn Ridge regression; ±20% for min/max range
│       ├── evaluate.py              # AUC-ROC, NDCG, MAE utilities
│       ├── upload.py                # Upload .joblib + metadata.json to Supabase Storage
│       └── run.py                   # Entry point: python -m pipelines.training.run
├── data/                            # gitignored — local pipeline outputs
│   ├── raw/                         # OSM graph + generated rides (.parquet)
│   ├── features/                    # Feature matrices (.parquet)
│   └── models/                      # Local .joblib artifacts before upload
├── tests/
│   ├── unit/
│   │   ├── test_feature_engineering.py   # Feature vector determinism + zone centroid correctness
│   │   ├── test_match_scorer.py          # Score clamping, valid range
│   │   └── test_price_recommender.py     # Output range > 0, currency EGP
│   └── integration/
│       ├── test_health_endpoint.py       # Health statuses (ok/degraded/unavailable)
│       └── test_prediction_endpoints.py  # Round-trip prediction calls with mock models
├── pyproject.toml
└── ruff.toml
```

---

## Complexity Tracking

No constitution violations — section not applicable.
