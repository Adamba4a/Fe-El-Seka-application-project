# Contract: `services/ai` HTTP Endpoints (new + extended)

All endpoints below are internal service-to-service calls from `services/api`'s `ai_client.py`, following the existing client's conventions: `httpx.AsyncClient`, structured `ai_prediction_call`/`ai_training_call` log events with `model_version`/`latency_ms`, and `AIServiceUnavailableError` raised on timeout/unreachable/non-2xx.

## Extended: `POST /predict/match-score`, `POST /predict/ride-ranking`

**Change**: response gains two optional fields, populated whenever a `candidate.json` pointer exists for the model type. No change to the request shape.

**Existing response shape** (unchanged fields):
```json
{
  "match_score": 0.8421,
  "model_version": "2026-06-13T14-30-22Z"
}
```

**Extended response shape**:
```json
{
  "match_score": 0.8421,
  "model_version": "2026-06-13T14-30-22Z",
  "shadow_score": 0.8677,
  "shadow_model_version": "2026-08-09T02-00-00Z"
}
```

- `shadow_score` / `shadow_model_version`: `null` when no candidate is currently loaded (the common case pre-feature and between rollout cycles). Never affects `match_score` — the champion score returned in `match_score` is always what today's contract already returns; shadow fields are strictly additive.
- Computed synchronously in the same request (both models already resident in `app.state.models`), so no extra network round-trip; `services/api` still enforces its existing 1.0s hard timeout on the whole call (NFR-003 — no measurable added latency).
- `services/api`'s call site persists `shadow_score`/`shadow_model_version` onto the corresponding `match_events` row via the existing fire-and-forget `match_logging_service.persist_match_events()` path — no new logging mechanism.

## New: `POST /training/retrain`

Triggered by `services/api`'s `retraining_scheduler_loop` (on cadence) or an on-demand admin trigger (FR-005).

**Request**:
```json
{
  "model_type": "match_score",
  "dataset_storage_path": "match_score/2026-08-09T02-00-00Z/dataset.parquet",
  "dataset_snapshot_id": "b3f1...-uuid"
}
```

**Response (success — gates passed)**:
```json
{
  "status": "trained",
  "storage_version": "2026-08-09T03-15-00Z",
  "evaluation_score": 0.7912,
  "auc_roc": 0.8930,
  "expected_calibration_error": 0.031
}
```

**Response (gate failure — matches existing `TrainingGateError` behavior)**:
```json
{
  "status": "gate_failed",
  "reason": "auc_roc_below_threshold",
  "auc_roc": 0.58
}
```
On `gate_failed`, no model artifact is uploaded to Storage and `services/api` records the attempt (status only, no `model_versions` row created — a gate-failed run produces nothing to govern, consistent with today's synthetic pipeline aborting entirely on `TrainingGateError`).

On success, `services/ai` uploads `model.joblib`/`metadata.json` to `{model_type}/{storage_version}/` in the `model-registry` bucket (existing atomic-upload convention) but does **not** touch `latest.json` or `candidate.json` — `services/api` decides what to do with the returned `evaluation_score` (compare to current champion, insert a `model_versions` row as `candidate` or `rejected`) and only calls a separate endpoint to actually load it as a shadow candidate.

## New: `POST /models/shadow`

Called by `services/api`'s `model_lifecycle_service.py` when a `candidate` version passes the promotion margin and becomes eligible for shadow burn-in (User Story 3).

**Request**:
```json
{ "model_type": "match_score", "storage_version": "2026-08-09T03-15-00Z" }
```

**Behavior**: writes `candidate.json` = `{"version": "2026-08-09T03-15-00Z"}` to the `model-registry` bucket, downloads and loads that version into `app.state.models[model_type]["candidate"]`. From this point, `/predict/*` responses for this `model_type` include `shadow_score`.

**Response**: `{"status": "shadow_active", "storage_version": "2026-08-09T03-15-00Z"}`

## New: `POST /models/promote`

Called by `services/api`'s `model_lifecycle_service.py` when a `partial_rollout` version reaches its final rollout step and holds without rollback (User Story 3, transition to `champion`).

**Request**:
```json
{ "model_type": "match_score", "storage_version": "2026-08-09T03-15-00Z" }
```

**Behavior**: copies the candidate's artifact reference to `latest.json` (the existing champion pointer), clears `candidate.json`, and reloads `app.state.models[model_type]["model"]` — reusing the exact swap logic already in `/models/reload`, just re-targeted at a specific version instead of "whatever latest.json currently says."

**Response**: `{"status": "promoted", "storage_version": "2026-08-09T03-15-00Z"}`

## New: `POST /models/discard-candidate`

Called on rejection (fails promotion margin), unfavorable shadow burn-in, or automatic/manual rollback — clears `candidate.json` and drops `app.state.models[model_type]["candidate"]` so `/predict/*` stops returning shadow fields for this model type.

**Request**: `{ "model_type": "match_score" }`

**Response**: `{"status": "candidate_cleared"}`

**Note on rollback speed (FR-012)**: the *traffic* rollback (stop routing any percentage to the candidate) is a pure `services/api`-side change (`model_versions.rollout_pct → 0`, read by the next `continuous_learning_config`-style cache refresh) and takes effect within one refresh cycle (≤30s) with zero call to `services/ai`. This endpoint is only for eventually cleaning up the now-unused shadow slot in `services/ai`'s memory — not on the critical rollback path.

## Existing (unchanged): `POST /models/reload`, `GET /health`

No changes. `/models/reload`'s existing `_ALL_MODEL_TYPES = ["match_score", "ride_ranker"]` remains accurate — this feature does not add a third model type (pricing is out of scope per spec.md's scope correction).
