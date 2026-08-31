# Quickstart: Validating Recurring Rides

**Feature**: 027-recurring-rides | **Date**: 2026-08-31

Local dev has no OSRM instance (`project_osrm_not_configured_locally`), so validation here goes through the service layer directly against the real local Supabase DB, consistent with how Spec 026 (Sponsored Groups) was verified — not through live HTTP requests to `POST /rides`-family endpoints, which 503 locally without OSRM.

## Prerequisites

- Local Supabase stack running (`supabase start`), migrations applied including `20260901000001_recurring_ride_definitions.sql` (see data-model.md).
- A verified test driver + vehicle already seeded (reuse existing seed/fixture data used by prior feature verification, e.g. Spec 026/024's fixtures).
- `services/api` virtualenv active, pytest installed.

## Scenario 1 — Definition creates generated instances (Story 1)

1. Run `recurring_ride_service.create_definition(driver_id, vehicle_id, weekdays=[1,3], ...)` directly (bypassing the HTTP router, same as existing service-layer test pattern).
2. Run `recurring_ride_service.generate_upcoming_instances()` once (simulating one loop tick).
3. Assert: a `rides` row exists for the next occurrence of each of Monday and Wednesday within the 2-week window, each with `recurring_ride_definition_id` set and route data populated (stub the OSRM call boundary the same way existing ride-creation tests do).
4. Re-run `generate_upcoming_instances()` a second time; assert no duplicate rows were created (idempotency, backed by the unique constraint in data-model.md).

**Expected outcome**: matches Acceptance Scenario 1 of User Story 1.

## Scenario 2 — Passenger books a specific day instance (Story 2)

1. Using one of the generated instances from Scenario 1, call the existing `booking_service` booking flow exactly as for a one-off ride.
2. Assert booking succeeds, seat counts update on that instance only, and the sibling instance (the other weekday) is untouched.

**Expected outcome**: matches Acceptance Scenario 3 of User Story 2 (bookings on separate day instances are independent).

## Scenario 3 — Single-day cancellation leaves the series intact (Story 3)

1. Call the existing `ride_service.cancel_ride(ride_id=<one instance's id>, ...)` on one generated instance that has a confirmed booking.
2. Assert: existing cancellation consequences apply (passenger notified, refund/reversal per current rules) — no new code path.
3. Re-run `generate_upcoming_instances()`; assert the next occurrence of that same weekday is still generated (FR-007 — cancelling one instance doesn't remove the weekday from the definition).
4. Call `recurring_ride_service.end_definition(definition_id)`; assert `status` becomes `ended`, no future instances generate afterward, and all previously-generated instances (including the cancelled one and any other untouched ones) are unaffected (FR-008).

**Expected outcome**: matches Acceptance Scenarios 1-3 of User Story 3.

## Scenario 4 — Edit propagation and eligibility lapse (Edge Cases / FR-011 / FR-012)

1. Edit a definition's `price_per_seat`; assert not-yet-generated instances and zero-booking generated instances pick up the new price on the next generation tick / immediately (per FR-011), while an instance with a confirmed booking keeps its locked price.
2. Mark the test driver/vehicle ineligible (e.g., flip verification status in the fixture); assert a zero-booking generated instance becomes excluded from search results, while a booked instance remains visible/unaffected (FR-012).
3. Restore eligibility; assert the previously-hidden instance becomes visible again and generation resumes on the next tick.

**Expected outcome**: matches the Edge Cases section of spec.md and FR-011/FR-012.
