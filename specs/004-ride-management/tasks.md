# Tasks: Ride Management

**Input**: Design documents from `specs/004-ride-management/`

**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/rides-api.md ✅ · quickstart.md ✅

**Tests**: Not included — not requested in the specification.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete peer task)
- **[Story]**: Which user story this task belongs to (US1–US6)

---

## Phase 1: Setup

**Purpose**: Install new dependencies and create the directory structure needed for Ride Management.

- [ ] T001 Install backend dependencies: `GeoAlchemy2`, `resend` — add to `backend/requirements.txt`
- [ ] T002 [P] Install frontend dependencies: `leaflet`, `react-leaflet`, `@types/leaflet` — add to `apps/main/package.json`
- [ ] T003 [P] Add Leaflet CSS import to `apps/main/src/app/layout.tsx` (`import 'leaflet/dist/leaflet.css'`)
- [ ] T004 [P] Add environment variables to `apps/main/.env.example`: `NEXT_PUBLIC_NOMINATIM_URL`
- [ ] T005 [P] Add environment variables to `backend/.env.example`: `RESEND_API_KEY`, `WEBHOOK_SECRET`
- [ ] T006 Create frontend directory structure: `apps/main/src/app/(driver)/rides/`, `apps/main/src/app/(driver)/rides/new/`, `apps/main/src/app/(driver)/rides/[id]/`, `apps/main/src/app/(driver)/rides/[id]/edit/`, `apps/main/src/components/rides/`, `apps/main/src/lib/api/rides.ts`
- [ ] T007 [P] Create backend directory structure: `backend/src/api/rides.py`, `backend/src/models/ride.py`, `backend/src/services/ride_service.py`, `backend/src/services/revocation_service.py`, `backend/src/services/notification_service.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database schema, core models, shared types, and router registration — everything all user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T008 Create Supabase migration file for enums: `ride_status` (`scheduled`, `in_progress`, `completed`, `cancelled`), `ride_action` (`created`, `edited`, `cancelled`, `started`, `completed`), `email_notification_status` (`pending`, `sent`, `failed`, `failed_permanent`) — in `supabase/migrations/`
- [ ] T009 Create Supabase migration for `rides` table per `data-model.md`: UUID PK, `driver_id`, `vehicle_id`, `origin_coordinates geography(Point,4326)`, `origin_address`, `destination_coordinates geography(Point,4326)`, `destination_address`, `departure_datetime`, `total_seats`, `booked_seats DEFAULT 0`, `available_seats GENERATED ALWAYS AS (total_seats - booked_seats) STORED`, `price_per_seat`, `status ride_status DEFAULT 'scheduled'`, `cancellation_reason`, `cancellation_source`, `notes`, `created_at`, `updated_at`
- [ ] T010 Add all indexes to the `rides` migration: `idx_rides_driver_status (driver_id, status)`, `idx_rides_driver_departure (driver_id, departure_datetime)`, `GIST idx_rides_origin_geo (origin_coordinates)`, `GIST idx_rides_destination_geo (destination_coordinates)`
- [ ] T011 Add RLS policies to `rides` migration: `driver_read_own_rides` (SELECT where `driver_id = auth.uid()`); no direct client INSERT/UPDATE (service role only)
- [ ] T012 [P] Create Supabase migration for `ride_history_logs` table: UUID PK, `ride_id`, `actor_id` (nullable), `action ride_action`, `changed_fields jsonb`, `reason text`, `created_at`; index `idx_ride_history_ride_id (ride_id, created_at)`; RLS: driver reads own ride's history only
- [ ] T013 [P] Create Supabase migration for `email_notifications` table: UUID PK, `ride_id`, `passenger_id`, `passenger_email`, `notification_type DEFAULT 'ride_cancelled'`, `status email_notification_status DEFAULT 'pending'`, `retry_count DEFAULT 0`, `last_attempted_at`, `created_at`; partial index on `(status, created_at) WHERE status IN ('pending','failed')`; RLS: service role only
- [ ] T014 Create SQLAlchemy models in `backend/src/models/ride.py`: `Ride`, `RideHistoryLog`, `EmailNotification` mapped to the tables above; include `updated_at` trigger hook (or `onupdate=func.now()`)
- [ ] T015 [P] Create Pydantic request/response schemas in `backend/src/models/ride.py`: `CoordinatesSchema`, `LocationSchema`, `CreateRideRequest`, `EditRideRequest`, `CancelRideRequest`, `RideResponse`, `RideDetailResponse` (ride + history), `RideListResponse`
- [ ] T016 [P] Create shared TypeScript types in `packages/shared-types/src/rides.ts`: `RideStatus`, `RideAction`, `Coordinates`, `Location`, `Ride`, `RideHistoryEntry`, `CreateRidePayload`, `EditRidePayload`, `CancelRidePayload`
- [ ] T017 Create FastAPI router in `backend/src/api/rides.py`: register all route stubs (returning `501 Not Implemented`) — `POST /api/v1/rides`, `GET /api/v1/rides`, `GET /api/v1/rides/{ride_id}`, `PATCH /api/v1/rides/{ride_id}`, `POST /api/v1/rides/{ride_id}/cancel`, `POST /api/v1/rides/{ride_id}/start`, `POST /api/v1/rides/{ride_id}/complete`, `POST /api/v1/internal/driver-revocation`; register router in `backend/src/main.py`
- [ ] T018 [P] Implement status transition validator in `backend/src/services/ride_service.py`: a dict mapping `(ride_status, action) → new_status`; raise `ride_not_editable` error for invalid transitions; raise `start_too_early` if current time < departure when action is `start`
- [ ] T019 [P] Implement `get_verified_driver_dependency` FastAPI dependency in `backend/src/api/rides.py`: reads the JWT, fetches the user, asserts `verification_status == 'verified'` and an approved vehicle exists — returns `(user, vehicle)` or raises `403 not_verified_driver`
- [ ] T020 [P] Implement error response helper in `backend/src/api/rides.py` matching the error schema from `contracts/rides-api.md`: `ride_not_found`, `ride_not_editable`, `ride_time_conflict`, `ride_departure_past`, `ride_departure_too_far`, `ride_same_locations`, `seat_count_invalid`, `start_too_early`, `reason_required`
- [ ] T021 [P] Create `apps/main/src/lib/api/rides.ts`: API client module stub with typed functions `createRide`, `listRides`, `getRide`, `editRide`, `cancelRide`, `startRide`, `completeRide` — each calls the backend with the Supabase session Bearer token

**Checkpoint**: Database schema applied, models wired up, router registered, shared types in place — user story implementation can begin.

---

## Phase 3: User Story 1 — Create a Ride (Priority: P1) 🎯 MVP

**Goal**: A verified driver with an approved vehicle can post a new ride by dropping pins for origin and destination, entering a departure time within 48 hours, selecting seats, and setting a price.

**Independent Test**: Quickstart scenario 1 (create ride → status `scheduled`, `available_seats = total_seats`) and scenario 2 (unverified driver blocked) and scenario 3 (departure beyond 48 hours blocked).

- [ ] T022 [P] [US1] Create `RideMap` component in `apps/main/src/components/rides/RideMap.tsx`: renders a `react-leaflet` `MapContainer` with OpenStreetMap tiles; accepts an `onPinDrop(lat, lng)` callback; on map click places a marker and calls a `GET` to `NEXT_PUBLIC_NOMINATIM_URL/reverse?lat={lat}&lon={lng}&format=json` (debounced 300ms) to fetch the address label; exposes `coordinates` and `address` to parent
- [ ] T023 [P] [US1] Create `RideForm` component in `apps/main/src/components/rides/RideForm.tsx`: composes two `RideMap` instances (origin, destination) plus inputs for `departure_datetime` (datetime-local), `total_seats` (1 to vehicle capacity), `price_per_seat`, and `notes`; validates same-location, past departure, >48h departure, and zero seats client-side before submit; calls `onSubmit(payload: CreateRidePayload)`
- [ ] T024 [US1] Implement `createRide` in `apps/main/src/lib/api/rides.ts`: POST to `/api/v1/rides` with Bearer token; return typed `Ride` or throw typed error
- [ ] T025 [US1] Create `apps/main/src/app/(driver)/rides/new/page.tsx`: renders `RideForm`; on success redirects to `/driver/rides/{id}`; shows backend error messages inline
- [ ] T026 [US1] Implement `create_ride()` in `backend/src/services/ride_service.py`:
  - Assert driver verified + vehicle approved (via dependency T019)
  - Validate origin ≠ destination (compare coordinates)
  - Validate departure > now and departure ≤ now + 48h
  - Validate `total_seats` ≥ 1 and ≤ `vehicle.passenger_seat_count`
  - Acquire `pg_advisory_xact_lock(hashtext(driver_id::text))`
  - Query for any existing `scheduled`/`in_progress` ride within 2h window; raise `ride_time_conflict` if found
  - INSERT into `rides` with `status='scheduled'`, `booked_seats=0`
  - INSERT into `ride_history_logs` with `action='created'`
  - Return `Ride` response
- [ ] T027 [US1] Wire `POST /api/v1/rides` endpoint in `backend/src/api/rides.py` to call `create_ride()`; apply `get_verified_driver_dependency`; return `201` with `RideResponse`

**Checkpoint**: Verified driver can create a ride end-to-end. Unverified driver gets `403`. Past / >48h departure gets `400`. Duplicate time window gets `409`.

---

## Phase 4: User Story 2 — Edit a Ride (Priority: P2)

**Goal**: A driver can update the destination, departure time, seat count, price, or notes on a `scheduled` ride; every change is recorded in the history log.

**Independent Test**: Quickstart scenario 4 (edit price → persisted) and verify `changed_fields` in history.

- [ ] T028 [P] [US2] Implement `edit_ride()` in `backend/src/services/ride_service.py`:
  - Fetch ride by `ride_id`; return `ride_not_found` if missing or `driver_id ≠ caller`
  - Assert `status == 'scheduled'`; raise `ride_not_editable` otherwise
  - For seat count changes: assert new `total_seats >= ride.booked_seats`
  - Re-run departure time validations if `departure_datetime` is in the payload
  - Compute `changed_fields` dict from before/after values of modified fields
  - UPDATE `rides` row; UPDATE `updated_at`
  - INSERT `ride_history_logs` with `action='edited'`, `changed_fields=changed_fields`
  - Return updated `Ride`
- [ ] T029 [US2] Wire `PATCH /api/v1/rides/{ride_id}` in `backend/src/api/rides.py` to call `edit_ride()`; return `200` with updated `RideResponse`
- [ ] T030 [P] [US2] Implement `editRide` in `apps/main/src/lib/api/rides.ts`: PATCH to `/api/v1/rides/{id}` with partial payload
- [ ] T031 [US2] Create `apps/main/src/app/(driver)/rides/[id]/edit/page.tsx`: fetches existing ride data, pre-populates `RideForm` with current values (reuse T023 component), calls `editRide` on submit; on success redirects back to `/driver/rides/{id}`

**Checkpoint**: Driver can edit a scheduled ride and the change appears in the history log. Edit on non-scheduled ride returns `409`.

---

## Phase 5: User Story 3 — Cancel a Ride (Priority: P3)

**Goal**: A driver can cancel a `scheduled` ride by providing a mandatory reason; the ride moves to `cancelled` and is excluded from active listings.

**Independent Test**: Quickstart scenario 6 (cancel with reason → status `cancelled`; cancel without reason → `400`).

- [ ] T032 [P] [US3] Implement `cancel_ride()` in `backend/src/services/ride_service.py`:
  - Fetch ride; assert ownership; assert `status == 'scheduled'`
  - Assert `reason` is non-empty; raise `reason_required` otherwise
  - UPDATE `rides`: `status='cancelled'`, `cancellation_reason=reason`, `cancellation_source='driver'`, `updated_at=now()`
  - INSERT `ride_history_logs` with `action='cancelled'`, `reason=reason`, `actor_id=driver_id`
  - Call `notification_service.enqueue_cancellation_emails(ride_id)` (no-op until Phase 6 bookings exist)
  - Return updated `Ride`
- [ ] T033 [US3] Wire `POST /api/v1/rides/{ride_id}/cancel` in `backend/src/api/rides.py` to `cancel_ride()`; return `200` with updated `RideResponse`
- [ ] T034 [P] [US3] Implement `cancelRide` in `apps/main/src/lib/api/rides.ts`
- [ ] T035 [P] [US3] Create `CancelRideModal` sub-component in `apps/main/src/components/rides/StartCompleteActions.tsx`: modal dialog with a required textarea for cancellation reason; calls `cancelRide` on confirm; closes and updates UI on success
- [ ] T036 [US3] Implement `enqueue_cancellation_emails()` stub in `backend/src/services/notification_service.py`: queries `email_notifications` for booked passengers on the ride (returns empty result until Phase 6 booking table exists); for each, INSERT a `pending` row into `email_notifications`

**Checkpoint**: Driver can cancel a scheduled ride with a reason. Ride appears in "Cancelled" filter. Cancel without reason returns `400`. Cancel on in-progress/completed ride returns `409`.

---

## Phase 6: User Story 4 — Seat Management (Priority: P4)

**Goal**: `available_seats` is always accurate (`total_seats − booked_seats`), never negative, and the UI reflects the current seat counts at all times.

**Independent Test**: Quickstart scenario 5 (edit seats → `available_seats` recalculated; `available_seats` never negative).

- [ ] T037 [P] [US4] Create `RideStatusBadge` component in `apps/main/src/components/rides/RideStatusBadge.tsx`: colour-coded pill for each `RideStatus` value (e.g., blue=scheduled, yellow=in_progress, green=completed, red=cancelled)
- [ ] T038 [P] [US4] Create `RideCard` component in `apps/main/src/components/rides/RideCard.tsx`: displays `origin_address → destination_address`, `departure_datetime`, `available_seats / total_seats`, `price_per_seat`, `RideStatusBadge`; links to `/driver/rides/{id}`
- [ ] T039 [US4] Add explicit backend guard in `edit_ride()` in `backend/src/services/ride_service.py` (already started in T028): when `total_seats` is being reduced, assert `new_total_seats >= ride.booked_seats`; return `seat_count_invalid` error if violated. Confirm the `available_seats` generated column is returning correctly in the `RideResponse` schema (read from DB, never computed in Python)
- [ ] T040 [US4] Validate seat invariant in the `GET /api/v1/rides/{ride_id}` response (T044): confirm `available_seats` value matches `total_seats - booked_seats` in the returned JSON to catch any model serialisation gaps

**Checkpoint**: Seat counts are always accurate in both the API response and the UI cards. Attempting to reduce seats below booked count returns `seat_count_invalid`.

---

## Phase 7: User Story 5 — Driver Ride Dashboard (Priority: P5)

**Goal**: Driver can view all their rides in a filterable list, open any ride for full detail and history, and access the Create/Edit/Cancel/Start/Complete actions.

**Independent Test**: Quickstart scenario 9 (dashboard loads <2s, status filter works) and scenario 10 (accessing another driver's ride returns `ride_not_found`).

- [ ] T041 [P] [US5] Implement `listRides` in `apps/main/src/lib/api/rides.ts`: GET `/api/v1/rides?status={filter}&page={n}&page_size=20`; return `RideListResponse`
- [ ] T042 [P] [US5] Implement `getRide` in `apps/main/src/lib/api/rides.ts`: GET `/api/v1/rides/{id}`; return `RideDetailResponse` (ride + history)
- [ ] T043 [P] [US5] Implement `list_rides()` in `backend/src/services/ride_service.py`: SELECT from `rides` where `driver_id = caller.id`; apply optional status filter; ORDER BY `created_at DESC`; paginate; return list + total count
- [ ] T044 [P] [US5] Implement `get_ride()` in `backend/src/services/ride_service.py`: SELECT `rides` + JOIN `ride_history_logs` where `rides.driver_id = caller.id`; return `ride_not_found` (as 404) if ride belongs to another driver
- [ ] T045 [US5] Wire `GET /api/v1/rides` in `backend/src/api/rides.py` to `list_rides()`; return `200` with `RideListResponse`
- [ ] T046 [US5] Wire `GET /api/v1/rides/{ride_id}` in `backend/src/api/rides.py` to `get_ride()`; return `200` with `RideDetailResponse`
- [ ] T047 [P] [US5] Create `RideHistoryLog` component in `apps/main/src/components/rides/RideHistoryLog.tsx`: renders a timeline of `RideHistoryEntry` items with action label, actor (or "System"), timestamp, and `changed_fields` diff for `edited` entries
- [ ] T048 [US5] Create `apps/main/src/app/(driver)/rides/page.tsx` (My Rides dashboard): fetches `listRides`; renders status filter tabs (Scheduled / In Progress / Completed / Cancelled / All); renders `RideCard` list; includes a "Post a Ride" button linking to `/driver/rides/new`
- [ ] T049 [US5] Create `apps/main/src/app/(driver)/rides/[id]/page.tsx` (Ride detail): fetches `getRide`; displays full ride info, `RideStatusBadge`, seat counts, `RideHistoryLog`; renders `StartCompleteActions` with appropriate action buttons per status; includes Edit and Cancel links/buttons
- [ ] T050 [US5] Create `StartCompleteActions` component in `apps/main/src/components/rides/StartCompleteActions.tsx`: shows "Start Ride" button when `status=scheduled` (disabled until `now >= departure_datetime`); shows "Complete Ride" button when `status=in_progress`; includes `CancelRideModal` (from T035) when `status=scheduled`; calls `startRide` / `completeRide` / `cancelRide` from the API client
- [ ] T051 [US5] Add `(driver)` route group layout `apps/main/src/app/(driver)/layout.tsx`: guards page for driver role (redirect non-drivers); provides driver navigation header linking to `/driver/rides`

**Checkpoint**: Dashboard lists rides with correct filter, detail view shows history, seat counts, and status actions. Another driver's ride returns 404.

---

## Phase 8: User Story 6 — Verification Revocation Handling (Priority: P6)

**Goal**: When an admin revokes a driver's verification or vehicle, all their `scheduled` rides are automatically cancelled within 1 minute and an apology email is queued for each booked passenger.

**Independent Test**: Quickstart scenario 8 (admin suspends driver → scheduled rides auto-cancelled within 1 minute → driver blocked from creating new rides; `cancellation_source = "system"`).

- [ ] T052 [P] [US6] Implement `send_cancellation_email()` in `backend/src/services/notification_service.py`: calls the Resend API (`resend.Emails.send(...)`) with a simple text/HTML apology template; updates the `email_notifications` row to `sent` on success or increments `retry_count` and updates `last_attempted_at` on failure; marks `failed_permanent` after 5 retries
- [ ] T053 [P] [US6] Implement `retry_pending_emails()` in `backend/src/services/notification_service.py`: queries `email_notifications` where `status IN ('pending','failed')` and `retry_count < 5`; calls `send_cancellation_email()` for each; respects exponential backoff timestamps (`last_attempted_at + backoff_minutes`)
- [ ] T054 [US6] Implement `handle_driver_revocation()` in `backend/src/services/revocation_service.py`:
  - Accepts `driver_id` and `revocation_type`
  - In a single transaction: SELECT all rides where `driver_id=driver_id AND status='scheduled'` FOR UPDATE
  - Bulk UPDATE `rides` to `status='cancelled'`, `cancellation_source='system'`, `cancellation_reason='Driver verification revoked'`
  - Bulk INSERT `ride_history_logs` rows with `action='cancelled'`, `actor_id=NULL`, `reason='Driver verification revoked'`
  - For each cancelled ride call `notification_service.enqueue_cancellation_emails(ride_id)`
  - Return count of cancelled rides
- [ ] T055 [US6] Wire `POST /api/v1/internal/driver-revocation` in `backend/src/api/rides.py`:
  - Validate `X-Webhook-Secret` header against `WEBHOOK_SECRET` env var; return `401` on mismatch
  - Call `handle_driver_revocation(driver_id, revocation_type)`
  - Return `200` with `{ "cancelled_rides": N, "notification_emails_queued": M }`
- [ ] T056 [US6] Register email retry background sweep in `backend/src/main.py`: on FastAPI `startup` event, launch `asyncio.create_task` that loops every 5 minutes calling `notification_service.retry_pending_emails()`
- [ ] T057 [US6] Configure Supabase Database Webhook in Supabase dashboard: on `UPDATE` to `users` table when `verification_status` changes to `'suspended'` → POST to `{API_BASE}/api/v1/internal/driver-revocation` with `X-Webhook-Secret` header and body `{"driver_id": "{{record.id}}", "revocation_type": "identity"}`; document configuration steps in `specs/004-ride-management/quickstart.md` (append a "Webhook Setup" section)
- [ ] T058 [US6] Configure a second Supabase Database Webhook: on `UPDATE` to `vehicles` table when `active` changes to `false` → POST to the same endpoint with `revocation_type: "vehicle"` and `driver_id` from `vehicles.driver_id`

**Checkpoint**: Suspending a driver's verification triggers auto-cancellation of all their scheduled rides within 1 minute. `cancellation_source` is `"system"`. Apology emails are queued. Driver is blocked from creating new rides (existing FR-001 / FR-018 enforcement).

---

## Phase 9: Ride Lifecycle Actions + Polish

**Purpose**: Implement start/complete ride actions, connect all components into a coherent flow, and validate the full feature with quickstart scenarios.

- [ ] T059 [P] Implement `start_ride()` in `backend/src/services/ride_service.py`: fetch ride; assert ownership; assert `status == 'scheduled'`; assert `now() >= departure_datetime` (raise `start_too_early` otherwise); UPDATE `status='in_progress'`, `updated_at`; INSERT `ride_history_logs` with `action='started'`
- [ ] T060 [P] Implement `complete_ride()` in `backend/src/services/ride_service.py`: fetch ride; assert ownership; assert `status == 'in_progress'`; UPDATE `status='completed'`, `updated_at`; INSERT `ride_history_logs` with `action='completed'`
- [ ] T061 Wire `POST /api/v1/rides/{ride_id}/start` in `backend/src/api/rides.py` to `start_ride()`
- [ ] T062 Wire `POST /api/v1/rides/{ride_id}/complete` in `backend/src/api/rides.py` to `complete_ride()`
- [ ] T063 [P] Implement `startRide` and `completeRide` in `apps/main/src/lib/api/rides.ts`
- [ ] T064 [P] Add driver-home navigation entry point: update `apps/main/src/app/(app)/` home screen to include a "My Rides" card/button linking to `/driver/rides` (visible only to driver-role users)
- [ ] T065 [P] Ensure `apps/main/src/app/(driver)/rides/new/page.tsx` is linked from the dashboard's "Post a Ride" button (T048 already includes the link; verify routing works end-to-end)
- [ ] T066 [P] Add `updated_at` auto-update trigger or `onupdate` hook to the `rides` SQLAlchemy model in `backend/src/models/ride.py` if not already set (ensures `updated_at` reflects every mutation)
- [ ] T067 Run all 10 quickstart validation scenarios from `specs/004-ride-management/quickstart.md` and confirm each passes
- [ ] T068 [P] Verify GIST indexes exist on `origin_coordinates` and `destination_coordinates` in production DB (run `\d rides` in psql or Supabase SQL editor to confirm index names)
- [ ] T069 [P] Confirm Nominatim debounce (300ms) is in place in `RideMap.tsx` (T022) to stay within the 1 req/s rate limit
- [ ] T070 [P] Confirm `available_seats` is never returned as writable in the API — it must be read-only in `RideResponse` (Pydantic field with no setter); add a note in `backend/src/models/ride.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately; T002–T007 all run in parallel
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user story phases
- **Phase 3 (US1)**: Depends on Phase 2 — MVP milestone; all other user stories depend on US1's DB schema
- **Phase 4 (US2)**: Depends on Phase 2; independent of US1's frontend (shares backend model)
- **Phase 5 (US3)**: Depends on Phase 2; `notification_service` stub (T036) must exist before T032
- **Phase 6 (US4)**: Depends on Phase 2; `RideCard` (T038) reused by Phase 7 (US5)
- **Phase 7 (US5)**: Depends on Phase 2 + Phase 6 (T037, T038 for `RideCard`/`RideStatusBadge`); incorporates actions from US2 + US3 + US6
- **Phase 8 (US6)**: Depends on Phase 2 + Phase 5 (notification stub T036); fully independent of US2–US5
- **Phase 9 (Polish)**: Depends on all user story phases

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependency on other user stories
- **US2 (P2)**: Can start after Phase 2 — shares `ride_service.py` with US1 but adds new function
- **US3 (P3)**: Can start after Phase 2 + notification stub (T036)
- **US4 (P4)**: Can start after Phase 2; builds on `RideCard` and reuses `edit_ride()` guard from US2
- **US5 (P5)**: Can start after Phase 2 + Phase 6 (`RideCard`, `RideStatusBadge`)
- **US6 (P6)**: Can start after Phase 2 + notification stub (T036); fully independent of US2–US5

### Within Each User Story

- Backend service function → Backend endpoint wiring → Frontend API client → Frontend page/component

### Parallel Opportunities

- Phase 1: T002–T007 all in parallel
- Phase 2: T008–T009–T010–T011 are sequential (one migration); T012, T013, T014, T015, T016, T018, T019, T020, T021 all run in parallel after T011
- US1: T022 (RideMap) and T023 (RideForm) in parallel; T026 (service) in parallel with T022/T023
- US2: T028 (service) and T030 (API client) in parallel; T031 (page) after T028+T030
- US5: T041–T044 and T047 all in parallel; T048+T049 after T041+T042+T043+T044+T047
- US6: T052 and T053 in parallel; T054 after T052; T057 and T058 in parallel after T055
- Phase 9: T059, T060, T063, T064, T066, T068, T069, T070 all in parallel

---

## Parallel Example: User Story 1

```text
# These tasks have no dependencies on each other — run in parallel:
T022  Create RideMap.tsx (react-leaflet + Nominatim reverse geocode)
T023  Create RideForm.tsx (origin + destination maps + fields)
T026  Implement create_ride() service (advisory lock, validations, DB insert)

# After T023 + T024 complete:
T025  Create /driver/rides/new/page.tsx (composes RideForm, calls createRide)

# After T026 complete:
T027  Wire POST /api/v1/rides endpoint
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: US1 — Create a Ride
4. **STOP and VALIDATE**: Run quickstart scenarios 1, 2, 3
5. Demo: verified driver can post a ride on the map

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 (US1) → Rides can be created → **MVP Demo**
3. Phase 4 (US2) → Rides can be edited
4. Phase 5 (US3) → Rides can be cancelled
5. Phase 6 (US4) → Seat counts are accurate in UI
6. Phase 7 (US5) → Full driver dashboard live
7. Phase 8 (US6) → Trust enforcement continuous
8. Phase 9 (Polish) → Lifecycle complete, all scenarios validated

---

## Notes

- **No direct client writes to `rides`** — all mutations go through FastAPI; RLS has no client INSERT/UPDATE policy
- **`available_seats` is a generated column** — never write to it; only `total_seats` and `booked_seats` are writable
- **Advisory lock in T026 is mandatory** — without it, concurrent ride creation by the same driver can bypass the 2-hour overlap check
- **Nominatim debounce (T022)** — 300ms debounce on pin drop prevents rate-limit violations on the public Nominatim instance
- **Webhook secret (T055)** — must be provisioned in Supabase Vault and loaded via `WEBHOOK_SECRET` env var before the revocation endpoint is deployed
- [P] tasks = different files, no dependency on incomplete peer tasks
- Each user story is independently completable and testable without requiring the next story to be built
