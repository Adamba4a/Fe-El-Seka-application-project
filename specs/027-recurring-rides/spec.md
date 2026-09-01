# Feature Specification: Recurring Rides

**Feature Branch**: `027-recurring-rides`

**Created**: 2026-08-31

**Status**: Draft

**Input**: User description: "Recurring Rides (feature 027-recurring-rides) — a driver posts one recurring ride definition covering a whole week (the days of the week they drive, a fixed route, and a seat count) instead of creating a separate one-off ride for each day. Passengers search and book individual day instances of that recurring ride the same way they book a normal ride today. A driver can cancel a single day's instance without cancelling the whole recurring series, using the same cancellation mechanism/consequences as cancelling a normal one-off ride. Part of the Students/Employees Pivot (specs 025-028): commuters (students, employees) travel the same route on the same days most weeks, so recurring rides remove the friction of re-posting an identical ride every single day."

## Business Objective *(mandatory)*

Let a driver who repeats the same commute on the same days every week post it once instead of re-creating an identical one-off ride every day, reducing driver posting friction and keeping the ride pool populated with predictable, bookable commute options for the passenger side of the same pivot (org-verified students/employees).

**Constitutional Domain**: Ride Creation / Ride Management (extends the existing one-off Ride entity with a recurring definition and day instances)

**Affected Applications**: Main App (Driver experience — defining and managing a recurring ride, cancelling a single day; Passenger experience — searching and booking a specific day's instance exactly as with a normal ride). Admin Panel is not directly affected beyond existing ride-visibility tooling already covering rides generically.

---

## Clarifications

### Session 2026-08-31

- Q: When a driver ends a recurring definition entirely, what happens to its already-booked upcoming day instances? → A: Ending the series only stops future generation — already-generated instances (booked or not) run their course untouched unless the driver cancels each one individually via the existing single-instance cancellation mechanism (FR-006).
- Q: Can one recurring ride definition have a different route/departure time per selected day, or is one fixed route+time+seat-count shared across all its selected days? → A: One fixed route, departure time, and seat count shared across all selected days per definition; a driver wanting different patterns on different days creates a separate recurring definition per pattern.
- Q: When a driver edits a recurring definition's route/time/seats, what happens to already-generated day instances that have zero bookings yet and haven't hit the edit cutoff? → A: They are updated in place to the new values — only instances with at least one confirmed booking keep their pre-edit locked details; this matches how editing a normal one-off ride already behaves.
- Q: When a driver's vehicle/verification becomes ineligible mid-series (FR-012), what happens to already-generated, unbooked future instances that exist at that moment? → A: They are immediately hidden/unbookable, same as an ineligible driver being unable to post a new one-off ride today; already-booked instances are untouched — existing bookings are not cancelled just because eligibility lapsed.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Driver Defines a Recurring Ride (Priority: P1)

A driver who travels the same route on the same days most weeks creates a single recurring ride definition: the route (origin, destination, stops), the days of the week they drive it, a departure time, and a seat count — instead of posting a separate ride for each day.

**Why this priority**: Nothing else in this feature works without a recurring definition to generate day instances from. This is the foundation every other story depends on.

**Independent Test**: Can be fully tested by having a driver create a recurring ride definition selecting 2+ days of the week, then confirming a bookable day instance exists on each of the next occurrences of those selected days — delivers standalone value (recurring instances appear without the driver re-posting) even before cancellation or edit logic is tested.

**Acceptance Scenarios**:

1. **Given** a driver with a verified vehicle, **When** they define a recurring ride with a route, one or more days of the week, a departure time, and a seat count, **Then** the system creates a bookable day instance for the next upcoming occurrence of each selected day, and continues generating each subsequent week's instance as prior ones pass.
2. **Given** a driver defining a recurring ride, **When** they select zero days of the week, **Then** the system rejects the definition and requires at least one day to be selected.
3. **Given** a driver already offering a recurring ride, **When** they view their rides list, **Then** individual day instances are visibly grouped or labeled as belonging to the same recurring series, distinguishing them from one-off rides.

---

### User Story 2 - Passenger Books a Single Day Instance (Priority: P1)

A passenger searches for rides and finds a specific day's instance of a recurring ride, then books a seat on it using the exact same search and booking flow used for a normal one-off ride today.

**Why this priority**: This is the entire point of the feature from the passenger side — a recurring definition that can't be found and booked delivers no value. Depends on User Story 1 producing bookable instances.

**Independent Test**: Can be fully tested by searching for rides on a date matching one of a recurring ride's active days, confirming that day's instance appears in results, and completing a booking on it exactly as with a normal ride.

**Acceptance Scenarios**:

1. **Given** a recurring ride with an upcoming instance on a given date, **When** a passenger searches for rides covering that date and route, **Then** that day's instance appears in search results indistinguishably bookable from a one-off ride (same booking flow, seat selection, pricing, and confirmation).
2. **Given** a passenger viewing a recurring ride's day instance, **When** they open its detail page, **Then** they can see it is part of a recurring series (e.g., which other days the driver runs the same route) without that information blocking or complicating the booking action itself.
3. **Given** a passenger who has booked one day instance of a recurring ride, **When** they search again for a different day the same recurring ride runs, **Then** they can book that separate day's instance independently — a booking on one day does not consume or reserve a seat on any other day.

---

### User Story 3 - Driver Cancels a Single Day's Instance (Priority: P1)

A driver who can't make one specific day (e.g., a one-off conflict) cancels just that day's instance, leaving the rest of the recurring series (past history and future weeks' instances on the other selected days, and future weeks' instances on the same day) untouched.

**Why this priority**: Without single-day cancellation, a driver's only option for a one-time conflict would be to cancel or pause the entire series, destroying already-booked seats on unrelated days. This is core to the feature being usable in practice, hence P1 alongside Stories 1–2.

**Independent Test**: Can be fully tested by cancelling one specific day's instance of a recurring ride that has other upcoming instances, then confirming that instance shows as cancelled (with the same passenger-facing consequences as cancelling a one-off ride) while the recurring definition keeps generating instances for its other selected days and future weeks.

**Acceptance Scenarios**:

1. **Given** a specific day's instance of a recurring ride, **When** the driver cancels that instance, **Then** the same cancellation mechanism and consequences that apply to a one-off ride cancellation apply here (booked passengers are notified and refunded/reversed per existing cancellation rules), and no other instance of the recurring series is affected.
2. **Given** a driver has cancelled one day's instance, **When** the next occurrence of that same weekday arrives, **Then** a new bookable instance for that weekday is generated as normal — a single-day cancellation does not remove that weekday from the recurring definition going forward.
3. **Given** a driver wants to stop offering the recurring ride entirely, **When** they end the recurring definition, **Then** no further future instances are generated, while every already-generated instance (booked or not) remains untouched and continues to run its own course — ending the series is not itself a cancellation, and any of those instances is only cancelled if the driver separately cancels it via Scenario 1.

---

### Edge Cases

- What happens when a driver edits the recurring definition's route, time, or seat count? Edits apply to future instances not yet generated or not yet departed, subject to the same ride-edit cutoff window already enforced for one-off rides; already-booked instances keep the locked price/details a passenger booked under, consistent with how editing a one-off ride never changes an existing booking's locked price.
- What happens when a driver's vehicle or verification status becomes invalid partway through a recurring series? Future instance generation stops and any already-generated, unbooked instance becomes immediately unsearchable/unbookable until eligibility is restored (already-booked instances are untouched), mirroring the eligibility checks already enforced when posting a one-off ride.
- What happens if a driver tries to define two recurring rides with heavily overlapping days/times/routes? No new restriction is introduced — this is treated the same as a driver posting two overlapping one-off rides today (allowed, at the driver's own discretion).
- How far in advance are future day instances visible/bookable? A rolling window is generated (see Assumptions) rather than generating every future week indefinitely.
- What happens when a recurring ride's day instance passes with zero bookings? It simply lapses the same way an unbooked one-off ride does today; no special handling needed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let a driver define a single recurring ride covering a route (origin, destination, stops), one or more selected days of the week, a departure time, and a seat count, in one creation flow.
- **FR-002**: System MUST reject a recurring ride definition that selects zero days of the week.
- **FR-003**: System MUST automatically generate a bookable day instance for each selected day of the week, for a rolling forward window, without requiring the driver to manually re-post each week.
- **FR-004**: System MUST make each generated day instance searchable and bookable through the exact same search and booking flow already used for one-off rides — no new passenger-facing booking mechanism is introduced.
- **FR-005**: System MUST allow a booking made on one day instance to be entirely independent of any other day instance in the same recurring series — booking or cancelling one day's seat MUST NOT affect seat availability on any other day.
- **FR-006**: System MUST allow a driver to cancel a single day's instance without ending the recurring definition, using the platform's existing ride-cancellation mechanism and consequences (passenger notification, refund/reversal per current cash and sponsored cancellation rules) applied to just that instance.
- **FR-007**: System MUST continue generating future instances for a weekday after a single instance of that weekday has been cancelled — a single-day cancellation MUST NOT remove that day from the recurring definition.
- **FR-008**: System MUST allow a driver to end a recurring definition so that no further future instances are generated, while leaving every already-generated instance (past, booked, or unbooked upcoming) unaffected — ending the definition is not itself a cancellation — except through that instance's own individual cancellation per FR-006.
- **FR-009**: System MUST visibly indicate, on both the driver's ride list and the passenger-facing ride detail view, that a given day instance is part of a recurring series rather than a one-off ride.
- **FR-010**: System MUST apply the same driver-eligibility checks (verified vehicle, verification status) to recurring ride definitions and their generated instances as already apply to one-off ride creation.
- **FR-011**: System MUST let a driver edit a recurring definition's route, departure time, or seat count, and MUST apply the edit to both not-yet-generated future instances and already-generated instances that have zero confirmed bookings and have not yet passed the existing ride-edit cutoff window; the edit MUST NOT alter the locked details of any instance with at least one confirmed booking.
- **FR-012**: System MUST stop generating new future instances of a recurring ride if the driver's vehicle or verification status becomes ineligible, and MUST immediately make any already-generated, not-yet-booked instance unsearchable and unbookable for as long as the driver remains ineligible; instances with at least one confirmed booking are unaffected. Generation and visibility resume automatically once eligibility is restored.

### Key Entities *(include if feature involves data)*

- **Recurring Ride Definition**: A driver's reusable ride template — route, selected days of the week, departure time, seat count, and active/ended status — that generates individual day instances.
- **Ride Day Instance (existing Ride entity, extended)**: A single day's occurrence of a recurring ride definition; behaves exactly like a one-off Ride for search, booking, pricing, and cancellation purposes, with an added link back to its parent Recurring Ride Definition.
- **Booking (existing entity, unchanged)**: Continues to reference a single Ride Day Instance exactly as it references a one-off ride today; no schema meaning changes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A driver can set up a full week's worth of recurring rides in under 3 minutes, versus repeating a full one-off ride-creation flow once per day.
- **SC-002**: A passenger can find and book a specific day's instance of a recurring ride in the same number of steps as booking a one-off ride today.
- **SC-003**: 100% of single-day cancellations leave every other instance in the same recurring series (past, currently booked, and future) unaffected.
- **SC-004**: 100% of generated day instances carry forward the driver's defined route, time, and seat count accurately until the driver edits or ends the definition.

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Generation of upcoming day instances MUST be reliable enough that no selected weekday silently stops producing a bookable instance while the recurring definition remains active and the driver remains eligible.
- **NFR-002**: Recurring-ride search and booking MUST perform within the same response-time envelope already established for one-off ride search and booking — no additional latency introduced by the recurring layer.
- **NFR-003**: Cancelling a single day's instance MUST NOT be capable of cascading a data change to any other instance's booking or pricing state.

---

## Dependencies *(mandatory)*

- **Internal**: Ride Creation/Management domain (`ride_service.py`) — day instances reuse the existing Ride entity, creation, edit-cutoff-window, and cancellation logic; Ride Booking domain (`booking_service.py`) — bookings on day instances use the existing booking flow unchanged; Organization-Only Access (Spec 025) — booking a day instance still requires the platform-wide org-email verification gate already in effect for all rides.
- **External**: None new — route calculation continues to rely on the existing OSRM routing service already required for one-off rides.
- **Data**: No new external data dependency; uses the platform's existing PostgreSQL database.

---

## Out-of-Scope

- Recurring rides scoped to a sponsored group (Spec 026) — this spec covers general recurring rides only; combining recurring generation with sponsored-group scoping is a future enhancement, not required for v1.
- Passenger-side recurring bookings (auto-booking the same seat every week without re-booking) — out of scope for this iteration; passengers book each day instance individually.
- Bulk/partial editing of only some future instances while leaving others on the old definition (e.g., "change Tuesdays only starting next month") — an edit applies uniformly to all not-yet-generated/not-yet-cutoff instances.
- Any change to how one-off (non-recurring) ride creation, search, or cancellation works — this spec only adds a recurring variant alongside existing mechanics.

---

## Technical Considerations

- Day instance generation should reuse the existing Ride entity/table rather than introducing a parallel ride type, per Principle VI (modular, non-duplicative architecture) — a generated instance is a Ride row linked to its parent Recurring Ride Definition.
- Single-day cancellation must call the existing `cancel_ride` mechanism on that specific instance's Ride row, not a new cancellation code path, so cash and sponsored cancellation consequences (already covered by Spec 026's settlement/reversal logic) apply unchanged.
- Route feasibility for each generated instance must still be computed via OSRM, consistent with Principle II — the recurring definition stores the route once, but instance generation is not exempt from the platform's route-intelligence requirement.

---

## Assumptions

- The forward generation window is 2 weeks of upcoming instances at any time, refreshed as instances pass — long enough for a passenger to plan ahead, short enough to avoid generating rides far past a driver's likely eligibility/pricing changes; exact window is an implementation default, not user-specified.
- A recurring ride definition has a single fixed route, departure time, and seat count shared across all its selected days for v1 (confirmed, see Clarifications) — a driver wanting different times/routes on different days creates a separate recurring definition per distinct pattern.
- Existing driver fare-override (Spec 023) and ride-edit cutoff window behavior apply to recurring day instances identically to one-off rides; no new pricing or timing rule is introduced.
- A driver may run multiple independent recurring ride definitions simultaneously (e.g., different routes on different days); the platform does not limit a driver to one active recurring definition.
