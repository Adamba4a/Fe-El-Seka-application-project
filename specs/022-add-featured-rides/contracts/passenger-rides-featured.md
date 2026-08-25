# Contract: Passenger Featured Rides Read

Extends the existing public rides API (`services/api/app/api/rides/router.py`). Must be declared **before** the `/{ride_id}` route (same reason `/pending-bookings-count` is declared first in this router — otherwise FastAPI would match `/featured` as a `ride_id` path param).

## `GET /api/v1/rides/featured`

Returns the passenger-visible Featured Rides Listing (see data-model.md), computed fresh on every call — no caching, no polling contract implied (per Clarifications 2026-08-25: fetch-on-load only, client decides when to call this).

**Auth**: `Depends(get_current_user)` — same gating as other passenger-facing reads in this router (e.g. `/{ride_id}/passenger-detail`), satisfying FR-014 (no new/different access control from today's search page).

**Query params**: none in this iteration (platform-wide, per FR-007's resolved scope — no location/city filter param).

**Success — 200**:
```json
{
  "rides": [
    {
      "ride_id": "uuid",
      "origin_address": "string",
      "destination_address": "string",
      "departure_datetime": "2026-08-26T07:30:00Z",
      "price_per_seat": "120.00",
      "available_seats": 3
    }
  ]
}
```

Ordering: `departure_datetime ASC` (soonest first, per spec Assumptions).

An empty `rides: []` array is a valid, expected response (FR-011's empty state is a frontend concern — the backend does not distinguish "no featured rides" from any other empty-result case).

**Errors**: `401 unauthorized` if the caller is not authenticated (standard `get_current_user` behavior, no new error case introduced).

**Non-goals** (explicitly, per FR-013 and research.md §4): this endpoint does not call, wrap, or otherwise interact with `services/api/app/api/search/router.py`'s AI ranking/matching logic. It is a plain deterministic filter over `rides`, structurally isolated from the ranking service.
