# Feature Specification: Ride Management

**Feature Branch**: `004-ride-management`

**Created**: 2026-06-16

**Status**: Draft

**Input**: Phase 4 — Ride Management: driver ride creation, edit, cancel, and seat management.

## Clarifications

### Session 2026-06-17

- Q: Should `booked_seats` be a stored counter on the Ride record or derived at query time from Booking records? → A: Stored counter on the Ride record, initialized to 0 in Phase 4 and updated atomically by the Phase 6 booking system.
- Q: If the email delivery service fails when sending cancellation notifications, should the cancellation itself be blocked or proceed? → A: Cancellation always proceeds regardless of email outcome; notification emails are best-effort and failed deliveries are retried in the background.
- Q: How does a driver input origin and destination? → A: Map pin drop — driver taps a point on an interactive map; coordinates are captured directly from the tap and a human-readable address label is generated via reverse geocoding.

---

## Business Objective *(mandatory)*

Enable verified drivers to publish, modify, and manage the rides they are already planning to take, so that route-sharing supply exists on the platform before search, booking, and matching are introduced in later phases. This phase establishes the ride as the central record of the platform.

**Constitutional Domain**: Ride Creation

**Affected Applications**: Main App (driver ride creation, editing, cancellation, dashboard)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Create a Ride (Priority: P1)

A verified driver with a registered vehicle plans a trip they are already taking. They open the "Post a Ride" screen, enter their origin, destination, departure date and time, and the number of seats they're offering, then publish it. For this phase, the driver also enters a price per seat manually; system-calculated, fuel-cost-based pricing is planned for a later phase (see Out-of-Scope).

**Why this priority**: Without the ability to create a ride, no supply exists on the platform. Every other story in this phase, and the passenger-facing phases that follow, depend on rides existing.

**Independent Test**: Log in as a verified driver with a registered vehicle, drop a pin on the map for origin and another for destination, set a future departure time within the 2-day window, enter seat count and price, and submit. Verify a ride record is created with status `scheduled`, coordinates and address labels stored for both locations, and `available_seats` equal to the entered seat count.

**Acceptance Scenarios**:

1. **Given** a verified driver with an approved vehicle, **When** they submit a ride with a valid origin, destination, future departure time, seat count, and price, **Then** the ride is created with status `scheduled`.
2. **Given** a driver who has not completed identity or vehicle verification, **When** they attempt to create a ride, **Then** the system blocks the request at the backend with a "Complete verification first" error.
3. **Given** a driver entering identical origin and destination, **When** they submit, **Then** the system rejects the ride with a clear validation error.
4. **Given** a driver entering a departure time in the past, **When** they submit, **Then** the system rejects the ride with an error indicating departure must be in the future.
5. **Given** a driver entering a departure time more than 2 days from the current time, **When** they submit, **Then** the system rejects the ride with an error indicating rides can only be scheduled up to 2 days in advance.
6. **Given** a driver entering a seat count greater than their registered vehicle's passenger capacity, **When** they submit, **Then** the system rejects the request with a clear capacity error.
7. **Given** a driver who already has a `scheduled` or `in_progress` ride departing within 2 hours of the new ride's departure time, **When** they attempt to create the new ride, **Then** the system rejects it with a "conflicts with another ride" error.

---

### User Story 2 — Edit a Ride (Priority: P2)

A driver realizes a detail of an upcoming ride is wrong — the departure time slipped, the price needs adjusting, or they want to update the seat count — and edits the ride before it departs.

**Why this priority**: Plans change between posting and departure. Without editing, drivers would need to cancel and recreate rides for minor corrections, losing any forward-looking associations (e.g., future bookings).

**Independent Test**: Create a `scheduled` ride, edit its departure time and price, and verify the changes persist and are reflected on the ride dashboard, with the edit recorded in the ride's history.

**Acceptance Scenarios**:

1. **Given** a `scheduled` ride, **When** the owning driver edits its destination, departure time, seat count, price, or notes, **Then** the changes are saved and reflected immediately.
2. **Given** a ride with status `in_progress`, `completed`, or `cancelled`, **When** the driver attempts to edit it, **Then** the system blocks the edit with a status-appropriate error.
3. **Given** a `scheduled` ride, **When** the driver attempts to reduce total seats below the number of seats already booked, **Then** the system rejects the change with a clear error.
4. **Given** a successful edit, **When** it is saved, **Then** the system records which fields changed, the acting driver, and a timestamp.
5. **Given** a driver attempting to edit a ride that does not belong to them, **When** the request is made, **Then** the system rejects it with an authorization error.

---

### User Story 3 — Cancel a Ride (Priority: P3)

A driver can no longer take a planned trip and cancels the ride from their dashboard, providing a reason.

**Why this priority**: Drivers need a clear way to remove rides they can no longer fulfill, keeping the platform's available supply accurate and trustworthy.

**Independent Test**: Create a `scheduled` ride, cancel it with a reason, and verify its status changes to `cancelled`, it disappears from active listings, and the cancellation is recorded with a reason and timestamp.

**Acceptance Scenarios**:

1. **Given** a `scheduled` ride, **When** the owning driver cancels it and provides a reason, **Then** the ride's status becomes `cancelled` and the reason is stored.
2. **Given** a driver attempting to cancel without entering a reason, **When** they submit, **Then** the system requires a reason before the cancellation is accepted.
3. **Given** a ride with status `in_progress` or `completed`, **When** the driver attempts to cancel it, **Then** the system blocks the action with a status-appropriate error.
4. **Given** a cancelled ride, **When** the driver views their ride dashboard, **Then** the ride appears in a distinct "Cancelled" section, not among active rides.
5. **Given** a ride (cancelled manually or automatically) that has one or more passengers with a confirmed booking, **When** the cancellation is recorded, **Then** an apology email is sent to each affected passenger.

---

### User Story 4 — Seat Management (Priority: P4)

A driver manages how many seats they're offering on a ride, both at creation and afterward, and always sees an accurate count of seats still available.

**Why this priority**: Seat counts are the core supply unit that later phases (booking, matching) will consume. Getting seat tracking right now establishes the foundation those phases rely on.

**Independent Test**: Create a ride with 3 seats, verify `available_seats` is 3, then reduce total seats to 2, and verify `available_seats` updates to 2 without going negative or below any (currently zero) booked count.

**Acceptance Scenarios**:

1. **Given** a newly created ride, **When** it is saved, **Then** `available_seats` equals the entered `total_seats`.
2. **Given** a `scheduled` ride with no bookings, **When** the driver increases or decreases total seats within the vehicle's capacity, **Then** `available_seats` is recalculated accordingly.
3. **Given** a `scheduled` ride, **When** the driver attempts to set total seats to zero or a negative number, **Then** the system rejects the change.
4. **Given** any ride at any time, **When** its data is read, **Then** `available_seats` is never negative and never exceeds `total_seats`.

---

### User Story 5 — Driver Ride Dashboard (Priority: P5)

A driver opens their "My Rides" screen and sees all the rides they've created, with the ability to filter by status and drill into any ride's details and history.

**Why this priority**: Drivers need visibility into their own rides to manage them effectively; without a dashboard, the create/edit/cancel capabilities above have no discoverable entry point.

**Independent Test**: As a driver with rides in multiple statuses, open the dashboard, filter by "Scheduled," and verify only scheduled rides appear; open one ride and verify its full details and edit history are visible.

**Acceptance Scenarios**:

1. **Given** a driver with rides in different statuses, **When** they open their ride dashboard, **Then** they see all their rides grouped or filterable by status (scheduled, in progress, completed, cancelled).
2. **Given** a ride listing, **When** the driver views it, **Then** they see origin, destination, departure date/time, available/total seats, price per seat, and status at a glance.
3. **Given** a specific ride, **When** the driver opens its detail view, **Then** they see the full edit and status-change history for that ride.
4. **Given** a driver, **When** they attempt to view another driver's ride by direct reference, **Then** the system denies access.

---

### User Story 6 — Verification Revocation Handling (Priority: P6)

A driver who was previously verified has their identity verification or vehicle registration revoked or suspended by an admin (for example, after a complaint or a re-review). The platform immediately stops that driver from posting new rides and cleans up their existing upcoming rides so passengers aren't left waiting on a trip that won't happen.

**Why this priority**: Trust enforcement (Constitution Principle III) must hold continuously, not just at the moment a driver first signs up. Without this safeguard, a revoked driver could keep operating rides already on the platform.

**Independent Test**: As an admin, revoke a previously verified driver's verification while they have a `scheduled` ride with no bookings. Verify the ride is automatically cancelled with a system-generated reason, and that the driver is blocked from creating a new ride until an admin re-approves them.

**Acceptance Scenarios**:

1. **Given** a driver whose verification or vehicle registration is later revoked or suspended, **When** they attempt to create a new ride, **Then** the system blocks the request with a "Resolve your verification issue to continue" error.
2. **Given** a driver with one or more `scheduled` rides, **When** their verification or vehicle registration is revoked, **Then** every one of their `scheduled` rides is automatically cancelled with a system-generated reason.
3. **Given** an automatically cancelled ride that has passengers with confirmed bookings, **When** the cancellation occurs, **Then** each such passenger receives an apology email explaining the ride was cancelled.
4. **Given** a driver who was blocked after a revocation, **When** an admin re-approves their verification, **Then** the driver can create new rides again; their previously auto-cancelled rides remain cancelled and are not restored.

---

### Edge Cases

- What happens if a driver's vehicle is later un-registered or their identity verification is revoked after a ride is already `scheduled`? The driver is blocked from creating any new ride until an admin resolves the issue; all of that driver's `scheduled` rides are automatically cancelled with a system-generated reason, and an apology email is sent to every passenger with a confirmed booking on each cancelled ride.
- What if an admin re-verifies a driver after a revocation-triggered cancellation? The block on creating new rides is lifted, but previously auto-cancelled rides are not restored — the driver must create new rides if they still intend to travel.
- What if a driver tries to mark a ride `in_progress` before its scheduled departure time? The system rejects the action until the current time reaches the departure time.
- What if a driver tries to mark a ride `in_progress` exactly when the departure time arrives, without taking any action? The transition does not happen automatically; the ride remains `scheduled` until the driver explicitly confirms the start.
- What if a driver tries to mark a `scheduled` ride as `completed` directly, skipping `in_progress`? The system rejects the transition; status changes must follow `scheduled` → `in_progress` → `completed`.
- What if two simultaneous edit requests are made for the same ride? The first write wins; the second request is re-validated against the now-current ride state and may fail if it conflicts (e.g., seat count check).
- What if a driver tries to create a ride with a departure time more than 2 days in the future? The system rejects it with a clear error; rides may only be scheduled up to 2 days ahead for MVP.
- What happens to a `scheduled` ride if its departure time passes and the driver never marks it `in_progress`? It remains `scheduled` and visible to the driver as overdue; automatic status transitions based on time alone are out of scope for this phase.

---

## Requirements *(mandatory)*

### Functional Requirements

**Ride Creation**

- **FR-001**: System MUST allow only verified drivers with an approved, registered vehicle to create a ride, enforced server-side.
- **FR-002**: A ride MUST include origin, destination, departure date and time, total seats offered, and price per seat. Origin and destination MUST each be captured as a map pin drop by the driver; the system records the precise coordinates from the tap and generates a human-readable address label via reverse geocoding. Free-text address entry is not supported in this phase.
- **FR-003**: Origin and destination MUST be distinct locations; identical origin and destination MUST be rejected.
- **FR-004**: Departure date and time MUST be in the future at the time of creation and no more than 2 days (48 hours) after the time of creation.
- **FR-005**: Total seats offered MUST be a positive integer not exceeding the driver's registered vehicle's passenger seat count.
- **FR-006**: For this phase, price per seat MUST be entered manually by the driver as a positive monetary value in Egyptian Pounds. System-calculated, fuel-cost-based pricing is planned for a later phase once trip distance is available (see Out-of-Scope and Assumptions).
- **FR-007**: On creation, a ride's status MUST be set to `scheduled` and `available_seats` MUST equal `total_seats`.
- **FR-008**: A driver MUST NOT have more than one ride in `scheduled` or `in_progress` status with departure times within 2 hours of each other.

**Ride Editing**

- **FR-009**: A driver MAY edit a ride's destination, departure time, total seats, price per seat, and notes while the ride's status is `scheduled`.
- **FR-010**: Editing MUST be blocked once a ride's status is `in_progress`, `completed`, or `cancelled`.
- **FR-011**: Reducing total seats below the number of currently booked seats MUST be rejected.
- **FR-012**: Every successful edit MUST be recorded with the changed fields, the acting driver, and a timestamp.
- **FR-013**: A driver MUST NOT be able to edit a ride that does not belong to them, enforced server-side.

**Ride Cancellation**

- **FR-014**: A driver MAY cancel a ride while its status is `scheduled`.
- **FR-015**: Cancellation MUST require the driver to enter a cancellation reason before the action is committed.
- **FR-016**: On cancellation, the ride's status MUST be set to `cancelled`, and the reason and timestamp MUST be stored.
- **FR-017**: A ride with status `in_progress` or `completed` MUST NOT be cancellable.

**Verification & Vehicle Revocation Handling**

- **FR-018**: The system MUST continuously enforce driver and vehicle verification status, not only at signup — if a previously verified driver's identity verification or vehicle registration is later revoked or suspended by an admin, the driver MUST be immediately blocked from creating any new ride.
- **FR-019**: The block established in FR-018 MUST remain in effect until an admin re-approves the driver's verification or vehicle registration through the verification workflow established in `003-auth-verification`.
- **FR-020**: When a driver's verification or vehicle registration is revoked or suspended while they have one or more rides with status `scheduled`, the system MUST automatically cancel all of those rides, recording a system-generated cancellation reason (e.g., "Driver verification revoked").
- **FR-021**: Whenever a ride is cancelled — whether manually by the driver or automatically per FR-020 — and the ride has one or more passengers with a confirmed booking, the system MUST enqueue an email notification to each such passenger informing them of the cancellation and apologizing for the inconvenience. The cancellation MUST succeed and be persisted regardless of whether email queuing or delivery succeeds; failed emails MUST be retried in the background and MUST NOT block or roll back the cancellation. *(This rule has no effect until the booking system from Phase 6 exists; it is specified now so cancellation logic does not need to be revisited later.)*

**Ride Status Lifecycle & Seat Management**

- **FR-022**: A driver MAY mark a `scheduled` ride as `in_progress` only at or after its scheduled departure time, and only via an explicit driver confirmation action; the transition MUST NOT happen automatically merely because the departure time has passed.
- **FR-023**: A driver MAY mark an `in_progress` ride as `completed` via an explicit driver confirmation action.
- **FR-024**: Status transitions MUST follow the order `scheduled` → `in_progress` → `completed`, or `scheduled` → `cancelled`; no other transition is permitted.
- **FR-025**: The system MUST track `available_seats` as `total_seats` minus currently booked seats (booked seats default to 0 until the booking system, introduced in a later phase, is operational).
- **FR-026**: A driver MAY increase or decrease `total_seats` for a `scheduled` ride, within the vehicle's passenger capacity and not below the number of seats already booked.
- **FR-027**: The system MUST prevent `available_seats` from ever being negative or exceeding `total_seats`.

**Driver Ride Dashboard**

- **FR-028**: A driver MUST be able to view a list of their own rides, filterable by status (`scheduled`, `in_progress`, `completed`, `cancelled`).
- **FR-029**: Each ride listing MUST display origin, destination, departure date/time, available/total seats, price per seat, and status.
- **FR-030**: A driver MUST be able to view the full detail and change history of any of their own rides.
- **FR-031**: A driver MUST NOT be able to view, edit, or cancel rides belonging to other drivers, enforced server-side.

### Key Entities

- **Ride**: Unique identifier, reference to driver (User), reference to Vehicle, origin (location + address text), destination (location + address text), departure date/time, total seats offered, booked seats (stored counter, initialized to 0; incremented/decremented atomically by the Phase 6 booking system), available seats (derived as total seats minus booked seats), price per seat, status (`scheduled` | `in_progress` | `completed` | `cancelled`), cancellation reason (nullable; either a driver-entered reason or a system-generated reason such as "driver verification revoked"), cancellation source (`driver` | `system`), notes (optional), created timestamp, last updated timestamp.

- **RideHistoryLog**: Unique identifier, reference to Ride, acting user reference (nullable when system-triggered), action type (`created` | `edited` | `cancelled` | `started` | `completed`), changed fields (nullable, recorded on edits), reason (nullable, recorded on cancellation), timestamp.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A verified driver with a registered vehicle can publish a new ride in under 2 minutes.
- **SC-002**: 100% of ride creation attempts by unverified drivers or drivers without a registered vehicle are blocked at the server level.
- **SC-003**: Available-seat counts are accurate (equal to total seats minus booked seats) for 100% of rides at all times.
- **SC-004**: A driver can cancel an upcoming ride in under 30 seconds from the ride dashboard.
- **SC-005**: Zero instances occur of a single driver having two overlapping (within 2 hours) scheduled or in-progress rides.
- **SC-006**: 100% of ride edits and cancellations are traceable to an acting user (or "system"), a timestamp, and the changed data.
- **SC-007**: 100% of a driver's `scheduled` rides are automatically cancelled within 1 minute of that driver's verification or vehicle registration being revoked.
- **SC-008**: 100% of ride creation attempts with a departure time beyond 2 days from the current time are rejected.

---

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Ride creation, edit, and cancellation endpoints MUST respond within 500ms at p95 under expected load (≤1,000 concurrent users).
- **NFR-002**: Ride origin and destination MUST be persisted using PostGIS geography/geometry point types, not plain latitude/longitude columns.
- **NFR-003**: Ride status transitions MUST be validated and enforced server-side; clients MUST NOT be able to set an arbitrary status value directly.
- **NFR-004**: Ride history logs MUST be append-only and not editable or deletable by drivers.
- **NFR-005**: A driver's full ride list (up to 200 rides) MUST render within 2 seconds on the dashboard.
- **NFR-006**: Cancellation notification emails MUST be enqueued within 5 minutes of the triggering cancellation event and retried on failure; email delivery outcome MUST NOT affect the persistence of the cancellation itself.

---

## Dependencies *(mandatory)*

- **Internal**:
  - `001-platform-foundation` — Supabase project, FastAPI backend, monorepo structure, and the Main App must be operational.
  - `003-auth-verification` — Drivers must be identity-verified and have an approved, registered Vehicle before creating rides; admin re-approval/suspension actions from that phase are reused to resolve revocation blocks here.

- **External**:
  - A transactional email delivery service (e.g., SendGrid, Amazon SES, or equivalent) is required to send passenger cancellation notification emails. This is a new external dependency not yet present in the approved technology stack and must be selected and provisioned before FR-021 can be implemented.
  - A map and reverse-geocoding service (e.g., Mapbox, Google Maps, or OpenStreetMap/Nominatim) is required to render the interactive map for pin drop input and to convert coordinates into human-readable address labels. This is a new external dependency introduced in this phase.

- **Data**:
  - Supabase PostgreSQL database with PostGIS extension enabled.
  - Row Level Security (RLS) policies required so drivers can only read and modify their own rides.

---

## Out-of-Scope

- Route overlap, proximity, and detour calculations, and OSRM-based travel time/distance — covered by Phase 5 (Route Intelligence).
- System/AI-calculated, fuel-cost-based pricing (price per seat = trip fuel cost ÷ total seats, plus a 20% platform commission and safety margin, with the driver collecting the full per-seat amount from passengers in cash) — deferred to Phase 5, because it requires trip distance which depends on the OSRM integration built in that phase. Manual driver-entered pricing is used as an interim measure in this phase (FR-006).
- Automatic ride completion triggered by all passengers confirming arrival, or by a timeout after the expected arrival time — both are deferred. The passenger-confirmation path depends on the booking system (Phase 6); the timeout path depends on an OSRM-derived expected arrival time (Phase 5). Noted here for implementation once those phases land; only manual driver-triggered completion (FR-023) is available in this phase.
- Passenger ride search, booking, and seat reservation — covered by Phase 6 (Passenger Experience).
- AI-based price recommendations and ride ranking beyond the fuel-cost formula above — covered by Phase 9 (AI Application).
- Real-time location tracking and live status push notifications — covered by Phase 7 (Real-Time).
- Recurring or repeating ride schedules — only single, one-time rides are supported for MVP.
- Intermediate route stops or waypoints — a ride is defined by a single origin and destination only for MVP.

---

## Technical Considerations

- Ride origin and destination MUST use PostGIS geography/geometry point types (Constitution §Data Standards).
- Ride creation, editing, cancellation, and status-transition business logic MUST live in the FastAPI backend; the frontend issues requests against backend APIs only and MUST NOT enforce these rules exclusively client-side (Constitution §Architecture Standards).
- RLS policies MUST restrict ride read/write access to the owning driver; admin read access for support/audit purposes may be added in a later admin-focused spec.
- Ride history logging follows the same append-only audit pattern established for verification actions in `003-auth-verification` (Constitution §Auditability).
- Seat capacity validation MUST reference the driver's registered Vehicle entity created in `003-auth-verification`.
- Verification/vehicle revocation events MUST trigger ride cancellation synchronously (or via an immediately-processed background job), not as part of an unrelated batch process, to satisfy SC-007.
- Email delivery for cancellation notifications and map/reverse-geocoding for pin drop input are new external dependencies outside the currently approved technology stack table (Constitution §Technical Standards); both must be formally selected and added to the stack before their respective requirements can be implemented.
- This phase preserves Constitution Principle I (Driver-First Route Sharing): rides represent trips drivers are already taking, not requests passengers initiate.
- This phase preserves Constitution Principle III (Trust Before Transportation): verification enforcement is continuous, not just a one-time gate at signup.

---

## Assumptions

- A ride is defined by a single origin and a single destination; multi-stop routes are a future enhancement once route intelligence (Phase 5) is integrated.
- Drivers operate exactly one vehicle per account (per `003-auth-verification`), so seat capacity validation uses that single registered vehicle.
- Price per seat is entered manually in Egyptian Pounds (EGP) as an interim measure for this phase. The target pricing model — system/AI-calculated as trip fuel cost divided by total seats offered, plus a 20% platform commission and safety margin, with the driver collecting the full per-seat price from each passenger in cash — requires trip distance from the OSRM integration in Phase 5 and will replace manual entry at that point without changing the rest of this phase's ride lifecycle.
- A 2-hour buffer between a driver's ride departure times is a reasonable default to prevent accidental double-booking before real route-duration intelligence is available; this may be tuned once Phase 5 is integrated.
- Rides may only be created up to 2 days (48 hours) in advance of their departure time, reflecting that drivers post trips they are already planning to take in the near term rather than long-range recurring schedules.
- `in_progress` and `completed` status changes are manually triggered by the driver for MVP; automated transitions based on passenger confirmation or elapsed time past the expected arrival are deferred to later phases once their dependencies (Phase 5 ETA, Phase 6 booking) exist.
- `booked_seats` (and therefore the gap between `total_seats` and `available_seats`) remains 0 for all rides until the booking system (Phase 6) is implemented; this phase only establishes the field and its invariants.
- Verification and vehicle revocation are admin-triggered actions performed through the `003-auth-verification` admin dashboard; this phase does not introduce a new revocation mechanism, only reacts to it.
