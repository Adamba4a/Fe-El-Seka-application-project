# Tasks: Passenger Experience

**Input**: Design documents from `specs/009-passenger-experience/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅ | quickstart.md ✅

**Tests**: Not requested — no test tasks generated. Validate using `quickstart.md` scenarios.

**Organization**: Tasks grouped by user story (P1→P6) to enable independent implementation and testing.

---

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Parallelizable — touches a different file, no dependency on an incomplete sibling task
- **[Story]**: User story label — [US1] through [US6]
- All paths are relative to repository root

---

## Phase 1: Setup

**Purpose**: Create directory scaffolding and stub files. All of T002–T006 are parallelizable.

- [X] T001 Write database migration file `supabase/migrations/20260624000001_phase6_bookings.sql` with full schema per `data-model.md`: `booking_status` / `booking_cancelled_by` / `booking_event_type` / `booking_actor_role` enums; `bookings` table with all columns, constraints, and partial unique index; `booking_audit_log` table (append-only); `ALTER TABLE email_notifications ADD COLUMN IF NOT EXISTS payload JSONB DEFAULT '{}'`; all indexes from data-model.md; all RLS policies
- [X] T002 [P] Create `services/api/app/api/bookings/__init__.py` (empty) and `services/api/app/api/bookings/router.py` (stub: `router = APIRouter()`)
- [X] T003 [P] Create `services/api/app/api/search/__init__.py` (empty) and `services/api/app/api/search/router.py` (stub: `router = APIRouter()`)
- [X] T004 [P] Create `apps/main/src/app/(passenger)/layout.tsx` (stub — copy structure from `apps/main/src/app/(driver)/layout.tsx`, adjust for passenger role)
- [X] T005 [P] Create `apps/main/src/app/(driver)/rides/[id]/bookings/page.tsx` (stub — empty React component with TODO comment)
- [X] T006 [P] Create `apps/main/src/components/bookings/` directory with empty `index.ts` barrel file

---

## Phase 2: Foundation

**Purpose**: Core infrastructure that MUST be complete before any user story begins.

**⚠️ CRITICAL**: No user story work can start until T008 (migration applied) is done. T009–T012 can then run in parallel.

- [ ] T007 Apply migration: run `supabase db push` (or `supabase migration up`) from repo root and confirm `bookings`, `booking_audit_log` tables exist and `email_notifications.payload` column is present
- [ ] T008 [P] Create `services/api/app/models/booking.py` with all Pydantic schemas per `contracts/api.md`: `BookingCreateRequest`, `BookingResponse`, `BookingListResponse`, `BookingCancelRequest`, `DriverConfirmResponse`, `DriverRejectResponse`, `DriverBookingItem`, `DriverBookingListResponse`
- [ ] T009 [P] Add `get_current_verified_passenger` dependency to `services/api/app/dependencies/verification.py` — mirrors `get_current_verified_driver` but checks `verification_status = 'approved'` without requiring driver role; returns profile dict
- [ ] T010 [P] Create `services/api/app/services/booking_service.py` scaffold with shared helpers only (no story logic yet): `get_booking_or_404(conn, booking_id, caller_id)` → raises HTTP 404/403; `_assert_ride_owner(conn, ride_id, driver_id)` → raises HTTP 403; `_insert_audit_log(conn, booking_id, event_type, actor_id, actor_role, prev_status, new_status, metadata)` → inserts one row into `booking_audit_log`
- [ ] T011 [P] Add booking notification enqueue function to `services/api/app/services/notification_service.py`: `enqueue_booking_notification(conn, notification_type, recipient_user_id, payload_dict)` → inserts one row into `email_notifications` with `payload = payload_dict`

**Checkpoint**: Migration applied, models defined, dependency added, service scaffold ready — user story implementation can begin.

---

## Phase 3: User Story 1 — Ride Search (Priority: P1) 🎯 MVP

**Goal**: Verified passengers can search for compatible rides by origin, destination, and departure time. Results are drawn from the Phase 5 candidate engine and returned as a ranked list.

**Independent Test**: `POST /api/v1/search/rides` with valid passenger JWT and a route that has compatible scheduled rides returns a non-empty `candidates` array; each item includes `ride_id`, `driver`, `available_seats`, `per_seat_price`, and `compatibility`. A route with no compatible rides returns `{"candidates": [], "no_rides_found": true}`.

- [ ] T012 [US1] Implement `POST /api/v1/search/rides` in `services/api/app/api/search/router.py`: accept `SearchRidesRequest` (origin lat/lng, destination lat/lng, desired_departure_at); use `get_current_verified_passenger` dependency; call `candidate_service.generate_candidates()` with parsed `GeoPoint` objects; shape the response into `SearchRidesResponse` (per `contracts/api.md`); return `no_rides_found: true` on empty list; propagate `RouteServiceUnavailableError` as HTTP 503
- [ ] T013 [US1] Register search router in `services/api/app/main.py`: `app.include_router(search_router, prefix="/api/v1/search", tags=["search"])`
- [ ] T014 [P] [US1] Create `apps/main/src/components/bookings/RideSearchForm.tsx`: origin address input with geocode (lat/lng capture), destination address input with geocode, datetime picker for desired departure, Submit button; emits `onSearch(origin, destination, departure)` callback; validates origin ≠ destination and departure is in the future
- [ ] T015 [P] [US1] Create `apps/main/src/components/bookings/RideCard.tsx`: displays driver avatar + name, departure time, available seats, per-seat price, route overlap quality indicator; shows amber "PREMIUM" badge and additional fee when `candidate_type === 'premium'`; accepts onClick handler; uses existing shadcn/ui Card component
- [ ] T016 [US1] Implement `apps/main/src/app/(passenger)/search/page.tsx`: two-phase screen (form → results); on submit calls `POST /api/v1/search/rides`; renders `RideSearchForm` and list of `RideCard` components; handles loading spinner, empty state ("No rides found for your route and time"), and error state ("Route service unavailable, please try again"); passes `origin_lat`, `origin_lng`, `dest_lat`, `dest_lng` as query params when navigating to `/rides/{id}`

**Checkpoint**: US1 complete — passenger can search for rides end-to-end via the app.

---

## Phase 4: User Story 2 — Ride Detail View (Priority: P2)

**Goal**: Passengers can tap a search result and see full ride details — driver info, route on map, boarding/alighting points, premium options — before deciding to book.

**Independent Test**: `GET /api/v1/rides/{id}/passenger-detail?origin_lat=...&origin_lng=...&destination_lat=...&destination_lng=...` returns `ride` object (driver name, departure, price, available seats, route geometry) and `passenger_context` (boarding/alighting points, walk distances, estimated travel time, premium flags and fees). A cancelled/completed ride returns HTTP 410.

- [ ] T017 [US2] Add `GET /api/v1/rides/{id}/passenger-detail` to `services/api/app/api/rides/router.py`: accept `origin_lat`, `origin_lng`, `destination_lat`, `destination_lng` as query params; build passenger and driver `GeoPoint` objects; call `route_service` for route geometry if needed; call `candidate_service` to compute compatibility for this specific ride; fetch driver profile (`display_name`, `avatar_url`, `is_verified`); return shaped response per `contracts/api.md`; return HTTP 410 if ride status is `cancelled` or `completed`
- [ ] T018 [P] [US2] Create `apps/main/src/components/bookings/RideDetailMap.tsx`: full-width Leaflet/OpenStreetMap map; accepts `routeGeometry` (encoded polyline), `boardingPoint`, `alightingPoint`, `origin`, `destination`; renders: blue driver route polyline decoded from polyline; green boarding pin; red alighting pin; dashed grey walk lines from origin→boarding and alighting→destination; uses the OSM tile layer and Leaflet instance already established in Phase 4.2
- [ ] T019 [US2] Implement `apps/main/src/app/(passenger)/rides/[id]/page.tsx`: reads `origin_lat`, `origin_lng`, `dest_lat`, `dest_lng` from query params; calls `GET /api/v1/rides/{id}/passenger-detail`; renders driver card (avatar, name, verified badge), `RideDetailMap`, departure time, estimated travel minutes, available seats; for premium-eligible rides renders two option cards (Standard / Premium) and requires user selection before activating Book button; shows "Ride no longer available" state on HTTP 410; disables Book button when `available_seats === 0`

**Checkpoint**: US2 complete — passenger can view a full ride detail screen with map and premium options.

---

## Phase 5: User Story 3 — Booking Creation (Priority: P3)

**Goal**: A passenger taps "Book Seat" and the system atomically reserves a seat, creates a `pending` booking, and shows a confirmation summary.

**Independent Test**: `POST /api/v1/bookings` with a valid verified-passenger JWT and an existing scheduled ride with available seats returns HTTP 201 with `status: "pending"`. Immediately after: `rides.booked_seats` is incremented by 1; one `booking_audit_log` row exists with `event_type = 'created'`; one `email_notifications` row exists with the passenger's `recipient_user_id` (notification_type `booking_created` — informational). A second identical request returns HTTP 409 `duplicate_booking`.

- [ ] T020 [US3] Implement `create_booking(conn, ride_id, passenger_id, boarding_point, alighting_point, premium_pickup, premium_dropoff, premium_pickup_fee, premium_dropoff_fee)` in `services/api/app/services/booking_service.py`: (1) SELECT ride FOR UPDATE; validate status = 'scheduled' and departure in future; (2) `UPDATE rides SET booked_seats = booked_seats + 1 WHERE id = $1 AND booked_seats < total_seats RETURNING id` — zero rows → raise HTTP 409 `no_seats_available`; (3) INSERT into `bookings` locking in `per_seat_price` from ride; (4) call `_insert_audit_log` with `event_type = 'created'`; (5) call `enqueue_booking_notification` with `notification_type = 'booking_created'`; all in one transaction
- [ ] T021 [US3] Implement `POST /api/v1/bookings` in `services/api/app/api/bookings/router.py`: use `get_current_verified_passenger` dependency; validate request body; call `create_booking()`; return HTTP 201 `BookingResponse`; handle `duplicate_booking`, `no_seats_available`, `ride_not_schedulable`, `ride_departed` error codes
- [ ] T022 [US3] Register bookings router in `services/api/app/main.py`: `app.include_router(bookings_router, prefix="/api/v1", tags=["bookings"])`
- [ ] T023 [US3] Add booking confirmation bottom sheet to `apps/main/src/app/(passenger)/rides/[id]/page.tsx`: when Book button is tapped, show a modal/bottom sheet summarising driver name, departure, boarding address, alighting address, price breakdown (base + premium fee if applicable), total; "Confirm Booking" button calls `POST /api/v1/bookings`; on HTTP 201 navigate to `/bookings/{booking_id}`; on HTTP 409 show "No seats available — this ride just filled up"

**Checkpoint**: US3 complete — the full search → detail → book flow works end-to-end.

---

## Phase 6: User Story 4 — Driver Booking Response (Priority: P4)

**Goal**: Drivers can see pending booking requests for their rides and confirm or reject them; confirmed/rejected transitions update booking status and seat counts.

**Independent Test**: Authenticated driver calls `POST /api/v1/rides/{id}/bookings/{bid}/confirm` → booking transitions to `confirmed`, `booking_audit_log` row added, `email_notifications` row with `booking_confirmed` added. Driver calls `POST /api/v1/rides/{id}/bookings/{bid}/reject` → booking transitions to `cancelled`, `booked_seats` restored, `email_notifications` row with `booking_rejected` added.

- [ ] T024 [US4] Implement `confirm_booking(conn, booking_id, ride_id, driver_id)` in `services/api/app/services/booking_service.py`: validate driver owns ride; validate booking is `pending` on that ride; UPDATE booking to `confirmed`, set `confirmed_at`; call `_insert_audit_log` with `event_type = 'confirmed'`; call `enqueue_booking_notification` with `booking_confirmed` to passenger
- [ ] T025 [US4] Implement `reject_booking(conn, booking_id, ride_id, driver_id, reason)` in `services/api/app/services/booking_service.py`: validate driver owns ride; validate booking is `pending`; apply premium fallback rule (spec FR-021): if `premium_pickup_requested` and passenger's boarding_point is within standard walk threshold, keep booking as `confirmed` at base price (set `premium_pickup_requested = false`, `premium_pickup_fee = null`) — else cancel; if cancelling: `UPDATE rides SET booked_seats = booked_seats - 1`; UPDATE booking to `cancelled`, `cancelled_by = 'driver'`; call `_insert_audit_log`; call `enqueue_booking_notification` with `booking_rejected`; return `fallback_applied` boolean
- [ ] T026 [US4] Add `GET /api/v1/rides/{ride_id}/bookings` to `services/api/app/api/rides/router.py`: `get_current_verified_driver` dependency; verify driver owns ride; query bookings joined with profiles for passenger `display_name` and `avatar_url`; return `DriverBookingListResponse` with optional `status` filter
- [ ] T027 [US4] Add `POST /api/v1/rides/{ride_id}/bookings/{booking_id}/confirm` to `services/api/app/api/rides/router.py`: `get_current_verified_driver` dependency; call `confirm_booking()`; return `DriverConfirmResponse`
- [ ] T028 [US4] Add `POST /api/v1/rides/{ride_id}/bookings/{booking_id}/reject` to `services/api/app/api/rides/router.py`: `get_current_verified_driver` dependency; call `reject_booking()`; return `DriverRejectResponse` with `fallback_applied` field
- [ ] T029 [P] [US4] Create `apps/main/src/components/bookings/BookingCard.tsx`: accepts `booking` object and `variant: 'passenger' | 'driver'`; passenger variant shows driver name, departure, status badge, price; driver variant shows passenger name, boarding/alighting mini-map (static image or inline map), premium fee if applicable, and action buttons (Confirm / Reject for pending; Cancel for confirmed); uses `BookingStatusBadge`
- [ ] T030 [P] [US4] Create `apps/main/src/components/bookings/BookingStatusBadge.tsx`: status chip component mapping `booking_status` to colour + label — `pending` → amber "Awaiting Confirmation"; `confirmed` → green "Confirmed"; `cancelled` → red "Cancelled"; `completed` → grey "Completed"
- [ ] T031 [US4] Implement `apps/main/src/app/(driver)/rides/[id]/bookings/page.tsx`: calls `GET /api/v1/rides/{id}/bookings`; renders two sections — "Pending Requests" (BookingCard with Confirm/Reject buttons) and "Confirmed Passengers" (BookingCard with Cancel button); on Confirm/Reject, call respective endpoints and update card state optimistically; empty state per section

**Checkpoint**: US4 complete — driver can manage the full booking confirmation flow from their ride screen.

---

## Phase 7: User Story 5 — Booking Cancellation (Priority: P5)

**Goal**: Passengers and drivers can cancel bookings at any point before completion; seats are released and the cancellation is recorded with a late-cancellation flag when applicable.

**Independent Test**: Authenticated passenger calls `POST /api/v1/bookings/{id}/cancel` on a confirmed booking → status transitions to `cancelled`, `cancelled_by = 'passenger'`, `rides.booked_seats` decremented by 1, audit log entry created. For a booking within 1 hour of departure, `late_cancellation = true`.

- [ ] T032 [US5] Implement `cancel_booking(conn, booking_id, caller_id, caller_role, reason)` in `services/api/app/services/booking_service.py`: validate booking is `pending` or `confirmed` (reject if `cancelled` or `completed` with HTTP 409 `booking_terminal`); compute `late_cancellation` (booking departure < 1h from now); `UPDATE rides SET booked_seats = booked_seats - 1 WHERE booked_seats > 0`; UPDATE booking: `status = 'cancelled'`, `cancelled_by`, `cancellation_reason`, `late_cancellation`, `cancelled_at = now()`; call `_insert_audit_log`; call `enqueue_booking_notification` with `booking_cancelled_by_passenger` or `booking_cancelled_by_driver`
- [ ] T033 [US5] Add `POST /api/v1/bookings/{booking_id}/cancel` to `services/api/app/api/bookings/router.py`: `get_current_verified_passenger` dependency; verify booking belongs to passenger; call `cancel_booking(caller_role='passenger')`; return cancellation response
- [ ] T034 [US5] Add `POST /api/v1/rides/{ride_id}/bookings/{booking_id}/cancel` to `services/api/app/api/rides/router.py`: `get_current_verified_driver` dependency; verify driver owns ride; call `cancel_booking(caller_role='driver')`; return cancellation response
- [ ] T035 [US5] Extend `cancel_ride()` in `services/api/app/services/ride_service.py` to cascade: after updating ride status to `cancelled`, call `cancel_all_bookings_for_ride(conn, ride_id)` (a new helper in `booking_service.py`) which: bulk-SELECTs all `pending` and `confirmed` bookings for the ride; for each, calls `cancel_booking()` with `caller_role = 'system'`, `cancellation_reason = 'ride_cancelled_by_driver'`; this restores booked_seats per booking and enqueues `ride_cancelled` notifications to each affected passenger
- [ ] T036 [US5] Implement `apps/main/src/app/(passenger)/bookings/[id]/page.tsx`: calls `GET /api/v1/bookings/{id}`; renders driver name, departure, boarding address, alighting address, price breakdown (base + premium if applicable), `BookingStatusBadge`; shows "Cancel Booking" button only when `status === 'pending' || status === 'confirmed'`; on tap, shows confirmation dialog ("Are you sure you want to cancel?"); on confirm, calls `POST /api/v1/bookings/{id}/cancel` and updates badge in-place

**Checkpoint**: US5 complete — booking cancellation is fully functional for passengers, drivers, and via ride cascade.

---

## Phase 8: User Story 6 — My Bookings (Priority: P6)

**Goal**: Passengers can view all their bookings (past and present) and access booking detail with status and available actions.

**Independent Test**: `GET /api/v1/bookings` returns all bookings for the authenticated passenger, most recent departure first. `GET /api/v1/bookings?status=confirmed` returns only confirmed bookings. The `/bookings` page renders tabs filtering by All / Active / Past and renders a `BookingCard` for each.

- [ ] T037 [US6] Implement `GET /api/v1/bookings` in `services/api/app/api/bookings/router.py`: use `get_current_verified_passenger` dependency (any authenticated user returns only their own via RLS); accept optional `status` query param; accept `page` (default 1) and `page_size` (default 20) for pagination; join with rides to include `departure_datetime`, `driver_id`; join with profiles on `driver_id` to include `driver_display_name`; return `BookingListResponse` ordered by `departure_datetime DESC`
- [ ] T038 [US6] Implement `GET /api/v1/bookings/{booking_id}` in `services/api/app/api/bookings/router.py`: accessible by booking's passenger OR ride's driver (check both); return full booking detail including `boarding_point` (as lat/lng), `alighting_point` (as lat/lng), `cancellation_reason`, and all premium fields
- [ ] T039 [US6] Implement `apps/main/src/app/(passenger)/bookings/page.tsx`: calls `GET /api/v1/bookings`; renders tab bar (All / Active / Completed); maps each booking to `BookingCard` (passenger variant); handles loading, empty state per tab; tapping a card navigates to `/bookings/{id}`

**Checkpoint**: US6 complete — passenger has full self-service booking management.

---

## Phase 9: Background Tasks & Completion Cascade

**Purpose**: Automated booking lifecycle — expiry of unresponded pending bookings and completion cascade when a ride finishes.

**Independent Test**: A pending booking aged to 25 hours via `UPDATE bookings SET created_at = NOW() - INTERVAL '25 hours'` is cancelled by the next expiry sweep (status → `cancelled`, `cancelled_by = 'system'`, seat released, audit log row with `event_type = 'expired'`). A ride marked `completed` causes all its `confirmed` bookings to transition to `completed` atomically.

- [ ] T040 Implement `_expire_pending_bookings(pool)` in `services/api/app/services/booking_service.py`: SELECT bookings WHERE `status = 'pending'` AND `created_at < NOW() - INTERVAL '24 hours'` using `FOR UPDATE SKIP LOCKED` (max 500 rows per sweep); for each: UPDATE booking to `cancelled` (`cancelled_by = 'system'`); UPDATE ride `booked_seats - 1`; call `_insert_audit_log` with `event_type = 'expired'`; call `enqueue_booking_notification` with `booking_expired` to passenger; idempotent — check status again inside lock before updating
- [ ] T041 Implement `booking_expiry_loop()` in `services/api/app/services/booking_service.py` following the exact pattern of `email_retry_loop()` in `notification_service.py`: `while True: try: await _expire_pending_bookings(pool) except Exception as exc: logger.error(...) await asyncio.sleep(600)`
- [ ] T042 Implement `complete_ride_bookings(conn, ride_id)` in `services/api/app/services/booking_service.py`: `UPDATE bookings SET status = 'completed' WHERE ride_id = $1 AND status = 'confirmed' RETURNING id`; for each returned booking ID, call `_insert_audit_log` with `event_type = 'completed'`, `actor_role = 'system'`; idempotent (WHERE status = 'confirmed' ensures no double-completion)
- [ ] T043 Call `complete_ride_bookings(conn, ride_id)` from the ride completion handler in `services/api/app/services/ride_service.py`: identify the point where ride status is set to `completed` and add the call within the same database transaction
- [ ] T044 Register `booking_expiry_loop` as an asyncio startup task in `services/api/app/main.py` following the same pattern as the existing `email_retry_loop` registration

**Checkpoint**: Booking lifecycle is fully automated — pending bookings expire, completed rides cascade to bookings.

---

## Phase 10: Polish & Cross-Cutting

**Purpose**: Final wiring, navigation, and route protection.

- [ ] T045 [P] Update `apps/main/src/app/(passenger)/layout.tsx` with passenger bottom navigation bar: "Search" → `/search`, "My Bookings" → `/bookings`; use the same shadcn/ui navigation pattern as the `(driver)` layout
- [ ] T046 [P] Update `apps/main/src/middleware.ts` to protect `(passenger)` routes: add `/search`, `/rides/:id`, `/bookings`, `/bookings/:id` to the authenticated+verified matcher so unauthenticated users are redirected to sign-in and unverified users are redirected to the verification pending screen
- [ ] T047 [P] Export new components from `apps/main/src/components/index.ts`: add `BookingCard`, `BookingStatusBadge`, `RideSearchForm`, `RideCard`, `RideDetailMap`
- [ ] T048 Add `(passenger)/` route group link to driver home screen in `apps/main/src/app/(driver)/rides/page.tsx`: add "Search Rides" navigation entry so drivers who are also passengers can switch to the passenger experience
- [ ] T049 Run all 7 quickstart.md validation scenarios; confirm each passes; fix any regressions before marking Phase 10 complete

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)         → No dependencies — start immediately
Phase 2 (Foundation)    → Depends on Phase 1 — BLOCKS all user story phases
Phase 3 (US1 Search)    → Depends on Phase 2
Phase 4 (US2 Detail)    → Depends on Phase 2; integrates Phase 3 navigation
Phase 5 (US3 Booking)   → Depends on Phase 2; requires Phase 4 (detail page hosts Book button)
Phase 6 (US4 Driver)    → Depends on Phase 5 (bookings must exist to confirm/reject)
Phase 7 (US5 Cancel)    → Depends on Phase 5; independent of Phase 6
Phase 8 (US6 My Bkg)    → Depends on Phase 5
Phase 9 (Background)    → Depends on Phase 5 (bookings table must exist); Phase 6 ride completion caller
Phase 10 (Polish)       → Depends on all prior phases
```

### User Story Dependencies

- **US1 (Search)**: No dependency on other stories — first independently deliverable increment
- **US2 (Detail)**: Integrates US1 navigation (search → detail), but the API endpoint is independent
- **US3 (Booking Creation)**: Requires US2 detail page to host the booking confirmation UI; API endpoint is independent
- **US4 (Driver Response)**: Requires bookings to exist (US3); driver queue page is independent
- **US5 (Cancellation)**: Requires bookings to exist (US3); cancel API and UI are independent of US4
- **US6 (My Bookings)**: Requires bookings to exist (US3); list/detail pages are independent of US4–US5

### Within Each Phase

```
T001 → T007 (migration file must exist before applying)
T007 → T008–T011 (migration must be applied before service code depends on table shape)
T020 (create_booking service) → T021 (POST /bookings endpoint)
T024 (confirm_booking service) → T027 (POST /confirm endpoint)
T025 (reject_booking service) → T028 (POST /reject endpoint)
T032 (cancel_booking service) → T033, T034 (cancel endpoints)
T040 (expiry helper) → T041 (expiry loop)
T042 (complete_ride_bookings) → T043 (wired into ride_service)
T041, T044 (loop impl + wiring) → register in main.py (T044)
```

---

## Parallel Opportunities

### Phase 1 (Setup)
```
T001 (migration file) — then in parallel:
  T002 (bookings API stub)
  T003 (search API stub)
  T004 (passenger layout)
  T005 (driver bookings page stub)
  T006 (components dir)
```

### Phase 2 (Foundation) — after T007 applied
```
In parallel:
  T008 (booking models)
  T009 (passenger dependency)
  T010 (booking_service scaffold)
  T011 (notification helper)
```

### Phase 3 (US1) — after Foundation
```
T012 (search endpoint) — independent
In parallel:
  T014 (RideSearchForm)
  T015 (RideCard)
Then: T013 (wire router), T016 (search page)
```

### Phase 6 (US4) — after US3
```
T024 (confirm service) — independent
T025 (reject service) — independent
T026 (driver list endpoint) — independent
In parallel (frontend):
  T029 (BookingCard)
  T030 (BookingStatusBadge)
Then: T027, T028, T031
```

---

## Implementation Strategy

### MVP First (US1 Only — Ride Search)

1. Complete Phase 1: Setup (T001–T006)
2. Complete Phase 2: Foundation (T007–T011) — **critical gate**
3. Complete Phase 3: US1 (T012–T016)
4. **VALIDATE**: Run quickstart.md Scenario 1 — confirm search returns candidates
5. Passengers can discover rides (search only, no booking yet)

### Full Incremental Delivery

```
Phase 1+2 → Foundation ready
Phase 3    → US1: Passengers can search rides  [MVP slice 1]
Phase 4    → US2: Passengers can view ride details  [MVP slice 2]
Phase 5    → US3: Passengers can book a seat  [MVP slice 3 — platform live]
Phase 6    → US4: Drivers can confirm/reject bookings  [MVP slice 4]
Phase 7    → US5: Both parties can cancel  [MVP slice 5]
Phase 8    → US6: My Bookings self-service  [MVP slice 6]
Phase 9    → Background automation  [production hardening]
Phase 10   → Polish and validation  [release ready]
```

### Parallel Team Strategy

Once Phase 2 (Foundation) is complete:
- **Developer A**: Phase 3 (US1 Search) → Phase 4 (US2 Detail) → Phase 5 (US3 Booking) — sequential backend + frontend
- **Developer B**: Phase 6 (US4 Driver Response) → Phase 7 (US5 Cancel) — after US3 creates bookings
- **Developer C**: Phase 8 (US6 My Bookings) → Phase 9 (Background) — after US3

---

## Notes

- **`booked_seats` is the writable column** — `available_seats` is generated and cannot be written directly. Every seat reservation increments `booked_seats`; every release decrements it.
- **`notification_service.enqueue_booking_notification`** maps Phase 6 booking events to rows in `email_notifications` (with `payload JSONB`). Phase 7 will add FCM delivery as a consumer of the same queue.
- **`booking_expiry_loop`** follows the exact same `asyncio.sleep` pattern as the existing `email_retry_loop()` — register both at startup in `main.py`.
- **RLS is the second security layer** — the FastAPI dependency checks ownership in application code, but Supabase RLS enforces it at the database layer independently. Both must be present.
- **Premium rejection fallback** (T025): if `premium_pickup_requested = true` and the boarding point geometry is within the standard walk threshold (500m), the booking is kept as confirmed at base price — do not cancel. This is FR-021.
- Commit after each phase checkpoint using `/speckit-git-commit`.
