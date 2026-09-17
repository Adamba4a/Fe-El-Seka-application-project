# Research: Ride Preferences and Round Trips

## Decision 1 — Represent a round trip as two linked normal rides

**Decision**: A round-trip submission creates an outbound `rides` row and a return `rides` row in one database transaction. Both share a generated `round_trip_group_id`; their `trip_leg` values are `outbound` and `return`.

**Rationale**: The booking, seat-reservation, cancellation, lifecycle, wallet, and notification workflows already operate on one `rides` row. Two normal rows make both legs independently bookable without duplicating or branching those mature flows.

**Alternatives rejected**:

- One ride with a nested return booking: would require a second seat counter, price, status, and cancellation state inside the booking domain.
- One booking that reserves both legs: conflicts with the clarified requirement for independent leg bookings.

## Decision 2 — Protect women-only rules at the transaction boundary

**Decision**: Store a nullable private `gender` on `profiles` for backward compatibility. Add `is_women_only` to `rides`. At ride create/edit time, the API verifies the driver is a woman before enabling the flag. At the beginning of `booking_service.create_booking`, inside its existing transaction and before claiming seats or calculating money, it verifies the passenger is a woman when the ride is women-only.

**Rationale**: Client-side disabling is helpful UX but cannot protect against direct API calls or stale UI. Performing the check before every mutation keeps an ineligible attempt side-effect free.

## Decision 3 — Reverse the route for the return leg

**Decision**: The return row uses the outbound destination as origin and outbound origin as destination, and obtains its own route/fare calculation through the existing route/pricing services.

**Rationale**: A reverse route may differ in duration, geometry, and calculated fair price. It also lets the driver select a separate return price and seat count as required.

## Decision 4 — Round-trip integrity on individual edits

**Decision**: The existing per-ride edit workflow remains the way to edit one eligible leg. When the row is in a round-trip group, the service locks its sibling and rejects a change that would put the return at or before the outbound departure. Journey type and pairing cannot be changed after creation.

**Rationale**: Legs must remain independently manageable, but the pair still represents a chronological journey.

## Decision 5 — Recurring round trips generate linked pairs per date

**Decision**: Extend a recurring definition with `journey_type`, women-only preference, outbound/return times, and separate per-leg seats/prices. For each selected date, the generator creates both legs under a new per-occurrence `round_trip_group_id`; the existing one-instance-per-date unique index is replaced with a unique `(definition_id, UTC date, trip_leg)` index.

**Rationale**: It maintains the existing rolling generation model while avoiding a duplicate generator or separate recurring booking path.

## Decision 6 — Use a dedicated atomic recurring-occurrence override

**Decision**: Add a driver endpoint that accepts a definition ID, occurrence date, outbound departure, and return departure. It locks both generated legs, applies the existing edit cutoff/confirmed-booking protection to both, checks pair chronology and driver-time conflicts, then updates both or neither.

**Rationale**: Calling two ordinary PATCH endpoints could leave one leg updated when the other fails. A single operation gives the driver the requested date-specific schedule adjustment safely.

