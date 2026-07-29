# Phase 0 Research: Trust & Community

No `NEEDS CLARIFICATION` markers remain in the Technical Context (all four ambiguities were
resolved during `/speckit-clarify`; see spec.md Clarifications). This document records the
implementation-pattern decisions made while grounding the plan in the existing codebase.

## R1: Backend access pattern — asyncpg raw SQL vs. `supabase-py` client

**Decision**: Split by write-transactionality. `rating_service.py` and `report_service.py` use
`asyncpg` raw SQL, participating in existing `conn.transaction()` blocks. `moderation_service.py`'s
admin-facing queue/resolve endpoints use the `supabase-py` service-role client.

**Rationale**: The codebase already has two established patterns and they map cleanly onto this
feature's two halves:
- Rating/report *submission* is a synchronous, user-facing write that must be atomic with reads it
  depends on (e.g., checking booking status and inserting the rating in one transaction) — this
  matches `booking_service.py`'s `asyncpg` convention exactly.
- The admin moderation queue is paginated, read-heavy, and each action (warn/suspend/dismiss/
  reinstate) is a single independent row update, not part of a larger multi-step transaction — this
  matches `verification_router.py` + `audit_service.py`'s `supabase-py` convention exactly.

**Alternatives considered**: Standardizing everything on one client library was considered and
rejected — it would mean either bolting transactional guarantees onto `supabase-py` (not a
first-class capability of that client) or rewriting the admin-panel convention project-wide, neither
of which this feature has scope or reason to do.

## R2: Extending `admin_audit_logs.action_type`

**Decision**: `ALTER TABLE admin_audit_logs DROP CONSTRAINT <existing_check_name>, ADD CONSTRAINT
... CHECK (action_type IN ('approved','rejected','suspended','reinstated','unlocked','warned'))`.

**Rationale**: Confirmed via `20260614000004_create_admin_audit_logs.sql` that `action_type` is a
`TEXT CHECK (...)` constraint, not a Postgres `ENUM` type. This matters because the migration syntax
for adding a new allowed value is a constraint replacement, not `ALTER TYPE ... ADD VALUE` (which
would be the wrong approach and would fail — there is no enum type to alter).

**Alternatives considered**: Introducing a separate `moderation_audit_logs` table was considered (to
avoid touching an existing table) and rejected per spec Technical Considerations — it would create a
second, competing audit mechanism for admin-taken actions, which the spec explicitly says to avoid.

## R3: Auto-flagging thresholds — config pattern

**Decision**: New `moderation_config` singleton table (one row, cached in-process, refreshed on a
loop), following `pricing_config`/`ranking_config` exactly: `init_moderation_config()` on startup,
`moderation_config_refresh_loop()` as a background `asyncio` task, `get_flagging_thresholds()` as a
cheap in-memory read for request handlers.

**Rationale**: FR-019/NFR-004 require the thresholds (rating floor, minimum rating count, report
count, time window) to be adjustable without a deployment. `ranking_config_service.py` and
`pricing_service.py` already solve exactly this problem (singleton table + `updated_at` trigger +
cached refresh loop) — reusing the pattern is both faster to build and consistent with the existing
codebase, per constitution Quality Standards ("follow established architectural patterns").

**Alternatives considered**: Environment-variable-based thresholds were considered and rejected —
they would require a deployment to change, which directly violates FR-019/NFR-004.

## R4: Double-blind reveal (FR-008) and rating deadline (FR-011) — computed vs. stored

**Decision**: Reveal state and deadline enforcement are computed at read/write time from existing
timestamps (`ratings.created_at`, the booking's ride `completed_at`), not maintained by a scheduled
job or a stored "revealed" boolean that something has to flip.

**Rationale**: Both conditions are pure functions of data already on hand at query time — "has the
other party's rating been submitted" (a second-row existence check) and "have 14 days passed since
ride completion" (a timestamp comparison). No background sweep is needed to "reveal" a rating; the
read path simply decides visibility each time it's queried. This avoids introducing a new scheduled
job for a feature whose write volume (~100 rides/day) doesn't warrant one.

**Alternatives considered**: A cron-style sweep that flips a `revealed_at` column once 14 days pass
was considered and rejected as unnecessary complexity — it would need a new background loop purely
to precompute something the read path can already determine in a single query at negligible cost.

## R5: Rating-prompt notification delivery

**Decision**: Reuse `notification_events` (the existing table `notification_dispatcher.py` already
polls every 30 seconds) by inserting a row when `booking_service.py`'s `complete_ride_bookings()`
transitions a booking to `completed` — no new dispatcher.

**Rationale**: `010-realtime-transportation` already built and deployed the exact "durably enqueue a
notification, dispatch via FCM on a poll loop" mechanism this feature needs for both the rate-your-
ride prompt and moderation-outcome notifications (FR-025). Reusing it is a one-row insert inside the
existing booking-completion transaction; building a second delivery path would duplicate working
infrastructure with no functional benefit.

**Alternatives considered**: A dedicated real-time push (Supabase Realtime channel) for the rating
prompt was considered and rejected — push notifications via the existing FCM/`notification_events`
path already satisfy the UX need ("prompted to rate after a ride ends") without a new delivery
mechanism.

## R6: Rating aggregate storage

**Decision**: Denormalized `rating_avg` / `rating_count` columns on `profiles`, recalculated
synchronously inside the same transaction as each new rating insert.

**Rationale**: NFR-002 requires the aggregate to reflect within 5 seconds; recalculating and writing
it in the same transaction as the rating insert satisfies this trivially (it's available
immediately, not just within 5 seconds) and avoids a second read-path query that joins/aggregates the
raw `ratings` table on every profile view — consistent with spec Technical Considerations.

**Alternatives considered**: Computing the aggregate on-the-fly from `ratings` on every profile read
was considered and rejected per the spec's own Technical Considerations section, which calls this out
explicitly in favor of the denormalized approach.
