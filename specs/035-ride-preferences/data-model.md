# Data Model: Ride Preferences and Round Trips

## `profiles`

| Column | Type | Rules |
|---|---|---|
| `gender` | `profile_gender` nullable | Values: `woman`, `man`. Nullable only for pre-existing accounts; private and never included in public-profile responses. |

New onboarding requires a value. A legacy `NULL` profile is ineligible to post or book a women-only ride until it supplies one.

## `rides`

| Column | Type | Rules |
|---|---|---|
| `is_women_only` | `boolean NOT NULL DEFAULT false` | Only a woman driver may set it true. |
| `round_trip_group_id` | `uuid` nullable | Shared by the outbound and return rows of one round trip; null for one-way rides. |
| `trip_leg` | `ride_trip_leg NOT NULL DEFAULT 'one_way'` | `one_way`, `outbound`, or `return`. |

Constraints and indexes:

- A check ties `trip_leg = 'one_way'` to a null group ID and `outbound`/`return` to a non-null group ID.
- A unique partial index on `(round_trip_group_id, trip_leg)` prevents duplicate legs.
- A paired create transaction stores an `outbound` and `return` row with one shared group ID.

Existing rows receive `false`, `NULL`, and `one_way`, respectively.

## `recurring_ride_definitions`

| Column | Type | Rules |
|---|---|---|
| `journey_type` | `recurring_journey_type` | `one_way` or `round_trip`, default `one_way`. |
| `is_women_only` | `boolean NOT NULL DEFAULT false` | Same driver eligibility rule as one-off rides. |
| `return_departure_time` | `time` nullable | Required only for a round trip and later than the outbound time within the same occurrence date. |
| `return_total_seats` | `smallint` nullable | Required only for a round trip; validated against vehicle capacity. |
| `return_price_per_seat` | `numeric(10,2)` nullable | Required only for a round trip and positive. |

The existing outbound `departure_time`, `total_seats`, and `price_per_seat` fields remain the outbound schedule. Constraints enforce that all return fields are present only for round trips.

## No new booking entity

`bookings.ride_id` continues to reference exactly one ride row. It therefore already provides independent bookings, prices, seat counters, cancellations, payment, and lifecycle for each round-trip leg.

## Recurring occurrence identity

The existing unique index `(recurring_ride_definition_id, utc_date(departure_datetime))` must be replaced with `(recurring_ride_definition_id, utc_date(departure_datetime), trip_leg)` so a round-trip definition can generate exactly one outbound and one return row for a selected date.

