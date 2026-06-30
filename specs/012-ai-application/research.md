# Research: AI Application (Phase 9)

**Branch**: `012-ai-application` | **Date**: 2026-07-01

---

## 1. Database Schema — No Migration Required

**Decision**: No new database tables or columns are needed for Phase 9.

**Rationale**: The `rides` table (migration `20260617000001_ride_management.sql`, Phase 4) already contains `price_per_seat NUMERIC(10, 2) NOT NULL CHECK (price_per_seat > 0)`. This column IS the system fare — Phase 9 changes only HOW it is populated (AI model instead of driver input). AI match scores are ephemeral per the spec clarification and require no storage.

**Alternatives considered**: Adding a `fare_egp NUMERIC(12, 2)` column alongside `price_per_seat`. Rejected — redundant column, would require a migration and a data synchronisation step for existing rides. Using the existing column is strictly correct.

---

## 2. AI Service Integration Pattern — httpx Async Client

**Decision**: Use `httpx.AsyncClient` with a 1-second timeout, instantiated once per FastAPI app lifespan (not per request) and injected via FastAPI dependency.

**Rationale**:
- `httpx` is already the standard async HTTP client for FastAPI projects in Python 3.11.
- A shared client instance (connection pooling via lifespan) avoids per-request TCP handshake overhead, keeping the AI scoring step within the 500ms p95 budget.
- Wrapping the client in `AIServiceUnavailableError` on `httpx.TimeoutException` and `httpx.ConnectError` gives the search service and ride service a clean error surface for fallback logic.

**Client configuration**:
```python
client = httpx.AsyncClient(
    base_url=settings.AI_SERVICE_URL,  # e.g., "http://localhost:8001"
    timeout=httpx.Timeout(1.0),
    headers={"Content-Type": "application/json"},
)
```

**Alternatives considered**: Per-request `httpx.AsyncClient` context manager. Rejected — creates a new TCP connection per request, adds latency, and is the anti-pattern explicitly called out in httpx docs.

---

## 3. Cairo Zone Centroid Lookup

**Decision**: Hardcoded 13-district lookup table in `utils/zone_lookup.py`. Nearest-zone mapping uses minimum Euclidean distance to zone centroids.

**Rationale**: The AI models (Phase 2) were trained using zone centroid coordinates (lat/lng) as geographic features. Passing raw ride coordinates directly would produce feature values outside the training distribution, degrading model predictions. Mapping to the nearest zone centroid normalises inputs to the training-time encoding with no external dependencies.

**Zone centroid table** (sourced from Phase 2 spec + OpenStreetMap centroids):

| Zone | Lat | Lng |
|------|-----|-----|
| Downtown Cairo | 30.0444 | 31.2357 |
| Maadi | 30.0131 | 31.2089 |
| Zamalek | 30.0626 | 31.2197 |
| Heliopolis | 30.0876 | 31.3219 |
| Nasr City | 30.0561 | 31.3360 |
| New Cairo | 30.0271 | 31.4697 |
| 6th of October | 29.9285 | 30.9188 |
| Giza | 30.0131 | 31.2089 |
| Mohandessin | 30.0619 | 31.1997 |
| Dokki | 30.0380 | 31.2114 |
| Shubra | 30.1060 | 31.2436 |
| Ain Shams | 30.1180 | 31.3197 |
| Smart Village | 30.0723 | 30.9703 |

**Implementation** (`nearest_zone`):
```python
def nearest_zone(lat: float, lng: float) -> tuple[str, dict]:
    """Returns (zone_name, {"lat": ..., "lng": ...}) for the nearest Cairo zone."""
    return min(ZONES, key=lambda z: (z["lat"] - lat)**2 + (z["lng"] - lng)**2)
```

**Alternatives considered**: PostGIS spatial join to a zones table. Rejected — requires schema migration, adds a DB round-trip, and the result is equivalent for MVP purposes. Euclidean distance (vs Haversine) is sufficient at Cairo's scale (≤50 km radius, error < 0.1%).

---

## 4. System Fare Derivation from AI Price Range

**Decision**: System fare = `round((min_egp + max_egp) / 2, 2)` computed with `decimal.Decimal`; stored as `NUMERIC(10, 2)` in `price_per_seat`.

**Rationale**: The AI pricing model (`/predict/price-recommendation`) returns a range `[min_egp, max_egp]` where `min_egp ≈ point_estimate × 0.8` and `max_egp ≈ point_estimate × 1.2`. The midpoint equals the model's point estimate. Using the midpoint produces the model's best single-value fare prediction and is consistent with how the model was trained.

**Implementation**:
```python
from decimal import Decimal, ROUND_HALF_UP

def derive_fare(min_egp: float, max_egp: float) -> Decimal:
    mid = (Decimal(str(min_egp)) + Decimal(str(max_egp))) / 2
    return mid.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

**Validation**: If `fare <= 0`, reject and use the deterministic fallback. The AI service contract guarantees `min_egp ≥ 10.0`, so this case only occurs on malformed responses.

**Alternatives considered**: Always use `min_egp`. Rejected — systematically underprices the route by ~20%. Always use `max_egp`. Rejected — systematically overprices by ~20%.

---

## 5. Deterministic Fallback Fare Formula

**Decision**: Reuse the Phase 5 `pricing_config` table: `fare = (distance_km / 15.0) × fuel_price_per_litre + safety_margin`.

**Rationale**: The `pricing_config` table (migration `20260622000001_add_pricing_config.sql`) already holds `fuel_price_per_litre` (default: 15.00 EGP) and `safety_margin` (default: 5.00 EGP). Using the same formula and parameters ensures consistency between Phase 5 deterministic pricing and the Phase 9 fallback. Fuel efficiency of 15 km/litre is a standard baseline for Egyptian urban driving.

**Example**: 12 km route → `(12 / 15) × 15.00 + 5.00 = 12.00 + 5.00 = 17.00 EGP`.

**Implementation**: `ride_service.py` reads `pricing_config` using a standard SELECT (same connection as the create_ride transaction). No additional round-trip in the normal (AI available) path.

---

## 6. Search Pipeline — AI Scoring Integration Point

**Decision**: Insert AI scoring between Phase 5 candidate generation and Phase 6 response serialisation, within `search_service.py`.

**Rationale**: Phase 5 already computes compatibility features for each candidate (overlap_pct, pickup_walk_m, dropoff_walk_m, detour_km, etc.) and returns them in the search response. Phase 9 reuses these computed values as input to the AI feature vector — no additional route intelligence calls needed. The integration point is a single additional async call to `ai_client.score_candidates()` after candidate filtering.

**Feature vector mapping** (Phase 5 response field → AI service field):

| Phase 5 field | AI service field | Conversion |
|---|---|---|
| `overlap_percentage` | `estimated_overlap_ratio` | ÷ 100 |
| `pickup_walk_meters` | `estimated_pickup_detour_km` | ÷ 1000 |
| `dropoff_walk_meters` | `estimated_dropoff_distance_km` | ÷ 1000 |
| `per_seat_price` | (not sent) | Removed from Phase 9 |
| passenger `origin` | `origin_centroid` + `origin_zone` | `nearest_zone()` |
| passenger `destination` | `destination_centroid` + `destination_zone` | `nearest_zone()` |
| `desired_departure_at` | `departure_at` | Pass through |

**Filtering algorithm** (applied after ranking):
```
scored = [c for c in ranked if c.match_score_pct >= 20]
if len(scored) < 3:
    suppressed = sorted([c for c in ranked if c not in scored],
                        key=lambda c: c.match_score, reverse=True)
    scored += suppressed[:3 - len(scored)]
return scored
```

---

## 7. Match Score on Ride Detail Page

**Decision**: The ride detail endpoint (`GET /api/v1/rides/{ride_id}/passenger-detail`) already accepts `origin_lat`, `origin_lng`, `destination_lat`, `destination_lng` as query parameters. Phase 9 adds an optional `departure_at` query parameter and, when all four coordinate params are present, calls `ai_client.score_candidates()` for the single ride to produce its `match_score_pct`. If AI is unavailable or params are absent, `match_score_pct` is `null` in the response.

**Rationale**: Scores are ephemeral — re-computing for one ride on the detail page is an O(1) AI call, well within the 500ms budget. This avoids any client-side state passing (URL params or localStorage) while remaining consistent with the search result score.

**Alternatives considered**: Pass score via URL query param from search results. Rejected — breaks direct links, bookmarked rides, and push notification deep-links. Store score in Redis/cache. Rejected — adds infrastructure for a 1-call re-computation.

---

## 8. Fare Immutability Enforcement

**Decision**: Enforced at application layer only for MVP. No database trigger or generated column.

**Rationale**: The ride edit endpoint (`PATCH /api/v1/rides/{ride_id}`) already exists from Phase 4. Phase 9 simply ensures `price_per_seat` is not included in the editable fields list in the Pydantic `UpdateRideRequest` schema. The CREATE path computes the fare; the UPDATE path never touches it. A database-level trigger would provide defence-in-depth but adds migration complexity for MVP.

**Post-competition**: A `BEFORE UPDATE` trigger that raises an exception if `NEW.price_per_seat != OLD.price_per_seat` is the correct hardening step for Phase 12.
