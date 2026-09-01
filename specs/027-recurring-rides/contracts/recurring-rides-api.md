# API Contracts: Recurring Rides

**Feature**: 027-recurring-rides | **Date**: 2026-08-31

New router mounted at `services/api/app/api/rides/recurring_router.py`, prefixed under the existing `rides` domain (e.g. `/rides/recurring`). Existing endpoints (`GET /rides`, `GET /rides/{ride_id}`, `POST /rides/{ride_id}/cancel`, `PATCH /rides/{ride_id}`, booking endpoints) are unchanged — day instances flow through them exactly like one-off rides (FR-004), per Decision 3 in research.md.

## `POST /rides/recurring`

Create a recurring ride definition. Driver-only (existing driver-eligibility checks apply per FR-010).

**Request**:
```json
{
  "vehicle_id": "uuid",
  "origin_coordinates": { "lat": 0, "lng": 0 },
  "origin_address": "string",
  "destination_coordinates": { "lat": 0, "lng": 0 },
  "destination_address": "string",
  "departure_time": "HH:MM",
  "weekdays": [1, 3, 5],
  "total_seats": 3,
  "price_per_seat": 25.0,
  "notes": "string | null"
}
```

**Response `201`**: the created `RecurringRideDefinition` (id, status `active`, echoed fields, `created_at`).

**Errors**:
- `400` — `weekdays` empty (FR-002).
- `403` — driver ineligible (unverified vehicle/driver status), same eligibility error shape as `POST /rides` today (FR-010).

## `GET /rides/recurring`

List the authenticated driver's recurring definitions (active and ended).

**Response `200`**: array of `RecurringRideDefinition`, each including a count of upcoming generated instances.

## `GET /rides/recurring/{definition_id}`

Fetch one definition plus its generated instances (past, current, upcoming), so the driver's UI can show the grouping required by FR-009/Story 1 Scenario 3.

**Response `200`**:
```json
{
  "definition": { "...RecurringRideDefinition" },
  "instances": [ { "...existing Ride shape, each with recurring_ride_definition_id set" } ]
}
```

## `PATCH /rides/recurring/{definition_id}`

Edit route/departure_time/total_seats/price_per_seat/notes. Applies per FR-011: propagates to not-yet-generated and zero-booking/pre-cutoff generated instances; leaves booked instances' locked details untouched.

**Request**: partial `RecurringRideDefinition` fields (same shape as create, all optional).

**Response `200`**: updated `RecurringRideDefinition`, plus `updated_instance_count` (how many existing `rides` rows were propagated to, for driver-facing confirmation).

**Errors**: `403` if the definition is `ended`.

## `POST /rides/recurring/{definition_id}/end`

End the definition (FR-008). No request body. Idempotent — ending an already-ended definition returns `200` unchanged rather than an error.

**Response `200`**: updated `RecurringRideDefinition` with `status: "ended"`.

*Note*: single-day cancellation is intentionally NOT a new endpoint — it is the existing `POST /rides/{ride_id}/cancel` called directly on that instance's `ride_id` (FR-006), unchanged.

## Internal (non-HTTP): `recurring_ride_generation_loop()`

Not an API contract (no external caller) — documented here for completeness since it's the core new behavior. Runs on a fixed interval in `services/api/app/services/main.py` (or wherever background loops are started), calling `recurring_ride_service.generate_upcoming_instances()`:

1. Query all `active` definitions whose driver/vehicle are currently eligible.
2. For each, for each selected weekday, ensure a `rides` row exists for every occurrence within the rolling window (Decision 2) that doesn't already have one (unique constraint from data-model.md prevents duplicates as a backstop).
3. For newly-created rows: compute OSRM route data (Decision 4), set `total_seats`/`price_per_seat`/`notes` from the definition, set `recurring_ride_definition_id`, insert with `status: 'scheduled'`.
4. For definitions whose driver/vehicle just became ineligible: no explicit row mutation needed — visibility is computed at query time per FR-012 (see data-model.md State transitions), so the loop simply skips generating further instances for them until eligibility is restored.
