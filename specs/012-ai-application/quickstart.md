# Quickstart & Validation Guide: AI Application (Phase 9)

**Branch**: `012-ai-application` | **Date**: 2026-07-01

This guide describes how to validate that Phase 9 is working end-to-end. It covers prerequisites, service startup, and the key validation scenarios that prove each spec requirement.

For API shapes, see [`contracts/api.md`](contracts/api.md). For data model details, see [`data-model.md`](data-model.md).

---

## Prerequisites

1. All Phase 1–8 services running (Docker Compose or local uvicorn + Next.js dev server).
2. `services/ai` running with all three models loaded:
   ```bash
   curl http://localhost:8001/health
   # Expected: {"status": "ok", "models_loaded": 3, ...}
   ```
3. At least one verified driver with a funded wallet (Phase 8) and one verified passenger exist in the database.
4. OSRM routing service is reachable (Phase 5 dependency).

---

## Validation Scenario 1 — AI-Ranked Passenger Search

**Tests**: FR-001, FR-004, FR-005, SC-001, SC-002

**Steps**:
1. Authenticate as a verified passenger.
2. `POST /api/v1/search/rides` with a Cairo origin/destination that has existing scheduled rides.
3. Inspect the response.

**Expected**:
- `ai_ranking_active: true`
- Each candidate has `match_score_pct` in range 0–100 (integer).
- Candidates are ordered by `match_score_pct` descending.
- No candidate with `match_score_pct < 20` appears unless fewer than 3 candidates were above threshold.

---

## Validation Scenario 2 — Match Score on Ride Detail

**Tests**: FR-004 (detail page), spec clarification Q3

**Steps**:
1. From Scenario 1, note the `ride_id` and `match_score_pct` of the top result.
2. `GET /api/v1/rides/{ride_id}/passenger-detail?origin_lat=…&origin_lng=…&destination_lat=…&destination_lng=…&departure_at=…` using the same search parameters.
3. Inspect the response.

**Expected**:
- `match_score_pct` in the response matches (or is within ±1 of) the score from Scenario 1.

---

## Validation Scenario 3 — System Fare on Ride Creation

**Tests**: FR-009, FR-011, FR-012, SC-004, SC-005

**Steps**:
1. Authenticate as a verified driver with sufficient wallet balance.
2. `POST /api/v1/rides` — request body must NOT include `price_per_seat`.
3. Inspect the response.
4. Attempt to modify the fare: `PATCH /api/v1/rides/{ride_id}` with `{"price_per_seat": "999.00"}`.

**Expected**:
- Creation response includes `price_per_seat` as a positive decimal string (e.g., `"47.50"`).
- Fare reflects the route distance and departure time (different routes produce different fares).
- PATCH attempt either returns `422` (field rejected) or silently ignores the field and returns the unchanged `price_per_seat`.

---

## Validation Scenario 4 — AI Service Fallback (Search)

**Tests**: FR-006, FR-007, FR-008, SC-003, NFR-003

**Steps**:
1. Stop `services/ai` (`docker stop ai-service` or kill the process).
2. `POST /api/v1/search/rides` with the same parameters as Scenario 1.
3. Time the response.

**Expected**:
- Response arrives within ≤1 second after the AI timeout triggers.
- `ai_ranking_active: false`
- `match_score_pct: null` for all candidates.
- Candidates are ordered by `compatibility.overlap_percentage` descending.
- No error field in the response; HTTP 200.

---

## Validation Scenario 5 — AI Service Fallback (Ride Creation)

**Tests**: FR-013, NFR-006

**Steps**:
1. Keep `services/ai` stopped.
2. `POST /api/v1/rides` as a verified driver.

**Expected**:
- Ride created successfully (HTTP 201).
- `price_per_seat` is set to the deterministic fallback fare.
- Fallback fare formula: `(distance_km / 15.0) × fuel_price_per_litre + safety_margin` (values from `pricing_config` table — default: `fuel_price_per_litre = 15.00`, `safety_margin = 5.00`).

---

## Validation Scenario 6 — Score Threshold + Minimum-3 Guarantee

**Tests**: FR-005a, acceptance scenarios 7–8

**Steps** (requires test data setup):
1. Create test rides such that — for a specific passenger search — 4 out of 5 candidates score below 20%.
2. Run the search.

**Expected**:
- Response contains 3 candidates: the 1 above threshold + the 2 highest-scoring suppressed candidates.
- All 3 appear with their `match_score_pct` values (including the below-threshold ones added back).

---

## Validation Scenario 7 — MatchScoreBadge UI

**Tests**: FR-004 (frontend), SC-002

**Steps**:
1. Run the main app (`pnpm --filter main dev`).
2. Log in as a verified passenger and run a ride search.
3. Inspect each ride card visually.

**Expected**:
- Each card shows `"XX% match"` badge in the correct colour:
  - ≥70% → green badge
  - 40–69% → amber badge
  - <40% → grey badge
- Tapping a card navigates to the detail page, which shows the same badge with the same score.

---

## Validation Scenario 8 — Driver Ride Creation UI

**Tests**: FR-009, FR-011 (UI enforcement)

**Steps**:
1. Log in as a verified driver.
2. Navigate to ride creation form.

**Expected**:
- No price/fare input field is visible.
- After submitting the form, the confirmation screen shows: `"Fare: XX.XX EGP per seat"` as a read-only display.
