# Feature Specification: AI Foundation

**Feature Branch**: `002-ai-foundation`

**Created**: 2026-06-13

**Status**: Draft

**Input**: Competition MVP — Phase 2 — ai-foundation (025), ai-dataset-pipeline (026), ai-training-pipeline (027), ai-model-serving (028)

## Clarifications

### Session 2026-06-13

- Q: How should Cairo zones be encoded as numeric features in the feature vector? → A: Lat/lng centroid coordinates per zone (2 float values per zone) — preserves geographic distance meaning with a fixed-size encoding.
- Q: What serialization format should trained model artifacts use? → A: joblib for all three models — native to XGBoost and Scikit-Learn, no conversion step required.
- Q: What format should model version identifiers use? → A: UTC ISO 8601 date-time stamp (e.g., `2026-06-13T14:30:22Z`) — timezone-explicit, naturally sortable, unambiguous across environments, forward-compatible.
- Q: What is the minimum AUC-ROC score on the held-out validation set that constitutes a passing training run for the match score model? → A: AUC-ROC ≥ 0.65 on the held-out split.
- Q: How should the AI service handle prediction requests when only some models are loaded? → A: Serve each endpoint independently — loaded endpoints respond normally; unloaded endpoints return HTTP 503 with a clear message identifying which model is missing.

---

## Business Objective *(mandatory)*

Build the AI infrastructure that powers Fe El Seka's intelligent ride matching before any real user data exists — establishing a standalone AI service, a Cairo-realistic synthetic training dataset, three trained prediction models, and a prediction API — so that AI-powered match scoring, ride ranking, and price recommendations are operational from the moment the platform opens to passengers and drivers.

**Constitutional Domain**: AI-Augmented Transportation (Principle IV)

**Affected Applications**: AI Service, Backend API (consumer), Shared

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Generate Cairo Training Dataset (Priority: P1)

A data engineer runs the dataset pipeline against publicly available Cairo geographic data and synthetic ride generation parameters. The pipeline completes without errors and produces a minimum of 100,000 synthetic ride records that reflect realistic Egyptian carpooling behavior — covering Cairo districts, universities, business zones, and commute corridors — stored in a format ready for model training.

**Why this priority**: No model can be trained without data. This is the foundational input for all three AI models. Without a realistic Cairo dataset, every downstream pipeline step is blocked.

**Independent Test**: A data engineer runs the dataset pipeline from a clean environment and inspects the output — confirming at least 100,000 records exist, that origins and destinations span Cairo's major zones, and that departure times cluster appropriately around Egyptian peak commute hours.

**Acceptance Scenarios**:

1. **Given** the pipeline is configured with Cairo geographic parameters, **When** the dataset pipeline is executed, **Then** it completes without errors and produces at least 100,000 synthetic ride records.
2. **Given** the generated dataset, **When** its records are inspected, **Then** origins and destinations are distributed across Cairo's major districts, universities, and business zones — not concentrated in a single area.
3. **Given** the generated dataset, **When** departure times are analyzed, **Then** a statistically significant proportion of records fall within Cairo's morning peak (7–9am) and evening peak (4–7pm) windows.
4. **Given** the pipeline has completed, **When** the output is validated, **Then** every record includes all required fields for downstream feature engineering with no nulls in mandatory columns.
5. **Given** the pipeline encounters a data source that is unreachable, **When** execution proceeds, **Then** the pipeline logs the failure clearly and exits with a non-zero status code rather than producing a partial or corrupt dataset.

---

### User Story 2 — Train AI Prediction Models (Priority: P2)

A data engineer runs the training pipeline against the generated dataset and produces three trained, versioned model artifacts — match score prediction, ride ranking, and price recommendation — each stored in the model registry with its version identifier, training date, and performance summary. After training, a data engineer can confirm model accuracy is above the minimum threshold before the models are promoted to the serving layer.

**Why this priority**: The three trained model artifacts are the direct output consumed by the serving layer. Without them, the AI service has nothing to load and all prediction endpoints are non-functional.

**Independent Test**: A data engineer runs the training pipeline from a clean environment (with only the dataset as input) and confirms that three artifact files appear in the model registry, each tagged with a version identifier and a training metrics summary.

**Acceptance Scenarios**:

1. **Given** the dataset pipeline output is available, **When** the training pipeline is executed, **Then** all three models (match score, ride ranking, price recommendation) complete training without errors.
2. **Given** training completes, **When** the model registry is inspected, **Then** three versioned artifact files are present, each with a version identifier, training date, and performance metrics summary.
3. **Given** training completes, **When** the match score model's accuracy is measured on a held-out validation set, **Then** the model performs above the minimum acceptable threshold defined in the training pipeline configuration.
4. **Given** training completes, **When** the price recommendation model is evaluated, **Then** its fare predictions fall within a reasonable range for Cairo distances and do not produce negative or zero fares.
5. **Given** training fails partway through, **When** the failure is detected, **Then** no partial or corrupt artifact is written to the registry and the failure is clearly reported.

---

### User Story 3 — AI Service Serves Predictions (Priority: P3)

The main backend API sends a passenger's ride request and a list of candidate driver rides to the AI service and receives back a match score per candidate, a ranked ordering of candidates, and a price recommendation — all within a latency that does not degrade the passenger's search experience.

**Why this priority**: This is the externally visible AI capability required by the competition. It is the integration point between the AI Foundation (this phase) and the platform features built in later phases. Without this endpoint, the platform cannot claim AI-powered matching.

**Independent Test**: A developer calls the AI prediction endpoints directly (without the full platform running) and confirms that valid input produces numeric scores, a ranked list, and a price range in response within the latency target.

**Acceptance Scenarios**:

1. **Given** the AI service is running with trained models loaded, **When** the backend sends a match score prediction request with a passenger route and 10 candidate rides, **Then** the service returns a numeric match score (0.0 to 1.0) for each candidate within 500ms.
2. **Given** the AI service is running, **When** the backend sends a ride ranking request with scored candidates, **Then** the service returns the candidates ordered from highest to lowest predicted match quality.
3. **Given** the AI service is running, **When** the backend sends a price recommendation request with ride parameters, **Then** the service returns a recommended fare range (minimum and maximum) within 200ms.
4. **Given** the AI service receives a prediction request with malformed or missing fields, **When** the request is processed, **Then** the service returns a structured error response identifying the invalid fields — it does not crash or return a 500 error.
5. **Given** the AI service is queried with a batch of 20 candidate rides simultaneously, **When** the request completes, **Then** all 20 scores are returned in a single response within 500ms at p95.

---

### User Story 4 — Graceful Fallback When AI Unavailable (Priority: P4)

When the AI service is down, overloaded, or returns an unexpected error, the main backend automatically falls back to deterministic ride ranking (by route overlap percentage) without returning an error to the passenger. The passenger receives a ranked list of rides and is not aware that AI scoring was unavailable.

**Why this priority**: The AI service is an enhancement, not a blocker. Passengers must always be able to search for rides. A hard dependency on AI availability would make the entire platform fragile.

**Independent Test**: A developer stops the AI service while a ride search request is in flight from the backend, and confirms the backend returns a valid ranked ride list using the fallback logic — with no error exposed to the caller.

**Acceptance Scenarios**:

1. **Given** the AI service is unreachable, **When** the backend attempts a prediction request, **Then** the backend detects the failure within 1 second and falls back to deterministic ordering.
2. **Given** the fallback has been triggered, **When** the passenger's search response is returned, **Then** it contains a valid, ordered list of candidate rides — not an error response.
3. **Given** the AI service returns an unexpected error response, **When** the backend receives it, **Then** the backend logs the AI error and applies the fallback without propagating the error upstream.
4. **Given** the AI service recovers and becomes available again, **When** the next search request arrives, **Then** the backend resumes using AI scoring without requiring a restart.

---

### Edge Cases

- What happens if the dataset pipeline is interrupted mid-generation? The pipeline must not write partial output to the training location; it must fail cleanly so the next run starts fresh.
- What happens if a Cairo district or zone has insufficient synthetic rides? The generation parameters must enforce minimum record counts per zone to prevent model bias toward over-represented areas.
- What happens if the AI service starts before any trained models exist in the registry? The service must start successfully but report a degraded health status and return errors (not crashes) on prediction requests.
- What happens if a new model version is uploaded to the registry while the AI service is serving requests? The service must continue serving with the currently loaded version until an explicit reload is triggered; in-flight requests must not be interrupted.
- What happens if the match score model returns a score outside the 0.0–1.0 range? The serving layer must clamp the score to the valid range and log a warning rather than passing an invalid score to the backend.
- What happens if the feature engineering step receives a ride with a missing field? Feature engineering must reject the record and log a clear error identifying the missing field rather than silently producing a zero-filled feature vector.
- What happens if only one or two of the three models are successfully loaded at startup? Each prediction endpoint operates independently — loaded endpoints serve requests normally; unloaded endpoints return HTTP 503 identifying the missing model by name. The health check reports `degraded` with the count of loaded models.

---

## Requirements *(mandatory)*

### Functional Requirements

**AI Service Setup**

- **FR-001**: The AI service MUST be an independently deployable Python service with its own health check endpoint that returns overall status (`ok`, `degraded`, or `unavailable`), the number of loaded models, and the service version.
- **FR-002**: The AI service MUST start successfully and report `degraded` health (not crash) when no trained model artifacts are present in the registry, or when only a subset of the three models are loaded.
- **FR-002a**: Each prediction endpoint MUST operate independently of the others' model load status. An endpoint whose model is loaded MUST respond normally; an endpoint whose model is not loaded MUST return HTTP 503 with a structured error body identifying the missing model by name. The service MUST NOT fail globally because a single model is absent.
- **FR-003**: The AI service MUST expose prediction endpoints callable over HTTP by the main backend API without requiring shared memory or direct database access.

**Dataset Pipeline**

- **FR-004**: The dataset pipeline MUST ingest Cairo road network data from publicly available geographic sources to establish ground-truth route information for synthetic ride generation.
- **FR-005**: The dataset pipeline MUST generate a minimum of 100,000 synthetic ride records representing Egyptian carpooling patterns in Greater Cairo.
- **FR-006**: Each synthetic ride record MUST include: origin zone, destination zone, departure time, approximate route corridor, and synthetic passenger-driver behavioral signals sufficient for feature engineering.
- **FR-007**: The synthetic generation MUST ensure origins and destinations are distributed across Cairo's major districts, universities, business zones, and transportation corridors — with minimum representation thresholds per zone type to prevent geographic bias.
- **FR-008**: The synthetic generation MUST model Cairo-realistic commute timing, with morning peak concentration (7–9am) and evening peak concentration (4–7pm) reflected in the departure time distribution.
- **FR-009**: The dataset pipeline output MUST be stored in a format directly consumable by the feature engineering step without manual transformation.

**Feature Engineering**

- **FR-010**: A feature engineering pipeline MUST transform raw ride records into a standardized numerical feature vector used as model input, shared consistently across all three models.
- **FR-011**: The feature engineering pipeline MUST be deterministic: identical input records MUST always produce identical feature vectors.
- **FR-012**: The feature set MUST include, at minimum: estimated route overlap ratio, estimated pickup detour distance, estimated dropoff distance, time-of-day encoding, origin zone centroid (latitude + longitude as two float values), and destination zone centroid (latitude + longitude as two float values). Zone encoding MUST use geographic centroid coordinates — not ordinal integers or one-hot vectors — so that the model can learn distance relationships between zones.

**Training Pipeline**

- **FR-013**: The training pipeline MUST train a match score prediction model that, given a passenger route request and a candidate driver ride as feature vectors, outputs a numeric compatibility score between 0.0 and 1.0.
- **FR-014**: The training pipeline MUST train a ride ranking model that, given a set of scored candidate rides, produces an ordering ranked by predicted match quality for a given passenger.
- **FR-015**: The training pipeline MUST train a price recommendation model that, given ride parameters, outputs a recommended fare range (minimum and maximum) expressed in Egyptian Pounds.
- **FR-016**: The training pipeline MUST evaluate each model on a held-out validation split (minimum 20% of the dataset) and record performance metrics before writing artifacts to the registry. The match score model MUST achieve AUC-ROC ≥ 0.65 on the held-out split; a training run that falls below this threshold MUST log a warning and MUST NOT write artifacts to the registry.
- **FR-017**: All trained model artifacts MUST be stored in the model registry as joblib-serialized files (`.joblib`), accompanied by a JSON metadata file containing: version identifier (UTC ISO 8601 date-time string, e.g., `2026-06-13T14:30:22Z`), training date, dataset record count used, and a performance metrics summary. The version identifier MUST be recorded in UTC to ensure unambiguous ordering across environments.
- **FR-018**: The training pipeline MUST NOT overwrite an existing model version in the registry; each training run MUST produce a new version identified by the UTC ISO 8601 timestamp of when that run completed.

**Model Serving**

- **FR-019**: The AI service MUST expose a match score prediction endpoint that accepts a passenger ride request and one or more candidate driver rides and returns a predicted match score (0.0–1.0) for each candidate.
- **FR-020**: The AI service MUST expose a ride ranking endpoint that accepts a list of candidate rides (with or without pre-computed scores) and returns them ordered from highest to lowest predicted match quality.
- **FR-021**: The AI service MUST expose a price recommendation endpoint that accepts ride parameters (origin zone, destination zone, estimated distance, time of day) and returns a recommended fare range.
- **FR-022**: The AI service MUST return a structured error response (not crash) when a prediction request contains malformed or missing required fields.
- **FR-023**: The AI service MUST support loading a new model version from the registry on demand without requiring a full service restart.
- **FR-024**: Match scores returned by the serving layer MUST be clamped to the 0.0–1.0 range; out-of-range values from the model MUST be clamped and logged as warnings.

**Fallback Contract**

- **FR-025**: The AI service API design MUST support health-check-based fallback detection: the main backend MUST be able to determine AI unavailability within 1 second via the health endpoint or a failed prediction call.
- **FR-026**: When the AI service is unavailable, the main backend MUST fall back to ordering candidate rides by deterministic route overlap percentage — this fallback logic lives in the backend, but the AI service API contract must not hinder its implementation.

### Key Entities

- **Training Dataset**: The collection of synthetic and ingested ride records with geographic and behavioral fields, stored as the input to the feature engineering and training pipelines.
- **Feature Vector**: A standardized set of numerical values extracted from a ride pair (passenger request + candidate ride), used as input to all three prediction models.
- **Trained Model Artifact**: A versioned, serialized prediction model file stored in the model registry, alongside its metadata (version, date, metrics).
- **Model Registry**: Versioned storage of trained model artifacts with associated metadata, accessible to the AI service on startup and on reload.
- **Match Score**: A numeric value (0.0–1.0) representing predicted compatibility between a passenger's route and a candidate driver's ride.
- **Price Recommendation**: A suggested fare range (minimum and maximum in Egyptian Pounds) output by the pricing model for a given set of ride parameters.
- **Prediction Request**: A structured API call from the main backend to the AI service, carrying the ride data needed for one or more predictions.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The dataset pipeline runs end-to-end and produces at least 100,000 synthetic Cairo ride records in a single execution without manual intervention.
- **SC-002**: The generated dataset's origin and destination distributions cover at least 10 distinct Cairo zones, with no single zone exceeding 20% of total records.
- **SC-003**: The training pipeline produces all three versioned model artifacts (match score, ride ranking, price recommendation) in a single execution, and the match score model achieves AUC-ROC ≥ 0.65 on the held-out validation split.
- **SC-004**: The AI service returns match scores for a batch of up to 20 candidate rides within 500ms at p95 under normal operating conditions.
- **SC-005**: The AI service returns a price recommendation within 200ms at p95 under normal operating conditions.
- **SC-006**: All three trained models are loaded and available for predictions within 30 seconds of AI service startup.
- **SC-007**: When the AI service is unreachable, the main backend detects the failure and falls back to deterministic ordering within 1 second, with no error surfaced to the caller.
- **SC-008**: Any specific trained model version is retrievable from the model registry by version identifier at any point after its training run completes.

---

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: The AI service prediction endpoints MUST respond within 500ms at p95 for a batch of up to 20 candidate rides under normal load.
- **NFR-002**: The AI service MUST be independently deployable and startable without requiring the main backend, either Next.js application, or the database to be running.
- **NFR-003**: The dataset pipeline and training pipeline MUST be executable as standalone scripts independently of the serving layer — pipeline execution MUST NOT require the AI service to be running.
- **NFR-004**: Feature engineering MUST be deterministic: identical input data MUST always produce identical feature vectors, ensuring reproducible training and consistent online inference.
- **NFR-005**: The model registry MUST retain at least the two most recent model versions simultaneously; older versions MUST NOT be automatically purged until a retention policy is explicitly configured.
- **NFR-006**: The AI service MUST log all prediction requests with sufficient detail (input shape, model version used, response time) to enable audit and debugging without logging sensitive user data.
- **NFR-007**: The training pipeline MUST complete a full training run (all three models) on the 100,000-record dataset within 2 hours on a standard development machine.
- **NFR-008**: The AI service MUST handle at least 50 concurrent prediction requests without returning errors or exceeding the p95 latency target.

---

## Dependencies *(mandatory)*

- **Internal**: Phase 1 Platform Foundation (spec 001) — the `services/ai` service scaffold, monorepo project structure, and environment management must be in place before the AI service can be built upon.
- **External**: A Supabase project with an active Storage bucket must be provisioned for the model registry; this is the same Supabase project established in Phase 1.
- **External**: Publicly available Cairo road network data (OpenStreetMap) must be accessible for the dataset ingestion step; the pipeline must document the exact data source and download procedure.
- **External**: Kaggle datasets for transportation network features must be accessible; the pipeline must document the dataset identifier and access method.
- **Data**: No real user ride data exists at this phase; all training data is entirely synthetic or sourced from public geographic datasets.
- **Phase Dependency**: Phase 9 (AI Application) consumes the prediction endpoints defined in this phase; the API contract established here is binding for Phase 9 integration.

---

## Out-of-Scope

- Integration with the deterministic route overlap engine (PostGIS / OSRM) for live feature computation — this is Phase 5; this phase uses pre-computed synthetic features.
- Consuming AI predictions within passenger ride search — this is Phase 9 (AI Application).
- Real user ride data ingestion, model retraining on live data, and automated retraining pipelines — deferred to Post-Competition Phase 13.
- Demand forecasting and fraud detection models — deferred to Post-Competition Phase 13.
- Model performance monitoring, drift detection, and alerting — deferred to Post-Competition Phase 12.
- Admin dashboard visibility into model performance or training history — deferred to Post-Competition Phase 11.
- Authentication and authorization on the AI service prediction endpoints — the AI service is internal, accessed only by the main backend; mTLS or API key auth is deferred post-competition.
- Arabic language support in AI service responses or error messages.
- Cloud deployment of the AI service — the service runs locally for the competition demo; production deployment is Phase 12.

---

## Technical Considerations

- The AI service is implemented as a Python FastAPI service within `services/ai`, using `uv` as the package manager, consistent with the Phase 1 scaffold and the approved technology stack.
- Match score prediction and ride ranking models are implemented with XGBoost; price recommendation is implemented with Scikit-Learn — per the approved stack in the roadmap.
- Feature engineering must produce a consistent feature vector format used identically in both the offline training pipeline and the online serving path. Any divergence between training-time and serving-time features invalidates model predictions; this is the highest-risk technical area in this phase.
- Model artifacts are stored as joblib-serialized `.joblib` files in Supabase Storage, alongside a JSON metadata file per model version; the AI service loads the designated current version on startup and supports a reload endpoint for model updates without restart.
- Cairo-specific synthetic generation parameters include: districts (Maadi, Zamalek, Heliopolis, Nasr City, 6th of October, New Cairo, Downtown Cairo, Giza, Mohandessin, Dokki, Shubra, Ain Shams), universities (Cairo University, AUC, Ain Shams University, Helwan University, GUC, BUE), business zones (Smart Village, New Administrative Capital, Downtown Cairo CBD, 6th of October industrial zone), and transportation corridors (Ring Road, Salah Salem, Corniche el Nil, Autostrad, Cairo–Alexandria Desert Road).
- The fallback mechanism (ordering by route overlap when AI is unavailable) is implemented in the main backend (Phase 9), but the AI service API must be designed so unavailability is detectable within 1 second — via the health endpoint or a fast-timeout on prediction calls.
- All three models share a single feature engineering module to guarantee input consistency between training and serving.
- Model training is a one-time offline pipeline execution for the competition MVP; continuous retraining is a Post-Competition concern.
- The AI service MUST expose a `/health` endpoint following the same response structure established in Phase 1 for the backend API: `{"status": "ok|degraded|unavailable", "models_loaded": <count>, "version": "<version>"}`.
- Code quality in `services/ai` is enforced by `ruff` for linting and formatting, consistent with the Phase 1 setup.

---

## Assumptions

- OpenStreetMap Cairo road network data provides sufficient geographic coverage and accuracy to generate realistic synthetic ride routes across Greater Cairo.
- 100,000 synthetic ride records is sufficient training volume for the three competition MVP models to demonstrate meaningful prediction quality on synthetic data.
- Model quality is judged by the competition on functional demonstration and integration, not on benchmarked accuracy against real-world data; reasonable performance on synthetic Cairo data is the acceptable standard.
- The AI service is deployed locally for the competition demonstration; cloud deployment infrastructure is not required for the competition MVP.
- Dataset ingestion and model training pipelines are run once before the competition demo; scheduled or automated retraining is not required.
- Kaggle datasets used for road network features are publicly available and do not require institutional access or paid subscriptions.
- The main backend (implemented in Phase 9) is responsible for implementing the fallback logic; this specification defines only the AI service API contract that enables the fallback to be implemented.
- Synthetic ride records do not need to encode real street-level geometries — zone-level and corridor-level encoding is sufficient for MVP model training.
- A single Supabase Storage bucket is sufficient for the model registry at competition MVP scale; a dedicated model-serving infrastructure (e.g., MLflow, BentoML) is not required.
