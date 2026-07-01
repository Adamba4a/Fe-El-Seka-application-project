# Tasks: AI Application (Phase 9)

**Input**: Design documents from `specs/012-ai-application/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/api.md ✅ | contracts/frontend-pages.md ✅

**Tests**: Not included — no TDD requirement in spec.

**Organization**: Grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: US1 / US2 / US3 — maps to user stories from spec.md
- All file paths are relative to the repository root

---

## Phase 1: Setup

**Purpose**: Create new file stubs so downstream tasks have valid import targets from the start.

- [x] T001 Create empty stub files: `services/api/app/models/ai.py`, `services/api/app/utils/zone_lookup.py`, `services/api/app/services/ai_client.py`, `apps/main/src/components/search/MatchScoreBadge.tsx` — each file needs only a module docstring or empty export; no logic yet

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure consumed by all three user stories. No US work can begin until this phase is complete.

**⚠️ CRITICAL**: T005 (AI client) depends on T002, T003, T004. T002 and T003 are parallel. T004 is independent.

- [x] T002 [P] Implement all Pydantic AI schemas in `services/api/app/models/ai.py` — `ZoneCentroid`, `PassengerRequestFeatures`, `CandidateFeatures`, `ScoredCandidate`, `AIMatchScoreRequest`, `AIMatchScoreResponse`, `AIRankingRequest`, `AIRankingResponse`, `AIPriceRequest`, `AIPriceResponse` — exact field names and types from `data-model.md` §Python Pydantic Schemas

- [x] T003 [P] Implement Cairo zone centroid table and `nearest_zone(lat, lng)` in `services/api/app/utils/zone_lookup.py` — 13-district `CAIRO_ZONES` list with exact lat/lng values from `research.md` §3; `nearest_zone()` uses minimum Euclidean distance; returns `(zone_name: str, centroid: dict[str, float])`

- [x] T004 [P] Register shared `httpx.AsyncClient` lifespan in `services/api/app/main.py` — add to existing FastAPI lifespan context manager: instantiate `httpx.AsyncClient(base_url=settings.AI_SERVICE_URL, timeout=httpx.Timeout(1.0))` on startup, close on shutdown; expose via `app.state.ai_http_client`

- [x] T005 Implement `services/api/app/services/ai_client.py` with four async methods and `AIServiceUnavailableError` exception (depends on T002, T003, T004):
  - `score_candidates(passenger_req: PassengerRequestFeatures, candidates: list[CandidateFeatures]) -> list[ScoredCandidate]` — POST `/predict/match-score`; clamp scores to [0.0, 1.0]; convert to `match_score_pct = round(score * 100)`; raise `AIServiceUnavailableError` on timeout / connect error / HTTP 503
  - `rank_candidates(scored: list[ScoredCandidate]) -> list[str]` — POST `/predict/ride-ranking`; returns ordered `ride_id` list
  - `get_fare(req: AIPriceRequest) -> Decimal` — POST `/predict/price-recommendation`; derive fare as `Decimal((min_egp + max_egp) / 2).quantize(Decimal("0.01"), ROUND_HALF_UP)`; validate `> 0`; raise `AIServiceUnavailableError` on failure or invalid fare
  - `is_available() -> bool` — GET `/health`; returns `True` if status is `"ok"` or `"degraded"`; returns `False` on timeout or connect error

**Checkpoint**: Foundation complete — all three user stories can now proceed in parallel.

---

## Phase 3: User Story 1 — Passenger Receives AI-Ranked Ride Results (Priority: P1) 🎯 MVP

**Goal**: Every passenger search returns candidates scored 0–100% by AI, filtered to exclude <20% matches (with minimum-3 guarantee), ranked best-first, with the percentage badge visible on search result cards and the ride detail page.

**Independent Test**: `POST /api/v1/search/rides` returns candidates with `match_score_pct` (descending) and `ai_ranking_active: true`. The badge renders in the correct colour on ride cards and on the detail page.

- [x] T006 [P] [US1] Extend `RideCandidateResponse` and `SearchResponse` Pydantic response schemas in `services/api/app/api/search/router.py` — add `match_score_pct: int | None` to `RideCandidateResponse`; add `ai_ranking_active: bool` to `SearchResponse`; ensure existing fields are unchanged

- [x] T007 [US1] Implement AI scoring pipeline in `services/api/app/services/search_service.py` (depends on T005, T006):
  1. After Phase 5 candidate generation, build `CandidateFeatures` list — unit conversions: `overlap_pct / 100 → estimated_overlap_ratio`, `pickup_walk_m / 1000 → estimated_pickup_detour_km`, `dropoff_walk_m / 1000 → estimated_dropoff_distance_km`; zone lookup via `nearest_zone()` for both passenger and each driver's origin/destination
  2. Call `ai_client.score_candidates()` → receive `list[ScoredCandidate]` with clamped scores and `match_score_pct`
  3. Call `ai_client.rank_candidates()` to get final `ride_id` ordering
  4. Apply 20% threshold filter: exclude candidates where `match_score_pct < 20`; if remaining count < 3, append highest-scoring suppressed candidates until count = 3 or pool exhausted
  5. On `AIServiceUnavailableError` OR when all scores are identical: set `ai_ranking_active = False`, sort all candidates by `overlap_pct` descending, set `match_score_pct = None` for all

- [x] T008 [US1] Wire AI scoring into the `POST /api/v1/search/rides` endpoint handler in `services/api/app/api/search/router.py` — call updated `search_service` pipeline; populate `match_score_pct` per candidate and `ai_ranking_active` on the response (depends on T007)

- [x] T009 [P] [US1] Extend TypeScript types in `apps/main/src/lib/api/search.ts` — add `match_score_pct: number | null` to `RideCandidate`; add `ai_ranking_active: boolean` to `RideSearchResponse`; update `RidePassengerDetail` to include `match_score_pct: number | null` (used by detail page)

- [x] T010 [P] [US1] Implement `MatchScoreBadge` component in `apps/main/src/components/search/MatchScoreBadge.tsx` — props: `score_pct: number | null`; `null` renders nothing; display text: `"{score_pct}% match"`; colour coding: `score_pct >= 70` → `bg-green-100 text-green-800`, `score_pct >= 40` → `bg-amber-100 text-amber-800`, `score_pct < 40` → `bg-gray-100 text-gray-600`; pill shape consistent with existing `RideStatusBadge`

- [x] T011 [US1] Add `MatchScoreBadge` to each ride card in `apps/main/src/app/(passenger)/search/results/page.tsx` — import `MatchScoreBadge`; pass `candidate.match_score_pct` as `score_pct`; place below driver name / departure row, above price and seats row (depends on T009, T010)

- [x] T012 [US1] Extend `GET /api/v1/rides/{ride_id}/passenger-detail` in `services/api/app/api/rides/router.py` — add optional `departure_at: datetime | None` query parameter; when `departure_at` is present alongside the existing coordinate params, call `ai_client.score_candidates()` for this single ride; add `match_score_pct: int | None` to the response body; on `AIServiceUnavailableError` or missing `departure_at`: return `match_score_pct: null` (depends on T005)

- [x] T013 [US1] Add `MatchScoreBadge` to ride detail page in `apps/main/src/app/(passenger)/rides/[id]/page.tsx` — pass `departure_at` from search context (URL param or router state) to the detail API call; render `MatchScoreBadge` with `match_score_pct` from `RidePassengerDetail` response in the ride header section (depends on T010, T012)

**Checkpoint**: User Story 1 is independently testable — run quickstart.md Scenarios 1 and 2 to verify.

---

## Phase 4: User Story 2 — Fare Assigned by System at Ride Creation (Priority: P2)

**Goal**: Driver ride creation no longer accepts a price input. The system computes a fare via the AI pricing model (or deterministic fallback) and returns it in the creation response. The driver sees the fare on the confirmation screen. The fare cannot be changed after creation.

**Independent Test**: `POST /api/v1/rides` without `price_per_seat` returns a system-assigned fare. A PATCH attempt to change the fare is rejected. The driver creation form has no price field; the confirmation screen shows the fare read-only.

- [x] T014 [P] [US2] Remove `price_per_seat` from `CreateRideRequest` Pydantic schema in `services/api/app/api/rides/router.py`; confirm `UpdateRideRequest` (PATCH body) also has no `price_per_seat` field; add `price_per_seat: str` (read-only) to `CreateRideResponse`

- [x] T015 [P] [US2] Implement `_compute_ai_fare()` and `_compute_fallback_fare()` helpers in `services/api/app/services/ride_service.py` (depends on T005):
  - `_compute_ai_fare(req: AIPriceRequest) -> Decimal` — call `ai_client.get_fare()`; returns midpoint fare; propagates `AIServiceUnavailableError`
  - `_compute_fallback_fare(distance_km: float, pricing_config: dict) -> Decimal` — formula: `Decimal(distance_km / 15.0) * Decimal(str(pricing_config["fuel_price_per_litre"])) + Decimal(str(pricing_config["safety_margin"]))`; quantize to `"0.01"`; read `pricing_config` via a single `SELECT * FROM pricing_config LIMIT 1`

- [x] T016 [US2] Extend `create_ride()` in `services/api/app/services/ride_service.py` (depends on T014, T015):
  1. After OSRM route computation (which gives `estimated_distance_km`), call `nearest_zone()` on driver origin and destination coordinates to get zone names and centroids
  2. Build `AIPriceRequest` and call `_compute_ai_fare()`
  3. On `AIServiceUnavailableError` or fare ≤ 0: call `_compute_fallback_fare()`
  4. Assign computed fare to `price_per_seat` in the ride INSERT statement — `price_per_seat` is never taken from the request body in this function

- [x] T017 [P] [US2] Update TypeScript types in `apps/main/src/lib/api/rides.ts` — remove `price_per_seat` from `CreateRideRequest` interface; add `price_per_seat: string` to `CreateRideResponse` interface

- [x] T018 [US2] Update driver ride creation page in `apps/main/src/app/(driver)/rides/create/page.tsx` (depends on T017):
  - Remove the price-per-seat `<input>` (and its label, state variable, and validation) from the form
  - On successful `POST /api/v1/rides`, display `"Fare: {price_per_seat} EGP per seat"` as a read-only row on the success/confirmation screen using existing confirmation screen layout

**Checkpoint**: User Story 2 is independently testable — run quickstart.md Scenarios 3 and 5 to verify.

---

## Phase 5: User Story 3 — Graceful Degradation When AI Is Unavailable (Priority: P3)

**Goal**: All NFR-005 logging is in place. Fallback paths are verified to be stateless (automatic recovery). No user ever sees an error due to AI service downtime.

**Independent Test**: Stop `services/ai`. Both `POST /search/rides` (within 1s, `ai_ranking_active: false`) and `POST /rides` (deterministic fare, HTTP 201) succeed. Restart AI service; next requests use AI again automatically.

- [ ] T019 [P] [US3] Add structured fallback log to `services/api/app/services/search_service.py` — when AI fallback activates (either `AIServiceUnavailableError` or all-identical scores), emit a structured log entry: `{"event": "ai_search_fallback", "reason": "<exception class or 'identical_scores'>", "candidate_count": N, "fallback": "overlap_pct_desc"}`

- [ ] T020 [P] [US3] Add structured fallback log to `services/api/app/services/ride_service.py` — when fare fallback activates, emit: `{"event": "ai_fare_fallback", "reason": "<exception class or 'invalid_fare'>", "fallback_fare_egp": "<value>", "formula": "distance_km/15*fuel+safety"}`

- [ ] T021 [P] [US3] Add per-call request/response log to `services/api/app/services/ai_client.py` — after each `score_candidates()`, `rank_candidates()`, and `get_fare()` call (success or failure), emit: `{"event": "ai_prediction_call", "endpoint": "/predict/...", "input_shape": N, "model_version": "<version or null>", "latency_ms": N, "fallback_triggered": bool}`

- [ ] T022 [US3] Verify stateless recovery in `services/api/app/services/ai_client.py` — confirm that `httpx.AsyncClient` shared via `app.state` requires no manual reconnect logic after AI service restarts; add a one-line comment at the client initialisation site: `# Stateless: auto-reconnects on next request after AI service restart — no manual reset needed`

**Checkpoint**: All three user stories fully functional with observability in place — run quickstart.md Scenarios 4 and 5 to verify fallback end-to-end.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, type safety check, and visual verification.

- [ ] T023 [P] Run `pnpm --filter main build` and confirm zero TypeScript errors across all new/modified files: `search.ts`, `rides.ts`, `MatchScoreBadge.tsx`, `search/results/page.tsx`, `rides/[id]/page.tsx`, `rides/create/page.tsx`

- [ ] T024 [P] Run quickstart.md Scenario 1 — `POST /api/v1/search/rides` returns `ai_ranking_active: true` and `match_score_pct` values in descending order on each candidate

- [ ] T025 [P] Run quickstart.md Scenario 2 — `GET /api/v1/rides/{ride_id}/passenger-detail?…&departure_at=…` returns `match_score_pct` equal to (or within ±1 of) the score shown on the search result card

- [ ] T026 [P] Run quickstart.md Scenario 3 — `POST /api/v1/rides` (no `price_per_seat` in body) returns a positive `price_per_seat`; confirm `PATCH /api/v1/rides/{id}` with `price_per_seat` has no effect on the stored fare

- [ ] T027 [P] Run quickstart.md Scenarios 4 & 5 — with AI service stopped: search returns valid results within 1s (`ai_ranking_active: false`, `match_score_pct: null`); ride creation returns HTTP 201 with a deterministic fare

- [ ] T028 [P] Run quickstart.md Scenario 7 — in browser, verify `MatchScoreBadge` renders green for a high-score ride (≥70%), amber for a mid-score ride (40–69%), and grey for a low-score ride (<40%); verify badge appears on both the search list card and the detail page

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    └─► Phase 2 (Foundational) — T002, T003, T004 in parallel → T005
            ├─► Phase 3 (US1) — tasks proceed after T005
            ├─► Phase 4 (US2) — tasks proceed after T005
            └─► Phase 5 (US3) — logging/verification tasks after US1+US2 complete
                    └─► Phase 6 (Polish) — all validation after all stories done
```

### User Story Dependencies

| Story | Depends on | Notes |
|-------|-----------|-------|
| US1 (P1) | Phase 2 complete (T005) | No dependency on US2 or US3 |
| US2 (P2) | Phase 2 complete (T005) | No dependency on US1 or US3 |
| US3 (P3) | US1 + US2 complete | Adds logging; verifies combined fallback behaviour |

### Within Each User Story

- Models/schemas before services (T006 before T007, T014 before T016)
- Backend before frontend type extensions (T009 after T006, T017 after T014)
- Components before page integration (T010 before T011/T013, T017 before T018)

### Parallel Opportunities

**Phase 2**: T002, T003, T004 all parallel → then T005

**Phase 3 (US1)**:
```
T006 ──┐
T009 ──┼──► T011 ──► T008
T010 ──┘
T012 ──────────────► T013
```

**Phase 4 (US2)**:
```
T014 ──┐
T015 ──┼──► T016
T017 ──────► T018
```

**Phase 5 (US3)**: T019, T020, T021 all parallel → T022

**Phase 6**: T023–T028 all parallel

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) → Phase 2 (Foundational)
2. Complete Phase 3 (US1) — backend scoring + frontend badge
3. **Validate**: quickstart.md Scenarios 1 & 2 pass
4. Demo AI-ranked search with visible match percentages ✅

### Incremental Delivery

1. Phase 1 + 2 → AI client ready
2. Phase 3 (US1) → AI-ranked search (**demo milestone**)
3. Phase 4 (US2) → System-assigned fares
4. Phase 5 (US3) → Logging + fallback hardening
5. Phase 6 → Final validation

### Parallel Team Strategy

After Phase 2 completes:
- **Developer A**: Phase 3 backend (T006–T008, T012)
- **Developer B**: Phase 3 frontend (T009–T011, T013)
- **Developer C**: Phase 4 (T014–T018)

---

## Notes

- `[P]` = different files, no shared in-progress dependencies — safe to run simultaneously
- Each user story has an independent test in the quickstart.md validation guide
- All Decimal arithmetic: use `decimal.Decimal` throughout — never `float` for fare values
- Feature vector field names in `services/api/app/models/ai.py` are a **stability contract** with the Phase 2 AI models — do not rename without a model retrain
- The `price_per_seat` column on `rides` uses `NUMERIC(10, 2)` (Phase 4 migration) — this is the system fare column; no migration needed
