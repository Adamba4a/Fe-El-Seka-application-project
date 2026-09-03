# Quickstart: Fraud Signal Capture

Validation scenarios for the local dev stack (Docker-based Supabase + API, per repo convention). All queries run
against the local Postgres container's `fraud_signals` table.

## Prerequisites

- Local stack up (`docker compose up` per repo convention), API container running the branch's code.
- A test passenger/driver account (or ability to sign up a new one via OTP).

## Scenario 1 — Signup produces a signal row (FR-001, SC-001)

1. Send an OTP request, then verify it with a fresh test email and header `X-Device-Id: test-device-1`.
2. Query: `SELECT event_type, hashed_device_id, hashed_ip, user_id FROM fraud_signals WHERE event_type = 'signup' ORDER BY created_at DESC LIMIT 1;`
3. **Expected**: One row, `hashed_device_id` non-null (not equal to the literal string `test-device-1`), `hashed_ip`
   non-null, `user_id` set to the newly created account's id.

## Scenario 2 — Login, ride-posting, booking-creation each produce their own signal row (FR-001)

1. Log in with the same account (`X-Device-Id: test-device-1`), then create a ride as a driver, then have a
   second test passenger book a seat on it (each with their own `X-Device-Id`).
2. Query: `SELECT event_type, COUNT(*) FROM fraud_signals GROUP BY event_type;`
3. **Expected**: At least one row each for `login`, `ride_posted`, `booking_created`, in addition to `signup`.

## Scenario 3 — Same device/IP across two accounts hashes identically (FR-002, SC-004)

1. Sign up two different test accounts using the same `X-Device-Id` header value and the same origin (so both
   requests share one real source IP).
2. Query: `SELECT DISTINCT hashed_device_id, hashed_ip FROM fraud_signals WHERE event_type = 'signup' ORDER BY created_at DESC LIMIT 2;`
3. **Expected**: Both accounts' rows show the identical `hashed_device_id` and identical `hashed_ip` value —
   confirms the HMAC digest is deterministic per input, proving graph-linking is usable (research.md R2).

## Scenario 4 — No raw value is ever stored (FR-002, FR-003, SC-003)

1. Repeat Scenario 1 with a distinctive, greppable device ID, e.g. `X-Device-Id: qa-raw-value-check-12345`.
2. Query: `SELECT * FROM fraud_signals WHERE hashed_device_id LIKE '%qa-raw-value-check%' OR hashed_ip LIKE '%qa-raw-value-check%';`
3. **Expected**: Zero rows — the raw literal never appears anywhere in the stored digest (a 64-hex-char HMAC-SHA256
   digest cannot contain a readable substring of its input).

## Scenario 5 — Missing device header never blocks the request (Edge Cases, FR-002)

1. Send a signup/login/ride-post/booking-create request with no `X-Device-Id` header at all.
2. **Expected**: The request succeeds exactly as it did before this feature (identical response shape/status).
3. Query: the corresponding `fraud_signals` row has `hashed_device_id IS NULL` and `hashed_ip` still populated.

## Scenario 6 — Signal persistence never blocks or fails the instrumented request (FR-005, FR-006, NFR-001, NFR-002)

1. Deliberately break the signal write path (e.g. temporarily rename the `fraud_signals` table, or point the pool
   at a bad connection for the background task only) and repeat Scenario 1.
2. **Expected**: The signup request still succeeds with its normal response; no signal row is created; the
   failure appears in application logs (`fraud_signal_persist_failure`-style event), never surfaced to the client.
3. Restore the table/connection afterward.

## Scenario 7 — No client/API-visible change (Out-of-Scope)

1. Diff the response body/status of each of the four instrumented endpoints, with and without an `X-Device-Id`
   header, against their pre-feature behavior.
2. **Expected**: Byte-identical response shape in all cases — this feature is additive instrumentation only.
