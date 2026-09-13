# Feature Specification: Ride Auto-Completion Timeout

**Feature Branch**: `031-ride-auto-completion`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "We need to add some things related to time, like if a ride has not started or started but not completed, it should be signed completed and its consequences should happen, reservations, etc, after amount of time, we need to make this. And especially for the recurring rides, old rides should be completed, not like the error happened of the 5 past rides."

## Business Objective *(mandatory)*

Ensure no ride can be left stuck indefinitely in a non-terminal state (`scheduled` past its departure time, or `in_progress` with no completion) because the driver never acted. After a grace period, the system automatically finalizes such a ride to `completed` with the exact same consequences as a driver manually completing it — commission charged, wallet reservation released, confirmed bookings finalized, passengers notified — holding the driver accountable rather than leaving the ride, its passengers, and its held funds in limbo. Applies uniformly to driver-created one-off rides and recurring-ride-generated instances alike (this is the general fix for the class of bug discovered 2026-09-13, where a recurring series' past-due unbooked instances stayed `scheduled` for a week until manually cleaned up).

**Constitutional Domain**: Ride Management / Financial System (commission & wallet reservations)

**Affected Applications**: Shared (`services/api`) — backend-only. Driver App and Passenger App receive the existing ride-list/notification behavior for a completed ride; no new UI is required.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A ride the driver never started gets auto-completed (Priority: P1)

As the platform, when a ride's departure time has passed by more than the not-started grace period and the driver never tapped "Start," the ride is automatically finalized as completed — the driver is charged commission for any confirmed bookings exactly as if the ride had run, the held wallet reservation is released, and affected passengers are notified the ride is finalized. The driver is held accountable for failing to run a ride they committed to, rather than being let off with a free cancellation.

**Why this priority**: This is the scenario that produced the discovered bug — rides sit `scheduled` forever, holding reservations and leaving passengers with no resolution. It is the most common and most damaging case (affects real driver commission and passenger trust).

**Independent Test**: Create a ride with a confirmed booking, let its departure time pass without starting it, wait past the not-started grace period, and confirm the ride transitions to `completed`, the driver's wallet reflects the commission charge and released reservation, and the passenger's booking is finalized and notified — with no manual action taken.

**Acceptance Scenarios**:

1. **Given** a `scheduled` ride with one or more confirmed bookings whose departure time is more than the not-started grace period in the past, **When** the automatic sweep runs, **Then** the ride is marked `completed`, commission is charged for each confirmed cash booking, the wallet reservation for that ride is released, each confirmed booking is transitioned to completed, and each affected passenger receives the existing ride-completed notification.
2. **Given** a `scheduled` ride with zero confirmed bookings whose departure time is more than the not-started grace period in the past, **When** the automatic sweep runs, **Then** the ride is marked `completed` and its wallet reservation is released, with no commission charged (nothing to charge) and no passenger notifications sent.
3. **Given** a `scheduled` ride still has one or more `pending` (not yet accepted/declined) booking requests when the sweep finalizes it, **When** the ride is auto-completed, **Then** those pending requests are expired, the same way they are when a driver manually starts a ride.

---

### User Story 2 - A ride the driver started but never completed gets auto-completed (Priority: P1)

As the platform, when a ride has been `in_progress` for longer than the in-progress grace period without the driver tapping "Complete," the ride is automatically finalized as completed with the same consequences as if the driver had tapped it — the ride almost certainly happened, the driver simply forgot to close it out.

**Why this priority**: Equally important as User Story 1 — an in-progress ride holds its reservation and leaves confirmed passengers unable to rate their trip or receive loyalty points until it's finalized.

**Independent Test**: Start a ride, let more time than the in-progress grace period pass without completing it, and confirm the ride transitions to `completed` with the same commission/reservation/notification consequences as a manual completion, without manual action.

**Acceptance Scenarios**:

1. **Given** an `in_progress` ride whose `started_at` is more than the in-progress grace period in the past, **When** the automatic sweep runs, **Then** the ride is marked `completed` with the identical consequences (commission charge, reservation release, booking finalization, notification) as if the driver had tapped "Complete."
2. **Given** an `in_progress` ride whose estimated route duration is longer than the in-progress grace period itself, **When** the sweep evaluates it before that ride's own reasonable travel time has elapsed, **Then** the ride is left untouched — the grace period must not fire while the ride could still plausibly be underway.

---

### User Story 3 - Auto-completions are auditable and distinguishable from real driver completions (Priority: P2)

As the platform (and, indirectly, future trust/fraud review), every ride's completion is traceable to whether the driver actually completed it or the system did so after a timeout, so repeated auto-completions for one driver can be reviewed later without re-deriving it from timestamps.

**Why this priority**: Depends on User Stories 1 and 2 existing. Without this, there's no way to later distinguish "driver ran every ride and always tapped Complete" from "driver routinely no-shows and the system quietly picks up the pieces," which matters for driver-reliability review even though no such review is being built in this feature.

**Independent Test**: Auto-complete one ride via timeout and manually complete another as a driver; query both rides afterward and confirm each one's completion source is correctly recorded and distinguishable.

**Acceptance Scenarios**:

1. **Given** a ride is finalized by the automatic timeout, **When** its record is inspected afterward, **Then** it is recorded as system-completed, distinguishable from a driver-completed ride.
2. **Given** a ride is completed normally by the driver tapping "Complete," **When** its record is inspected afterward, **Then** it is recorded as driver-completed.

---

### Edge Cases

- What happens if a passenger or the driver cancels the last confirmed booking on a ride in the moments before the sweep runs? The sweep only ever acts on rides still in `scheduled`/`in_progress` at the moment it runs — normal cancellation flows are unaffected and take precedence if they land first.
- What happens if the driver taps "Start" or "Complete" at the same moment the sweep is evaluating the same ride? Only one of the two must win; the ride must never end up double-processed or in an inconsistent state.
- What happens to a recurring-ride instance mid-series (its definition is still `active`) that goes stale? It is auto-completed the same as any other ride — recurring-vs-one-off origin makes no difference to this feature.
- What happens to an already-`cancelled` or already-`completed` ride? The sweep never touches rides already in a terminal state.
- What happens for a long intercity-style ride whose route duration legitimately exceeds a short flat grace period? The in-progress grace period is `route_duration_minutes × 2` (floor 2 hours), so it scales with the ride's own expected duration and a ride that's still plausibly running is never prematurely finalized (see User Story 2, Acceptance Scenario 2).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST periodically scan for rides in `scheduled` status whose departure time is more than the not-started grace period in the past, and finalize each one to `completed`.
- **FR-002**: System MUST periodically scan for rides in `in_progress` status whose start time is more than the in-progress grace period in the past, and finalize each one to `completed`.
- **FR-003**: Finalizing a ride via the automatic timeout MUST apply the exact same consequences as a driver manually completing it: commission charged for confirmed cash bookings, held wallet reservation released, confirmed bookings transitioned to completed, and affected passengers notified — regardless of whether the ride has any confirmed bookings.
- **FR-004**: A ride finalized via timeout while still `scheduled` (never started) MUST have a start time recorded as part of being marked completed, so its history remains consistent with a normally-run ride.
- **FR-005**: Any booking still in a `pending` (not yet accepted/declined) state on a ride at the moment it is auto-finalized MUST be expired, the same way pending requests are expired when a driver manually starts a ride.
- **FR-006**: The system MUST record, for every ride that reaches `completed`, whether it was completed by the driver or by the automatic timeout, in a way that can be queried after the fact.
- **FR-007**: The automatic timeout MUST apply identically to rides regardless of whether they were created directly by a driver or generated from a recurring ride definition.
- **FR-008**: The sweep MUST be idempotent and safe to run repeatedly — it MUST NOT re-process, or take any action on, a ride that is already in a terminal status (`completed` or `cancelled`).
- **FR-009**: The sweep MUST NOT act on a ride that a concurrent driver action (start/cancel/complete) is processing at the same time — exactly one outcome MUST win for any given ride.
- **FR-010**: The not-started grace period MUST be 2 hours past `departure_datetime` — a `scheduled` ride more than 2 hours past its departure time is eligible for auto-completion.
- **FR-011**: The in-progress grace period MUST scale with the ride's own expected travel time: `route_duration_minutes × 2`, with a floor of 2 hours — an `in_progress` ride is eligible for auto-completion once that much time has passed since `started_at`. This prevents a legitimately long-running ride from being finalized while still plausibly underway, while still bounding short local rides to a sensible minimum window.

### Key Entities *(include if feature involves data)*

- **Ride** (existing entity, extended): gains a recorded completion source (driver vs. system/automatic-timeout) alongside its existing status, so a completed ride's origin is auditable after the fact — mirroring how a cancelled ride already records whether the driver or the system cancelled it.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No ride remains in `scheduled` status more than the not-started grace period (plus one sweep interval) after its departure time has passed.
- **SC-002**: No ride remains in `in_progress` status more than the in-progress grace period (plus one sweep interval) after being started.
- **SC-003**: 100% of automatically-finalized rides show the same commission charge, reservation release, and booking/notification outcome that a manually-completed ride with identical booking data would show.
- **SC-004**: The specific class of bug discovered 2026-09-13 (a recurring series' past-due, never-started instances staying `scheduled` indefinitely, requiring manual/one-off cleanup) cannot recur for any ride, recurring or one-off.
- **SC-005**: A driver or admin can determine, for any completed ride, whether it was completed by the driver or by the automatic timeout, without needing to infer it from timestamps.

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: The sweep MUST run on a recurring fixed interval consistent with existing background-job cadence in this codebase (e.g. the existing 10-minute recurring-ride-generation cadence), so staleness is bounded predictably.
- **NFR-002**: The sweep MUST be safe under concurrency with driver-initiated start/cancel/complete actions on the same ride — no double-processing, no lost update, no inconsistent partial state (see FR-009).
- **NFR-003**: A failure to finalize one ride during a sweep tick MUST NOT prevent other eligible rides from being processed in that same tick, and MUST be retried on the next tick rather than silently dropped.
- **NFR-004**: The sweep MUST NOT introduce a noticeable increase in database load under normal operating volume, consistent with how the existing recurring-ride-generation sweep is scoped.

---

## Dependencies *(mandatory)*

- **Internal**: Existing ride-completion consequence logic (commission deduction, reservation release, booking finalization, passenger notification) — reused as-is, not reimplemented. Existing recurring-ride generation (the instances that surfaced this bug, though this feature's fix is general and does not modify the generation logic itself). Existing pending-booking-expiry behavior (reused for FR-005).
- **External**: None new.
- **Data**: Adds a completion-source field to the existing ride record, mirroring the existing cancellation-source field.

---

## Out-of-Scope

- Any change to the recurring-ride generation loop itself — it already correctly stops generating once a series is ended; this feature only affects what happens to already-generated instances that go stale.
- Any new fraud-detection scoring, driver-reliability rating, or admin-facing reporting surface built on top of the completion-source data — this feature only makes that data recordable and queryable, per User Story 3; consuming it for a trust/fraud signal is a future, separate effort (see `030-fraud-signal-capture` for the existing, separate fraud-signal groundwork).
- Any dispute/appeal flow for a driver who believes a ride was wrongly auto-completed — not built in this iteration.
- Making the grace periods configurable per driver, per vehicle type, or per ride — v1 uses fixed, server-side values.
- Any new passenger- or driver-facing UI or wording change distinguishing an auto-completed ride from a manually-completed one — both simply show as "Completed."

---

## Technical Considerations

- Should reuse the existing ride-completion transaction logic (commission deduction, reservation release, booking finalization, notification) rather than duplicating it in a new code path, to guarantee the "identical consequences" requirement (FR-003) can't drift out of sync with manual completion over time.
- A ride finalized directly from `scheduled` needs its start recorded as part of the same operation that marks it completed (FR-004) — this is a new transition path (`scheduled` → `completed` in one step) that today's manual flow does not have (today: `scheduled` → `in_progress` → `completed` as two separate driver actions).
- The sweep should follow the existing background-loop pattern already established for recurring-ride generation (fixed-interval loop, per-ride try/except so one failure doesn't block the rest of the tick).
- Concurrency safety (FR-009/NFR-002) should follow the existing locking discipline already used elsewhere in ride mutation (e.g. row-level locking / conditional status checks that make a stale read a no-op rather than a double-apply).

---

## Assumptions

- Grace periods are fixed, server-side configuration values for v1, not user- or admin-configurable (see Out-of-Scope): 2 hours past `departure_datetime` for never-started rides, and `route_duration_minutes × 2` (floor 2 hours) past `started_at` for in-progress rides — confirmed with the user rather than defaulted silently.
- "Identical consequences to manual completion" (FR-003) means literally reusing the existing charge/release/notify logic and its existing edge-case behavior (e.g. how it behaves if a driver's wallet balance situation is unusual) — this feature does not change what completion does, only when/how it gets triggered.
- The new completion-source data is for backend/audit querying only in this iteration (User Story 3) — no admin UI surface is being built to browse it (see Out-of-Scope).
- A ride with no confirmed bookings that gets auto-completed produces no passenger-facing effect at all (no notification, since there is no passenger to notify) — "completed" in that case is administrative housekeeping only (releasing the reservation), not a claim that a trip occurred.
