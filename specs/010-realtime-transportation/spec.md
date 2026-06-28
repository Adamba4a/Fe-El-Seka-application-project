# Feature Specification: Real-Time Transportation

**Feature Branch**: `010-realtime-transportation`

**Created**: 2026-06-26

**Status**: Draft

**Input**: Phase 7 — Real-Time Transportation: live driver location tracking, ride lifecycle management (start and complete), FCM push notifications for booking and ride events, and Supabase Realtime subscriptions for in-app status updates.

---

## Clarifications

### Session 2026-06-28

- Q: Should deep link paths in FCM notification payloads use Next.js layout-group parenthesis notation (e.g., `/(driver)/…`, `/(passenger)/…`) or flat prefixes (e.g., `/driver/…`)? → A: Layout-group convention — all deep links use `/(driver)/` for driver routes and `/(passenger)/` for passenger routes, consistent with Next.js App Router standards.
- Q: Should Supabase Realtime Authorization be enabled in the project settings to enforce RLS server-side on `driver_locations` and `bookings` Realtime subscriptions, or is client-side filtering sufficient? → A: Enable Realtime Authorization — required to satisfy NFR-009 and FR-030; without it, Postgres Changes events bypass RLS and unauthorized clients still receive the raw data.
- Q: Is the `bearing` field in the location POST endpoint required or optional? GPS devices do not report bearing when stationary. → A: Optional / nullable — bearing may be omitted; the map pin is shown without orientation until a valid bearing arrives.
- Q: Does the driver pending-booking reminder check run inside the FCM dispatcher loop or as a separate APScheduler job? → A: Separate APScheduler job — runs independently at ~5-minute intervals; inserts reminder notification_event rows which the FCM dispatcher picks up on its next run.
- Q: Should `speed_kmh` be included in the GET `/rides/{ride_id}/location` response visible to passengers, or stored only for future internal use? → A: Stored, not exposed — `speed_kmh` is persisted in the DB for future analytics but excluded from the GET response; the tracking screen only needs position and bearing.

### Session 2026-06-26

- Q: Should confirmed passengers be able to view the driver's live location before the driver taps "Start Ride," or only once the ride is `in_progress`? → A: In-progress only — live tracking is only available after the driver starts the ride; no pre-ride location visibility is provided.
- Q: What is the maximum FCM retry count before marking a notification event `failed`? → A: 3 retries — balances transient-failure recovery with dispatcher throughput.
- Q: Should Phase 7 require structured observability (per-request logs + per-endpoint metrics) matching the Phase 5 NFR-009 standard? → A: Yes — full structured observability: per-request structured logs and per-endpoint request count and p95 latency metrics for all Phase 7 endpoints and the notification dispatcher.
- Q: Is the 2-hour driver response reminder window a fixed system constant or an admin-configurable parameter? → A: Fixed system constant — consistent with Phase 6's 24-hour expiry approach; no config table entry required.
- Q: When the ride completes, should the live tracking screen show a static "Ride Completed" state or auto-redirect the passenger? → A: Auto-redirect to booking detail after 3 seconds — the tracking screen displays "Ride Completed" briefly then navigates to the passenger's booking detail screen.

---

## Business Objective *(mandatory)*

Bridge the communication gap between the Phase 6 booking system and the people using it. When a passenger books a ride, the driver must know immediately. When a driver confirms or starts the ride, the passenger must know immediately. When a ride is in progress, confirmed passengers must be able to see where the driver is in real time.

This phase delivers three tightly coupled real-time capabilities: FCM push notifications that inform passengers and drivers of booking and ride events even when the app is backgrounded or closed; ride lifecycle management where drivers explicitly start and complete rides, triggering Phase 6's booking completion cascade; and live driver location broadcasting during active rides so confirmed passengers can follow the driver's position on a map without polling.

Without this phase, the Phase 6 booking system is effectively silent — drivers do not know bookings have arrived, passengers do not know whether their booking was accepted, and the platform cannot function as a trusted transportation service.

**Constitutional Domain**: Real-Time Transportation / Notifications

**Affected Applications**: Main App (passenger live tracking screen; driver ride control panel); FastAPI backend (notification dispatcher, location endpoint, ride lifecycle endpoints); Firebase Cloud Messaging (push notification delivery).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — FCM Push Notification Dispatch (Priority: P1)

A passenger who just booked a ride seat puts her phone in her pocket. A few minutes later, she feels a vibration: "Your booking was confirmed. Ahmed will pick you up at Cairo University Gate at 8:05 AM." She did not need to open the app. On the driver's side, Ahmed received his own notification a moment earlier: "New booking request — Sarah wants to join your 8:00 AM ride to Maadi."

**Why this priority**: Phase 6 has been deploying `notification_events` rows since it launched, but nothing is dispatching them. Drivers do not know bookings have arrived; passengers do not know their booking status changed. This is the highest-priority story because it unblocks the entire two-sided booking communication loop that Phase 6 built. All other stories depend on the ride being in motion, which requires drivers to know and act on bookings first.

**Independent Test**: Register two users with FCM tokens. Trigger each notification event type by exercising the Phase 6 booking lifecycle (create booking, confirm, reject, cancel, expire) and the Phase 7 ride lifecycle (start, complete). For each event, verify: the recipient's registered FCM token receives a notification within 30 seconds; the `notification_events` row transitions to `status = dispatched`; notification title and body match the event type template; calling the same event twice does not produce a second notification.

**Acceptance Scenarios**:

1. **Given** an authenticated user (passenger or driver) who opens the app, **When** their device registers an FCM token via the registration endpoint, **Then** the token is stored associated with their user account; if the same token was previously registered, `last_seen_at` is updated rather than creating a duplicate row.
2. **Given** a pending `notification_event` row (status = `pending`), **When** the dispatcher background task runs, **Then** the system sends an FCM push notification to all active device tokens for the event's `recipient_user_id` within 30 seconds.
3. **Given** a `booking_received` event targeting a driver, **When** the notification is dispatched, **Then** the driver receives a notification with the passenger's display name, the ride's departure time, and a deep link to the pending booking in their booking queue.
4. **Given** a `booking_confirmed` event targeting a passenger, **When** the notification is dispatched, **Then** the passenger receives a notification with the driver's display name, departure time, and a deep link to their booking detail screen.
5. **Given** a `booking_rejected` event targeting a passenger, **When** the notification is dispatched, **Then** the passenger receives a notification informing them their booking was declined, with a deep link to the ride search screen.
6. **Given** a `booking_cancelled` event targeting the non-cancelling party, **When** the notification is dispatched, **Then** the recipient receives a notification identifying who cancelled and which ride is affected.
7. **Given** a `booking_expired` event targeting a passenger (auto-expired after 24 hours, Phase 6), **When** the notification is dispatched, **Then** the passenger receives a notification that their booking request expired without a driver response.
8. **Given** a `ride_cancelled` event targeting a passenger (triggered when driver cancels the entire ride, Phase 6), **When** the notification is dispatched, **Then** each affected passenger receives a notification that the ride was cancelled, with the original departure time included.
9. **Given** a `ride_started` event targeting a confirmed passenger, **When** the notification is dispatched, **Then** the passenger receives a notification that the driver has started the ride, with a deep link to the live tracking screen.
10. **Given** a `ride_completed` event targeting a passenger, **When** the notification is dispatched, **Then** the passenger receives a notification confirming the ride has ended.
11. **Given** an FCM dispatch attempt that returns a token-expired or token-invalid response from FCM, **When** the failure is recorded, **Then** the system marks the notification event `status = failed`, logs the error, and deregisters that specific token from the user's active tokens; other tokens for the same user are unaffected.
12. **Given** the dispatcher processes the same `notification_event` row twice (concurrent runs or retry), **When** the second pass occurs, **Then** no duplicate notification is sent — the operation is idempotent because the row is already in `dispatched` or `failed` status and is skipped.

---

### User Story 2 — Ride Lifecycle: Start and Complete (Priority: P2)

At 7:55 AM, Ahmed is in his car at his departure point. He opens the driver view, finds his upcoming ride, and taps "Start Ride." Each of his confirmed passengers receives a notification that the trip has begun. At 8:47 AM, he drops off his last passenger and taps "Complete Ride." The ride closes, all confirmed bookings complete, and passengers receive a completion notification.

**Why this priority**: Start and Complete are the operational triggers for multiple cascades — the booking completion cascade (Phase 6 FR-031), the live tracking session boundary (Story 3), and the financial commission deduction (Phase 8). Without these actions, rides remain in `scheduled` status indefinitely and the platform has no mechanism to close out trips. P2 because it is the prerequisite for live tracking and must precede Phase 8 financial settlement.

**Independent Test**: As a driver, navigate to an active ride's management screen. Tap "Start Ride." Verify: ride `status` becomes `in_progress`; `started_at` is recorded; each confirmed passenger receives a `ride_started` notification event. Then tap "Complete Ride." Verify: ride `status` becomes `completed`; all `confirmed` bookings for that ride become `completed` atomically (Phase 6 cascade); each affected passenger receives a `ride_completed` notification event. Attempt to call "Start" again on the completed ride and verify HTTP 409 is returned.

**Acceptance Scenarios**:

1. **Given** a driver on her ride management screen for a ride in `scheduled` status, **When** she taps "Start Ride," **Then** the ride status transitions to `in_progress`, `started_at` is recorded, and a `notification_event` row with `event_type = ride_started` is inserted for each passenger with a `confirmed` booking on that ride.
2. **Given** a driver on her ride management screen for a ride in `in_progress` status, **When** she taps "Complete Ride," **Then** within a single atomic transaction: (a) the ride status becomes `completed`, (b) `completed_at` is recorded, (c) the Phase 6 booking completion cascade fires transitioning all `confirmed` bookings to `completed`, and (d) a `notification_event` row with `event_type = ride_completed` is inserted for each passenger whose booking was just completed.
3. **Given** a ride in `scheduled` status with zero confirmed bookings (only pending or no bookings), **When** the driver taps "Start Ride," **Then** the ride transitions to `in_progress` without error; no `ride_started` notifications are inserted since there are no confirmed passengers to notify.
4. **Given** a ride whose current status is not `scheduled`, **When** the driver calls the start endpoint, **Then** the system returns HTTP 409 with the current ride status; the ride status is unchanged.
5. **Given** a ride whose current status is not `in_progress`, **When** the driver calls the complete endpoint, **Then** the system returns HTTP 409 with the current ride status; the ride status is unchanged.
6. **Given** any user who is not the ride's assigned driver, **When** they call the start or complete endpoint, **Then** the system returns HTTP 403; no status change occurs.
7. **Given** the ride completion transaction encounters a database error during the booking cascade, **When** the error occurs, **Then** the entire transaction rolls back — the ride remains `in_progress`, no bookings transition, no notification events are inserted; the driver receives an error response and is prompted to retry.

---

### User Story 3 — Live Driver Location Tracking (Priority: P3)

Sarah's confirmed ride is now in progress. She opens the app and navigates to her booking. A live map shows Ahmed's position as a moving pin on the road — heading toward her boarding point. As she watches, the pin advances steadily. She knows he is four minutes away and begins walking to the pickup spot.

**Why this priority**: Live location tracking is the real-time transportation experience that distinguishes the platform from a static booking system. For passengers sharing a ride with a stranger, spatial confidence — seeing where the driver is — reduces last-minute cancellations and builds platform trust. P3 because it depends on the ride being `in_progress` (Story 2) and requires device GPS integration; it is the flagship real-time feature but gates no other story.

**Independent Test**: Start a test ride. As the driver, call the location update endpoint with a series of GPS coordinates 5 seconds apart. Simultaneously, as a confirmed passenger on that ride, open the live tracking screen and observe the map. Verify: each location update appears on the passenger's map within 3 seconds; the driver pin moves along the route; a user without a confirmed booking on this ride cannot retrieve location data (receives HTTP 403).

**Acceptance Scenarios**:

1. **Given** a ride in `in_progress` status and the driver's device reporting a GPS update, **When** the location endpoint receives the update, **Then** the system upserts the driver's position (coordinates, bearing, timestamp) in the `driver_locations` table for that ride and the change is broadcast to subscribed Supabase Realtime clients.
2. **Given** a passenger with a `confirmed` booking on the active ride, **When** she opens the live tracking screen, **Then** she sees a map with the driver's most recently reported position; the map pin updates in real time as new location events arrive via Supabase Realtime, without page refresh.
3. **Given** a user without a `confirmed` booking on the active ride (including authenticated users with `pending`, `cancelled`, or no booking), **When** they request the driver's location via the GET endpoint, **Then** the system returns HTTP 403 and no location data is exposed.
4. **Given** a user who is not the ride's assigned driver, **When** they call the location update endpoint, **Then** the system returns HTTP 403 and the location record is not modified.
5. **Given** a ride that transitions from `in_progress` to `completed` or `cancelled`, **When** the status changes, **Then** the system stops accepting new location updates for that ride (returns HTTP 409) but continues to serve the last recorded position via the GET endpoint until the client disconnects.
6. **Given** 60 seconds have elapsed since the driver's last location update, **When** a passenger views the tracking screen, **Then** the last known position is still displayed with a "location may be stale" visual indicator; the UI does not crash or show an empty state.
7. **Given** a passenger viewing the live tracking screen, **When** the ride is marked completed and the Realtime completion event is received, **Then** the tracking screen displays a "Ride Completed" state with the driver's final position for 3 seconds, then automatically redirects the passenger to their booking detail screen; active location broadcasting has ended.

---

### User Story 4 — Real-Time In-App Status Updates (Priority: P4)

Sarah has the app open on "My Bookings" after placing a booking. Without refreshing, her booking status badge flips from "Pending" to "Confirmed" the instant Ahmed approves it. On Ahmed's side, the moment a new booking arrives on his ride, it appears in his queue — he does not need to pull-to-refresh.

**Why this priority**: Real-time in-app updates eliminate polling and create the responsive feel expected of a modern transportation platform. This is P4 because it enhances the Phase 6 UX — those screens still work via manual refresh without this story — but it is required to make the platform feel live and trustworthy rather than stale and clunky.

**Independent Test**: As a passenger, open "My Bookings" in one browser tab. In a second tab, log in as the driver and confirm the pending booking. Verify: the passenger's booking status updates to "Confirmed" within 3 seconds on the first tab, without a page reload. Repeat with a cancellation. Verify the status changes similarly.

**Acceptance Scenarios**:

1. **Given** a passenger with the app open on any screen showing booking status, **When** a booking status change occurs (confirmed, rejected, cancelled), **Then** the displayed status updates within 3 seconds without a page reload, driven by the Supabase Realtime `bookings` table subscription.
2. **Given** a driver with the app open on the ride's booking queue, **When** a new `pending` booking is created for her ride, **Then** the new booking card appears in her queue within 3 seconds without a page reload.
3. **Given** a passenger with the live tracking screen open, **When** a new driver location event is broadcast via Supabase Realtime, **Then** the map pin moves to the driver's updated position within 3 seconds.
4. **Given** a user whose Supabase Auth session has expired, **When** a Realtime event is received, **Then** the update is silently discarded and the user is redirected to the login screen; no unauthorized data is displayed.
5. **Given** a user who loses network connectivity while subscribed to Realtime updates, **When** connectivity is restored, **Then** the Supabase client reconnects automatically and the UI reflects the current database state on reconnection.

---

### Edge Cases

- What if the driver's device has no GPS signal at the moment they tap "Start Ride"? Start Ride succeeds — live tracking is a best-effort service and does not gate the ride lifecycle. The tracking screen shows a "location unavailable" indicator until the driver begins reporting coordinates.
- What if the driver's battery dies mid-ride and location updates stop? The last known position remains on the tracking screen. After 60 seconds without an update, a "location may be stale" indicator appears. The ride is not automatically cancelled or completed; the driver must resume reporting when possible.
- What if a passenger receives a push notification but their booking has already been further updated by the time they open the deep link? Deep links navigate to the booking or ride screen, which always renders current database state. The notification is informational; the screen is the source of truth.
- What if the FCM service is temporarily unavailable when the dispatcher runs? The dispatcher marks events as `failed` after the retry limit and continues processing remaining events. Booking state changes still propagate via Supabase Realtime to users with the app open. The failure is logged; no ride flow is blocked.
- What if a passenger has no registered FCM token (they denied notification permission)? The dispatcher skips FCM dispatch for that user, marks the event `dispatched` (delivery was attempted but no valid token exists), and continues. In-app Realtime updates still work while the app is open.
- What if two device tokens are registered for the same user and one has expired? The dispatcher attempts delivery to all tokens. The expired token produces a failure response from FCM, triggering deregistration of that token. The valid token receives the notification. The event is marked `dispatched` if at least one token succeeded.
- What if "Start Ride" is called but the server response is lost before the driver receives it (offline moment)? The endpoint is idempotent for the `in_progress` transition — calling it on an already-`in_progress` ride returns HTTP 409. The driver sees an error, checks the ride status, and proceeds without re-triggering notifications.
- What if the Phase 6 booking cascade fails during "Complete Ride"? The entire transaction rolls back. The ride remains `in_progress`, bookings remain `confirmed`, and no notification events are inserted. The driver is shown an error and prompted to retry. No partial completion state persists.
- What if a driver response reminder (FR-029) is about to be sent but the driver responds to the booking a millisecond before the insert? The reminder insertion MUST check that the booking is still `pending` within the same atomic operation; if it has transitioned, the reminder is not sent.

---

## Requirements *(mandatory)*

### Functional Requirements

**Device Token Management**

- **FR-001**: The system MUST provide an authenticated endpoint (`POST /users/me/device-tokens`) that accepts an FCM registration token and platform identifier and stores them associated with the authenticated user's account.
- **FR-002**: A user MAY have multiple active device tokens (multiple registered devices). Each unique token MUST be stored as a separate row associated with the same `user_id`.
- **FR-003**: If a token submitted via FR-001 already exists in the table (for any user), the system MUST update `last_seen_at` and re-associate it with the current user, rather than creating a duplicate row.
- **FR-004**: When an FCM dispatch attempt returns a token-expired or token-invalid error from FCM, the system MUST automatically delete that token from `user_device_tokens`. All other tokens for the same user remain active.
- **FR-005**: Device token registration MUST be available to all authenticated users (passengers and drivers) regardless of verification status.

**Notification Dispatch**

- **FR-006**: The system MUST run a background dispatcher process that polls the `notification_events` table for rows with `status = pending` and dispatches FCM push notifications to all active device tokens for each event's `recipient_user_id`.
- **FR-007**: The dispatcher MUST handle the following event types with a distinct notification title and body template for each: `booking_received`, `booking_confirmed`, `booking_rejected`, `booking_cancelled`, `booking_expired`, `ride_cancelled`, `ride_started`, `ride_completed`.
- **FR-008**: After successful FCM dispatch, the dispatcher MUST update the `notification_event` row's `status` to `dispatched` and set `dispatched_at` to the current timestamp.
- **FR-009**: If FCM dispatch fails, the dispatcher MUST retry up to 3 times before marking the event `status = failed` and logging the failure reason. Failed events MUST NOT block subsequent pending events from being processed.
- **FR-010**: The dispatcher MUST be idempotent — if a `notification_event` row is already in `dispatched` or `failed` status, the dispatcher MUST skip it without sending a duplicate notification.
- **FR-011**: FCM notification payloads MUST include a data object containing: `event_type`, `ride_id`, `booking_id` (when applicable), and a `deep_link` app path so the recipient can navigate directly to the relevant screen on tap.

**Booking Received Notification (Phase 6 Contract Addendum)**

- **FR-012**: When a passenger creates a new booking (Phase 6 FR-013), the system MUST also insert a `notification_event` row with `event_type = booking_received`, `recipient_user_id` = the ride's driver user ID, and a payload containing the passenger's display name, ride ID, booking ID, and departure time. This extends the Phase 6 booking creation flow; the `notification_events.event_type` enum is extended via a Phase 7 database migration to include `booking_received`.

**Ride Lifecycle: Start**

- **FR-013**: The system MUST provide an authenticated endpoint (`POST /rides/{ride_id}/start`) that transitions a ride from `scheduled` to `in_progress`. Only the ride's assigned driver may call this endpoint; all other authenticated users MUST receive HTTP 403.
- **FR-014**: The start endpoint MUST reject requests where the ride's current status is not `scheduled`, returning HTTP 409 with the current ride status in the response body.
- **FR-015**: On a successful ride start, the system MUST: (a) set `Ride.status = in_progress`, (b) record `started_at` with the current timestamp, and (c) insert a `notification_event` row with `event_type = ride_started` for each passenger whose booking on this ride has `status = confirmed`.

**Ride Lifecycle: Complete**

- **FR-016**: The system MUST provide an authenticated endpoint (`POST /rides/{ride_id}/complete`) that transitions a ride from `in_progress` to `completed`. Only the ride's assigned driver may call this endpoint; all other authenticated users MUST receive HTTP 403.
- **FR-017**: The complete endpoint MUST reject requests where the ride's current status is not `in_progress`, returning HTTP 409 with the current ride status.
- **FR-018**: On a successful ride completion, within a single database transaction, the system MUST: (a) set `Ride.status = completed` and record `completed_at`; (b) execute the Phase 6 booking completion cascade (all `confirmed` bookings for this ride → `completed`, per Phase 6 FR-031); and (c) insert a `notification_event` row with `event_type = ride_completed` for each passenger whose booking was just completed.
- **FR-019**: The ride completion MUST be fully atomic — if any step of the cascade fails, the entire transaction MUST roll back; the ride MUST remain `in_progress` and no bookings or notification events are altered.

**Driver Location Reporting**

- **FR-020**: The system MUST provide an authenticated endpoint (`POST /rides/{ride_id}/location`) accepting a GPS location update containing latitude, longitude, an optional bearing (0–359 degrees — nullable; omitted when the device is stationary or bearing is unavailable), and a client-side timestamp. Only the ride's assigned driver may submit updates; all other users MUST receive HTTP 403.
- **FR-021**: Location updates MUST only be accepted for rides in `in_progress` status; updates submitted for rides in any other status MUST be rejected with HTTP 409.
- **FR-022**: The system MUST upsert the driver's current position in the `driver_locations` table, keyed by `ride_id` — one record per in-progress ride, updated in place on each report. Historical location points are not retained.
- **FR-023**: The `location` field in `driver_locations` MUST be stored as a PostGIS geometry Point type, with the driver's reported latitude and longitude converted on insert. Plain float coordinate columns are prohibited.

**Passenger Location Access**

- **FR-024**: The system MUST provide an authenticated endpoint (`GET /rides/{ride_id}/location`) returning the driver's most recently reported position for a ride. The response MUST include: latitude, longitude, bearing (nullable), `client_timestamp`, and `updated_at`. The `speed_kmh` field MUST NOT be included in the response — it is stored in the DB for future analytics use only. Access is restricted to passengers with a `confirmed` booking on that ride; all other requests MUST receive HTTP 403.
- **FR-025**: Once a ride transitions out of `in_progress` status, the system MUST stop accepting new location updates (FR-021 handles this) and MUST continue serving the last recorded position via the GET endpoint until the ride record is no longer relevant to the client.

**Real-Time In-App Subscriptions**

- **FR-026**: The `bookings` table and `driver_locations` table MUST be included in the Supabase Realtime publication, enabling authorized frontend clients to subscribe to row-level change events.
- **FR-027**: The passenger-facing booking list and detail screens in the frontend MUST subscribe to Supabase Realtime events on the `bookings` table filtered by the authenticated passenger's user ID, reflecting status changes within 3 seconds without a page reload.
- **FR-028**: The driver-facing booking queue screen in the frontend MUST subscribe to Supabase Realtime INSERT events on the `bookings` table filtered by rides the driver owns, surfacing new bookings in real time.
- **FR-029**: The passenger's live tracking screen MUST subscribe to Supabase Realtime UPDATE events on the `driver_locations` table filtered by the active ride's ID, updating the map pin position on each received event without page refresh.
- **FR-030**: Supabase Realtime subscriptions for `bookings` and `driver_locations` MUST be authorized through the authenticated user's Supabase Auth JWT and enforced by Row Level Security policies at the database layer.

**Driver Pending Booking Reminder**

- **FR-031**: The system MUST send a reminder push notification to the driver if a booking remains in `pending` status for more than 2 hours without a response. The 2-hour window is a fixed system constant (not admin-configurable), consistent with Phase 6's approach for the 24-hour expiry. The reminder check MUST run as a dedicated APScheduler background job (separate from the FCM dispatcher) at approximately 5-minute intervals; it inserts a `notification_event` row with `event_type = booking_received` (reminder variant) which the FCM dispatcher then dispatches on its next run. The reminder notification MUST include the passenger's display name, the ride's departure time, and a deep link to the pending booking at `/(driver)/rides/{ride_id}/bookings`.
- **FR-032**: Each pending booking MUST receive at most one reminder notification — a booking MUST NOT be reminded more than once. The 24-hour auto-expiry (Phase 6 FR-023) remains the terminal action.
- **FR-033**: The check for whether a booking is still `pending` and the insertion of the reminder `notification_event` MUST be performed atomically to prevent sending a reminder for a booking that was just acted upon.

### Key Entities

- **UserDeviceToken**: Stores FCM registration tokens for push notification delivery. Attributes: UUID primary key; `user_id` (foreign key — the authenticated user); `token` (text, unique — the FCM registration token); `platform` (text — `web`, `android`, or `ios`); `created_at`; `last_seen_at` (updated each time the token is re-registered by the client).

- **DriverLocation**: The current GPS position of a driver during an active ride — one record per in-progress ride, updated in place. Attributes: UUID primary key; `ride_id` (foreign key, unique constraint — one active location per ride); `driver_id` (foreign key); `location` (PostGIS geometry Point — the driver's current position); `bearing` (smallint, **nullable** — direction of travel in degrees 0–359; null when the device is stationary or bearing is unavailable); `speed_kmh` (decimal, nullable — device-reported speed if available); `client_timestamp` (timestamp — the device-side time the GPS fix was captured); `updated_at` (timestamp — server-side time of last upsert).

- **NotificationEvent (extended from Phase 6)**: The `event_type` enum is extended via a Phase 7 migration to add three new values: `booking_received` (driver notified when a passenger creates a booking on their ride); `ride_started` (confirmed passengers notified when driver starts the ride); `ride_completed` (confirmed passengers notified when the ride is marked complete). All other attributes — `id`, `recipient_user_id`, `payload`, `status`, `created_at`, `dispatched_at` — remain as defined in Phase 6.

- **Ride (extended from Phase 4)**: Two new timestamp fields are added via a Phase 7 migration, without changing existing Phase 4 columns: `started_at` (nullable timestamp — set when the driver taps "Start Ride"); `completed_at` (nullable timestamp — set when the driver taps "Complete Ride").

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 95% of push notifications for booking lifecycle events (`booking_received`, `booking_confirmed`, `booking_rejected`, `booking_cancelled`, `booking_expired`) are delivered to the recipient's device within 30 seconds of the originating `notification_event` row being inserted.
- **SC-002**: Driver location updates appear on confirmed passengers' live tracking screens within 3 seconds of the driver reporting the GPS update, measured end-to-end from the driver's location POST to the passenger's Realtime event.
- **SC-003**: In-app booking status changes (confirmed, cancelled, new booking received) are reflected on the relevant open screen within 3 seconds of the database write, without page refresh.
- **SC-004**: 100% of ride completion events successfully execute the Phase 6 booking cascade atomically — no ride reaches `completed` status while any associated booking remains in `confirmed` status.
- **SC-005**: 100% of location update requests from users without a `confirmed` booking on the active ride (or not the assigned driver) are rejected before any location data is read or written.
- **SC-006**: Zero duplicate push notifications are delivered for the same `notification_event` row, verified across concurrent dispatcher runs and retry scenarios.
- **SC-007**: 100% of pending bookings older than 2 hours and not yet responded to receive exactly one driver reminder notification before the 24-hour expiry fires.

---

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: The FCM notification dispatcher MUST run at intervals of no more than 30 seconds and MUST process a queue of up to 1,000 pending `notification_event` rows per run without exceeding the run interval.
- **NFR-002**: The driver location update endpoint (`POST /rides/{ride_id}/location`) MUST respond within 200ms at p95 under expected load, as the driver device calls this endpoint approximately every 5 seconds during an active ride.
- **NFR-003**: The passenger location read endpoint (`GET /rides/{ride_id}/location`) MUST respond within 300ms at p95; Supabase Realtime location events MUST propagate to subscribed clients within 3 seconds of the underlying database upsert.
- **NFR-004**: All ride lifecycle endpoints (start, complete) and location endpoints MUST require a valid Supabase Auth JWT; unauthenticated requests MUST be rejected with HTTP 401.
- **NFR-005**: The driver's real-time GPS coordinates MUST NOT be readable by any user other than the ride's driver and passengers with a `confirmed` booking on that ride. Row Level Security policies on `driver_locations` MUST enforce this constraint at the database layer, not exclusively at the API layer.
- **NFR-006**: FCM server credentials (Firebase service account key) MUST be stored in Supabase Vault; they MUST NOT appear in environment files, source code, or configuration files committed to the repository.
- **NFR-007**: The ride completion transaction (ride status update + booking cascade + notification event inserts) MUST execute within a single database transaction. If the transaction exceeds 5 seconds, the system MUST time out and roll back; the ride remains `in_progress`.
- **NFR-008**: The notification dispatcher MUST use `SELECT ... FOR UPDATE SKIP LOCKED` (or an equivalent exclusive-claim pattern) when fetching pending events, ensuring that concurrent dispatcher instances each process disjoint sets of events and no event is dispatched more than once.
- **NFR-009**: Supabase Realtime subscriptions for `driver_locations` MUST be authorized by Row Level Security — a client subscribing to location events for a ride MUST hold a `confirmed` booking on that ride; all other subscription attempts MUST be silently rejected by the RLS policy.
- **NFR-010**: Every ride lifecycle endpoint (start, complete), location endpoint (POST and GET), device token registration endpoint, and notification dispatcher run MUST emit a structured log entry containing: endpoint name or task name, input parameters (sanitized — no raw GPS coordinates in logs beyond ride ID and timestamp), output summary, duration in milliseconds, and error details if applicable. Per-endpoint request count and p95 latency MUST be exported as metrics to enable production verification of SC-001, SC-002, and SC-003.

---

## Dependencies *(mandatory)*

- **Internal**:
  - `009-passenger-experience` (Phase 6) — the `notification_events` table (schema and existing event types), `bookings` table (booking status machine and completion cascade in FR-031), and `booking_audit_log` are direct runtime dependencies. Phase 7 extends the `notification_events.event_type` enum and adds `booking_received` insertion to the Phase 6 booking creation flow.
  - `004-ride-management` (Phase 4) — the `Ride` entity and its `status` field are the data Phase 7 acts on. Phase 7 adds `started_at` and `completed_at` timestamp columns to the `rides` table via a new migration.
  - `003-auth-verification` (Phase 3) — Supabase Auth JWTs are required for all endpoints; the user identity from the JWT is used to verify ride ownership and booking membership.

- **External**:
  - **Firebase Cloud Messaging (FCM)**: A Firebase project with a server-side service account configured and the FCM API enabled. The FCM service must be reachable from the FastAPI backend at dispatch time.
  - **Supabase Realtime**: Enabled by default on all Supabase project instances. The `bookings` and `driver_locations` tables must be added to the Realtime publication via a configuration step (not a code change). **Supabase Realtime Authorization MUST be enabled** in the project settings so that RLS policies on `driver_locations` and `bookings` are enforced server-side for all Realtime subscriptions — without this setting, Postgres Changes events bypass RLS and all row changes are broadcast to any connected client. No additional Supabase plan tier is required at MVP scale (≤1,000 concurrent users).

- **Data**:
  - Supabase PostgreSQL with PostGIS extension enabled (Phase 1).
  - `notification_events` table created in Phase 6 with `pending` rows from Phase 6 booking events waiting for dispatch.
  - `Ride` records from Phase 4 in `scheduled` status ready for lifecycle management.
  - User records from Phase 3 whose IDs are referenced as `recipient_user_id` in notification events.

---

## Out-of-Scope

- **Live ETA calculation** — displaying a precise "arrives in X minutes" estimate derived from the driver's live GPS position and remaining road-network distance is a post-competition enhancement. This phase shows the driver's live position; computed ETA is not included.
- **In-app passenger-to-driver messaging** — direct chat between passenger and driver is a post-competition feature. Communication in this phase is limited to push notifications.
- **SMS or email notification fallback** — FCM push is the only notification delivery channel for MVP. Users who deny notification permissions receive no alternate-channel fallback.
- **Notification preferences and muting** — users cannot configure which event types they subscribe to. All supported event types are delivered unconditionally.
- **Breadcrumb location history** — only the driver's most recent position is stored and served. Historical location paths are not retained or displayed.
- **Adaptive location reporting frequency** — the driver device reports at a fixed interval (5 seconds). Adaptive reporting based on speed, battery state, or movement is a post-competition enhancement.
- **Pedestrian live tracking (passenger walking to boarding point)** — only the driver's location is tracked. Passenger location is never collected or broadcast.
- **Driver-to-passenger or passenger-to-driver audio/video calls** — not part of the platform.
- **Financial settlement on ride completion** — commission deduction and driver balance ledger updates triggered by `Ride.status = completed` are Phase 8 scope.
- **Ratings and reviews after ride completion** — post-competition feature.
- **Traffic or road-condition integration** — real-time traffic data is not incorporated into ETA estimates or location display.
- **Geofence-based automatic ride start or completion** — rides are started and completed by explicit driver action only. No automatic trigger based on GPS proximity to origin or destination is implemented.

---

## Technical Considerations

- The FCM dispatcher MUST use `SELECT ... FOR UPDATE SKIP LOCKED` when claiming `pending` notification events from the database. This prevents duplicate dispatch when multiple FastAPI worker processes run the dispatcher concurrently — exactly the same pattern used by the Phase 6 booking expiry loop. The dispatcher selects a batch of pending events, locks them, processes them, and updates their status within a transaction.
- The `driver_locations` table uses a single-row upsert per ride (`INSERT ... ON CONFLICT (ride_id) DO UPDATE SET ...`). This keeps the table O(active rides) in size rather than growing with every location report. If a future phase requires location history (e.g., trip replay, audit), a separate `driver_location_history` append-only table is the appropriate extension point.
- Supabase Realtime subscription authorization depends on Row Level Security policies AND requires **Supabase Realtime Authorization** to be enabled in the project settings. Without this setting, Postgres Changes events bypass RLS entirely. With it enabled, the frontend connects using the user's Supabase Auth JWT (via the `@supabase/supabase-js` client with the anon key and user session), and the `driver_locations` RLS policy MUST join against the `bookings` table to verify that the subscribing user's ID appears in a `confirmed` booking for the requested `ride_id`. Enabling Realtime Authorization is a one-time project configuration step — it is not a migration or code change, but it MUST be completed before deploying Phase 7. The service role key MUST NOT be used in frontend clients.
- The ride completion endpoint coordinates with Phase 6's booking cascade by updating `Ride.status = completed` within the same transaction that Phase 6's cascade trigger or transactional handler monitors. Phase 7 does not re-implement the cascade — it fires the trigger by changing ride status; Phase 6's implementation handles the `confirmed → completed` booking transitions.
- FCM credentials (Firebase service account JSON) MUST be loaded at FastAPI startup from Supabase Vault using the Vault API. The key MUST NOT be written to disk, committed to source control, or injected as a plain environment variable in production. This aligns with Constitution §Security & Privacy (Secrets MUST be stored exclusively through approved secrets-management infrastructure).
- The `started_at` and `completed_at` columns added to the `rides` table in this phase are a non-breaking schema extension delivered via a new Supabase migration. No Phase 4 code changes are required; existing ride creation and management endpoints continue to function without modification.
- Deep links embedded in FCM notification payloads MUST use relative paths matching the Next.js 14 App Router route structure, using layout-group parenthesis notation: `/(driver)/` for all driver-facing routes and `/(passenger)/` for all passenger-facing routes. The canonical mapping for each event type is:

  | Event type | Recipient | Deep link path |
  |---|---|---|
  | `booking_received` | Driver | `/(driver)/rides/{ride_id}/bookings` |
  | `booking_confirmed` | Passenger | `/(passenger)/bookings/{booking_id}` |
  | `booking_rejected` | Passenger | `/(passenger)/rides` |
  | `booking_cancelled` (passenger notified) | Passenger | `/(passenger)/bookings/{booking_id}` |
  | `booking_cancelled` (driver notified) | Driver | `/(driver)/rides/{ride_id}/bookings` |
  | `booking_expired` | Passenger | `/(passenger)/rides` |
  | `ride_cancelled` | Passenger | `/(passenger)/bookings/{booking_id}` |
  | `ride_started` | Passenger | `/(passenger)/rides/{ride_id}/tracking` |
  | `ride_completed` | Passenger | `/(passenger)/bookings/{booking_id}` |
- The driver reminder background task (FR-031 to FR-033) MUST perform the "check if still pending AND insert reminder event" operation atomically using a single SQL statement or a serializable transaction, to avoid a race condition where the driver responds in the window between the check and the insert.
- The `notification_events.event_type` PostgreSQL enum MUST be extended via an `ALTER TYPE ... ADD VALUE` migration. Since PostgreSQL does not allow adding enum values inside a transaction in older versions, this migration MUST run as a standalone non-transactional migration step before Phase 7 application code is deployed.

---

## Assumptions

- **FCM for web and mobile**: All device tokens are FCM tokens (web push via service worker, Android, iOS). No APNs-direct path is required for MVP. The platform is a mobile-first web app (Next.js PWA); web push via FCM is the primary delivery mechanism.
- **Location reporting interval**: The driver device reports GPS coordinates every 5 seconds during an active ride. This is a fixed system constant for MVP; adaptive frequency based on device battery, motion state, or network quality is out of scope.
- **Supabase Realtime at MVP scale**: Supabase Realtime supports ≤1,000 concurrent connections on the free and pro tiers, which is sufficient for the MVP target of ≤1,000 active users. No plan upgrade is required.
- **Single Firebase project**: One Firebase project serves all platform clients (passenger web, driver web). No per-application Firebase project segregation is needed for MVP.
- **No location history**: Only the most recent driver GPS fix is stored per ride. If a passenger wants to see where the driver has traveled, only the current pin is shown. This is an explicit scope reduction for MVP.
- **Manual ride start and completion**: There is no automatic trigger based on GPS proximity, departure time, or any other sensor. The driver explicitly taps "Start Ride" and "Complete Ride." This is an intentional MVP simplification.
- **Notification content in English**: All push notification text is in English for MVP, consistent with the English-first policy in the MVP roadmap. Arabic/RTL localization is deferred post-competition.
- **Background process hosting**: Phase 7 adds two separate APScheduler jobs to the FastAPI service: (1) the FCM dispatcher, running every ≤30 seconds (NFR-001); (2) the driver pending-booking reminder check, running every ~5 minutes. Both use the same APScheduler setup as the Phase 6 booking expiry loop. No dedicated worker queue or separate process is required at MVP scale.
- **Ride start does not require confirmed bookings**: A driver can start a ride even if all bookings are still pending or there are no bookings at all. Live tracking and ride-started notifications only fire for passengers with `confirmed` bookings, but the ride lifecycle itself is not gated on booking count.
