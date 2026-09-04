# Contract: Fraud Signal Data Schema

This feature adds no new external REST endpoints and changes no existing request/response shapes visible to
clients — sign-up, login, ride-posting, and booking-creation keep their current response contracts unchanged (per
spec Out-of-Scope: no passenger/driver-facing UI or UX changes). It adds exactly one new optional request header
(`X-Device-Id`, research.md R4) clients MAY send on those four request types; its absence changes nothing about the
response. The interface this feature exposes is the **database schema itself** — the direct input contract for the
future roadmap TBD `fraud-detection` model.

## Consumers

- The roadmap's TBD `fraud-detection` item — reads `fraud_signals` to build device/IP graph features (shared
  device or network across many accounts, rapid account cycling) joined against the account-level trust data
  already captured (`ratings`, `reports`, `admin_audit_logs`), per spec FR-004.

## Guaranteed shape

See `data-model.md` for full column definitions. The future fraud-detection consumer can rely on:

- Every `fraud_signals` row has a non-null `hashed_ip` — every HTTP request has a source IP, so this field is
  never absent (contrast with `hashed_device_id`, which is legitimately null).
- `hashed_device_id` is null exactly when the originating request had no `X-Device-Id` header — this is a normal,
  expected state (older client versions, direct API calls), not a data-quality problem to filter out.
- `hashed_device_id` and `hashed_ip` are **one-way HMAC-SHA256 digests**, never the raw values (FR-002/FR-003) —
  the same raw device ID or IP always produces the same digest (required for graph-linking, FR-008), but no digest
  is reversible to its raw input without the server-side secret. Consumers can equality-join on these columns to
  find shared-device/shared-IP account clusters; they can never recover an actual device ID or IP from a row.
- `event_type` is one of exactly four values (`signup`, `login`, `ride_posted`, `booking_created`, FR-001) — no
  other event types exist in this table's v1.
- `user_id` is nullable — a null value means the event occurred before an authenticated identity was attached to
  the request (spec Key Entities: "nullable for pre-authentication events"), not a data-quality problem.
- No column in this schema is ever backfilled retroactively; a row's absence for a time period before this
  feature's deployment means no signal exists for that period (spec Edge Cases).
- Rows are retained indefinitely — no retention/purge job exists for this table (contrast with
  029-driver-gps-trace-history's `driver_location_history`, which has a 30-day rolling window); consumers do not
  need to account for rows disappearing over time.

## Non-goals of this contract

- No fraud scoring, thresholding, or automated action of any kind — owned entirely by the future
  roadmap `fraud-detection` item this feature only supplies data for.
- No guaranteed maximum latency between an event occurring and its row being queryable (best-effort, matching
  `match_events`/`driver_location_history`'s fire-and-forget posture).
- No coverage of Google OAuth sign-in as a discrete `login` event (research.md R6) — a known, documented gap, not
  addressed by this schema.
