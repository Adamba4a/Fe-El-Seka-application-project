# API Contracts: Driver Fare Override (Capped)

Scope: changes to existing endpoints in `services/api/app/api/rides/router.py` and
`services/api/app/api/admin/rides_router.py`. No new endpoints.

## `POST /api/v1/rides` (create ride)

**Request body** (`CreateRideRequest`) — new optional field:

```jsonc
{
  "origin": { ... },
  "destination": { ... },
  "departure_datetime": "...",
  "total_seats": 3,
  "notes": "...",
  "final_price_per_seat": 60.0   // NEW, optional. Omit → defaults to the computed fair price (FR-007).
}
```

**Response body** — `RideResponse` gains one field:

```jsonc
{
  "ride": {
    "...": "...",
    "price_per_seat": "60.00",          // unchanged field, now explicitly the FINAL price
    "fair_price_per_seat": "50.00"      // NEW — system baseline, always present
  }
}
```

**New error case** (400, `RideServiceError` → existing `_service_error_response` shape):

```jsonc
{
  "error": "price_out_of_band",
  "message": "Price must be between 50.00 and 65.00 EGP per seat."
}
```

Triggered when `final_price_per_seat` is supplied and falls outside `[fair_price, fair_price × 1.30]`
(FR-005; boundary values inclusive, per User Story 2 acceptance scenario 3).

## `PATCH /api/v1/rides/{ride_id}` (edit ride)

**Request body** (`EditRideRequest`) — new optional field, same name/semantics as create:

```jsonc
{
  "total_seats": 4,
  "final_price_per_seat": 55.0   // NEW, optional
}
```

**Behavior change** (FR-008, §Research #4): if `total_seats` changes and the recomputed fair price moves
the existing final price outside the new band, the request MUST include an in-band
`final_price_per_seat` or the whole edit is rejected with `price_out_of_band` — no field of the edit is
partially applied (matches the existing transactional `edit_ride` behavior, which already applies all
`sets` in one `UPDATE`).

**Response body**: same shape as create's response — includes `fair_price_per_seat`.

## `GET /api/v1/rides` / `GET /api/v1/rides/{ride_id}` (driver's own rides)

No request changes. `RideResponse` (used by both) gains `fair_price_per_seat`, same as above — so the
driver app can show the band on any already-created ride's detail/edit view without a second call.

## `GET /api/admin/rides` / `GET /api/admin/rides/{ride_id}` (admin panel, FR-010)

`admin/rides_router.py` builds its own response dicts (not `RideResponse`). Both the list and detail
responses gain:

```jsonc
{
  "price_per_seat": "60.00",
  "fair_price_per_seat": "50.00",   // NEW
  "markup_egp": "10.00",            // NEW, derived: price_per_seat - fair_price_per_seat
  "markup_percentage": 20           // NEW, derived: round(markup_egp / fair_price_per_seat * 100)
}
```

Admin endpoints remain read-only for pricing — no new admin write capability is introduced.

## Passenger-facing endpoints (search, ride detail, booking) — unchanged

Per FR-009 and NFR-003: these continue to read and charge `price_per_seat` exactly as today. No new
fields, no new fair-price exposure to passengers — this is an explicit non-goal (spec Out-of-Scope:
"Passenger-side price negotiation, counter-offers, or bidding").
