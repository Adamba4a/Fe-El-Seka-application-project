# Tasks: AI Foundation

**Input**: Design documents from `specs/002-ai-foundation/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅ | quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on each other)
- **[Story]**: Which user story this task belongs to (US1 = Dataset, US2 = Training, US3 = Predictions, US4 = Fallback)
- File paths are relative to the repo root

---

## Phase 1: Setup (Scaffold Expansion)

**Purpose**: Expand the Phase 1 `services/ai` skeleton into the full directory structure required by this spec. All subsequent phases depend on this structure existing.

- [X] T001 Expand `services/ai/` directory tree: create `app/models/`, `app/routers/`, `app/services/`, `pipelines/dataset/`, `pipelines/features/`, `pipelines/training/`, `tests/unit/`, `tests/integration/`, `data/raw/`, `data/features/`, `data/models/`; add `__init__.py` to every Python package directory
- [X] T002 Replace `services/ai/pyproject.toml` with full dependency set: runtime (`fastapi>=0.111`, `uvicorn[standard]`, `pydantic-settings>=2.2`, `xgboost>=2.0`, `scikit-learn>=1.4`, `joblib`, `pandas`, `pyarrow`, `osmnx>=1.9`, `numpy`, `supabase`), dev (`ruff>=0.4`, `pytest>=8.0`, `pytest-asyncio>=0.23`, `httpx`)
- [X] T003 [P] Configure `services/ai/ruff.toml` (line-length = 100, target Python 3.11, enable E/W/F/I rule sets, per-file ignores for `__init__.py`)
- [X] T004 [P] Create `services/ai/app/config.py` using pydantic-settings: `Settings` class with `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `MODEL_REGISTRY_BUCKET` (default `"model-registry"`), `AI_VERSION` (default `"0.1.0"`); expose `get_settings()` cached singleton
- [X] T005 [P] Create `services/ai/data/.gitignore` ignoring `raw/`, `features/`, `models/` subdirectories; create `services/ai/data/raw/.keep`, `data/features/.keep`, `data/models/.keep` placeholder files

**Checkpoint**: Run `uv sync` in `services/ai/` — all dependencies install without errors. Directory tree matches `plan.md § Project Structure`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared modules required by both the pipeline scripts (Phase 3, 4) and the serving layer (Phase 5, 6). MUST be complete before any user story phase begins.

**⚠️ CRITICAL**: US1 depends on T006. US2 and US3 depend on T007. US3 depends on T008. No user story can start until its foundational dependency is done.

- [X] T006 Define `CairoZone` dataclass and all 18 zone entries in `services/ai/pipelines/dataset/zones.py`: fields `name: str`, `zone_type: str` (`district|university|business_zone`), `centroid_lat: float`, `centroid_lng: float`, `weight: float`; include all zones from `research.md § Decision 2` (Downtown Cairo, Maadi, Zamalek, Heliopolis, Nasr City, New Cairo, 6th of October, Giza, Mohandessin, Dokki, Shubra, Ain Shams, Cairo University, AUC New Cairo, Ain Shams University, Helwan University, Smart Village, New Admin Capital); add assertion that weights sum to 1.0; expose `ZONES: list[CairoZone]` and `zone_by_name: dict[str, CairoZone]`
- [X] T007 [P] Implement shared feature engineering module in `services/ai/app/services/feature_engineering.py`: `build_feature_vector(...)` and `build_feature_vector_from_coords(...)` returning deterministic 14-element float64 arrays in fixed field order from `data-model.md § Entity 3 — FeatureVector`; zone name variant used by training pipeline; coords variant used by serving layer; clamp `overlap_ratio` to [0.0, 1.0]; compute `dest_zone_distance_km` as Euclidean distance; cyclical time encoding; this is the SINGLE source of truth for feature computation
- [X] T008 [P] Implement model registry client in `services/ai/app/services/model_registry.py`: `ModelRegistry` class wrapping `supabase-py` Storage; `get_latest_version`, `download_model`, `upload_model`, `upload_metadata`, `write_latest`; raise `RegistryError` on Storage failure; colons in version strings replaced with hyphens for path safety

**Checkpoint**: `uv run python -c "from app.services.feature_engineering import build_feature_vector; from app.services.model_registry import ModelRegistry; print('OK')"` runs without import errors.

---

## Phase 3: User Story 1 — Generate Cairo Training Dataset (Priority: P1) 🎯 MVP

**Goal**: Run the dataset pipeline and produce 100,000+ synthetic Cairo ride records in `data/raw/rides.parquet`, ready for feature engineering.

**Independent Test**: `uv run python -m pipelines.dataset.run` completes without errors; `data/raw/rides.parquet` contains ≥ 100,000 rows, zero nulls, 18+ distinct origin zones, 30–40% positive `match_label` rate (see `quickstart.md § Step 1`).

- [X] T009 [US1] Implement OSM Cairo road network ingestion in `services/ai/pipelines/dataset/ingest_osm.py`: `download_cairo_graph() -> nx.MultiDiGraph` using `osmnx.graph_from_place("Cairo, Egypt", network_type="drive")`; cache the downloaded graph to `data/raw/cairo_graph.graphml` so subsequent runs skip the download; return cached graph if file exists; log download progress and node/edge counts on completion
- [X] T010 [P] [US1] Implement synthetic ride generator in `services/ai/pipelines/dataset/generate_rides.py`: `generate_rides(n: int = 100_000) -> pd.DataFrame`; weighted zone sampling; Gaussian noise σ=0.008° on centroids; bimodal departure times (40/40/20 morning/evening/off-peak); match_label=1 if dest within 5km AND time within 30min AND origin within 5km; enforce min 1,000 records per zone
- [X] T011 [US1] Implement dataset pipeline entry point in `services/ai/pipelines/dataset/run.py`: call OSM ingest, generate rides, validate, write to `data/raw/rides.parquet`; exit non-zero on validation failure
- [X] T012 [US1] Implement feature engineering pipeline in `services/ai/pipelines/features/engineer.py` and `run.py`: `engineer_features(rides_df) -> pd.DataFrame` calling `build_feature_vector()` per row; `run.py` loads rides.parquet, calls engineer_features, validates finite floats, writes `data/features/features.parquet`

**Checkpoint**: US1 is fully functional. `data/raw/rides.parquet` and `data/features/features.parquet` both exist and pass validation.

---

## Phase 4: User Story 2 — Train AI Prediction Models (Priority: P2)

**Goal**: Run the training pipeline and produce three versioned, joblib-serialized model artifacts uploaded to the Supabase Storage `model-registry` bucket, with match score AUC-ROC ≥ 0.65 confirmed.

**Independent Test**: `uv run python -m pipelines.training.run` completes without errors; `data/models/` contains 3 `.joblib` files and 3 `_metadata.json` files; `match_score_metadata.json` shows `"gate_passed": true` and `"auc_roc" >= 0.65` (see `quickstart.md § Step 3`).

- [X] T013 [P] [US2] Implement evaluation utilities in `services/ai/pipelines/training/evaluate.py`: `auc_roc_score`, `mae_score`, `build_metadata`
- [X] T014 [US2] Implement match score model training in `services/ai/pipelines/training/train_match_score.py`: stratified 80/20 split; `XGBClassifier(objective="binary:logistic", n_estimators=200, max_depth=6, learning_rate=0.1, subsample=0.8, colsample_bytree=0.8, eval_metric="auc", random_state=42)`; **GATE: raise `TrainingGateError` if AUC-ROC < 0.65**; serialize to `data/models/match_score.joblib`; write metadata
- [X] T015 [P] [US2] Implement ride ranker model training in `services/ai/pipelines/training/train_ranker.py`: same XGBClassifier architecture; serialize to `data/models/ride_ranker.joblib`; write metadata (no gate)
- [X] T016 [P] [US2] Implement price recommendation model training in `services/ai/pipelines/training/train_price.py`: synthetic fare labels `15 + 3.5*dist + 10*peak + N(0,5)`; `Ridge(alpha=1.0)` on 7 price features; serialize to `data/models/price_recommender.joblib`; write metadata with MAE
- [X] T017 [US2] Implement model upload script in `services/ai/pipelines/training/upload.py`: upload all 3 models and metadata; write `latest.json` ONLY after all uploads succeed
- [X] T018 [US2] Implement training pipeline entry point in `services/ai/pipelines/training/run.py`: generate UTC ISO version at start; load features.parquet; train match_score (gate hard-stop), ranker, price; call upload; log metrics summary

**Checkpoint**: US2 is fully functional. All three models trained, artifacts in `data/models/`, registry updated. `match_score_metadata.json` shows `gate_passed: true`.

---

## Phase 5: User Story 3 — AI Service Serves Predictions (Priority: P3)

**Goal**: Start the AI service; it loads all 3 models from the registry and serves match scores, rankings, and price recommendations via HTTP within latency targets.

**Independent Test**: `GET /health` returns `"status": "ok"`; `POST /predict/match-score` with valid body returns scores in [0.0, 1.0] within 500ms; `POST /predict/price-recommendation` returns `recommended_price_egp ≥ 10.0` within 200ms (see `quickstart.md § Steps 4–5`).

- [X] T019 [P] [US3] Create Pydantic schemas in `services/ai/app/models/health.py`: `ModelVersions`, `HealthResponse`
- [X] T020 [P] [US3] Create Pydantic schemas in `services/ai/app/models/prediction.py`: `ZoneCoords`, `MatchScoreBatchRequest`, `MatchScoreResponse`, `RideRankingBatchRequest`, `RideRankingResponse`, `PriceRequest`, `PriceResponse`
- [X] T021 [P] [US3] Create Pydantic schemas in `services/ai/app/models/registry.py` and `services/ai/app/models/errors.py`: `ReloadRequest`, `ReloadResponse`, `ErrorResponse`
- [X] T022 [US3] Create FastAPI application with lifespan in `services/ai/app/main.py`: `@asynccontextmanager` lifespan loads 3 models at startup; `app.state.models` dict; graceful None on load failure; mount routers for health, predict, models
- [X] T023 [P] [US3] Implement match scorer service in `services/ai/app/services/match_scorer.py`: `predict_scores()` using `build_feature_vector_from_coords`; `np.clip()` to [0.0, 1.0]
- [X] T024 [P] [US3] Implement ride ranker service in `services/ai/app/services/ride_ranker.py`: `rank_candidates()` returning sorted `RideRankingResponse`
- [X] T025 [P] [US3] Implement price recommender service in `services/ai/app/services/price_recommender.py`: `predict_price()` with `min_egp = max(10.0, raw_price)` floor
- [X] T026 [US3] Implement health router in `services/ai/app/routers/health.py`: `GET /health` reads `app.state.models` synchronously (NO I/O); returns `HealthResponse`
- [X] T027 [US3] Implement prediction router in `services/ai/app/routers/predict.py`: `POST /predict/match-score`, `POST /predict/ride-ranking`, `POST /predict/price-recommendation`; per-endpoint 503 guards (T029); structured logging (T030)
- [X] T028 [US3] Implement models reload router in `services/ai/app/routers/models.py`: `POST /models/reload`; reload all or targeted models; return `ReloadResponse`

**Checkpoint**: US3 is fully functional. Start service with `uv run uvicorn app.main:app --port 8001`, health returns `"ok"`, all 3 prediction endpoints return valid responses within latency targets.

---

## Phase 6: User Story 4 — Graceful Fallback When AI Unavailable (Priority: P4)

**Goal**: Each prediction endpoint returns a structured HTTP 503 when its model is not loaded; health endpoint reports `"degraded"` with loaded model count; all responses conform to the `ErrorResponse` contract so the main backend can detect and fall back.

**Independent Test**: Start service without uploading models (empty registry) — health returns `"degraded"`; call any prediction endpoint — receive HTTP 503; load only match_score model — POST /predict/match-score returns 200, POST /predict/price-recommendation still returns 503 (see `quickstart.md § Step 6`).

- [X] T029 [US4] Per-endpoint model-not-loaded guard in `services/ai/app/routers/predict.py`: implemented in `_get_model()` helper; returns HTTP 503 with structured detail message per missing model type; all three endpoints guard independently
- [X] T030 [US4] Structured request/response logging in `services/ai/app/routers/predict.py`: INFO level on success (endpoint, model_version, batch_size, response_time_ms); WARNING on 503; uses Python `logging` module

**Checkpoint**: US4 is fully functional. Partial model loading produces per-endpoint 503 exactly matching `contracts/prediction-api.md § Error Response Schema`. Unaffected endpoints continue serving 200.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation, latency verification, and determinism guarantee.

- [ ] T031 Run all 8 quickstart validation steps in `specs/002-ai-foundation/quickstart.md` end-to-end: dataset pipeline → feature pipeline → training pipeline → start AI service → match score endpoint → price endpoint → partial model availability → hot reload; confirm every checkpoint passes and document any deviations
- [X] T032 [P] Validate feature engineering determinism per FR-011: `services/ai/scripts/validate_determinism.py` calls `build_feature_vector_from_coords()` 10 times with identical inputs and asserts `np.array_equal`; print PASS/FAIL summary
- [X] T033 [P] Validate concurrent prediction latency: `services/ai/scripts/load_test.py` fires `ITERATIONS` requests with batch size `BATCH_SIZE` against all 3 prediction endpoints; prints p50/p95/min/max latency summary

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    └── Phase 2 (Foundational)
            ├── T006 (zones) ──────────────────────────────── Phase 3 (US1)
            ├── T007 (feature_engineering) ─────────────────── Phase 3 (US1) + Phase 4 (US2) + Phase 5 (US3)
            └── T008 (model_registry) ──────────────────────── Phase 4 (US2) + Phase 5 (US3)
                    │
                    ├── Phase 3 (US1) ─────────────── Phase 4 (US2) [rides.parquet → features.parquet → training]
                    ├── Phase 4 (US2) ─────────────── Phase 5 (US3) [trained models in registry → load at startup]
                    ├── Phase 5 (US3) ─────────────── Phase 6 (US4) [endpoints exist → add 503 guards]
                    └── Phase 6 (US4)
                            └── Final Phase (Polish)
```

### User Story Dependencies

| Story | Can Start After | Depends On |
|---|---|---|
| US1 — Dataset (P1) | T006 done | T006 (zones), T007 (feature_engineering for engineer.py) |
| US2 — Training (P2) | US1 complete | US1 outputs (`features.parquet`), T007, T008 |
| US3 — Predictions (P3) | US2 complete | US2 outputs (models in registry), T007, T008 |
| US4 — Fallback (P4) | US3 complete | US3 endpoints exist in predict.py |
| Polish | US4 complete | All endpoints and pipelines operational |

### Within Each User Story

- Within US1: T009 (OSM) before T011 (run.py); T010 can run in parallel with T009; T012 after T011
- Within US2: T013 (eval) can parallel with T014/T015/T016; T014 must complete and gate-pass before T017; T017 before T018
- Within US3: T019/T020/T021 schemas first, then T022 (app), T023/T024/T025 services, then T026/T027/T028 routers in sequence
- Within US4: T029/T030 integrated into predict.py (T027) — done together

---

## Implementation Strategy

### MVP First (US1 → US2 → Service Up)

1. Complete Phase 1 (Setup) + Phase 2 (Foundational)
2. Complete Phase 3 (US1): dataset pipeline → `rides.parquet` and `features.parquet` exist
3. Complete Phase 4 (US2): training pipeline → models uploaded to registry
4. Complete Phase 5 (US3): AI service starts and serves predictions
5. **STOP and VALIDATE**: `GET /health` → `"ok"`; call all 3 prediction endpoints
6. Complete Phase 6 (US4): add 503 guards and logging ✅ (integrated into T027)
7. Run Final Phase: quickstart validation + load test (T031 pending runtime)

### Incremental Delivery

Each phase delivers a standalone, verifiable output:
- Phase 3 alone: `rides.parquet` exists and passes validation → dataset ready
- Phase 4 alone (after 3): models in Supabase Storage with `gate_passed: true` → training verified
- Phase 5 alone (after 4): `GET /health` → `"ok"` → service verified
- Phase 6 alone (after 5): partial model test passes → fallback contract verified

---

## Notes

- `[P]` tasks operate on different files and have no mutual dependencies — safe to run simultaneously
- `[Story]` label maps each task to its user story for traceability and independent validation
- `feature_engineering.py` (T007) is imported by both `pipelines/features/engineer.py` and `app/services/` — never duplicate this logic
- The AUC-ROC gate in T014 is a hard stop: if the match score model fails the gate, do NOT upload any models and fix the dataset or feature engineering
- Model version string (UTC ISO 8601) is generated ONCE at the start of `training/run.py` and shared across all three model artifacts uploaded in that run
- `latest.json` is written LAST, after all joblib and metadata uploads succeed, to maintain registry consistency per `contracts/model-registry.md § Upload Sequence`
- T029 and T030 were integrated directly into `predict.py` (T027) rather than as separate edits
- `build_feature_vector_from_coords()` added to feature_engineering.py for serving layer — uses raw lat/lng instead of zone names
