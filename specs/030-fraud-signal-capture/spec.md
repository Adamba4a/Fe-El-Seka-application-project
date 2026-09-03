# Feature Specification: Fraud Signal Capture

**Feature Branch**: `030-fraud-signal-capture`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Close data-collection gap #3 from the 2026-09-03 roadmap audit — no device ID, IP address, or session fingerprint is captured anywhere in the schema, the single biggest gap for a future fraud model. Capture a hashed device ID and hashed IP address only, ahead of the future fraud-detection model."

## Business Objective *(mandatory)*

Capture the minimum device/network signal needed for a future fraud-detection model — most real fraud models lean on device/IP graph signals (the same device or network behind many accounts, rapid account cycling, etc.) — without storing anything that directly identifies a person's device or network location. Only a one-way hash of the device ID and a one-way hash of the IP address are persisted, never the raw values. Like 044/045 (013-match-learning-foundation), this signal is generated on every relevant request right now and is unrecoverable once past if not captured; this feature captures it, it does not build the fraud model itself.

**Constitutional Domain**: AI Integration / Trust & Community

**Affected Applications**: Shared (`services/api`) — backend-only. Client apps (`apps/main`, `apps/driver` if applicable) must generate and send a stable per-install device identifier; no other passenger- or driver-facing UI changes.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trust-relevant events are tagged with a hashed device/IP signal (Priority: P1)

As the platform, when a user performs a trust-relevant action (sign-up, login, ride posting, booking creation), the request's device identifier and source IP are hashed and recorded alongside that action, so that a future fraud model has device/IP graph signal to learn from — e.g. many accounts sharing one device, or rapid account creation from one network.

**Why this priority**: This is the entire foundation of the fraud-signal strategy named in the 2026-09-03 audit as the single biggest data gap for a future fraud model. Without it, nothing downstream (fraud-detection modeling) has anything to work with, and the gap cannot be closed retroactively.

**Independent Test**: Perform a sign-up, a login, and a booking creation from the same simulated device/IP, then query the signal store directly. Confirm one record exists per event, each carrying the same hashed device ID and hashed IP for that session, and that no raw (unhashed) device ID or IP appears anywhere in the stored record.

**Acceptance Scenarios**:

1. **Given** a user signs up, **When** the request is processed, **Then** a signal record is persisted containing the hashed device ID, the hashed IP, the event type (`signup`), the user identifier, and a timestamp.
2. **Given** a user logs in, creates a ride, or creates a booking, **When** each of those requests is processed, **Then** a corresponding signal record is persisted the same way, tagged with its own event type.
3. **Given** the same physical device and network are used for two different accounts, **When** signal records are compared, **Then** both accounts' records show the identical hashed device ID and hashed IP — proving the graph-linking signal survives hashing.
4. **Given** a signal record is stored, **When** it is inspected directly (e.g. via database query), **Then** neither the raw device identifier nor the raw IP address is present or derivable from the stored value alone (one-way hash, not encryption).

---

### User Story 2 - Signal capture never degrades the request it instruments (Priority: P2)

As a user, my sign-up, login, ride-posting, and booking requests complete with the same speed and reliability regardless of whether fraud-signal logging succeeds, fails, or is slow.

**Why this priority**: Instrumentation that breaks or slows down the requests it instruments risks being disabled under pressure, which would silently re-create the "never captured from day one" problem this feature exists to prevent. It depends on User Story 1 existing to have anything to protect.

**Independent Test**: Simulate the signal-store write path being slow or failing entirely. Confirm the instrumented endpoints still return successfully within their existing performance expectations.

**Acceptance Scenarios**:

1. **Given** the signal store is temporarily unreachable, **When** a user signs up, logs in, posts a ride, or creates a booking, **Then** the request still succeeds normally, and the logging failure is recorded for operational visibility rather than surfaced to the user.
2. **Given** normal operation, **When** an instrumented request is made, **Then** signal persistence does not add measurable latency to that request's response.

---

### Edge Cases

- What happens if the client does not send a device identifier (e.g. an older app version, or a direct API call with no device header)? The signal record is still written with the hashed-device field null/absent and the hashed-IP field populated — partial signal is still useful, and the request is never blocked for missing a device identifier.
- What happens behind a shared IP (e.g. a mobile carrier NAT or campus network shared by many unrelated real users)? Out of scope for this feature to disambiguate — it is a known, accepted noise source for any future model trained on this signal, not something this capture step tries to solve.
- What happens if a user is behind a proxy/VPN that changes their IP between requests in the same session? Each event's IP is hashed and recorded independently at request time; no session-level IP consistency is enforced or assumed.
- What happens to signals for events before this feature ships? None exist — like GPS trace history and match events, this signal cannot be backfilled retroactively; historical data before this feature's deployment simply has no fraud-signal coverage.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST record a signal entry for each of the following events: user sign-up, user login, ride posting (driver), booking creation (passenger).
- **FR-002**: Each signal entry MUST store a one-way, salted hash of the client's device identifier (when provided) and a one-way, salted hash of the request's source IP address — never the raw device identifier or raw IP.
- **FR-003**: System MUST NOT store any value from which the raw device identifier or raw IP address can be recovered (no reversible encryption, no separate raw-value column, no un-hashed logging of these fields at info level or above).
- **FR-004**: Each signal entry MUST include the associated user identifier (when authenticated), the event type, and a timestamp, so future modeling can join signals to the account-level trust/moderation data already captured (`ratings`, `reports`, `admin_audit_logs`).
- **FR-005**: Signal persistence MUST NOT delay or block the response of the request it instruments — persistence is best-effort, matching the non-blocking pattern established by match-event logging (013-match-learning-foundation).
- **FR-006**: A failure to persist a signal entry MUST NOT fail the underlying request; the failure MUST be recorded for operational visibility.
- **FR-007**: The client apps MUST send a stable per-install device identifier on requests for the instrumented events; the identifier only needs to be stable per app install, not tied to hardware serials or advertising IDs.
- **FR-008**: The hash used for both device identifier and IP MUST use a server-side secret salt/pepper (not derivable from the input alone), so the stored hash cannot be reversed via a rainbow-table-style lookup even if the hashing algorithm is known.

### Key Entities *(include if feature involves data)*

- **Fraud Signal**: One record per trust-relevant event. Attributes: user identifier (nullable for pre-authentication events like sign-up-in-progress, if applicable), event type (signup, login, ride_posted, booking_created), hashed device identifier (nullable), hashed IP address, timestamp.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Under normal operation, 100% of sign-up, login, ride-posting, and booking-creation requests produce a corresponding fraud-signal record.
- **SC-002**: None of the instrumented endpoints show measurable latency regression compared to their pre-instrumentation baseline.
- **SC-003**: A manual audit of the signal table confirms zero raw device identifiers or raw IP addresses are present in stored records, only hashed values.
- **SC-004**: Two accounts created from the same simulated device/network produce signal records with matching hashed device ID and hashed IP, confirming the graph-linking signal is usable by a future model.

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Fraud-signal logging MUST NOT add measurable synchronous latency to any instrumented request path.
- **NFR-002**: A failure to persist a fraud-signal entry MUST NOT fail the instrumented request; the failure MUST be recorded for operational visibility, not retried or replayed (best-effort, matching 013-match-learning-foundation).
- **NFR-003**: The hashing salt/pepper MUST be stored as server-side configuration (e.g. environment secret), never in client code or a database column alongside the hashes themselves.
- **NFR-004**: No raw device identifier or raw IP address MUST appear in application logs at a level or destination outside the request's own transient processing (i.e. do not accidentally log the raw value while computing its hash).

---

## Dependencies *(mandatory)*

- **Internal**: `013-match-learning-foundation` — precedent for the best-effort, non-blocking logging pattern reused here. Existing sign-up, login, ride-posting, and booking-creation request handlers, which this feature adds a side-effect write to, without modifying their existing behavior.
- **External**: None new.
- **Data**: New table in the existing Supabase Postgres database for fraud signals. No changes to existing `users`, `rides`, or `bookings` schemas required.

---

## Out-of-Scope

- The fraud-detection model itself, including scoring, thresholds, and any automated action (flagging, blocking, rate-limiting) — the roadmap's TBD `fraud-detection` item, which consumes the data this feature produces.
- Session fingerprinting beyond device ID + IP (e.g. browser/OS/screen fingerprint composites) — named as a possible future signal in the audit, but only device ID and IP are captured in v1.
- Any passenger- or driver-facing UI or UX changes, and any user-visible indication that this signal is being captured — this feature is backend instrumentation only.
- A retention/expiry policy for this data — unlike GPS trace history (029-driver-gps-trace-history), fraud/trust signal is intentionally treated as longer-lived account-level history (consistent with how `ratings`, `reports`, and `admin_audit_logs` are already retained indefinitely); revisit only if a specific retention requirement emerges.

---

## Technical Considerations

- Should follow the project's existing asyncpg / raw-SQL convention for the new table — no ORM (per current `services/api` conventions), consistent with `match_events`/`match_outcomes`.
- Hashing should use a standard salted HMAC (e.g. HMAC-SHA256 with a server-side secret key) rather than a bare hash function, so the same device ID/IP always hashes identically (required for graph-linking) while remaining infeasible to reverse without the secret.
- The signal write should happen as a fire-and-forget background task from each instrumented handler (same mechanism as `match_logging_service.persist_match_events` — FastAPI `BackgroundTasks`), not inline in the request-response path.
- This is a `services/api` concern only; no `services/ai` changes are needed to support capture (modeling is out-of-scope, see above).

---

## Assumptions

- "Hashed device ID + IP only" means no other raw identifying signal (browser fingerprint, precise geolocation, etc.) is captured in v1 — confirmed as the intended reading of the original request.
- The client apps can generate and persist a stable per-install identifier (e.g. a UUID generated on first launch and stored locally) to serve as the device identifier; this feature assumes that identifier is supplied by the client, it does not invent a new device-fingerprinting technique.
- A single shared HMAC secret/pepper, managed the same way other `services/api` secrets are (environment configuration), is sufficient for v1 — no per-tenant or rotating-key scheme is required.
- Retention for this table follows the same "keep it, it's account-level trust history" posture as `ratings`/`reports`/`admin_audit_logs`, not the 30-day rolling window used for GPS trace history (029-driver-gps-trace-history), since fraud graph signal loses value if it only covers a rolling recent window.
