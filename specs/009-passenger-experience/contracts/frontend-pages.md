# Frontend Page Contracts: Passenger Experience

**Feature**: `009-passenger-experience` | **Date**: 2026-06-24

All passenger pages live in the `(passenger)` route group under `apps/main/src/app/`. The group is protected by the existing `middleware.ts` — unauthenticated users are redirected to `/sign-in`; unverified users are redirected to the verification pending screen.

---

## Passenger Pages

### `/search` — Ride Search

**File**: `apps/main/src/app/(passenger)/search/page.tsx`

**Purpose**: Entry point for ride discovery. Two-phase screen: search form → results list.

**State**:
- Form state: origin (text + lat/lng), destination (text + lat/lng), desired departure datetime
- Results state: `RideCandidate[]` | loading | error | empty

**Key behaviours**:
- Origin and destination inputs use geocoding (via the map picker established in Phase 4.2) to capture geographic coordinates alongside display text
- On submit, calls `POST /api/v1/search/rides`
- Renders `RideCard` for each candidate; premium candidates show a "Premium" badge with the additional fee
- Standard candidates shown before premium candidates (default Phase 5 sort; Phase 9 AI re-ranking overrides this without UI change)
- Empty state: "No rides found for your route and time" with a suggestion to try a different time
- Error state: "Route service unavailable, please try again"
- Tapping a `RideCard` navigates to `/rides/{ride_id}?origin_lat=...&origin_lng=...&dest_lat=...&dest_lng=...`

**Components used**: `RideSearchForm`, `RideCard`

---

### `/rides/[id]` — Ride Detail

**File**: `apps/main/src/app/(passenger)/rides/[id]/page.tsx`

**Purpose**: Full ride detail before a passenger commits to booking.

**Query parameters** (passed from `/search`):
- `origin_lat`, `origin_lng`, `dest_lat`, `dest_lng` — passenger's journey endpoints

**Data source**: `GET /api/v1/rides/{id}/passenger-detail?origin_lat=...&origin_lng=...&destination_lat=...&destination_lng=...`

**Key behaviours**:
- Renders driver card: avatar, display name, verified badge
- Full-width map (`RideDetailMap`) showing:
  - Driver route polyline (blue)
  - Passenger boarding point (green pin)
  - Passenger alighting point (red pin)
  - Dashed walk lines from origin→boarding and alighting→destination
- Price section:
  - Standard rides: base per-seat price only
  - Premium-eligible: two option cards (Standard — walk to route; Premium — driver detours to exact address) with the premium fee itemised; passenger must select one before the Book button becomes active
- "Book Seat" button: disabled until (a) at least one option selected for premium rides, (b) ride is still `scheduled`
- If ride status is `cancelled` or `completed` (received from API): show "Ride no longer available" state; Book button hidden
- If `available_seats = 0` on load: show "Fully booked" state; Book button disabled

**Components used**: `RideDetailMap`

**On "Book Seat" tap**: Opens a confirmation bottom sheet showing the booking summary (driver name, departure, price breakdown, pickup/dropoff addresses), then calls `POST /api/v1/bookings`. On success, navigates to `/bookings/{new_booking_id}`.

---

### `/bookings` — My Bookings

**File**: `apps/main/src/app/(passenger)/bookings/page.tsx`

**Purpose**: List of all the passenger's bookings, ordered by departure time descending.

**Data source**: `GET /api/v1/bookings`

**Key behaviours**:
- Filter tabs: All | Active (pending + confirmed) | Past (completed + cancelled)
- Renders `BookingCard` for each booking
- `BookingCard` shows: driver name, departure datetime, status badge, per-seat price
- Tapping navigates to `/bookings/{id}`
- Empty state per tab

**Components used**: `BookingCard`, `BookingStatusBadge`

---

### `/bookings/[id]` — Booking Detail

**File**: `apps/main/src/app/(passenger)/bookings/[id]/page.tsx`

**Purpose**: Full booking detail with status and available actions.

**Data source**: `GET /api/v1/bookings/{id}`

**Key behaviours**:
- Shows: driver name, departure datetime, boarding address, alighting address, price, status badge
- Shows premium fee breakdown if premium options were requested
- "Cancel Booking" button visible only when `status = pending | confirmed`; hidden for `cancelled | completed`
- Cancel taps `POST /api/v1/bookings/{id}/cancel`; on success, updates status badge in place
- Status badge reflects live status: `BookingStatusBadge` uses colour coding — pending (amber), confirmed (green), cancelled (red), completed (grey)

**Components used**: `BookingStatusBadge`

---

## Driver Pages (Extension to Existing Route Group)

### `/driver/rides/[id]/bookings` — Driver Booking Queue

**File**: `apps/main/src/app/(driver)/rides/[id]/bookings/page.tsx`

**Purpose**: Driver reviews and responds to booking requests for a specific ride.

**Data source**: `GET /api/v1/rides/{id}/bookings`

**Key behaviours**:
- Pending bookings section: each card shows passenger name, boarding/alighting points on a mini map, price, and premium fee if applicable
  - "Confirm" button → `POST /api/v1/rides/{id}/bookings/{booking_id}/confirm`
  - "Reject" button → `POST /api/v1/rides/{id}/bookings/{booking_id}/reject`
- Confirmed bookings section: each card shows passenger name, boarding/alighting, "Cancel" button → `POST /api/v1/rides/{id}/bookings/{booking_id}/cancel`
- Past bookings (cancelled/completed): read-only, no action buttons
- On confirmation or rejection, card moves to the appropriate section without full page reload (optimistic update)

**Components used**: `BookingCard`, `BookingStatusBadge`

---

## New Components

### `RideSearchForm`

Inputs: origin address/geocode picker, destination address/geocode picker, departure datetime picker. Submit button. Handles geocoding state and validation (origin ≠ destination, departure in the future).

### `RideCard`

Displays a single candidate in the search results list. Props: ride candidate object from the search API. Shows driver avatar, name, departure time, available seats, per-seat price, overlap quality indicator, and a "PREMIUM" badge for premium-eligible candidates.

### `RideDetailMap`

Full-width Leaflet/OpenLayers map (using the OSM tile layer established in Phase 4.2). Renders the driver route polyline, passenger boarding/alighting pins, and dashed walk paths. Props: route geometry (encoded polyline), boarding point, alighting point, origin, destination.

### `BookingCard`

Compact booking summary card for list views. Props: booking object. Shows driver name, departure time, route summary, price, and status badge. Supports passenger view (from `/bookings`) and driver view (from `/driver/rides/[id]/bookings`) via a `variant` prop.

### `BookingStatusBadge`

Status indicator chip. Maps `booking_status` enum to colour + label: `pending` → amber "Awaiting Confirmation"; `confirmed` → green "Confirmed"; `cancelled` → red "Cancelled"; `completed` → grey "Completed".
