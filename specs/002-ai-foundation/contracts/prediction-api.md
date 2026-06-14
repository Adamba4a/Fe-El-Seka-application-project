# Contract: AI Prediction API

**Service**: `services/ai` | **Feature**: `002-ai-foundation` | **Date**: 2026-06-13

Base URL (local): `http://localhost:8001`

All request and response bodies are JSON (`Content-Type: application/json`).
All `datetime` fields are UTC ISO 8601 strings (e.g., `"2026-06-13T08:00:00Z"`).
All `ride_id` fields are UUID strings.

---

## GET /health

Returns the service health status and loaded model inventory.

**Response 200**:
```json
{
  "status": "ok",
  "models_loaded": 3,
  "model_versions": {
    "match_score": "2026-06-13T14:30:22Z",
    "ride_ranker": "2026-06-13T14:30:22Z",
    "price_recommender": "2026-06-13T14:30:22Z"
  },
  "version": "0.1.0"
}
```

**Status values**:
- `"ok"` — all 3 models loaded and ready
- `"degraded"` — service is running but 0–2 models are loaded
- `"unavailable"` — service is unreachable (connection refused or timeout)

**Notes**:
- This endpoint must respond within 1 second even under degraded conditions (FR-025)
- Main backend uses this endpoint to detect AI unavailability for fallback triggering

---

## POST /predict/match-score

Scores each candidate driver ride against a passenger's ride request.

**Request**:
```json
{
  "passenger_request": {
    "origin_zone": "Downtown Cairo",
    "destination_zone": "Maadi",
    "origin_centroid": { "lat": 30.0444, "lng": 31.2357 },
    "destination_centroid": { "lat": 30.0131, "lng": 31.2089 },
    "departure_at": "2026-06-13T08:00:00Z"
  },
  "candidates": [
    {
      "ride_id": "550e8400-e29b-41d4-a716-446655440000",
      "driver_origin_zone": "Downtown Cairo",
      "driver_destination_zone": "Maadi",
      "driver_origin_centroid": { "lat": 30.0500, "lng": 31.2400 },
      "driver_dest_centroid": { "lat": 30.0100, "lng": 31.2100 },
      "driver_departure_at": "2026-06-13T07:55:00Z",
      "estimated_overlap_ratio": 0.78,
      "estimated_pickup_detour_km": 0.5,
      "estimated_dropoff_distance_km": 0.3
    }
  ]
}
```

**Constraints**:
- `candidates` must contain 1–20 items (inclusive)
- `estimated_overlap_ratio` ∈ [0.0, 1.0]
- `estimated_pickup_detour_km` ≥ 0
- `estimated_dropoff_distance_km` ≥ 0

**Response 200**:
```json
{
  "model_version": "2026-06-13T14:30:22Z",
  "model_type": "match_score",
  "scores": [
    {
      "ride_id": "550e8400-e29b-41d4-a716-446655440000",
      "match_score": 0.87
    }
  ]
}
```

**Notes**:
- `match_score` is always in [0.0, 1.0] — clamped by the serving layer (FR-024)
- Response order matches request `candidates` order
- Target latency: ≤ 500ms p95 for 20 candidates (NFR-001)

**Response 503** (model not loaded):
```json
{
  "error": "model_not_loaded",
  "model_type": "match_score",
  "message": "match_score model is not currently loaded. Check /health for status."
}
```

**Response 422** (validation error): standard Pydantic validation error body.

---

## POST /predict/ride-ranking

Returns candidate ride IDs ordered from best to worst predicted match quality.

**Request**:
```json
{
  "candidates": [
    {
      "ride_id": "550e8400-e29b-41d4-a716-446655440000",
      "match_score": 0.87
    },
    {
      "ride_id": "661f9511-f3ac-52e5-b827-557766551111",
      "match_score": 0.62
    }
  ]
}
```

**Constraints**:
- `candidates` must contain 1–50 items
- `match_score` is optional per candidate; if absent for any candidate, the ranker scores them internally (requires `passenger_request` context — see extended contract note below)

**Response 200**:
```json
{
  "model_version": "2026-06-13T14:30:22Z",
  "model_type": "ride_ranker",
  "ranked": [
    "550e8400-e29b-41d4-a716-446655440000",
    "661f9511-f3ac-52e5-b827-557766551111"
  ]
}
```

**Notes**:
- `ranked` contains `ride_id` strings in descending predicted match quality order
- For MVP, the backend is expected to call `/predict/match-score` first, then pass scores to this endpoint
- Target latency: ≤ 500ms p95

**Response 503**: same structure as `/predict/match-score` with `"model_type": "ride_ranker"`.

---

## POST /predict/price-recommendation

Returns a recommended fare range for a given ride.

**Request**:
```json
{
  "origin_zone": "Downtown Cairo",
  "destination_zone": "Maadi",
  "origin_centroid": { "lat": 30.0444, "lng": 31.2357 },
  "destination_centroid": { "lat": 30.0131, "lng": 31.2089 },
  "estimated_distance_km": 12.5,
  "departure_at": "2026-06-13T08:00:00Z"
}
```

**Constraints**:
- `estimated_distance_km` > 0
- `departure_at` must be a valid UTC ISO 8601 datetime

**Response 200**:
```json
{
  "model_version": "2026-06-13T14:30:22Z",
  "model_type": "price_recommender",
  "recommended_fare": {
    "min_egp": 35.0,
    "max_egp": 52.5,
    "currency": "EGP"
  }
}
```

**Notes**:
- `min_egp` has a hard floor of 10 EGP (enforced by serving layer regardless of model output)
- `min_egp = max(10.0, point_estimate × 0.8)`, `max_egp = point_estimate × 1.2`
- `currency` is always `"EGP"` for MVP
- Target latency: ≤ 200ms p95 (NFR-001)

**Response 503**: same structure with `"model_type": "price_recommender"`.

---

## POST /models/reload

Triggers a hot-reload of models from the Supabase Storage registry without restarting the service.

**Request**: empty body (`{}`) to reload all models, or:
```json
{
  "model_types": ["match_score"]
}
```
to reload specific models only.

**Response 200**:
```json
{
  "reloaded": ["match_score", "ride_ranker", "price_recommender"],
  "versions": {
    "match_score": "2026-06-13T14:30:22Z",
    "ride_ranker": "2026-06-13T14:30:22Z",
    "price_recommender": "2026-06-13T14:30:22Z"
  }
}
```

**Notes**:
- In-flight requests to prediction endpoints are not interrupted during reload
- If a model fails to reload, its entry in `versions` is `null` and `reloaded` omits it
- Reload reads `{model_type}/latest.json` to determine which version to download (FR-023)

---

## Error Response Schema (all endpoints)

```json
{
  "error": "model_not_loaded | invalid_input | internal_error",
  "model_type": "match_score | ride_ranker | price_recommender | null",
  "message": "Human-readable description of the error"
}
```

HTTP status codes:
- `200` — success
- `422` — request body validation failure (Pydantic; standard FastAPI format)
- `503` — model not loaded for this endpoint
- `500` — unexpected internal error (generic message; details in service logs)
