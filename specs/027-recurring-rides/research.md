# Research: Recurring Rides

**Feature**: 027-recurring-rides | **Date**: 2026-08-31

No `NEEDS CLARIFICATION` markers remain in the Technical Context (resolved during spec/clarify). This document records the key implementation-approach decisions made while grounding the plan in the existing codebase.

## Decision 1: Generation mechanism — background loop vs. on-demand

**Decision**: A background async loop (`recurring_ride_generation_loop`), started via `asyncio.create_task(...)` in `main.py`'s startup/lifespan alongside the existing loops (`driver_reminder_loop`, `booking_expiry_loop`, `pricing_config_refresh_loop`, `notification_dispatcher_loop`), runs on a fixed interval and ensures every active recurring definition has generated instances covering the rolling forward window.

**Rationale**: Matches the established, already-proven pattern in this codebase for periodic server-side work. Avoids introducing a new job-scheduling dependency (e.g., Celery, cron) that Principle VI (modular, non-duplicative architecture) and the existing stack (no ORM, no task queue) would flag as unjustified complexity. Generation is not on the request path, so a periodic sweep (rather than generating lazily on search) keeps search/booking latency (NFR-002) unaffected.

**Alternatives considered**:
- *Generate lazily at search time* — rejected: would add latency to the hot search path and complicate idempotency (concurrent searches racing to generate the same instance).
- *External cron/task queue* — rejected: no existing infrastructure for it; would be a new deployable/operational surface for a single background sweep that the existing loop pattern already handles adequately.

## Decision 2: Rolling generation window

**Decision**: 2 weeks forward, refreshed each loop tick — i.e., the loop tops up generation so that, for every active/eligible definition, instances exist for each selected weekday through 14 days out, and does nothing for weekdays that already have an instance in that window.

**Rationale**: Confirmed in spec.md Assumptions. Long enough for passengers to plan a commute ahead of time; short enough to avoid generating rides far past a point where a driver's eligibility, pricing, or route might change, and to bound how many stale unbooked instances need hiding when eligibility lapses (FR-012).

**Alternatives considered**:
- *Generate indefinitely far ahead* — rejected: wastes storage/compute on instances that may never be searched, and increases the blast radius of an eligibility lapse or edit needing to touch many rows.
- *Generate only the single next occurrence per weekday* — rejected: gives passengers very little lead time to plan around, undercutting SC-001/SC-002 intent.

## Decision 3: Data model — extend `rides` vs. new instance table

**Decision**: Reuse the existing `public.rides` table for day instances (add a nullable `recurring_ride_definition_id UUID FK` column) rather than introducing a parallel ride/instance entity. A new `public.recurring_ride_definitions` table holds the definition (route, days, time, seats, active/ended status).

**Rationale**: Directly required by spec.md's Technical Considerations and Principle VI — a day instance must behave exactly like a one-off `Ride` for search, booking, pricing, and cancellation, so it needs to be the same row type. This lets every existing endpoint (`GET /rides`, `POST /rides/{id}/cancel`, booking flow, `ride_history_logs`) work unchanged on generated instances with zero special-casing.

**Alternatives considered**:
- *Separate `recurring_ride_instances` table joined to bookings* — rejected: would require duplicating or wrapping every existing ride/booking/cancellation code path (search, detail, cancel, edit) to understand two ride-shaped entities instead of one, directly violating Principle VI and inflating scope well past this feature's requirements.

## Decision 4: Route computation per instance

**Decision**: Each generated instance still computes/store its own `route_geometry`/`route_distance_km`/`route_duration_minutes` via OSRM at generation time, rather than copying the definition's route data verbatim across all instances.

**Rationale**: Required by Principle II and spec.md's Technical Considerations — route intelligence must not be skipped just because the route was validated once at definition-creation time. In practice the origin/destination are fixed per definition, so the OSRM call result is expected to be stable, but computing it per instance keeps the invariant "every `rides` row has been through routing" universally true with no special case for recurring-generated rows.

**Alternatives considered**:
- *Compute route once at definition creation, copy to every instance* — rejected: breaks the invariant that every `rides` row's route data came from an actual OSRM call at that row's creation, and would silently go stale if OSRM behavior/road network changes between generations.

## Decision 5: Local testing without OSRM

**Decision**: Continue the established project pattern (used for Spec 026) of validating end-to-end behavior via direct-service-layer pytest scripts against the real local Supabase DB, rather than live HTTP round-trips, since local dev has no OSRM instance and `POST /rides`-family flows 503 without it.

**Rationale**: Documented existing constraint (`project_osrm_not_configured_locally`), not something this feature can fix. Service-layer tests can stub/skip the OSRM call boundary the same way existing ride-creation tests already do.

**Alternatives considered**: None — this is a pre-existing, already-adopted project constraint being followed, not a new choice.
