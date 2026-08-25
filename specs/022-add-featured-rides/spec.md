# Feature Specification: Featured Rides

**Feature Branch**: `022-add-featured-rides`

**Created**: 2026-08-25

**Status**: Draft

**Input**: User description: "As an admin, mark a ride as 'featured' so it appears to passengers as a recommended/featured ride. The passenger 'find a ride' page is currently map-only; redesign it into a normal page that shows recommended/featured rides plus a 'Find a Ride' button, similar in pattern to the driver's 'post a ride' page."

---

## Business Objective *(mandatory)*

Give admins a way to curate and surface high-quality, high-availability rides to passengers, and replace the passenger's map-only ride-search entry point with a landing page that showcases these Featured rides alongside a clear path into full route search — increasing ride discoverability and booking conversion without changing how routes are actually matched.

**Constitutional Domain**: Ride Discovery (passenger-facing) / Administration (admin curation)

**Affected Applications**: Passenger App, Admin Panel (shared backend API)

---

## Clarifications

### Session 2026-08-25

- Q: How fresh must the Featured Rides list be while a passenger has the find-a-ride page open? → A: Fetch fresh only on page load/navigation — no background polling or real-time push updates while the page stays open; booking-time re-validation already guards against staleness.
- Q: Does the Featured designation have its own expiry/duration, separate from the ride's natural lifecycle? → A: No separate expiry — manual toggle only; Featured status lasts until an admin unfeatures it or the ride itself stops being bookable (FR-004).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Passenger discovers a Featured ride on the find-a-ride page (Priority: P1)

A passenger opens the "Find a Ride" section of the app and, instead of landing directly in a full-screen map, sees a page listing currently bookable Featured rides (route, date/time, price, seats left). They tap one to view its details and book it.

**Why this priority**: This is the direct business value of the feature — it is the surface passengers actually see and act on. It can be validated even before an admin-facing toggle exists, by marking test rides as featured directly in the data layer.

**Independent Test**: Seed one or more eligible rides as "Featured," open the find-a-ride page as a passenger, confirm the Featured Rides section renders those rides with correct route/time/price/seats, and confirm tapping one opens that ride's existing detail/booking flow.

**Acceptance Scenarios**:

1. **Given** at least one ride is marked Featured and is still scheduled with open seats, **When** a passenger opens the find-a-ride page, **Then** that ride appears in a "Featured/Recommended Rides" section with its route, departure date/time, price per seat, and remaining seats visible.
2. **Given** a Featured ride is displayed on the find-a-ride page, **When** the passenger taps it, **Then** they are taken to that ride's existing detail/booking screen.
3. **Given** a previously Featured ride has since become fully booked, been cancelled, or already departed, **When** a passenger opens the find-a-ride page, **Then** that ride does NOT appear in the Featured Rides section.

---

### User Story 2 - Admin marks or unmarks a ride as Featured (Priority: P2)

An admin reviewing rides in the admin panel marks a ride as "Featured" so it will surface to passengers, and can remove that designation later.

**Why this priority**: This is the enabling capability behind User Story 1 — without it, featured content can only be seeded manually. It is scoped separately because it is independently testable via the admin UI/API alone.

**Independent Test**: As an admin, open a ride in the admin Rides list or detail view, toggle "Featured" on, and verify the ride is now returned by the featured-rides listing; toggle it off and verify it disappears.

**Acceptance Scenarios**:

1. **Given** an admin is viewing an eligible ride (scheduled, in the future, with open seats) in the admin Rides list or detail view, **When** they mark it as Featured, **Then** the ride is flagged as Featured and becomes eligible to appear in the passenger Featured Rides section.
2. **Given** a ride is currently Featured, **When** an admin removes the Featured designation, **Then** the ride stops appearing in the passenger Featured Rides section.
3. **Given** a ride is cancelled, completed, in progress, fully booked, or already departed, **When** an admin attempts to mark it as Featured, **Then** the system prevents it and explains why.
4. **Given** an admin features or unfeatures a ride, **When** the action completes, **Then** the system records which admin performed the action and when.

---

### User Story 3 - Passenger starts a full route search via "Find a Ride" (Priority: P3)

From the same find-a-ride landing page, a passenger who doesn't see a suitable Featured ride taps a "Find a Ride" button, which opens the existing map-based, pin-drop route search experience (the same mechanism used today), mirroring the pattern of the driver's "post a ride" page.

**Why this priority**: This preserves today's existing search capability; it is lower priority than Stories 1–2 only because it is a relocation of already-working functionality rather than new capability, but it must ship in the same release since it replaces the current default view.

**Independent Test**: Open the find-a-ride landing page, tap "Find a Ride," and confirm the existing origin/destination pin-drop map search flow opens and functions exactly as it does today, returning route-matched ride results.

**Acceptance Scenarios**:

1. **Given** a passenger is on the find-a-ride landing page, **When** they tap "Find a Ride," **Then** the existing full-screen map / pin-drop origin and destination search flow opens.
2. **Given** the passenger completes an origin/destination search, **When** results are returned, **Then** behavior matches today's route-matched search results (no change to matching/ranking logic).

---

### Edge Cases

- No rides are currently Featured: the landing page MUST still render a usable, non-empty state (e.g., an empty-state message) with the "Find a Ride" action clearly available.
- A Featured ride fills its last seat, is cancelled, or departs while a passenger is looking at the landing page: it must not be bookable from a stale card (the detail/booking screen re-validates availability, consistent with existing booking flow behavior).
- An admin features a ride that already has existing bookings: this is allowed — Featured only affects discovery, not booking eligibility.
- Two admins toggle the Featured designation on the same ride at nearly the same time: the system applies the last write without corrupting ride data.
- A ride is featured, then its driver edits or cancels it through existing ride-management flows: the ride must stop appearing as Featured automatically per FR-004, without requiring separate admin cleanup.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow an authenticated admin to mark an eligible ride — status "scheduled," departure time in the future, at least one seat available — as "Featured."
- **FR-002**: The system MUST allow an authenticated admin to remove the "Featured" designation from a ride at any time.
- **FR-003**: The system MUST prevent rides that are cancelled, completed, in progress, fully booked, or already departed from being newly marked as Featured, and MUST explain why when this is attempted.
- **FR-004**: The system MUST automatically stop presenting a ride in the passenger Featured Rides section the moment it becomes fully booked, cancelled, or its departure time passes — without requiring the admin to manually unfeature it.
- **FR-005**: The admin Rides list and detail views MUST indicate whether a ride is currently Featured and provide a control to toggle that status.
- **FR-006**: The system MUST record which admin featured or unfeatured a given ride, and when, for audit purposes.
- **FR-007**: The passenger find-a-ride entry page MUST display a "Featured/Recommended Rides" section listing currently bookable Featured rides platform-wide (not filtered by the passenger's location or region), in place of opening directly into the full-screen map.
- **FR-008**: Each Featured ride card MUST show, at minimum: origin and destination, scheduled departure date/time, price per seat, and remaining available seats.
- **FR-009**: Selecting a Featured ride card MUST take the passenger to that ride's existing detail/booking screen.
- **FR-010**: The find-a-ride landing page MUST present a "Find a Ride" action that opens the existing map-based, pin-drop origin/destination route search experience, preserving current search functionality unchanged.
- **FR-011**: When no rides are currently Featured, the landing page MUST still render a usable, non-empty state that surfaces the "Find a Ride" action.
- **FR-012**: The Featured Rides section MUST be computed fresh (server-side, live-filtered against current ride status/seats) each time the passenger loads or navigates to the find-a-ride page; no background polling or real-time push updates are required while the page remains open, since the booking screen re-validates availability before confirming a booking.
- **FR-013**: Marking a ride as Featured MUST NOT alter the outcome of route-matching or AI-ranked search results; Featured is a distinct curation surface, separate from the search-matching engine.
- **FR-014**: Access to the find-a-ride landing page and its Featured Rides section MUST honor the same authentication and verification gating currently applied to the existing find-a-ride/search page.

### Key Entities

- **Ride** *(existing entity, extended)*: gains a Featured designation — whether it is currently featured, and metadata about when and by which admin it was last featured or unfeatured.
- **Featured Rides Listing**: the derived, passenger-visible subset of Featured rides that are still scheduled, in the future, and have open seats; computed at read time rather than stored separately.
- **Admin Action Record** *(existing audit mechanism, extended)*: an entry capturing which admin featured or unfeatured which ride, and when.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can mark or unmark a ride as Featured in under 10 seconds from the Rides list or detail view, without leaving the admin panel.
- **SC-002**: A passenger can go from opening the find-a-ride page to viewing a Featured ride's full details in 2 taps or fewer.
- **SC-003**: 100% of rides shown in the Featured Rides section at any given time are currently scheduled, in the future, and have at least one open seat.
- **SC-004**: 100% of Featured/unfeatured actions are attributable to a specific admin and timestamp in audit records.
- **SC-005**: The find-a-ride landing page (Featured Rides section or its empty state) becomes visible to the passenger within 2 seconds on a typical mobile connection.

---

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: The Featured Rides listing MUST respond within 500ms at p95 under normal load.
- **NFR-002**: Only authenticated admin users MUST be able to feature or unfeature a ride.
- **NFR-003**: Every feature/unfeature admin action MUST be captured through the platform's existing administrative action auditing.
- **NFR-004**: If the Featured Rides section fails to load, the find-a-ride landing page MUST still render and keep the "Find a Ride" action usable (graceful degradation, no hard failure of the entry page).

---

## Dependencies *(mandatory)*

- **Internal**: Ride Management domain (ride status, seats, scheduling data); the existing Admin Rides visibility feature (admin Rides list/detail views, currently read-only, being extended with a mutation capability here); the existing passenger search/booking flow that the "Find a Ride" button opens unchanged; existing identity-verification gating (Deferred Identity Verification) reused as-is for landing page access.
- **External**: None new.
- **Data**: Extends the existing Ride data model with a Featured designation and its audit metadata; no new external services or data stores required.

---

## Out-of-Scope

- Changes to the AI ride-ranking/matching algorithm used once a passenger performs an actual route search — Featured is a separate curation surface (Principle II integrity preserved).
- Payment, pricing, or commission changes.
- Passenger-side personal favorites/wishlists (distinct from admin-curated Featured rides).
- Notifications (push/email/SMS) specifically about newly Featured rides.
- Role-based admin permission differentiation for who may feature rides — in this iteration, any authenticated admin can.
- Any change to the driver "post a ride" page itself — it is referenced only as the UI pattern the passenger redesign should mirror.
- Manual reordering/prioritization among multiple simultaneously Featured rides.

---

## Technical Considerations

- Reuse the existing map / bottom-sheet / pin-drop UI pattern already implemented for the driver "post a ride" page for the "Find a Ride" action on the redesigned passenger landing page, per Principle VII (shared foundations across applications) — avoid building a second, divergent search UI.
- Featured-eligibility filtering (scheduled, future, seats available) MUST be deterministic backend logic, not part of the AI ranking service, consistent with Principle II (route intelligence integrity) and Principle IV (AI remains a distinct, auditable layer).
- Admin mutation capability (feature/unfeature) must be added to the existing Admin Rides API surface, which today only exposes read (GET) endpoints.
- New data fields must follow existing Data Standards (reuse the ride's existing UUID identity; no new sensitive data exposed publicly).

---

## Assumptions

- Any authenticated admin user may feature or unfeature a ride; the admin panel does not yet have differentiated roles for this action.
- No cap is enforced on how many rides may be simultaneously Featured; admins are trusted to curate a reasonable number.
- Featured rides are shown platform-wide rather than filtered by passenger location/region; this may be revisited if ride volume grows large enough to make platform-wide curation less relevant.
- Featured rides are sorted by soonest upcoming departure in the passenger listing; no manual admin-controlled ordering is provided in this iteration.
- Featuring has no separate expiry/duration control; it is a manual toggle only (confirmed in Clarifications), ending when an admin unfeatures the ride or the ride itself stops being bookable.
- The "Find a Ride" button opens today's existing map-based, pin-drop search experience unchanged — this spec relocates it behind an entry action rather than redesigning its mechanics.
- The redesigned find-a-ride landing page is subject to the same authentication/verification access rules as the current search page (no change to who may view or use it).
