# Feature Specification: Ride Preferences and Round Trips

**Feature Branch**: `035-ride-preferences`  
**Created**: 2026-09-17  
**Status**: Clarified  
**Input**: User description: "Add women-only rides with gender-based booking eligibility, and allow drivers to post one-way or round-trip rides with a return date and time."

## Business Objective

Let drivers express the passenger eligibility and travel direction of a ride, while ensuring the platform enforces the women-only safety rule at the booking boundary.

**Constitutional Domain**: Authentication, Ride Creation, and Passenger Booking.  
**Affected Applications**: Passenger app, driver app, API, shared types, and database.

## User Scenarios & Testing

### User Story 1 — Complete a profile with gender (Priority: P1)

During account onboarding, a user selects a required gender value. The platform stores it with the user's private profile so it can make women-only booking eligibility decisions.

**Independent Test**: A new user cannot complete onboarding without selecting gender; after completion, their authenticated profile contains the selected value.

**Acceptance Scenarios**:

1. **Given** a new user is completing their profile, **When** they select a gender and submit valid profile details, **Then** the selected gender is saved.
2. **Given** a new user has not selected a gender, **When** they submit the profile form, **Then** the form clearly requires a selection and does not complete onboarding.

---

### User Story 2 — Post a women-only ride (Priority: P1)

A driver whose recorded gender is woman can decide whether a newly posted ride is available only to women, and the preference remains visible wherever the ride is managed or discovered.

**Independent Test**: A driver creates a women-only ride and later sees the designation on the ride details; a non-women-only ride remains open to all genders.

**Acceptance Scenarios**:

1. **Given** a driver whose gender is woman creates a ride, **When** they enable the women-only option, **Then** the ride persists as women-only.
2. **Given** a driver creates a ride without enabling the option, **When** it is saved, **Then** it is not restricted by gender.
3. **Given** a driver whose gender is not woman creates or edits a ride, **When** they try to enable women-only, **Then** the API rejects the change.

---

### User Story 3 — Enforce women-only booking eligibility (Priority: P1)

A passenger who is not recorded as a woman cannot reserve a seat on a women-only ride. The API, not only the interface, enforces this rule.

**Independent Test**: Attempting to book a women-only ride using an ineligible profile fails without reserving a seat; a woman can use the normal booking flow.

**Acceptance Scenarios**:

1. **Given** a women-only ride with seats available and a passenger whose gender is woman, **When** they request a seat, **Then** the normal booking workflow proceeds.
2. **Given** a women-only ride with seats available and a passenger whose gender is not woman, **When** they request a seat, **Then** the request is rejected and the available-seat count is unchanged.

---

### User Story 4 — Post a round trip (Priority: P1)

A driver can choose whether a ride is one-way or round trip. When selecting round trip, they choose the return date/time, seat count, and price. The outbound and return legs are separately represented, discovered, and booked.

**Independent Test**: A driver can post a round trip only with a valid return departure; the saved ride shows both outbound and return timings.

**Acceptance Scenarios**:

1. **Given** a driver selects one-way, **When** they submit a valid ride, **Then** no return departure is required or stored.
2. **Given** a driver selects round trip, **When** they omit the return date or time, **Then** they cannot submit the ride.
3. **Given** a driver selects round trip with a return departure after the outbound departure and valid return seat/price details, **When** they submit, **Then** the system creates a linked outbound and return ride, each available for independent booking.

---

### User Story 5 — Adjust one recurring round-trip occurrence (Priority: P2)

A driver can keep a standard weekly outbound and return schedule for a recurring round trip, while changing both timings for one specific date without changing the rest of the series.

**Independent Test**: A driver changes the outbound and return timings for one future recurring occurrence and confirms that other dates still use the standard schedule and each leg remains independently bookable.

**Acceptance Scenarios**:

1. **Given** a recurring round-trip series, **When** the driver edits one eligible future occurrence's outbound and return timings, **Then** only that date's linked outbound and return rides change.
2. **Given** a driver changes one occurrence, **When** later occurrences are generated, **Then** they continue to use the series' standard outbound and return times.
3. **Given** a selected occurrence has bookings or is beyond the established edit cutoff, **When** the driver attempts the timing override, **Then** the existing edit protections prevent an unsafe change.

## Edge Cases

- A legacy account with no gender must not bypass the women-only booking restriction.
- Changing an existing ride's women-only or journey-direction setting after bookings exist must preserve safety and booking consistency.
- A return departure at or before the outbound departure is invalid.
- The established driver overlap rule must account for the return leg of a round trip.
- A recurring occurrence override must move both linked legs together and must not alter other dates in the series.

## Requirements

### Functional Requirements

- **FR-001**: The onboarding profile flow MUST require and persist a gender value for new users.
- **FR-002**: Gender MUST remain private profile data and MUST NOT be exposed in public-profile responses or ride listings.
- **FR-003**: Drivers MUST be able to designate a ride as women-only or unrestricted when creating it.
- **FR-003a**: Only a driver whose recorded gender is woman MAY create or change a ride to women-only; the backend MUST enforce this rule.
- **FR-004**: The ride create, edit, detail, dashboard, discovery, and booking data contracts MUST expose the women-only designation where needed to make and understand booking decisions.
- **FR-005**: The backend MUST reject a booking for a women-only ride unless the booking passenger's recorded gender is woman; rejection MUST not reserve seats, charge funds, or create a booking.
- **FR-006**: Drivers MUST be able to designate a ride as one-way or round trip when creating it.
- **FR-007**: A round trip MUST require a return departure date and time later than the outbound departure. A one-way ride MUST have no return departure.
- **FR-008**: The backend MUST validate and persist journey direction and return departure, create linked outbound and return ride records for a round trip, and enforce all ride-creation constraints against both scheduled legs.
- **FR-008a**: The outbound and return legs of a round trip MUST have independent seat inventory, price, booking, cancellation, and lifecycle state. Booking one leg MUST NOT reserve a seat on the other.
- **FR-009**: The UI MUST clearly distinguish a one-way ride from a round trip and show the return departure for round trips.
- **FR-010**: Existing rides must remain valid and behave as unrestricted one-way rides after deployment.
- **FR-011**: A recurring round-trip definition MUST store a standard outbound and return time shared by all of its selected weekdays.
- **FR-012**: The driver MUST be able to change the linked outbound and return timings for one eligible, generated recurring occurrence without changing the series definition or any other occurrence.
- **FR-013**: A recurring occurrence override MUST obey the existing per-ride edit cutoff and booking protections for both legs; it MUST be rejected if either linked leg cannot safely change.

### Clarifications

- **CQ-001 (resolved)**: Only a driver whose recorded gender is woman may post a women-only ride.
- **CQ-002 (resolved)**: A round trip creates independently bookable outbound and return legs, each with its own seat inventory, price, bookings, cancellation, and lifecycle.
- **CQ-003 (resolved)**: A recurring round trip has standard outbound and return times shared by all selected weekdays; a driver can override both times for one eligible generated date without changing the rest of the series.
- **CQ-004 (resolved)**: A driver selects the return leg's seat count and price separately from the outbound leg.

### Key Entities

- **Profile gender**: Private self-declared value used solely for booking-eligibility decisions in this feature.
- **Ride eligibility preference**: Whether the posted ride is unrestricted or women-only.
- **Ride journey preference**: Whether the posted ride is one-way or round trip, with a linked independently bookable return ride for a round trip.
- **Recurring occurrence override**: A date-specific replacement for a recurring round trip's linked outbound and return departure times.

## Success Criteria

- **SC-001**: A non-woman cannot create a successful booking or seat reservation for a women-only ride through any API client.
- **SC-002**: A driver can post either ride type with all required details in one submission, with independently bookable linked legs for a round trip.
- **SC-003**: A round trip cannot be saved with a missing or non-later return departure.
- **SC-004**: Existing one-way unrestricted rides remain readable and bookable after the change.
- **SC-005**: A driver can safely update one eligible recurring round-trip date without changing any other date's times.

## Non-Functional Requirements

- **NFR-001**: Booking eligibility is enforced transactionally by the API before any seat, wallet, or booking mutation.
- **NFR-002**: Gender is protected as private profile information under existing profile access controls.
- **NFR-003**: Ride create, edit, discovery, and booking endpoints retain their established performance targets.

## Dependencies

- **Internal**: Existing authentication and profile onboarding; ride creation/editing; passenger ride discovery; booking seat-reservation transaction; existing ride overlap validation.
- **Data**: Existing `profiles`, `rides`, and `bookings` tables and their migrations/RLS policies.

## Out of Scope

- Identity-document verification of gender.
- Gender-based matching or ranking beyond the women-only booking restriction.
- Different routes for the return leg; the return uses the outbound route in reverse.
- Per-weekday outbound/return-time patterns within one recurring definition; drivers create separate recurring definitions for distinct weekly patterns.
- Editing historic account gender without a separate product decision.

## Assumptions

- The current product will use the existing profile-onboarding step for gender collection.
- Existing profiles will require a safe compatibility path before they can book women-only rides.
- A missing gender on a legacy profile makes that user ineligible to post or book a women-only ride until it is collected through the existing profile experience.
- A return leg uses the outbound route in reverse; a separate route-selection experience is outside this feature.
