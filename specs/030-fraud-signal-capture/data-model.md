# Data Model: Fraud Signal Capture

One new table in the existing Supabase Postgres database. No changes to `users`, `rides`, `bookings`, or any
existing table. UUID primary key (`gen_random_uuid()`), per constitution Data Standards. `asyncpg` raw SQL, no ORM.

---

## `fraud_signals`

Append-only record of one hashed device/IP observation per trust-relevant event — one row per event, never updated.
Mirrors the append-only posture of `driver_location_history` (029) and `match_events`/`search_sessions`
(013-match-learning-foundation), but — unlike 029's 30-day rolling retention — kept indefinitely, matching how
`ratings`/`reports`/`admin_audit_logs` are already retained (spec Out-of-Scope: "no retention policy").

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `user_id` | UUID NULL | FK → `auth.users(id)` ON DELETE SET NULL — nullable per spec Key Entities (pre-authentication events); references `auth.users` rather than `profiles` because the `signup` event fires from `verify_otp` at the moment the auth user is created, before any `profiles` row exists (profile creation happens later, during onboarding) — a `profiles` FK would reject every signup signal; ON DELETE SET NULL (not CASCADE) because this row's value as fraud/graph signal outlives the account it names (contrast with 029's `driver_location_history`, which is scoped to a ride and correctly cascades) |
| `event_type` | TEXT NOT NULL | One of `signup`, `login`, `ride_posted`, `booking_created` (FR-001) — plain `CHECK (event_type IN (...))` rather than a Postgres ENUM, since this table has no other place that constrains values (contrast with `admin_audit_logs.action_type`'s enum) |
| `hashed_device_id` | TEXT NULL | HMAC-SHA256 hex digest (research.md R2); null when the client sent no `X-Device-Id` header (FR-002, Edge Cases) |
| `hashed_ip` | TEXT NOT NULL | HMAC-SHA256 hex digest of `request.client.host` (research.md R3); always present — every HTTP request has a source IP |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT NOW() | The event's timestamp (FR-004) — no separate client-supplied timestamp field, unlike 029's `recorded_at` (there is no equivalent "event happened earlier than we heard about it" case for these four synchronous request-triggered events) |

Indexes:
- `(hashed_device_id)` WHERE `hashed_device_id IS NOT NULL` — supports the future fraud model's core query shape,
  "which accounts/events share this device" (SC-004's graph-linking use case).
- `(hashed_ip)` — same rationale, for IP-graph queries.
- `(user_id, created_at)` — supports joining a user's signal history to their `ratings`/`reports`/
  `admin_audit_logs` trail (FR-004).

Note: no `UNIQUE` constraint of any kind — the same user/device/IP legitimately produces many rows over time (one
per event), and duplicate-looking rows (same user, same device, same IP, different `event_type`) are expected, not
an anomaly.

---

## Relationships

```
auth.users (user, nullable) ──< fraud_signals
```

Independent of every other new-signal table this session (`driver_location_history`, 029) — no relationship exists
between them at the schema level. Both are populated from values available on their own respective request paths
only.

## RLS

`ENABLE ROW LEVEL SECURITY`, no public policies. Same posture as `match_events`/`search_sessions` (013) and
`driver_location_history` (029) — internal ML/trust telemetry, never surfaced in any passenger/driver/admin UI
(per spec Out-of-Scope). Only the backend service-role connection can read/write this table.

## Retention

None (spec Out-of-Scope) — rows are kept indefinitely, unlike 029's 30-day rolling window. No retention loop is
added in this feature.
