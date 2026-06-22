# Feature Specification: Route Intelligence

**Feature Branch**: `008-route-intelligence`

**Created**: 2026-06-21

**Status**: Draft

**Input**: Phase 5 — Route Intelligence: OSRM + PostGIS deterministic engine, route overlap and proximity analysis, premium pickup/dropoff requests, candidate ride generation, and fuel-cost-based pricing.

## Clarifications

### Session 2026-06-22

- Q: How wide is the route "corridor" used to calculate overlap percentage between a driver's route and a passenger's journey? → A: Configurable buffer radius with a 150m default; the buffer width is an admin-tunable system parameter, same governance as walk/detour thresholds.
- Q: Should CompatibilityResult data be persisted in the database or computed fresh per request? → A: Always computed fresh per request — transient response object only; no DB persistence required at MVP scale.
- Q: How does an admin update fuel_price_per_litre and safety_margin? → A: Admin edits a pricing config row directly via the Supabase dashboard — no dedicated admin UI screen for MVP.
- Q: How are the route intelligence API endpoints authenticated? → A: User-facing endpoints (candidate generation, fare calculation) require a valid Supabase Auth JWT; Phase 9 AI service endpoints use a server-to-server shared secret header.
- Q: What observability signals are required for the route intelligence engine? → A: Structured logs + latency metrics — every request logs inputs, outputs, duration, and errors; per-endpoint request count and p95 latency are exported to a monitoring sink.

---

## Business Objective *(mandatory)*

Build the deterministic transportation intelligence layer that enables Fe El Seka to match passengers and drivers based on actual route compatibility, not geographic proximity alone. This phase introduces four tightly coupled capabilities: route path calculation (actual road distances and travel times), route overlap and compatibility analysis (how well a driver's journey covers a passenger's journey, including premium door-to-door options), candidate ride generation (surfacing only rides that genuinely fit a passenger's trip), and fuel-cost-based fare calculation (replacing the temporary manual pricing from Phase 4 with a fixed, non-negotiable formula tied to actual trip distance and Egyptian petrol prices).

The output of this phase is the data foundation that Phase 6 (Passenger Experience) uses to show passengers meaningful search results, and that Phase 9 (AI Application) uses to score and rank those results.

**Constitutional Domain**: Route Matching / Pricing

**Affected Applications**: Shared backend service — consumed by the Main App (passenger ride search, driver price display) and by the AI service (Phase 9) for match-scoring feature inputs.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Route Path Calculation (Priority: P1)

Whenever the platform needs to understand a trip — a driver publishing a ride, a passenger describing their journey, or the system comparing two routes — it calculates the actual road-network path between two points: the distance in kilometers, the expected travel time in minutes, and the encoded route geometry for map display.

**Why this priority**: All other capabilities in this phase depend on road-network route data. Without accurate path calculations, overlap analysis, detour estimates, and fuel-cost pricing cannot function. This is the foundation every other story builds on.

**Independent Test**: Submit two geographic points in Cairo (e.g., Maadi to Dokki) to the route calculation endpoint and verify the response includes road-network distance in km, travel time in minutes, and an encoded route path. Repeat with two near-identical coordinates and verify the system returns a near-zero distance without error. Submit two points with no traversable road connection and verify the response is flagged "unroutable" with no straight-line fallback.

**Acceptance Scenarios**:

1. **Given** two distinct geographic points within the service area, **When** the system calculates the route between them, **Then** it returns the road-network distance in kilometers, travel time in minutes, and an encoded route geometry suitable for map display.
2. **Given** two identical or nearly-identical coordinates (within 10 meters of each other), **When** the system calculates the route, **Then** it returns a near-zero distance and duration without error.
3. **Given** two points with no traversable road-network connection between them, **When** the system calculates the route, **Then** it returns a clearly flagged "unroutable" result rather than falling back to a straight-line estimate.
4. **Given** any calculated route result, **When** the distance is stored or compared, **Then** it is expressed in kilometers using the road-network path, never in straight-line (Euclidean) distance or angular degrees.

---

### User Story 2 — Route Overlap & Compatibility Assessment (Priority: P2)

A driver is heading from New Cairo to Tahrir Square. A passenger wants to travel from near Nasr City to near Downtown Cairo. The platform assesses how compatible these two journeys are: how much of the passenger's route the driver already covers, how far the passenger would walk to reach a boarding point on the driver's route, how far the passenger would walk from the driver's dropoff to their final destination, and how many extra kilometers the driver would travel to accommodate the passenger.

Beyond the standard model — where the passenger walks to a nearby point on the driver's route — a passenger may optionally request a **premium pickup** (the driver deviates from their route to collect the passenger at their exact origin) or a **premium dropoff** (the driver continues past their route to deliver the passenger to their exact destination). Both options incur an extra detour fee calculated from the additional distance. The driver may accept or decline any premium request before the booking is confirmed.

**Why this priority**: Without compatibility assessment, candidate generation (Story 3) cannot distinguish between a ride that genuinely fits a passenger and one that merely happens to be in the same city. Route overlap analysis is the core intelligence that makes Fe El Seka a route-sharing platform rather than a proximity-matching app (Constitution Principle II).

**Independent Test**: Feed a driver route and a passenger route with a pre-calculated and documented overlap into the compatibility engine. Verify the returned overlap percentage, pickup walk distance, dropoff walk distance, and driver detour all match expected values. Then test with a route pair with minimal overlap and verify it is flagged incompatible. Finally, test a passenger whose origin exceeds the standard walk threshold but is within the premium detour limit — verify `premium_pickup_available` is true with a calculated fee.

**Acceptance Scenarios**:

1. **Given** a driver's planned route and a passenger's requested origin and destination, **When** the system assesses compatibility, **Then** it returns: (a) overlap percentage — the proportion of the passenger's journey covered by the driver's route; (b) pickup walk distance — walking distance from the passenger's origin to the nearest feasible boarding point on the driver's route; (c) dropoff walk distance — walking distance from the driver's route to the passenger's destination; (d) driver detour — the additional road-network distance and time the driver incurs to serve the passenger.
2. **Given** two routes that share no geographic corridor, **When** the system assesses compatibility, **Then** it returns a 0% or near-0% overlap and the result is flagged as incompatible.
3. **Given** a passenger whose origin is farther from the driver's route than the maximum allowed walk distance, **When** the system assesses standard compatibility, **Then** the result is flagged as incompatible — unless the origin falls within the configured premium detour limit, in which case `premium_pickup_available` is set to true (see scenario 6).
4. **Given** a driver detour that exceeds the maximum allowed standard detour threshold, **When** the system assesses compatibility, **Then** the result is flagged incompatible due to detour exceeding the threshold, even if route overlap is high.
5. **Given** any compatibility result, **When** it is returned to the caller, **Then** distances are in meters, times are in minutes, and overlap is a value between 0 and 100.
6. **Given** a passenger whose origin exceeds the standard walk threshold but is within the configured premium pickup detour limit, **When** compatibility is assessed, **Then** the result includes `premium_pickup_available = true` and a calculated premium pickup fee in EGP, rather than a hard incompatible result.
7. **Given** a passenger whose destination exceeds the standard walk threshold but is within the configured premium dropoff detour limit, **When** compatibility is assessed, **Then** the result includes `premium_dropoff_available = true` and a calculated premium dropoff fee in EGP.
8. **Given** a compatibility result where a premium option is available, **When** a passenger selects it at booking time (Phase 6), **Then** the driver is notified with the detour distance and extra fee itemized, and must explicitly accept or decline before the booking is confirmed.
9. **Given** a driver who declines a premium pickup request, **When** the decline is recorded, **Then** if the passenger's origin is also within the standard walk threshold, the booking falls back to the standard route-based boarding point; if the origin also exceeds the walk threshold, the booking is rejected.

---

### User Story 3 — Compatible Ride Candidate Generation (Priority: P3)

A passenger wants to travel from Heliopolis to Zamalek at 8:00 AM on a Tuesday. The platform searches the pool of scheduled rides and returns a shortlist of rides whose drivers depart at a compatible time, whose routes cover the passenger's journey (either as standard matches or as premium-eligible options), and who still have available seats — each candidate annotated with its compatibility metrics and any applicable premium options and fees.

**Why this priority**: This is the first end-to-end capability a passenger experiences in Phase 6. Without candidate generation, passengers cannot find rides and the entire demand side of the platform is blocked.

**Independent Test**: Load 20 test rides into the system — 4 standard-compatible, 2 premium-eligible, and 14 that should not appear (wrong time, no overlap, full, wrong direction, beyond premium limit). Submit the passenger request and verify exactly 6 rides are returned: 4 standard and 2 premium-eligible, each with correct metrics.

**Acceptance Scenarios**:

1. **Given** a passenger's origin, destination, and desired departure time, **When** the system generates candidates, **Then** it returns rides satisfying all of: (a) at least one available seat, (b) ride status is `scheduled`, (c) driver departure time is within the allowed time window of the passenger's requested time, and (d) either all standard thresholds are met (standard candidate) or a premium pickup/dropoff flag is true (premium-eligible candidate).
2. **Given** a passenger request with no compatible or premium-eligible rides, **When** the system generates candidates, **Then** it returns an empty list with a "no matching rides" indicator rather than an error.
3. **Given** a ride with zero available seats, **When** candidate generation runs, **Then** that ride is excluded regardless of route compatibility.
4. **Given** a ride with status `cancelled`, `in_progress`, or `completed`, **When** candidate generation runs, **Then** that ride is excluded from the candidate list.
5. **Given** a list of candidate rides, **When** returned to the caller, **Then** each candidate includes its ride identifier, driver departure time, available seat count, base per-seat price, and the full compatibility result including any premium flags and fees.
6. **Given** a candidate list returned by this deterministic engine, **When** no AI reranking is active, **Then** standard candidates appear first sorted by route overlap percentage descending, followed by premium-eligible candidates sorted by total premium fee ascending; Phase 9 AI reranking supersedes this ordering.
7. **Given** a candidate where `premium_pickup_available` or `premium_dropoff_available` is true, **When** it appears in the list, **Then** it is explicitly marked as premium-eligible with the applicable detour fee displayed, clearly distinct from standard candidates.

---

### User Story 4 — Fuel-Cost-Based Fare Calculation (Priority: P4)

A driver creates a new ride from Heliopolis to Giza. The system computes the per-seat price automatically using a fixed, transparent formula: the driver's fuel cost for the trip — road-network distance divided by the standard vehicle fuel efficiency (13 km/L), multiplied by the current Egyptian petrol price per litre — is divided among all offered seats, with a 20% platform commission and a configurable safety margin added on top. This price is non-negotiable; it cannot be changed by the driver. The formula ensures the driver fully recovers their trip fuel cost from all passengers collectively, while each passenger pays a fair, predictable share. The same formula is applied to compute the extra fee for any premium pickup or dropoff detour the driver agrees to serve.

**Why this priority**: Phase 4 established manual pricing as an explicit interim measure, with the stated intent to replace it once trip distance was available from Phase 5. This story fulfills that commitment and gives the platform a fair, auditable, and non-negotiable pricing foundation before passengers start booking in Phase 6.

**Independent Test**: Create a ride between two test points with a known road-network distance (e.g., 20 km). With fuel price configured at 15 EGP/L and safety margin at 5 EGP, verify: `fuel_cost = (20 / 13) × 15 ≈ 23.08 EGP`; `commission = 23.08 × 0.20 ≈ 4.62 EGP`. For 4 seats: `per_seat = (23.08 + 4.62 + 5) / 4 ≈ 8.18 → 8 EGP`. Change to 2 seats and verify the per-seat price approximately doubles. Attempt to override the price and verify the system rejects the change.

**Acceptance Scenarios**:

1. **Given** a driver provides origin, destination, and seat count, **When** the system calculates the fare, **Then** it returns `per_seat_price = (fuel_cost + (fuel_cost × 0.20) + safety_margin) / seat_count` where `fuel_cost = (distance_km / 13) × fuel_price_per_litre`, rounded to the nearest Egyptian Pound.
2. **Given** a computed fare, **When** it is presented to the driver, **Then** it includes the full breakdown: road-network distance used, fuel price per litre applied, fuel cost computed (the driver's trip fuel total), platform commission (20% of fuel cost), safety margin applied, seat count, and resulting per-seat total in EGP.
3. **Given** a driver changes the seat count on a ride, **When** the fare is recalculated, **Then** the per-seat price updates proportionally — more seats yield a lower per-seat price; fewer seats yield a higher per-seat price.
4. **Given** any system-calculated fare, **When** the driver attempts to modify the posted per-seat price, **Then** the system rejects the change — the system-generated price is final and non-overridable.
5. **Given** a driver who accepts a premium pickup or dropoff request, **When** the extra fee is calculated, **Then** the system applies the same formula to the detour distance: `extra_fee = (detour_km / 13) × fuel_price_per_litre + ((detour_km / 13 × fuel_price_per_litre) × 0.20) + safety_margin`, rounded to the nearest EGP, and adds it to the booking total of the passenger who requested the premium option — the base per-seat price for other passengers is unaffected.
6. **Given** a route between a driver's origin and destination that cannot be calculated (unroutable), **When** the driver attempts to create the ride, **Then** the system returns a clear error and blocks ride creation; no manual pricing fallback is available from Phase 5 onward.
7. **Given** an admin updates the pricing configuration (fuel price per litre or safety margin), **When** a new ride's fare is subsequently calculated, **Then** the updated parameters apply; previously published rides are not retroactively repriced.

---

### Edge Cases

- What happens if the road-network routing service is temporarily unavailable when a passenger searches for rides? Candidate generation is blocked and the user receives a "route intelligence temporarily unavailable" message; ride creation is also blocked (unlike Phase 4, no manual pricing fallback exists from Phase 5 onward).
- What if a Phase 4 ride (created before route geometry was introduced) appears in the candidate pool? Legacy rides without stored route geometry are excluded from candidate generation until the driver re-saves the ride, triggering a route recalculation. No automatic backfill is performed.
- What if two candidate rides have identical overlap percentages? Departure time (earliest first) is used as a tiebreaker in the deterministic sort. Phase 9 AI reranking supersedes this.
- What if a passenger's origin and destination are within walking distance of each other (under 500 meters)? The system processes the request normally but may return an empty candidate list; no error is returned.
- What if the maximum walk distance threshold is configured to zero? The system returns an empty candidate list; a configuration warning is logged but the request is not rejected as an error.
- What if calculating compatibility across a large ride pool causes a timeout? Candidate generation is capped at 500 rides per request, applied after filtering by time window and ride status, then by a geographic bounding box around the passenger's journey. Rides beyond the cap are excluded from the current search.
- What if a passenger requests both a premium pickup AND a premium dropoff on the same booking? Both are treated as a combined premium request. The driver receives a single notification with both detour fees itemized and must accept or decline the combined request; partial acceptance (one but not the other) is not supported for MVP.
- What if the pricing configuration changes between the time a candidate list is shown and the time a passenger books? The fare is recalculated at booking time using the current configuration; the candidate list price is advisory.
- What if a driver tries to create a ride but the route calculation takes too long? A configurable timeout applies to routing service calls; if exceeded, the system returns a "routing unavailable" error and the driver must retry.

---

## Requirements *(mandatory)*

### Functional Requirements

**Route Path Calculation**

- **FR-001**: The system MUST calculate road-network distance (km), travel time (minutes), and encoded route geometry between any two geographic points within the service area using actual road-network data.
- **FR-002**: Route distance calculations MUST use road-network paths; straight-line (Euclidean) distance and angular-degree measurements are explicitly prohibited.
- **FR-003**: When no traversable road-network path exists between two points, the system MUST return a clearly flagged "unroutable" result rather than silently falling back to a straight-line estimate.
- **FR-004**: Route geometry MUST be encoded in a format compatible with the map display library used in the Main App (established in Phase 4.2).

**Route Overlap & Compatibility Analysis**

- **FR-005**: The system MUST calculate the route overlap percentage between a driver's planned route and a passenger's requested journey, expressed as the proportion of the passenger's journey that falls within a configurable buffer zone around the driver's route polyline. The buffer radius defaults to 150 meters and is an admin-configurable system parameter.
- **FR-006**: The system MUST calculate pickup walk distance — the walk distance from the passenger's origin to the nearest feasible boarding point on the driver's route.
- **FR-007**: The system MUST calculate dropoff walk distance — the walk distance from the driver's route to the passenger's destination.
- **FR-008**: The system MUST calculate driver detour — the additional road-network distance (km) and time (minutes) the driver incurs to pick up and drop off the passenger compared to their original route.
- **FR-009**: A compatibility result MUST contain: overlap percentage (0–100), pickup walk distance (meters), dropoff walk distance (meters), driver detour distance (km), driver detour time (minutes).
- **FR-010**: A compatibility result MUST include: an `is_compatible` boolean (true only when all standard thresholds are simultaneously satisfied — minimum overlap met, pickup walk within limit, dropoff walk within limit, driver detour within limit); a `premium_pickup_available` boolean (true when the passenger's origin exceeds the standard walk threshold but falls within the configured premium detour limit); and a `premium_dropoff_available` boolean (true when the same applies to the passenger's destination). A ride is a valid candidate when `is_compatible` is true OR either premium flag is true.

**Premium Pickup & Dropoff Fee Calculation**

- **FR-011**: For any compatibility result where `premium_pickup_available` is true, the system MUST calculate a premium pickup fee using the pricing formula applied to the pickup detour distance: `premium_pickup_fee = (pickup_detour_km / 13) × fuel_price_per_litre + ((pickup_detour_km / 13 × fuel_price_per_litre) × 0.20) + safety_margin`, rounded to the nearest EGP.
- **FR-012**: For any compatibility result where `premium_dropoff_available` is true, the system MUST calculate a premium dropoff fee using the same formula applied to the dropoff detour distance.
- **FR-013**: Premium fees MUST be stored within the CompatibilityResult and returned to the caller alongside the corresponding premium detour distance.
- **FR-014**: The premium detour limit (the maximum additional driver distance that qualifies a ride as premium-eligible rather than fully incompatible) MUST be a separately configurable system parameter, distinct from the standard detour threshold.
- **FR-015**: When a passenger selects a premium pickup or dropoff option at booking time (Phase 6), the driver MUST receive a notification containing the detour distance, the extra fee, and an explicit accept/decline prompt before the booking is confirmed. *(Notification delivery is Phase 6 scope; this requirement defines the data contract Phase 5 must supply.)*
- **FR-016**: If a driver declines a premium pickup request and the passenger's origin is also within the standard walk threshold, the booking MUST continue with the standard route-based boarding point. If the passenger's origin also exceeds the walk threshold, the booking MUST be rejected.

**Candidate Ride Generation**

- **FR-017**: The system MUST accept a passenger trip request (origin, destination, desired departure time) and return a filtered list of candidate rides from the scheduled-ride pool.
- **FR-018**: Candidate generation MUST apply a pre-compatibility filter: ride status is `scheduled`, available seats is greater than zero, and driver departure time falls within the configured time window of the passenger's requested departure time.
- **FR-019**: Rides passing the pre-compatibility filter MUST undergo a full compatibility assessment (FR-005 through FR-010); the candidate list MUST include rides where `is_compatible` is true (standard candidates) OR where `premium_pickup_available` or `premium_dropoff_available` is true (premium-eligible candidates).
- **FR-020**: Each returned candidate MUST include the ride identifier, driver departure time, available seat count, base per-seat price, and the full compatibility result including any premium flags and fees.
- **FR-021**: Standard candidates and premium-eligible candidates MUST be clearly distinguished in the response to allow the passenger-facing UI to present them separately.
- **FR-022**: When no compatible or premium-eligible rides exist, the system MUST return an empty list and a "no matching rides" indicator rather than an error.
- **FR-023**: The default sort order MUST be: standard candidates first (sorted by route overlap percentage descending), followed by premium-eligible candidates (sorted by total premium fee ascending). Phase 9 AI reranking supersedes this ordering.

**Fuel-Cost-Based Fare Calculation**

- **FR-024**: The system MUST calculate a per-seat fare for any ride given origin, destination, and seat count using: `fuel_cost = (distance_km / 13) × fuel_price_per_litre`, then `per_seat_price = (fuel_cost + (fuel_cost × 0.20) + safety_margin) / seat_count`, rounded to the nearest Egyptian Pound. `distance_km` is the road-network distance; `13` is the assumed vehicle fuel efficiency in km/L; `fuel_price_per_litre` is the admin-configured current Egyptian petrol price in EGP/L; `0.20` is the fixed platform commission rate.
- **FR-025**: Pricing parameters (`fuel_price_per_litre` in EGP/L and `safety_margin` in EGP) MUST be stored in a dedicated database configuration table and editable by admins directly via the Supabase dashboard without requiring a code deployment. No admin UI screen is required for MVP. The vehicle fuel efficiency constant (13 km/L) and the platform commission rate (20%) are fixed system constants and are not configurable.
- **FR-026**: The system MUST present the full fare breakdown to the driver: road-network distance used, fuel price applied, fuel cost computed, platform commission (20% of fuel cost), safety margin, seat count, and resulting per-seat total.
- **FR-027**: The system-calculated fare is the final, non-negotiable posted price for the ride. Drivers MUST NOT be able to modify or override the per-seat price; the system MUST reject any such attempt.
- **FR-028**: For any premium pickup or dropoff detour the driver accepts, the system MUST calculate the extra fee per FR-011 or FR-012 and add it to the booking total of the passenger who requested the premium option; the base per-seat price for all other passengers on the ride is unaffected.
- **FR-029**: When the route between a driver's origin and destination is unroutable (FR-003), the system MUST surface a clear error and block ride creation; no manual pricing fallback is available from Phase 5 onward.

### Key Entities

- **RouteGeometry**: The computed road-network path between two geographic points — road distance in km, travel time in minutes, encoded polyline geometry for map rendering, and an `is_routable` flag indicating whether the route was successfully calculated.

- **CompatibilityResult**: A transient response object computed fresh on every request — never persisted to the database. Contains: overlap percentage (0–100), pickup walk distance (meters), dropoff walk distance (meters), driver detour distance (km), driver detour time (minutes), `is_compatible` boolean (all standard thresholds satisfied), `premium_pickup_available` boolean, `premium_pickup_detour_km`, `premium_pickup_fee` (EGP), `premium_dropoff_available` boolean, `premium_dropoff_detour_km`, and `premium_dropoff_fee` (EGP).

- **RideCandidate**: A driver ride that has passed candidate generation filters — includes ride identifier, driver departure time, available seat count, base per-seat price, candidate type (`standard` or `premium`), and the associated CompatibilityResult.

- **FareEstimate**: The output of the pricing engine for a given origin, destination, and seat count — includes: per-seat price in EGP, road-network distance used, `fuel_price_per_litre` applied, `fuel_cost` computed (driver's total trip fuel cost), platform commission applied (20% of fuel cost), `safety_margin` applied, seat count, and `total_collected` (per_seat_price × seat_count — the full amount collected from all passengers if all seats fill, representing the driver's full fuel cost recovery).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Candidate generation for a passenger trip request returns results within 3 seconds at p95 for a pool of up to 500 available scheduled rides.
- **SC-002**: 100% of new rides created after this phase is deployed receive a system-calculated fare where a valid road-network route exists between the driver's origin and destination.
- **SC-003**: Compatibility assessments correctly include or exclude rides based on configured standard and premium thresholds in 100% of unit-tested route pairs.
- **SC-004**: Zero candidates are returned where both `is_compatible` is false AND both premium flags are false (no false positives).
- **SC-005**: Fare estimates for routes with a known road-network distance fall within ±5% of the manually pre-calculated expected price using the same formula and configured parameters.
- **SC-006**: 100% of driver attempts to override a system-calculated price are rejected by the system.

---

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Route path calculation MUST complete within 500ms per request at p95 under expected load (≤1,000 concurrent users).
- **NFR-002**: Candidate generation for up to 500 rides MUST complete within 3 seconds at p95 under expected load.
- **NFR-003**: All geospatial calculations MUST use PostGIS spatial types for storage and measurement; latitude/longitude arithmetic in application code for distance calculations is prohibited.
- **NFR-004**: Fare calculations MUST be deterministic — identical inputs (origin, destination, seat count, pricing configuration) always produce identical output.
- **NFR-005**: The route intelligence engine MUST expose internal API endpoints that the AI service (Phase 9) can call to retrieve pre-calculated compatibility features for a (passenger-request, driver-ride) pair without recomputing them from scratch.
- **NFR-006**: When the road-network routing service is unavailable, the system MUST degrade gracefully — both ride creation and passenger search surface a "service unavailable" error; silent incorrect results are not acceptable.
- **NFR-007**: Pricing configuration changes MUST take effect within 60 seconds of an admin update, without requiring a service restart or code deployment.
- **NFR-008**: User-facing route intelligence endpoints (candidate generation, fare calculation) MUST require a valid Supabase Auth JWT; unauthenticated requests MUST be rejected with HTTP 401. Internal endpoints exposed to the Phase 9 AI service MUST require a server-to-server shared secret header; requests without a valid secret MUST be rejected with HTTP 403.
- **NFR-009**: Every route calculation, compatibility assessment, candidate generation, and fare calculation request MUST emit a structured log entry containing: endpoint name, input parameters (sanitized), output summary, duration in milliseconds, and error details if applicable. Per-endpoint request count and p95 latency MUST be exported as metrics to a monitoring sink to enable verification of NFR-001 and NFR-002 in production.

---

## Dependencies *(mandatory)*

- **Internal**:
  - `001-platform-foundation` — Supabase PostgreSQL + PostGIS, FastAPI backend, and monorepo structure must be operational.
  - `004-ride-management` — Driver rides with origin and destination stored as PostGIS point types, departure time, seat counts, and status must exist for candidate generation to have a pool to operate on.

- **External**:
  - **OSRM (Open Source Routing Machine)**: A self-hosted OSRM instance pre-loaded with OpenStreetMap road network data for Egypt must be running and reachable by the FastAPI backend. (Included in the approved technology stack as OSM + OSRM.)
  - **OpenStreetMap Egypt data**: A current OSM `.pbf` extract for Egypt, used to build the OSRM routing graph. Must be available at build time.

- **Data**:
  - Supabase PostgreSQL with PostGIS extension enabled (established in Phase 1).
  - Existing `Ride` records from Phase 4 with origin and destination stored as PostGIS point types.
  - Pricing configuration table for admin-managed parameters (`fuel_price_per_litre`, `safety_margin`).

---

## Out-of-Scope

- **Driver price negotiation or override** — the system-calculated fare is the final posted price; driver modification of prices is explicitly prohibited by the platform's pricing policy.
- **AI-based match scoring and ride ranking** — Phase 5 generates candidates deterministically; AI scoring and reranking are Phase 9 responsibilities.
- **Passenger-facing ride search UI** — the search experience is Phase 6; this phase delivers backend engine APIs only.
- **Real-time ETA updates during an active ride** — live ETA based on driver location is Phase 7; this phase provides static, departure-time-based estimates only.
- **Dynamic surge pricing based on real-time demand** — the platform commission and safety margin are fixed configuration values for MVP; demand-based surge is a post-competition feature.
- **Multi-stop routes and waypoints** — rides remain single origin-to-destination in this phase (per Phase 4 MVP scope).
- **International or inter-city routing** — the service area is limited to Cairo and its immediate surroundings for MVP.
- **Bulk retroactive route recalculation for Phase 4 legacy rides** — legacy rides are excluded from candidate matching until the driver re-saves them; automated backfill is out of scope.
- **Pedestrian routing for walk distances** — walking distances use a straight-line approximation for MVP; full pedestrian-network walk routing is a post-competition enhancement.

---

## Technical Considerations

- Route calculations MUST use OSRM, not straight-line distance (Constitution Principle II: Route Intelligence Over Geographic Proximity).
- All geospatial storage and spatial measurements MUST use PostGIS geometry/geography types (Constitution §Data Standards). Application-level latitude/longitude arithmetic for distance is prohibited.
- The route intelligence logic MUST reside in the FastAPI backend service (`services/api`); geospatial computation is a backend domain, not a frontend responsibility (Constitution §Architecture Standards).
- The AI service (`services/ai`, Phase 2) is a separate service and MUST NOT be called in this phase. The API contract between the route intelligence engine and the AI service (the feature set and data formats that Phase 9 will consume) MUST be defined and documented during this phase's implementation, even though the AI service does not call it until Phase 9.
- Pricing parameters (`fuel_price_per_litre` and `safety_margin`) MUST be stored as admin-configurable values in the database rather than as hardcoded constants in application code (Constitution §Architecture Standards: backend owns business logic). The 13 km/L fuel efficiency constant and the 20% platform commission rate are fixed formula constants.
- The `FareEstimate` breakdown (fuel_cost, commission, safety_margin, distance_used) MUST be persisted on the `Ride` entity to support future auditability and AI training data quality.
- OSRM is deployed as a Docker service in `docker-compose.yml`, consistent with the Dockerization work from Phase 4.1. The service MUST be included in both development and production compose configurations.
- Route geometry encoding MUST use the same format expected by the mapping library established in Phase 4.2 (Frontend Design).
- The distinction between standard candidates and premium-eligible candidates MUST be maintained throughout the API response chain to allow Phase 6 to render them separately in the passenger UI.

---

## Assumptions

- **OSRM deployment**: OSRM is self-hosted (not a commercial API), seeded with the current OSM Egypt `.pbf` extract, and added as a Docker service in the project's `docker-compose.yml`. This aligns with the approved technology stack and Phase 4.1 Dockerization.
- **Standard compatibility thresholds — configurable defaults**:
  - Route corridor buffer radius: 150 meters (the buffer zone around the driver's route polyline within which passenger journey segments count toward overlap)
  - Minimum route overlap: 50% of the passenger's journey
  - Maximum pickup walk distance: 500 meters
  - Maximum dropoff walk distance: 500 meters
  - Maximum driver detour (standard): 3 km additional distance or 10 additional minutes, whichever is exceeded first
  - Time window for ride eligibility: driver departs within ±30 minutes of the passenger's requested time
- **Premium pickup/dropoff thresholds — configurable defaults**:
  - Maximum premium pickup detour: 2 km additional driver distance (beyond which a ride is fully incompatible even for premium)
  - Maximum premium dropoff detour: 2 km additional driver distance
  - A ride where the walk distance exceeds the standard threshold but the required driver detour is within the premium limit is flagged as premium-eligible, not incompatible
- **Pricing defaults — configurable**:
  - Fuel price per litre: 15 EGP/L (approximate current Egyptian petrol price; must be kept current by admin)
  - Safety margin: 5 EGP per ride
  - Vehicle fuel efficiency: 13 km/L (fixed constant; reflects average Egyptian passenger car consumption)
  - Platform commission rate: 20% of fuel cost (fixed constant; not configurable)
  - Currency: Egyptian Pound (EGP)
- **Fare seat-count basis**: Fare calculation uses `total_seats` (the driver's full offering). If all seats fill, the driver recovers the full `fuel_cost` from passengers collectively and the platform retains the commission and safety margin. If not all seats fill, the driver recovers a proportional share of fuel cost; this is inherent ride-sharing economics.
- **Walk distance approximation**: Walk distances between a passenger's origin/destination and the driver's route boarding/alighting points use straight-line approximation for MVP. This is explicitly noted as a post-competition enhancement (see Out-of-Scope).
- **Optimal boarding/alighting point selection**: The boarding point is the point on the driver's route geometry closest to the passenger's origin by straight-line distance; the alighting point is the point closest to the passenger's destination. Both must be within the configured walk thresholds for a standard match.
- **Candidate pool cap**: Candidate generation processes a maximum of 500 rides per search request after filtering by time window, ride status, and a geographic bounding box. This cap is sufficient for the 1,000-user MVP scale.
- **Legacy ride handling**: Rides created in Phase 4 before route geometry was stored are excluded from candidate generation until the driver re-saves the ride, triggering a fresh route calculation. No automatic backfill is performed.
