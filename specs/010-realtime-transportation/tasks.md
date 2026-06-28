# Tasks: Real-Time Transportation

**Input**: Design documents from `specs/010-realtime-transportation/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅ | quickstart.md ✅

**Tests**: Not included — no test generation was requested in the spec.

**Organization**: Tasks grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Which user story ([US1]–[US4]) this task belongs to
- Exact file paths included in every task description

## Path Conventions

```
services/api/app/     → FastAPI backend
apps/main/src/        → Next.js frontend (passenger + driver)
supabase/migrations/  → Database migrations
```

---

## Phase 1: Setup

**Purpose**: Install new dependency and scaffold the new `users/` API module.

- [X] T001 Add `firebase-admin>=6.3.0` to `services/api/requirements.txt`
- [X] T002 [P] Add `firebase_service_account_secret_name: str = "firebase_service_account"` setting to `services/api/app/core/config.py`
- [X] T003 [P] Create empty `services/api/app/api/users/__init__.py` to scaffold the new users API module

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: All four database migrations, Supabase Realtime Authorization, FCM service, and Pydantic models. Every user story depends on these.

**⚠️ CRITICAL**: No user story work can begin until Phase 2 is complete.

- [X] T004 Write migration `supabase/migrations/20260628000001_phase7_device_tokens.sql`: create `user_device_tokens` table with `UNIQUE (token)` constraint, `idx_device_tokens_user_id` index, and RLS policy `user_manage_own_tokens` — see data-model.md §user_device_tokens
- [X] T005 [P] Write migration `supabase/migrations/20260628000002_phase7_notification_events.sql`: create `notification_event_type` enum (8 values), `notification_event_status` enum, `notification_events` table with `idx_notification_events_pending` partial index, and RLS policy `user_read_own_events` — see data-model.md §notification_events
- [X] T006 [P] Write migration `supabase/migrations/20260628000003_phase7_driver_locations.sql`: create `driver_locations` table with PostGIS `geometry(Point, 4326)` location column, `UNIQUE (ride_id)` constraint, `idx_driver_locations_ride_id` index, RLS policies for driver and confirmed passenger access, and `driver_locations_view` that exposes `lat`/`lng` as floats — see data-model.md §driver_locations
- [X] T007 [P] Write migration `supabase/migrations/20260628000004_phase7_rides_lifecycle.sql`: add `started_at TIMESTAMPTZ` and `completed_at TIMESTAMPTZ` nullable columns to `rides`; add `bookings` and `driver_locations` to Supabase Realtime publication via `ALTER PUBLICATION supabase_realtime ADD TABLE` — see data-model.md §rides extension
- [X] T008 Apply all four Phase 7 migrations: run `supabase db push` (or `supabase migration up`) and verify all four migrations applied without errors
- [X] T009 Enable **Supabase Realtime Authorization** in the Supabase project dashboard (Database → Replication → Realtime Authorization toggle) — required for RLS to filter Realtime events server-side per NFR-009; verify via Supabase Studio that the setting is active
- [X] T010 Implement `services/api/app/services/fcm_service.py`: load Firebase service account JSON from Supabase Vault using `vault.decrypted_secrets` view at startup, call `firebase_admin.initialize_app()`, expose `send_push_notifications(recipient_user_id, event_type, title, body, data_payload)` that fetches all active tokens for the user from `user_device_tokens`, calls `messaging.send_each_for_multicast()`, deregisters expired/invalid tokens (FR-004), and returns a count of successful sends — see research.md §1
- [X] T011 [P] Create `services/api/app/models/device_token.py`: Pydantic `DeviceTokenRequest` (fields: `token: str`, `platform: Literal["web", "android", "ios"]`) and `DeviceTokenResponse` (fields: `token_id: UUID`, `user_id: UUID`, `platform: str`, `last_seen_at: datetime`) — see contracts/api.md §Device Token Registration
- [X] T012 [P] Create `services/api/app/models/location.py`: Pydantic `LocationUpdateRequest` (fields: `lat: float`, `lng: float`, `bearing: Optional[int]`, `speed_kmh: Optional[float]`, `client_timestamp: datetime`) and `LocationResponse` (fields: `ride_id: UUID`, `lat: float`, `lng: float`, `bearing: Optional[int]`, `client_timestamp: datetime`, `updated_at: datetime`) — see contracts/api.md §Driver Location
- [X] T013 Update `_RIDE_COLS` SQL column list in `services/api/app/services/ride_service.py` to append `started_at, completed_at`; add `started_at: Optional[datetime]` and `completed_at: Optional[datetime]` fields to the `RideResponse` Pydantic model (or schema dict); update `_to_response()` to include these fields — required before US2 work can extend `start_ride()` and `complete_ride()`

**Checkpoint**: All migrations applied, FCM service initializable, Realtime Authorization enabled — user story implementation can begin.

---

## Phase 3: User Story 1 — FCM Push Notification Dispatch (Priority: P1) 🎯 MVP

**Goal**: Authenticated users can register FCM device tokens; a background dispatcher loop polls `notification_events` and sends FCM push notifications; booking lifecycle events from Phase 6 now also insert FCM notification rows; the driver ride-cancellation path also notifies confirmed passengers.

**Independent Test**: Register two users with FCM tokens. Trigger Phase 6 booking lifecycle events (confirm, reject, cancel, expire). Verify `notification_events` rows are inserted with `status = 'pending'`, the dispatcher updates them to `dispatched` within 30 seconds, and token-error responses from FCM trigger deregistration of that token. See quickstart.md Scenarios 1 and 5.

- [X] T014 [P] [US1] Implement `services/api/app/services/notification_dispatcher.py`: asyncio loop with `asyncio.sleep(30)`; inner function `_process_pending_notifications()` that acquires a pool connection, selects up to 100 `pending` notification_events rows `FOR UPDATE SKIP LOCKED`, for each row fetches recipient's device tokens from `user_device_tokens`, calls `fcm_service.send_push_notifications()` with the event's title/body/data (template per `event_type` from FR-007), updates `status = 'dispatched'` and `dispatched_at = now()` on success, or increments `retry_count` and sets `status = 'failed'` when `retry_count >= 3` on failure — see research.md §3 and §5
- [X] T015 [P] [US1] Implement `services/api/app/api/users/router.py`: `POST /users/me/device-tokens` endpoint using `get_current_user` dependency; upsert into `user_device_tokens` with `ON CONFLICT (token) DO UPDATE SET user_id = EXCLUDED.user_id, last_seen_at = now()`; return `DeviceTokenResponse` — see contracts/api.md §Device Token Registration and data-model.md §user_device_tokens
- [X] T016 [US1] Register `notification_dispatcher_loop` as `asyncio.create_task()` in `services/api/app/main.py` lifespan (alongside existing `email_task`, `expiry_task`, `pricing_task`); add cancellation in the yield-cleanup block; register `users_router` with `app.include_router(users_router, prefix="/api/v1/users", tags=["users"])`
- [X] T017 [P] [US1] Extend `services/api/app/services/booking_service.py`: inside each existing `async with conn.transaction()` block, add `notification_events` inserts — `confirm_booking()` → insert `booking_confirmed` event for `booking.passenger_id`; `reject_booking()` → insert `booking_rejected` event for `booking.passenger_id`; `cancel_booking()` → insert `booking_cancelled` event for the non-cancelling party; `booking_expiry_loop()` `_expire_pending_bookings()` → insert `booking_expired` event for each expired booking's `passenger_id` — all payloads must include `ride_id`, `booking_id`, `departure_datetime`, and the correct `deep_link` from contracts/api.md §data-model notification_events payload table
- [X] T018 [P] [US1] Extend `services/api/app/services/ride_service.py` `cancel_ride()`: after the existing `UPDATE rides SET status = 'cancelled'` and history log insert, add a query to find all `confirmed` bookings for `ride_id`, then insert one `ride_cancelled` `notification_event` row per confirmed passenger (recipient = `booking.passenger_id`); payload must include `ride_id`, `departure_datetime`, and `deep_link = "/(passenger)/bookings/{booking_id}"` — this must execute within the existing `conn.transaction()` block

**Checkpoint**: Device token registration works, notification_events rows are created on booking/ride lifecycle events, dispatcher loop dispatches them within 30 seconds and marks status correctly.

---

## Phase 4: User Story 2 — Ride Lifecycle: Start and Complete (Priority: P2)

**Goal**: `start_ride()` and `complete_ride()` record `started_at`/`completed_at`, insert `ride_started`/`ride_completed` notification events, `create_booking()` inserts `booking_received` for the driver, and the driver reminder loop sends a single overdue-pending-booking reminder after 2 hours.

**Independent Test**: Start a test ride with confirmed passengers; verify `rides.started_at` set, `notification_events` rows inserted for each passenger with `event_type = ride_started`. Complete the ride; verify `rides.completed_at`, Phase 6 booking cascade executed, `ride_completed` events inserted. Create a booking and age it to 2h 5m; verify exactly one `booking_received` reminder event appears within 5 minutes. See quickstart.md Scenarios 2, 6, and 7.

- [X] T019 [US2] Extend `start_ride()` in `services/api/app/services/ride_service.py`: change the UPDATE SQL to `SET status = 'in_progress', started_at = now(), updated_at = now()`; after the `ride_history_logs` insert, query `bookings` for all `confirmed` bookings on `ride_id` and insert one `notification_events` row per passenger with `event_type = 'ride_started'`, `recipient_user_id = booking.passenger_id`, and payload including `ride_id`, `booking_id`, `deep_link = "/(passenger)/rides/{ride_id}/tracking"` — all within the existing `conn.transaction()` block
- [X] T020 [US2] Extend `complete_ride()` in `services/api/app/services/ride_service.py`: change the UPDATE SQL to `SET status = 'completed', completed_at = now(), updated_at = now()`; after the `complete_ride_bookings()` cascade, query the now-`completed` bookings for `ride_id` and insert one `notification_events` row per passenger with `event_type = 'ride_completed'`, payload including `ride_id`, `booking_id`, `deep_link = "/(passenger)/bookings/{booking_id}"` — all within the existing `conn.transaction()` block
- [X] T021 [P] [US2] Extend `create_booking()` in `services/api/app/services/booking_service.py`: after the booking INSERT and `booked_seats` increment, inside the existing transaction, insert one `notification_events` row with `event_type = 'booking_received'`, `recipient_user_id = ride.driver_id`, and payload including `ride_id`, `booking_id`, `passenger_name` (fetched from `profiles`), `departure_datetime`, `deep_link = "/(driver)/rides/{ride_id}/bookings"` — implements FR-012
- [X] T022 [P] [US2] Implement `services/api/app/services/driver_reminder_service.py`: asyncio loop with `asyncio.sleep(300)`; inner function `_check_overdue_pending_bookings()` that executes a single atomic SQL INSERT (using a CTE or `INSERT ... SELECT ... WHERE NOT EXISTS`) to find `pending` bookings older than 2 hours that have no existing `booking_received` reminder `notification_event`, and insert one `notification_events` row per such booking with `recipient_user_id = ride.driver_id`; the check-and-insert MUST be atomic to satisfy FR-033 — see spec.md FR-031–FR-033 and research.md §3
- [X] T023 [US2] Register `driver_reminder_loop` as `asyncio.create_task()` in `services/api/app/main.py` lifespan (alongside existing tasks); add cancellation in the yield-cleanup block

**Checkpoint**: Ride start/complete record timestamps and insert notification events; booking creation notifies the driver; overdue bookings receive exactly one reminder.

---

## Phase 5: User Story 3 — Live Driver Location Tracking (Priority: P3)

**Goal**: Driver can POST GPS updates; passenger with a confirmed booking can GET and see live location via Supabase Realtime on the new tracking screen.

**Independent Test**: Start a test ride. POST 3 location updates 5 seconds apart as the driver. As a confirmed passenger, GET the location and verify lat/lng/bearing. Open the live tracking screen and verify the Leaflet pin moves within 3 seconds of each driver POST. Stop updates for 60 s; verify stale indicator appears. Complete ride; verify tracking screen auto-redirects after 3 seconds. See quickstart.md Scenarios 3, 4, and 8.

- [X] T024 [P] [US3] Implement `services/api/app/services/location_service.py`: `upsert_location(conn, ride_id, driver_id, lat, lng, bearing, speed_kmh, client_timestamp)` — verifies ride is `in_progress` and caller is the assigned driver, then executes PostGIS upsert `INSERT INTO driver_locations ... ON CONFLICT (ride_id) DO UPDATE SET ...` using `ST_SetSRID(ST_MakePoint($lng, $lat), 4326)` — see data-model.md §driver_locations upsert pattern and research.md §4; `read_location(conn, ride_id, caller_id)` — verifies caller has a `confirmed` booking on `ride_id`, queries `driver_locations` with `ST_Y(location) AS lat, ST_X(location) AS lng`
- [X] T025 [P] [US3] Implement `apps/main/src/lib/hooks/useDriverLocation.ts`: subscribes to `postgres_changes` UPDATE on `driver_locations` table with `filter: ride_id=eq.{rideId}` using `createClient()`; on each event, calls `getDriverLocation()` from `location.ts` to get fresh lat/lng/bearing (since raw Realtime payload does not expose PostGIS geometry as floats); tracks `updatedAt` and sets `isStale = Date.now() - new Date(updatedAt).getTime() > 60_000`; returns `{ location, isStale, error }`; cleans up channel in `useEffect` return — see contracts/frontend-pages.md §useDriverLocation
- [X] T026 [P] [US3] Implement `apps/main/src/lib/api/location.ts`: `reportLocation(token, rideId, data)` → `POST /api/v1/rides/{rideId}/location`; `getDriverLocation(token, rideId)` → `GET /api/v1/rides/{rideId}/location`, returns `null` on 404 — see contracts/frontend-pages.md §location.ts
- [X] T027 [US3] Add `POST /api/v1/rides/{ride_id}/location` and `GET /api/v1/rides/{ride_id}/location` endpoints to `services/api/app/api/rides/router.py`: POST uses `get_current_verified_driver` dependency and calls `location_service.upsert_location()`; GET uses `get_current_user` dependency and calls `location_service.read_location()`; both delegate ownership/access checks to `location_service`; use `LocationUpdateRequest` and `LocationResponse` models — see contracts/api.md §Driver Location
- [X] T028 [US3] Implement `apps/main/src/components/tracking/LiveTrackingMap.tsx`: Leaflet map initialized in `useEffect` with `useRef` (same pattern as `RideMap.tsx`); displays a `L.marker` at `location.lat, location.lng`; when `location.bearing` is non-null, applies `rotate(${location.bearing}deg)` CSS transform to a custom directional marker icon; calls `marker.setLatLng()` on each location update rather than destroying and recreating the marker; centers map on first position load; accepts `location` and `isStale` props
- [X] T029 [P] [US3] Implement `apps/main/src/components/tracking/TrackingStatusBanner.tsx`: accepts `isStale: boolean`, `rideCompleted: boolean`, `onRedirectComplete: () => void` props; when `isStale`, renders a yellow "Driver location may be outdated" strip; when `rideCompleted`, renders "Ride Completed" with a 3-second countdown using `useEffect` + `setTimeout`, then calls `onRedirectComplete`
- [X] T030 [US3] Implement `apps/main/src/app/(passenger)/rides/[id]/tracking/page.tsx`: on mount, fetch session + verify confirmed booking exists for `[id]`; use `useDriverLocation(rideId)` hook; subscribe to `bookings` Realtime UPDATE to detect `status = 'completed'` for the passenger's booking; render `LiveTrackingMap` with current location and `isStale`, and `TrackingStatusBanner`; on `rideCompleted = true` trigger auto-redirect to `/(passenger)/bookings/{bookingId}`; handle 404 from location GET (driver hasn't reported yet) with "Location unavailable" state — see contracts/frontend-pages.md §tracking/page.tsx

**Checkpoint**: Driver can push location updates; confirmed passengers see live map pin movement within 3 seconds; stale indicator appears after 60 s; tracking screen auto-redirects on ride completion.

---

## Phase 6: User Story 4 — Real-Time In-App Status Updates (Priority: P4)

**Goal**: Booking status changes (confirmed, rejected, cancelled) reflect in-app within 3 seconds on passenger booking screens without page reload; new pending bookings appear in driver booking queue in real time.

**Independent Test**: Open "My Bookings" in browser tab A as passenger. In tab B as driver, confirm the pending booking. Verify status badge in tab A changes to "Confirmed" within 3 seconds without reload. Open driver booking queue; create a new booking from a second passenger account; verify new booking card appears in real time. See quickstart.md Scenario 8.

- [X] T031 [P] [US4] Implement `apps/main/src/lib/hooks/useBookingStatus.ts`: accepts `filter: { passengerId?: string; bookingId?: string; rideId?: string }`; subscribes to `postgres_changes` INSERT and UPDATE events on `bookings` table with the appropriate filter expression; exposes `lastEvent: RealtimePostgresChangesPayload<BookingRow> | null`; removes channel subscription on component unmount — see contracts/frontend-pages.md §useBookingStatus
- [X] T032 [P] [US4] Implement `apps/main/src/lib/api/device-tokens.ts`: `registerDeviceToken(token, data)` → `POST /api/v1/users/me/device-tokens` — see contracts/frontend-pages.md §device-tokens.ts
- [X] T033 [US4] Extend `apps/main/src/app/(passenger)/bookings/page.tsx` to call `useBookingStatus({ passengerId: userId })` hook; when `lastEvent` contains an UPDATE to a booking already in the local state list, replace that item's `status` with `lastEvent.new.status` and re-render the status badge — no full data refetch needed
- [X] T034 [US4] Extend `apps/main/src/app/(passenger)/bookings/[id]/page.tsx` to call `useBookingStatus({ bookingId: params.id })` hook; when an UPDATE event arrives, update the displayed status and conditionally show/hide the cancel button (cancel only shown when `status === 'confirmed'`)
- [X] T035 [US4] Extend `apps/main/src/app/(driver)/rides/[id]/bookings/page.tsx` to subscribe to Realtime INSERT events on `bookings` filtered by `ride_id = [id]`; on INSERT event, prepend the new booking card to the existing list using the `lastEvent.new` payload (display name may require a separate fetch for passenger details)

**Checkpoint**: All booking lifecycle status changes propagate in real time to open passenger screens; new bookings appear in the driver queue without refresh.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Logging verification, metrics, and final end-to-end validation.

- [ ] T036 [P] Add structured log entries (endpoint name, input params sanitized, output summary, duration ms, error details) to all new backend endpoints and background loops per NFR-010: `POST /users/me/device-tokens`, `POST /rides/{id}/location`, `GET /rides/{id}/location`, `notification_dispatcher_loop`, `driver_reminder_loop`
- [ ] T037 Run quickstart.md validation scenarios 1–8 end-to-end against the deployed Phase 7 implementation and confirm all acceptance criteria from spec.md SC-001 through SC-007 pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Requires Phase 1 — **blocks all user stories**
- **Phase 3 (US1)**: Requires Phase 2 — FCM notification dispatch
- **Phase 4 (US2)**: Requires Phase 2; depends on T013 (\_RIDE\_COLS) specifically — ride lifecycle extensions
- **Phase 5 (US3)**: Requires Phase 2 and T009 (Realtime Authorization) — location tracking
- **Phase 6 (US4)**: Requires Phase 2 and T009; depends on T031 (useBookingStatus hook) for T033–T035 — in-app status updates
- **Phase 7 (Polish)**: Requires Phases 3–6 complete

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 2 — no dependencies on US2/US3/US4
- **US2 (P2)**: Depends on Phase 2 (specifically T013 for \_RIDE\_COLS); no dependency on US1 at code level, but US1 must be complete for notification events to be dispatched
- **US3 (P3)**: Depends on Phase 2 (specifically T009 Realtime Authorization) and T005/T006 migrations; no dependency on US1/US2 endpoints but notification events for ride_started won't exist without US2
- **US4 (P4)**: Depends on Phase 2 T009 (Realtime Authorization) and T005 migration; frontend hooks T033–T035 depend on T031 (useBookingStatus hook)

### Within Each Phase — Key Sequential Constraints

- **Phase 2**: T004–T007 (migrations) can run in parallel → T008 (apply) depends on all four → T009–T013 can run in parallel after T008
- **Phase 3**: T014+T015+T017+T018 can run in parallel → T016 (main.py register) depends on T014 and T015
- **Phase 4**: T021+T022 can run in parallel with T019 → T020 depends on T019 (same file `complete_ride`) → T023 (main.py) depends on T022
- **Phase 5**: T024+T025+T026 can run in parallel → T027 depends on T024 → T028+T029 can run in parallel after T026 → T030 depends on T027+T028+T029
- **Phase 6**: T031+T032 can run in parallel → T033+T034+T035 depend on T031

---

## Parallel Example: Phase 2 (Foundational)

```bash
# These four migration files can be written simultaneously:
Task T004: "Write migration 20260628000001_phase7_device_tokens.sql"
Task T005: "Write migration 20260628000002_phase7_notification_events.sql"
Task T006: "Write migration 20260628000003_phase7_driver_locations.sql"
Task T007: "Write migration 20260628000004_phase7_rides_lifecycle.sql"

# Then apply together:
Task T008: "Apply all four Phase 7 migrations"

# Then these can run in parallel after T008:
Task T010: "Implement fcm_service.py"
Task T011: "Create models/device_token.py"
Task T012: "Create models/location.py"
Task T013: "Update _RIDE_COLS in ride_service.py"
```

## Parallel Example: Phase 3 (US1)

```bash
# These four run in parallel after Phase 2:
Task T014: "Implement notification_dispatcher.py"
Task T015: "Implement users/router.py POST device-tokens"
Task T017: "Extend booking_service.py notification inserts"
Task T018: "Extend ride_service.py cancel_ride notification inserts"

# T016 depends on T014 + T015:
Task T016: "Register dispatcher loop and users router in main.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T013) — **CRITICAL, blocks everything**
3. Complete Phase 3: US1 (T014–T018) — FCM dispatcher + device token registration
4. **STOP and VALIDATE**: Tokens register, booking events insert notification_events rows, dispatcher dispatches them
5. Demo: notifications arrive on device when a booking is confirmed or rejected

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → FCM notifications working (MVP)
3. US2 → Ride start/complete with `started_at`/`completed_at` and ride lifecycle notifications
4. US3 → Live location tracking screen
5. US4 → In-app real-time status updates
6. Polish → Structured logging, metrics validation, end-to-end quickstart run

---

## Notes

- [P] tasks operate on different files and have no shared dependencies within their phase
- T009 (Realtime Authorization) is a dashboard configuration step, not a code task — must be done before any Realtime subscription testing
- The `start_ride()` and `complete_ride()` backend endpoints already exist and work; T019/T020 are targeted extensions only (add columns to SQL + insert notification events)
- T013 (`_RIDE_COLS` update) must complete before T019/T020 — the RETURNING clause will fail if `started_at`/`completed_at` are not in the column list
- Commit after each task or logical group; each Phase checkpoint is a natural commit boundary
