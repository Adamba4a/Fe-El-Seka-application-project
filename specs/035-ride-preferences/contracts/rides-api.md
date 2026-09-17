# API Contract: Ride Preferences and Round Trips

## Profile

`PATCH /api/profiles/me`

Add optional `gender: "woman" | "man"` to the authenticated private-profile update contract. `GET /api/profiles/me` returns it; public-profile endpoints do not.

## One-off ride create

`POST /api/v1/rides`

Existing one-way payloads remain valid. Add:

```json
{
  "is_women_only": true,
  "journey_type": "round_trip",
  "return_departure_datetime": "2026-09-20T17:00:00Z",
  "return_total_seats": 3,
  "return_final_price_per_seat": 45
}
```

- `journey_type` defaults to `one_way`.
- Return fields are required only for `round_trip`; they are rejected for `one_way`.
- The response returns both `outbound_ride` and, when applicable, `return_ride`.
- Error `women_only_driver_required` (403): a non-woman driver attempts to enable women-only.
- Error `return_departure_invalid` (422): the return is not later than the outbound.

## Ride responses and discovery

Ride list/detail/search responses add `is_women_only`, `round_trip_group_id`, and `trip_leg`. They do not expose any user's gender.

## Booking

`POST /api/v1/bookings` remains unchanged. It can target either leg by its ordinary `ride_id`.

- Error `women_only_ride` (403): a passenger who is not a woman tries to book a women-only ride.
- This error occurs before a seat claim, payment calculation, wallet operation, or booking insert.

## Recurring definitions

`POST` and `PATCH /api/v1/rides/recurring` add:

```json
{
  "journey_type": "round_trip",
  "is_women_only": true,
  "return_departure_time": "17:00",
  "return_total_seats": 3,
  "return_price_per_seat": 45
}
```

The corresponding response returns these fields. Existing definitions default to an unrestricted one-way schedule.

## Recurring occurrence timing override

`PATCH /api/v1/rides/recurring/{definition_id}/occurrences/{date}`

```json
{
  "outbound_departure_datetime": "2026-09-22T09:00:00Z",
  "return_departure_datetime": "2026-09-22T18:00:00Z"
}
```

Only the owning driver can call it. It returns both updated rides. It fails atomically when the pair is absent, either leg is booked or inside its edit cutoff, the chronological order is invalid, or either leg conflicts with the driver's schedule.

