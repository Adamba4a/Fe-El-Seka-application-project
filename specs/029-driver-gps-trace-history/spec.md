# Feature Specification: Driver GPS Trace History

**Feature Branch**: `029-driver-gps-trace-history`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Close data-collection gap #1 from the 2026-09-03 roadmap audit — driver GPS is overwrite-only (`driver_locations`, one row per ride via `INSERT ... ON CONFLICT DO UPDATE`), so the actual path driven is discarded after every ping. Add append-only trace history with 30-day rolling retention, ahead of the future route-overlap-pooling-optimization model."

## Business Objective *(mandatory)*

Preserve the sequence of GPS pings generated during every active ride, not just the most recent one, so a future model can reconstruct the route a driver actually drove and compare it to the route that was planned (`rides.route_geometry`). This data is generated continuously right now and is unrecoverable once a later ping overwrites it — the same "cannot be reconstructed retroactively" problem that made 044/045 (013-match-learning-foundation) mandatory before launch. This feature does not build the route-overlap model itself; it only stops the raw data from being thrown away.

**Constitutional Domain**: AI Integration / Route Intelligence

**Affected Applications**: Shared (`services/api`) — backend-only; no passenger or driver-facing UI changes. The existing live-location UI (driver map ping, passenger "driver is on the way" view) continues to read from `driver_locations` unchanged.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every location ping during an active ride is preserved (Priority: P1)

As the platform, when a driver's app sends a GPS ping during an active ride, the ping is appended to a history log in addition to updating the existing "current position" record, so that the full path driven can be reconstructed after the ride ends.

**Why this priority**: This is the entire point of the feature. Without it, there is nothing for a future route-overlap-pooling-optimization model to train on, and the gap cannot be closed retroactively.

**Independent Test**: Send a sequence of location pings for one active ride, then query the history table directly. Confirm one row exists per ping received, in order, distinct from the single current-position row in `driver_locations`.

**Acceptance Scenarios**:

1. **Given** an active ride, **When** the driver's app sends a location ping, **Then** `driver_locations` is updated in place (existing behavior, unchanged) **and** a new row is appended to the history table for that ping.
2. **Given** a ride with 40 pings sent over its duration, **When** the ride completes, **Then** the history table contains 40 rows for that ride, each with its own timestamp and point, in the order received.
3. **Given** the history write fails for some reason, **When** the ping is processed, **Then** the existing live-location update (`driver_locations`) still succeeds — history logging is additive and must never block or fail the live-tracking path.

---

### User Story 2 - History older than 30 days is automatically removed (Priority: P2)

As the platform, GPS trace history is retained on a rolling 30-day window, not indefinitely, so storage growth is bounded and precise historical location trails are not kept longer than needed for near-term model iteration.

**Why this priority**: Indefinite retention of precise GPS trails is unnecessary storage growth and a needless privacy exposure (Egypt PDPL 151/2020) for data that a training pipeline only needs in recent, rolling batches. It is lower priority than User Story 1 because retention only matters once there is history to retain.

**Independent Test**: Insert history rows with a `recorded_at` older than 30 days, run the retention job, and confirm those rows are deleted while rows within the last 30 days remain.

**Acceptance Scenarios**:

1. **Given** history rows exist with `recorded_at` older than 30 days, **When** the retention job runs, **Then** those rows are permanently deleted.
2. **Given** history rows exist with `recorded_at` within the last 30 days, **When** the retention job runs, **Then** those rows are left untouched.
3. **Given** the retention job fails to run on a given day, **When** it next runs successfully, **Then** it still deletes everything past the 30-day cutoff — the window is defined relative to "now," not a fixed daily quota.

---

### Edge Cases

- What happens to trace history for a ride that is still active when the 30-day cutoff would otherwise apply? Not expected in practice (rides do not run for 30 days), but the retention job deletes purely by `recorded_at` age regardless of the parent ride's status — no special-casing for in-progress rides.
- What happens to history rows belonging to a ride that is later cancelled? They are kept for the full 30-day window like any other ride's history — a cancelled ride's partial trace (e.g. driver started moving, then cancelled) is still potentially useful signal, not deleted early.
- What happens if a ping arrives with a location identical to the previous ping (driver stationary)? It is still appended as its own row — no de-duplication in v1; a future ETL can collapse stationary runs if needed, but the raw log stays complete.
- What happens to existing `driver_locations` rows and behavior? Fully unchanged — this feature is additive only, it does not modify the overwrite-per-ride table or its read paths.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST append one history row per location ping received for an active ride, in addition to the existing `driver_locations` upsert, without replacing or modifying that existing table or its behavior.
- **FR-002**: Each history row MUST capture at minimum: the ride identifier, the driver identifier, the point (lat/lng), and the timestamp the ping was recorded.
- **FR-003**: History logging MUST NOT block, delay, or fail the existing live-location update path — a history write failure MUST be logged for operational visibility and MUST NOT prevent `driver_locations` from being updated or the ping request from succeeding.
- **FR-004**: System MUST run a recurring retention job that permanently deletes history rows older than 30 days, based on `recorded_at`.
- **FR-005**: The retention window MUST be defined relative to the current time at the moment the job runs, not tied to a fixed calendar schedule that could leave gaps if a run is missed.
- **FR-006**: History data MUST be queryable per ride (all pings for a given `ride_id`, in order) so a future model or ETL can reconstruct the driven path.

### Key Entities *(include if feature involves data)*

- **Driver Location History**: One append-only record per GPS ping during an active ride. Attributes: ride identifier, driver identifier, point (lat/lng), recorded-at timestamp. Distinct from `driver_locations`, which remains the single current-position row per ride.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of location pings that successfully update `driver_locations` also produce a corresponding history row, under normal operation.
- **SC-002**: Live-location ping request latency is not measurably degraded compared to the pre-instrumentation baseline.
- **SC-003**: No history row persists with a `recorded_at` older than 30 days at any point after the retention job has run following that row's expiry.
- **SC-004**: A sample of one ride's full trace history can be exported and visually plotted as a path, distinct from and more granular than the single last-known point currently available.

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: History logging MUST NOT add measurable synchronous latency to the location-ping request path.
- **NFR-002**: A failure to persist a history row MUST NOT fail the ping request; the failure MUST be recorded for operational visibility, matching the best-effort pattern already established for match-event logging (013-match-learning-foundation).
- **NFR-003**: The retention job MUST be safe to re-run (idempotent) — running it twice in a row with nothing new to delete MUST be a no-op, not an error.

---

## Dependencies *(mandatory)*

- **Internal**: Existing `driver_locations` write path (`location_service.py`) — this feature adds a second write alongside it, does not modify it. `013-match-learning-foundation` — precedent for the best-effort, non-blocking logging pattern reused here.
- **External**: None new.
- **Data**: New append-only table in the existing Supabase Postgres database, plus a scheduled job (existing job-running mechanism used elsewhere in the platform, e.g. the retraining/retention jobs from 016-continuous-learning-pipeline) for the 30-day cleanup.

---

## Out-of-Scope

- The route-overlap-pooling-optimization model itself, and any planned-vs-actual route deviation analysis — this feature only preserves the raw trace data that model will eventually consume.
- Any change to the live "driver is on the way" passenger-facing tracking UI — it continues to read only the current position.
- De-duplication, smoothing, or compression of the raw ping stream — v1 stores every ping as received.
- Retention periods other than 30 days, or making the window configurable per environment — 30 days is a fixed default for v1; revisit once real storage volume is observed.

---

## Technical Considerations

- Should follow the project's existing asyncpg / raw-SQL convention for the new table — no ORM (per current `services/api` conventions), consistent with `match_events`/`match_outcomes`.
- The history INSERT should happen in the same request handler as the existing `driver_locations` upsert, but must not be allowed to fail that upsert (wrap in its own try/except, log-and-continue — same pattern as `match_logging_service.persist_match_events`).
- The retention job is a straightforward `DELETE ... WHERE recorded_at < now() - interval '30 days'`; no soft-delete or archival step is required for v1.

---

## Assumptions

- "30-day rolling retention" means a moving window relative to the retention job's run time, not a fixed monthly purge — confirmed as the intended reading of the original request.
- Storage volume at current/expected traffic levels does not require partitioning or a specialized time-series store for v1; a plain indexed table is sufficient. Revisit if real ping volume proves this wrong.
- No passenger- or driver-facing feature (e.g. a "trip replay" screen) is in scope — this is instrumentation for a future AI model only, not a product feature in its own right.
- Data retention/anonymization policy beyond the 30-day window itself (e.g. Egypt PDPL 151/2020 documentation) is addressed at the same level of rigor as 046 (real-outcome-dataset-pipeline) already established for match-event data, not re-litigated here.
