# Feature Specification: Passenger Experience

**Feature Branch**: `009-passenger-experience`

**Created**: 2026-06-24

**Status**: Draft

**Input**: Phase 6 — Passenger Experience: ride search, ride details, booking creation, and booking lifecycle management.

---

## Clarifications

### Session 2026-06-24

- Q: What triggers the `confirmed → completed` booking status transition? → A: Automatic cascade — when the driver marks the ride `completed` (Phase 7 action), Phase 6's backend atomically transitions all `confirmed` bookings for that ride to `completed`.
- Q: How does Phase 6 deliver notification events to Phase 7? → A: Database-driven — Phase 6 inserts a row into a `notification_events` table (event type, recipient IDs, JSON payload); Phase 7 reads and dispatches from that table independently.
- Q: Should the ride search endpoint enforce per-user rate limiting? → A: Deferred — no application-level rate limiting for MVP; Phase 12 (Production Readiness) addresses it holistically across all endpoints.

---

## Business Objective *(mandatory)*

Enable verified passengers to discover rides that genuinely match their journeys, inspect every meaningful detail before committing, create a booking with a single action, and manage that booking throughout its lifecycle — from pending through confirmed, and including cancellation by either party.

This phase is the demand side of the Fe El Seka marketplace. Phase 5 built the engine that generates compatible ride candidates; this phase builds the passenger-facing surface that turns those candidates into bookings. Every core passenger interaction lives here: search, inspect, book, and manage. Without this phase, passengers cannot participate in the platform and the entire ride-sharing value proposition is unreachable.

**Constitutional Domain**: Ride Discovery / Booking

**Affected Applications**: Main App (passenger-role screens); FastAPI backend (booking API); shared data layer (Booking entity, ride seat accounting).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Ride Search (Priority: P1)

A verified passenger opens the app intending to travel from Heliopolis to Zamalek at 8:00 AM on a Tuesday. She enters her origin, destination, and desired departure date and time, then submits the search. The app returns a ranked list of compatible rides — each card showing the driver's departure time, route overlap quality, price per seat, and available seats. She can scan the list and quickly identify which rides fit her journey best.

**Why this priority**: Passengers cannot participate in the platform at all without discovering rides. This is the entry point to every passenger journey. All subsequent stories — viewing details, booking, managing — are only reachable from a successful search result. P1 because it gates the entire passenger experience.

**Independent Test**: Create 10 test rides in the system — 3 standard-compatible with the test passenger's route, 1 premium-eligible, and 6 that should not appear (wrong time window, full seats, cancelled, or no route overlap). Submit a search request with the passenger's origin, destination, and desired departure time. Verify: exactly 4 rides appear (3 standard + 1 premium-eligible), standard rides appear before premium, each card includes departure time, per-seat price, available seats, and a visual distinction for premium candidates.

**Acceptance Scenarios**:

1. **Given** a verified passenger on the search screen, **When** she enters a valid origin, destination, and desired departure time and submits, **Then** the system returns a list of ride candidates sourced from the Phase 5 deterministic engine — containing only rides that are either standard-compatible or premium-eligible with the passenger's journey.
2. **Given** a search result list, **When** no AI reranking is active (Phase 9 not yet deployed), **Then** standard candidates appear first sorted by route overlap percentage descending, followed by premium-eligible candidates sorted by total premium fee ascending — matching the Phase 5 default sort contract.
3. **Given** a search result list after Phase 9 is deployed, **When** AI reranking has scored the candidates, **Then** the list is ordered by AI match score descending; the Phase 5 deterministic sort is superseded.
4. **Given** a search that returns results, **When** the passenger views the list, **Then** each ride card displays: driver's display name and profile photo, departure time, available seat count, per-seat price in EGP, and route overlap quality indicator. Premium-eligible rides are visually marked as premium with the additional fee shown.
5. **Given** a search for which no compatible or premium-eligible rides exist, **When** the results are returned, **Then** the app shows an empty state with a "no rides found" message — no error, no crash.
6. **Given** a passenger whose verification status is not `approved`, **When** she attempts to submit a search, **Then** the system returns an error indicating that identity verification must be completed before searching for rides.
7. **Given** a passenger who submits a search with an origin identical or within 100 meters of the destination, **When** the search is processed, **Then** the system returns an empty candidate list with a user-friendly message; it does not return an error or crash.
8. **Given** a passenger who submits a search, **When** the Phase 5 route intelligence service is temporarily unavailable, **Then** the search fails gracefully with a "service temporarily unavailable, please try again" message — no partial or incorrect results are returned.

---

### User Story 2 — Ride Detail View (Priority: P2)

The passenger taps a ride card from the search results. She sees the full ride detail: the driver's profile and verification badge, the route drawn on a map (from the driver's origin to destination with her boarding and alighting points highlighted), departure time, estimated arrival at her destination, total price for her seat, available seat count, and any premium pickup or dropoff option the system has flagged. She can see enough information to make a confident booking decision before committing.

**Why this priority**: A ride card in search shows enough to filter; the detail screen shows enough to trust. Passengers booking a shared ride with a stranger need driver transparency, route clarity, and price certainty before they tap "Book." Without this screen, conversion from search result to booking is impossible. P2 because it directly enables the booking action but is only reachable after a search.

**Independent Test**: Navigate to the detail screen for a known test ride. Verify: the driver's display name, profile photo, and verification badge are present; the map renders the full driver route polyline with the passenger's boarding point and alighting point marked as distinct pins; departure time, estimated travel time to passenger's destination, per-seat price, and available seat count are all displayed. Then open the detail screen for a premium-eligible ride and verify the premium pickup or dropoff option is shown with its fee clearly itemized.

**Acceptance Scenarios**:

1. **Given** a ride in the search results, **When** the passenger taps the ride card, **Then** the detail screen loads and displays: driver's display name, profile photo, and a verified identity badge; departure time and estimated arrival at the passenger's destination; per-seat price (base) and the total she will pay; available seat count; and the route drawn on a full-width map.
2. **Given** the ride detail map, **When** it renders, **Then** it shows: the full driver route polyline from driver origin to driver destination; the passenger's boarding point on the driver's route; the passenger's alighting point on the driver's route; the passenger's walk path from her origin to the boarding point; the passenger's walk path from the alighting point to her destination.
3. **Given** a standard-compatible ride on the detail screen, **When** the passenger reviews the price section, **Then** she sees the per-seat base price in EGP and the total amount she will pay for her seat — with no premium fees appended (this is a standard ride).
4. **Given** a premium-eligible ride on the detail screen (e.g., `premium_pickup_available = true`), **When** the passenger reviews the ride, **Then** the screen displays: (a) the standard boarding point option (walk to driver's route) with the base per-seat price; and (b) the premium pickup option (driver deviates to collect her at her exact origin) with the base price plus the itemized premium fee. She chooses one before proceeding to booking.
5. **Given** a ride where both `premium_pickup_available` and `premium_dropoff_available` are true, **When** the passenger reviews the options, **Then** the screen presents three options: standard (walk both ends), premium pickup only, premium dropoff only — but **not** both premium simultaneously, since combined premium is not supported for MVP.
6. **Given** a ride detail screen is open, **When** another passenger books the last available seat before the current passenger books, **Then** the available seat count is updated to reflect the change; if no seats remain, the "Book" button is disabled and an "unavailable" indicator is shown.
7. **Given** a ride whose status has changed to `cancelled` or `completed` since the search was performed, **When** the passenger loads the detail screen for that ride, **Then** the screen shows a "this ride is no longer available" state; the booking action is not available.

---

### User Story 3 — Booking Creation (Priority: P3)

Satisfied with the ride details, the passenger taps "Book Seat." The system creates a booking record in `pending` status, decrements the ride's available seat count by one, and confirms the booking request was received. The driver will be notified separately (Phase 7) and must confirm or reject. The passenger sees a booking confirmation screen with a summary and the current status of "waiting for driver confirmation."

**Why this priority**: This is the core transaction of the entire passenger experience — the moment a passenger commits to a ride. Without it, search and detail views are informational only. P3 (not P1) because it requires search and detail to work first, but it is the highest-value action on the demand side of the platform.

**Independent Test**: As a verified passenger, navigate to a ride detail screen and tap "Book Seat." Verify: a `Booking` record is created in the database with status `pending`, the ride's available seat count is decremented by 1, the passenger sees a confirmation screen with a booking summary (ride ID, driver name, departure time, price, and status "Pending Driver Confirmation"), and the same booking cannot be created again for the same passenger on the same ride (duplicate booking prevention).

**Acceptance Scenarios**:

1. **Given** a verified passenger on the ride detail screen for a ride with at least one available seat, **When** she taps "Book Seat," **Then** the system creates a `Booking` record with: a unique identifier, `passenger_id` = her user ID, `ride_id` = the selected ride's ID, `status = pending`, `per_seat_price` = the price at the moment of booking, `passenger_pickup_point` = her boarding point geometry, `passenger_dropoff_point` = her alighting point geometry, and any selected premium flags and fees. The ride's `available_seats` count is decremented by 1 atomically.
2. **Given** a booking has just been created, **When** the passenger is returned to the app, **Then** she sees a booking confirmation screen showing: driver name, departure time, boarding point, alighting point, price, total amount, and status "Pending Driver Confirmation."
3. **Given** a passenger who chose a premium pickup option on the detail screen, **When** she taps "Book Seat," **Then** the booking is created with `premium_pickup_requested = true` and `premium_pickup_fee` set to the fee shown on the detail screen. The driver will receive a premium request notification (Phase 7) and must explicitly accept or decline the detour before the booking is confirmed.
4. **Given** two passengers who simultaneously tap "Book Seat" on a ride with only one remaining seat, **When** both booking requests reach the backend, **Then** exactly one booking succeeds and the other receives a "no seats available" response — the seat count never goes negative.
5. **Given** a passenger who already has an active booking (status `pending` or `confirmed`) for the same ride, **When** she attempts to create another booking for the same ride, **Then** the system rejects the request with a "you already have an active booking for this ride" message.
6. **Given** a passenger whose verification status is not `approved`, **When** she attempts to create a booking, **Then** the system rejects the request with HTTP 403 and a message directing her to complete identity verification.
7. **Given** a ride whose status is not `scheduled` at the moment of booking, **When** the booking request is submitted, **Then** the system rejects it with an appropriate error — the ride must be in `scheduled` status at booking time.
8. **Given** a booking is created successfully, **When** the event is recorded, **Then** an audit log entry is created capturing: booking ID, passenger ID, ride ID, timestamp, price locked, and premium options selected.

---

### User Story 4 — Driver Booking Response (Priority: P4)

A driver receives a booking request notification (Phase 7 delivers the push notification; this story defines the action). She opens her driver app, sees the pending booking in her ride management screen, reviews the passenger's pickup and dropoff points on the map, and either confirms or rejects the booking. If she confirms, the booking moves to `confirmed` status and the passenger is notified. If she rejects, the booking is cancelled and the passenger is notified. For premium requests, the driver sees the detour distance and extra fee before deciding.

**Why this priority**: The driver's response completes the two-sided booking handshake. Without it, all bookings remain permanently `pending` and the platform cannot function as a transportation marketplace. P4 because it depends on P3 (booking creation) and requires the driver-side UI from the Main App's driver-role context.

**Independent Test**: Create a pending booking for a test ride. Log in as the driver. Navigate to the ride's booking queue in the driver view. Tap "Confirm" on the pending booking. Verify: the booking status changes to `confirmed`, the ride's `reserved_seats` count increases by 1, an audit log entry is created. Repeat with a second booking and tap "Reject." Verify: the booking status changes to `cancelled`, the ride's `available_seats` count is restored by 1, an audit log entry is created.

**Acceptance Scenarios**:

1. **Given** a pending booking on one of her rides, **When** the driver opens her ride's booking queue, **Then** she sees all pending bookings with: passenger display name, pickup and dropoff points shown on a mini-map, price to be collected, and — for premium requests — the detour distance and extra fee clearly itemized.
2. **Given** a driver who taps "Confirm" on a pending booking, **When** the confirmation is processed, **Then** the booking status changes to `confirmed`, the ride's seat accounting is updated (reserved seat count reflects the confirmation), and an audit log entry is created with driver ID, booking ID, and timestamp.
3. **Given** a driver who taps "Reject" on a pending booking, **When** the rejection is processed, **Then** the booking status changes to `cancelled`, the seat held for this booking is released back to `available_seats`, and an audit log entry is created.
4. **Given** a pending booking with `premium_pickup_requested = true`, **When** the driver taps "Confirm," **Then** the booking is confirmed with the premium detour included — the driver has implicitly accepted the detour. The extra premium fee is added to the passenger's total.
5. **Given** a pending booking with `premium_pickup_requested = true`, **When** the driver taps "Reject (decline detour)," **Then**: if the passenger's origin is also within the standard walk threshold, the booking falls back to the standard boarding point and becomes `confirmed` at the base price without the premium fee; if the passenger's origin exceeds the walk threshold, the booking is `cancelled` and the seat is released.
6. **Given** a driver whose ride has been cancelled (by the driver themselves) while a booking is in `pending` status, **When** the ride cancellation is processed, **Then** all pending bookings for that ride are automatically transitioned to `cancelled`, seats are released, and passengers are flagged for notification (Phase 7).
7. **Given** a driver who does not respond to a pending booking within 24 hours, **When** the response deadline expires, **Then** the booking is automatically cancelled, the seat is released, and the passenger is flagged for notification. *(Expiry enforcement is a background process; this requirement defines the business rule.)*

---

### User Story 5 — Booking Cancellation (Priority: P5)

Either a passenger or a driver may need to cancel a confirmed or pending booking before the ride departs. A passenger may change her plans; a driver may need to cancel a specific passenger's seat without cancelling the entire ride. The cancellation is recorded, the seat is released, and the other party is flagged for notification (delivered in Phase 7).

**Why this priority**: Cancellation is a necessary escape valve for both parties and is required for the platform to be trusted for daily commuting. Without it, a confirmed booking becomes a commitment with no exit path, which damages user confidence. P5 because it completes the booking lifecycle but is a recovery path, not the primary flow.

**Independent Test**: Create a confirmed booking. As the passenger, navigate to "My Bookings" and cancel the booking. Verify: booking status transitions to `cancelled`, the ride's `available_seats` count is incremented by 1, the seat is no longer reserved for the passenger. Repeat as the driver cancelling from the ride's booking list. Verify identical state transitions and the audit log records `cancelled_by` = `driver`.

**Acceptance Scenarios**:

1. **Given** a passenger with a booking in `pending` or `confirmed` status, **When** she cancels the booking from "My Bookings," **Then** the booking status changes to `cancelled`, the seat is released back to the ride's `available_seats`, and the `cancelled_by` field is set to `passenger`.
2. **Given** a driver with a confirmed booking on one of her rides, **When** she cancels a specific passenger's booking (without cancelling the entire ride), **Then** the booking status changes to `cancelled`, the seat is released, and `cancelled_by` is set to `driver`.
3. **Given** a booking in `completed` status, **When** either party attempts to cancel it, **Then** the system rejects the cancellation with a "completed bookings cannot be cancelled" message.
4. **Given** any booking cancellation, **When** it is processed, **Then** an audit log entry is created capturing: booking ID, who cancelled (`passenger` or `driver`), timestamp, and booking status at cancellation time.
5. **Given** a passenger who cancels a booking within 1 hour of the ride's scheduled departure time, **When** the cancellation is recorded, **Then** the system records a `late_cancellation` flag on the audit entry. *(No automatic penalty in MVP; this flag is available for future enforcement.)*

---

### User Story 6 — My Bookings (Priority: P6)

A passenger can view all her bookings — past and present — from a dedicated screen. She sees the booking status, the ride details, and can take available actions (cancel if still cancellable). A driver can view all booking requests for each of her rides from the ride management screen established in Phase 4.

**Why this priority**: Without a bookings list, passengers lose visibility into their pending and confirmed commitments and cannot manage their transportation. P6 because it is a management surface layered on top of the core booking transaction.

**Independent Test**: Create three bookings for a test passenger across different rides — one pending, one confirmed, one cancelled. Navigate to "My Bookings." Verify all three appear with correct status labels. Verify only the pending and confirmed bookings show a cancel action; the cancelled booking shows a "Cancelled" status with no actionable button.

**Acceptance Scenarios**:

1. **Given** a passenger on the "My Bookings" screen, **When** she views the list, **Then** she sees all her bookings — pending, confirmed, and cancelled — each showing: ride departure time, driver name, boarding point, alighting point, price, and current status.
2. **Given** a booking in `pending` or `confirmed` status on the list, **When** the passenger views it, **Then** a "Cancel Booking" action is available.
3. **Given** a booking in `cancelled` or `completed` status, **When** the passenger views it, **Then** no cancel action is shown; the booking is displayed as read-only history.
4. **Given** a driver on the ride management screen for a specific ride, **When** she views the booking list for that ride, **Then** she sees all bookings for that ride — pending (with confirm/reject actions), confirmed (with cancel action), and cancelled/completed (read-only) — including the passenger pickup/dropoff points for each.

---

### Edge Cases

- What if a ride fills up between the moment a passenger views the detail screen and the moment she taps "Book"? The booking request is rejected at submission time with a "no seats available" message. The available seat count on the detail screen should reflect the latest count, but there is no seat hold during browsing.
- What if the Phase 5 route intelligence service is unavailable when a search is submitted? The search fails with a "service temporarily unavailable" message. No partial or cached results are returned.
- What if a passenger submits an origin and destination that are identical? The search proceeds but returns an empty candidate list. No error is thrown.
- What if a driver cancels an entire ride that has one or more confirmed bookings? All confirmed and pending bookings for that ride are automatically transitioned to `cancelled`, their seats are released, and each passenger is flagged for notification via Phase 7.
- What if a passenger tries to book a ride that departs in the past? The system rejects the booking with a "ride departure has passed" message.
- What if a premium option was available at search time but the driver's route changed before the passenger attempts to book? The compatibility is re-evaluated at booking time. If the premium flag is no longer valid, the passenger is shown the updated options before confirming.
- What if a passenger has no profile photo? Driver name and a placeholder avatar are shown in the ride detail and booking screens. The verified badge is shown regardless of whether a photo exists.
- What if the passenger's device loses connectivity mid-booking? The booking request is either received and processed by the backend (success) or not received at all (no partial state). The passenger is shown a retry prompt on reconnection.

---

## Requirements *(mandatory)*

### Functional Requirements

**Ride Search**

- **FR-001**: The system MUST accept a passenger ride search request comprising: origin geographic point, destination geographic point, and desired departure date and time — and return a ranked list of compatible ride candidates by calling the Phase 5 candidate generation engine.
- **FR-002**: The system MUST only return rides that the Phase 5 engine classifies as standard-compatible (`is_compatible = true`) or premium-eligible (`premium_pickup_available = true` OR `premium_dropoff_available = true`).
- **FR-003**: The search endpoint MUST enforce identity verification — only passengers with `verification_status = approved` may perform searches; unverified users receive HTTP 403.
- **FR-004**: Each ride card in the search result list MUST expose: driver display name and profile photo URL, departure time, available seat count, per-seat base price in EGP, route overlap quality indicator, and a premium flag for premium-eligible candidates.
- **FR-005**: When no compatible rides exist, the system MUST return an empty list with a `no_rides_found` indicator — not an error response.
- **FR-006**: The search result list MUST default to the Phase 5 deterministic sort order (standard candidates by overlap descending, then premium candidates by fee ascending) and accept an AI-ranked result set from Phase 9 when available, treating the Phase 9 order as authoritative.

**Ride Detail View**

- **FR-007**: The system MUST provide an endpoint that returns full ride details for a given ride ID, including: ride identifier, driver display name and profile photo, driver verification status, departure time, per-seat price, available seat count, ride status, and route geometry in the format established in Phase 4.2 for map rendering.
- **FR-008**: The ride detail response MUST include the passenger's computed boarding point geometry, alighting point geometry, walk distance from the passenger's origin to the boarding point, and walk distance from the alighting point to the passenger's destination — derived from the Phase 5 CompatibilityResult for that passenger's journey.
- **FR-009**: For premium-eligible rides, the ride detail response MUST include the premium option(s) available (`premium_pickup_available`, `premium_dropoff_available`), the associated detour distances, and the calculated premium fees in EGP.
- **FR-010**: The ride detail endpoint MUST return the current available seat count reflecting any bookings that have been confirmed since the initial search; a ride that has since become fully booked MUST surface an "unavailable" indicator.
- **FR-011**: If the ride's status is `cancelled` or `completed` by the time the passenger loads the detail screen, the endpoint MUST return the ride with a status indicator reflecting the change; the booking action MUST NOT be available.

**Booking Creation**

- **FR-012**: The system MUST accept a booking creation request containing: ride ID, passenger ID (from auth token), boarding point, alighting point, and optionally `premium_pickup_requested` and `premium_dropoff_requested` flags.
- **FR-013**: On booking creation, the system MUST atomically: (a) verify the ride has at least one available seat, (b) decrement `available_seats` by 1, (c) create a `Booking` record with `status = pending`, locking in `per_seat_price` at the current posted price, `premium_pickup_fee` and `premium_dropoff_fee` if applicable.
- **FR-014**: The system MUST prevent duplicate active bookings — a passenger MUST NOT have more than one booking in `pending` or `confirmed` status for the same ride at the same time; duplicate attempts MUST be rejected with HTTP 409.
- **FR-015**: The system MUST reject booking creation if the ride's status is not `scheduled`.
- **FR-016**: The system MUST reject booking creation if the ride's departure time is in the past.
- **FR-017**: An audit log entry MUST be created for every booking creation event, capturing: booking ID, passenger ID, ride ID, timestamp, per-seat price locked, premium flags, and boarding/alighting points.

**Driver Booking Response**

- **FR-018**: The system MUST provide a driver-facing endpoint to confirm or reject a `pending` booking on a ride the driver owns.
- **FR-019**: On driver confirmation, the system MUST: transition the booking to `confirmed`, create an audit log entry, and insert a `NotificationEvent` row with `event_type = booking_confirmed` and `recipient_user_id` = the passenger's user ID.
- **FR-020**: On driver rejection, the system MUST: transition the booking to `cancelled`, atomically restore 1 to the ride's `available_seats`, create an audit log entry, and insert a `NotificationEvent` row with `event_type = booking_rejected` and `recipient_user_id` = the passenger's user ID.
- **FR-021**: For premium booking requests, driver confirmation MUST lock in the premium fee as part of the booking total. Driver rejection of a premium request MUST apply the fallback rule: if the passenger's boarding point is within the standard walk threshold, the booking MUST continue as a standard confirmed booking at the base price; otherwise the booking MUST be cancelled.
- **FR-022**: The system MUST enforce that only the ride's owner (the driver) can confirm or reject bookings for their rides; other users MUST receive HTTP 403.
- **FR-023**: Pending bookings that have not received a driver response within 24 hours MUST be automatically cancelled by a background process, releasing the held seat and inserting a `NotificationEvent` row with `event_type = booking_expired` and `recipient_user_id` = the passenger's user ID.

**Booking Cancellation**

- **FR-024**: The system MUST allow a passenger to cancel any of their own bookings in `pending` or `confirmed` status; cancellation of `completed` bookings MUST be rejected.
- **FR-025**: The system MUST allow a driver to cancel any individual confirmed or pending booking on their rides without cancelling the entire ride.
- **FR-026**: On any booking cancellation, the system MUST atomically: transition the booking to `cancelled`, restore 1 to the ride's `available_seats`, record `cancelled_by` (`passenger` or `driver`), and create an audit log entry with cancellation timestamp.
- **FR-027**: When a driver cancels an entire ride (Phase 4 scope), all associated `pending` and `confirmed` bookings MUST be automatically cancelled, each seat released, the cancellation reason recorded as `ride_cancelled_by_driver`, and a `NotificationEvent` row inserted for each affected passenger with `event_type = ride_cancelled`.
- **FR-028**: A `late_cancellation` flag MUST be set on the audit log entry if a cancellation occurs within 1 hour of the ride's scheduled departure time.

**Booking Completion**

- **FR-031**: When a ride's status transitions to `completed` (triggered by the driver via the Phase 7 workflow), the system MUST atomically transition all `confirmed` bookings for that ride to `completed` status and create a `BookingAuditLog` entry for each with `event_type = completed`, `actor_role = system`.
- **FR-032**: The `confirmed → completed` transition MUST be idempotent — if a booking is already in `completed` status when the ride-completion event is processed, the system MUST NOT create a duplicate audit entry or alter the booking record.

**Booking Management (My Bookings)**

- **FR-029**: The system MUST provide an endpoint returning all bookings for the authenticated passenger, ordered by departure time descending (most recent first), including ride details (departure time, driver name, route summary) and current booking status for each.
- **FR-030**: The booking list endpoint MUST support filtering by status (`pending`, `confirmed`, `cancelled`, `completed`) via an optional query parameter.

### Key Entities

- **Booking**: The core transactional record linking a passenger to a driver ride. Attributes: UUID primary key; `ride_id` (foreign key); `passenger_id` (foreign key); `status` (enum: `pending` / `confirmed` / `cancelled` / `completed`); `per_seat_price` (EGP, locked at booking time); `total_price` (EGP); `passenger_pickup_point` (PostGIS geometry — the boarding point on the driver's route); `passenger_dropoff_point` (PostGIS geometry — the alighting point on the driver's route); `premium_pickup_requested` (boolean, default false); `premium_dropoff_requested` (boolean, default false); `premium_pickup_fee` (EGP, null if not requested); `premium_dropoff_fee` (EGP, null if not requested); `cancelled_by` (enum: `passenger` / `driver` / `system`, null if not cancelled); `cancellation_reason` (text, null if not cancelled); `late_cancellation` (boolean, default false); `created_at`; `confirmed_at`; `cancelled_at`.

- **BookingAuditLog**: An immutable record of every state transition on a booking. Attributes: UUID primary key; `booking_id` (foreign key); `event_type` (enum: `created` / `confirmed` / `rejected` / `cancelled` / `expired` / `completed`); `actor_id` (user ID of who triggered the event, or null for system events); `actor_role` (enum: `passenger` / `driver` / `system`); `previous_status`; `new_status`; `metadata` (JSONB — captures premium flags, price locked, cancellation reason, etc.); `created_at`.

- **NotificationEvent**: A queue record written by Phase 6 and consumed by Phase 7. Attributes: UUID primary key; `event_type` (enum: `booking_confirmed` / `booking_rejected` / `booking_cancelled` / `booking_expired` / `ride_cancelled`); `recipient_user_id` (the user who should receive the notification); `payload` (JSONB — contains ride ID, booking ID, departure time, driver/passenger name, and any premium fee context relevant to the event); `status` (enum: `pending` / `dispatched` / `failed`); `created_at`; `dispatched_at`. Phase 6 writes rows with `status = pending`; Phase 7 updates `status` to `dispatched` or `failed` after delivery.

- **RideSearchRequest** *(transient, not persisted)*: The passenger's search input — `origin` (PostGIS point), `destination` (PostGIS point), `desired_departure_at` (timestamp). Passed directly to the Phase 5 candidate generation engine.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Passengers can complete the full journey — search → view details → book a seat — in under 90 seconds on a standard mobile connection.
- **SC-002**: Ride search returns results within 4 seconds at p95 for a candidate pool of up to 500 scheduled rides (inclusive of the Phase 5 candidate generation call).
- **SC-003**: Booking creation is atomic — in 100% of concurrent booking tests on a single-seat ride, exactly one booking succeeds and all others receive a "no seats available" rejection; available seat counts never go negative.
- **SC-004**: 100% of booking creation attempts by unverified passengers are rejected before creating any database record.
- **SC-005**: Driver confirmation and rejection actions complete within 2 seconds at p95.
- **SC-006**: Booking cancellations that occur within 1 hour of departure are flagged `late_cancellation = true` in 100% of cases.
- **SC-007**: Pending bookings that exceed the 24-hour response window are automatically cancelled in the next background process run, with no manual intervention required.

---

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: The ride search endpoint MUST respond within 4 seconds at p95 under expected load (≤1,000 concurrent users), including the round-trip to the Phase 5 candidate generation engine.
- **NFR-002**: The booking creation endpoint MUST respond within 1 second at p95. Seat decrement and booking record creation MUST be executed within a single database transaction to guarantee atomicity.
- **NFR-003**: All booking endpoints MUST require a valid Supabase Auth JWT; unauthenticated requests MUST be rejected with HTTP 401.
- **NFR-004**: Passengers MUST only be able to read, create, or cancel their own bookings. Drivers MUST only be able to confirm, reject, or cancel bookings on rides they own. Row-level security policies in Supabase MUST enforce these boundaries at the database layer.
- **NFR-005**: The `Booking` entity MUST use a UUID primary key and be soft-deletable — booking records MUST NOT be hard-deleted; cancellation sets `status = cancelled` and records `cancelled_at`.
- **NFR-006**: The `BookingAuditLog` table MUST be append-only — no update or delete operations are permitted on audit entries. The audit trail MUST be complete: every status transition, regardless of trigger (passenger, driver, or system), MUST produce an audit log entry.
- **NFR-007**: `passenger_pickup_point` and `passenger_dropoff_point` MUST be stored as PostGIS geometry types. Application-level latitude/longitude arithmetic for spatial operations is prohibited (Constitution §Data Standards).
- **NFR-008**: The passenger-facing ride detail and search endpoints MUST NOT expose the driver's precise home address or any National ID data; only the driver's display name, profile photo, and verification badge are surfaced.
- **NFR-009**: The background process that auto-cancels expired pending bookings MUST run at least every 15 minutes and MUST complete within 30 seconds for a queue of up to 500 expired bookings.

---

## Dependencies *(mandatory)*

- **Internal**:
  - `008-route-intelligence` (Phase 5) — the Phase 5 candidate generation engine, CompatibilityResult contract, and fare calculation are direct runtime dependencies of ride search and booking creation. This phase cannot function without Phase 5's APIs being operational.
  - `004-ride-management` (Phase 4) — the `Ride` entity (status, available_seats, departure_time, route geometry) is the primary data source for search and detail views.
  - `003-auth-verification` (Phase 3) — passenger verification status (`approved`) is checked at booking creation. Supabase Auth JWTs are required for all endpoints.
  - `005-user-management` (Phase 3) — driver display name and profile photo used in ride detail and booking confirmation screens.

- **External**:
  - **OSRM routing service** — indirectly through Phase 5; must be running for search to return results.
  - **Phase 7 (Real-Time Transportation)** — notification delivery for booking events (confirmed, rejected, cancelled) is Phase 7's responsibility. This phase defines the notification contract (event type, payload, recipient IDs) that Phase 7 consumes; Phase 7 is a downstream dependency, not a prerequisite.

- **Data**:
  - Supabase PostgreSQL with PostGIS extension enabled (Phase 1).
  - `Ride` records from Phase 4 with PostGIS origin/destination points and route geometry calculated by Phase 5.
  - User profiles with display name and profile photo from Phase 3.
  - Verification status records from Phase 3.

---

## Out-of-Scope

- **AI ride ranking** — Phase 9 (AI Application) scores and reranks search candidates; this phase only consumes the result. This phase MUST define the handoff interface (how Phase 9 injects its ranked result into the search response), but the AI models themselves are Phase 9 scope.
- **Push notifications** — all notification delivery (booking confirmed, rejected, cancelled, driver response reminder) is Phase 7 scope. This phase defines the notification events and their payloads as a contract for Phase 7 to fulfill.
- **Live driver location during active ride** — real-time driver tracking is Phase 7 scope. This phase shows the static planned route geometry on the detail screen, not a live position.
- **Cash payment collection** — passengers pay drivers in cash at pickup. No in-app payment action exists. The platform records the agreed fare; collection is offline.
- **Commission deduction** — driver balance and commission management is Phase 8 scope.
- **Ratings and reviews** — post-trip passenger-to-driver and driver-to-passenger rating is deferred post-competition.
- **Seat quantity selection** — passengers book exactly one seat per booking for MVP. Multi-seat bookings are deferred.
- **Combined premium pickup AND premium dropoff** — requesting both premium options simultaneously on a single booking is not supported for MVP. Passengers choose one premium option or neither.
- **Waiting list or ride request posting** — passengers cannot post a "looking for a ride" request that drivers respond to. This is not a ride-hailing model (Constitution Principle I).
- **Booking modification** — once created, a booking cannot be modified. Passengers must cancel and rebook if they change their plans.
- **Fare negotiation** — the posted per-seat price is system-calculated and non-negotiable (Phase 5 mandate). No bidding or counter-offer mechanism exists.
- **Per-user rate limiting on search** — application-level rate limiting is deferred to Phase 12 (Production Readiness). The nginx gateway from Phase 4.1 provides connection-level protection for MVP.

---

## Technical Considerations

- The ride search endpoint is a thin orchestration layer: it forwards the passenger's search parameters to the Phase 5 candidate generation engine and returns the result. All route intelligence logic — candidate filtering, compatibility scoring, premium fee calculation, and default sort order — lives in Phase 5 and MUST NOT be re-implemented here.
- Booking creation MUST use a database-level transaction with a row lock on the `Ride` record to prevent race conditions when multiple passengers concurrently book the last seat. Application-level optimistic locking is not sufficient for this constraint.
- `passenger_pickup_point` and `passenger_dropoff_point` on the `Booking` entity MUST store the exact PostGIS geometry values from the Phase 5 CompatibilityResult for that search (the computed boarding/alighting points on the driver's route). These values are locked at booking time and do not change even if the driver's route is subsequently updated.
- The notification event contract this phase publishes to Phase 7 MUST be defined and documented before Phase 7 implementation begins. The contract specifies: event type, recipient user IDs, and payload structure. Phase 7 is the consumer; this phase is the producer.
- The driver-facing booking queue (pending confirmations) is rendered within the Main App under the driver-role routing established in Phase 4 (`apps/main` with role-based navigation). No separate driver app or new app shell is required.
- Row-level security policies in Supabase MUST enforce booking ownership at the database layer — passengers can only SELECT/UPDATE their own bookings; drivers can only UPDATE bookings for rides they own. Backend API authorization checks are a second layer, not the only layer (Constitution §Architecture Standards: databases are the source of truth).
- The `BookingAuditLog` table should be implemented with `INSERT`-only RLS policies; no application role should be granted `UPDATE` or `DELETE` on this table.
- The auto-expiry background process (FR-023) MUST be idempotent — running it twice on the same set of expired bookings MUST NOT create duplicate cancellations or audit entries.
- Phase 6 owns the `notification_events` table schema and write path. Phase 6's backend inserts rows; Phase 7 is the sole reader and updater of `status`. No other phase writes to this table. The `notification_events` table MUST be created as part of Phase 6's database migration, even if Phase 7 is not yet deployed — rows will queue safely until Phase 7 processes them.
- The ride-completion cascade (FR-031) MUST be implemented as a database-level trigger or a transactional backend handler that fires in the same operation as the ride status update — not as an eventual-consistency side effect. This ensures the `Ride.status = completed` and all associated `Booking.status = completed` transitions are atomically consistent.
- Premium option selection occurs on the ride detail screen, before the booking creation request is submitted. The frontend MUST send the selected option in the booking creation payload; the backend MUST re-validate that the premium flag is still valid (CompatibilityResult may have changed) and reject if no longer applicable.

---

## Assumptions

- **Single-seat bookings only**: Each booking reserves exactly one seat. Multi-seat bookings (e.g., a passenger booking two seats for herself and a colleague) are deferred to post-competition.
- **Booking expiry window**: Pending bookings auto-expire after 24 hours of no driver response. This window is a fixed system constant for MVP (not admin-configurable).
- **No seat hold during browsing**: There is no reservation or lock applied when a passenger views a ride detail screen. Seat availability is only enforced at the moment of booking creation. Passengers who browse slowly may encounter a "no seats available" response.
- **Fare currency and rounding**: All prices are in Egyptian Pounds (EGP) rounded to the nearest whole pound. The price displayed on search results, ride detail, and booking confirmation is the price locked at booking time.
- **Compatibility re-evaluation at booking time**: The CompatibilityResult from the original search is advisory. At booking creation, the system re-calls the Phase 5 compatibility engine to validate the passenger's chosen boarding/alighting points and premium selection against the current ride state. If compatibility has changed (e.g., route modified by driver), the booking creation may fail with a "route no longer compatible" message.
- **Driver notification of pending bookings**: Push notification delivery to the driver (informing them of a new pending booking) is Phase 7's responsibility. This phase assumes Phase 7 is operational before end-to-end booking confirmation flows can be tested; the booking can be created and the driver can act on it via the app's booking queue even if Phase 7 is not yet deployed.
- **Verified passengers only**: A passenger must have `verification_status = approved` (National ID reviewed and approved by admin) before they can search for or book rides. This aligns with Constitution Principle III (Trust Before Transportation).
- **Profile photo optional**: Driver profile photos are displayed where available but are not required for ride search or detail views to function. A placeholder avatar is shown when no photo exists.
- **Background process hosting**: The auto-expiry background process is assumed to run as a scheduled task within the FastAPI service (e.g., APScheduler or a cron-triggered endpoint). A dedicated worker queue is not required for MVP scale.
