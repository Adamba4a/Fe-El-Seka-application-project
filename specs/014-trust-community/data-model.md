# Phase 1 Data Model: Trust & Community

## New Enums

```sql
CREATE TYPE report_category AS ENUM (
    'unsafe_driving', 'harassment', 'no_show', 'fraud_or_scam', 'vehicle_mismatch', 'other'
);

CREATE TYPE report_status AS ENUM ('open', 'under_review', 'resolved', 'dismissed');

CREATE TYPE report_resolution_action AS ENUM ('warn', 'suspend', 'dismiss');

CREATE TYPE rater_role AS ENUM ('passenger', 'driver');
```

## `ratings`

One row per `(booking_id, rater_id)` — one direction of a two-way rating on a completed booking.
Maps to spec Key Entity **Rating**, FR-001–FR-011.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `booking_id` | UUID NOT NULL | FK → `bookings(id) ON DELETE RESTRICT` |
| `ride_id` | UUID NOT NULL | FK → `rides(id) ON DELETE RESTRICT` — denormalized for query convenience (avoids a join through `bookings` on every read); ride is immutable once a booking exists |
| `rater_id` | UUID NOT NULL | FK → `profiles(id) ON DELETE RESTRICT` |
| `ratee_id` | UUID NOT NULL | FK → `profiles(id) ON DELETE RESTRICT` |
| `rater_role` | `rater_role` NOT NULL | passenger or driver, at time of rating (FR-002) |
| `stars` | SMALLINT NOT NULL | `CHECK (stars BETWEEN 1 AND 5)` (FR-001) |
| `comment` | TEXT | nullable; `CHECK (char_length(comment) <= 500)` (NFR-003) |
| `created_at` | TIMESTAMPTZ NOT NULL | `DEFAULT NOW()` |

**Constraints**:
- `UNIQUE (booking_id, rater_id)` — enforces FR-005 (at most one rating per direction per booking) at
  the database level, not just in application logic.
- No `UPDATE`/`DELETE` policy granted to any client role — ratings are immutable once submitted, per
  spec Assumptions ("No rating edit window").

**Reveal state (FR-008)** is not a stored column — it is computed at query time:
`revealed = (a counterpart row exists for the same booking_id, opposite rater) OR (now() - ride.completed_at >= interval '14 days')`.

**Deadline enforcement (FR-011)** is an application-layer check at submission time (not a stored
column, not a DB constraint — the ride's `completed_at` is on a different table): reject if
`now() - ride.completed_at > interval '14 days'`.

**Indexes**:
- `UNIQUE (booking_id, rater_id)` (also serves as the lookup index for the reveal-state counterpart check)
- `(ratee_id, created_at DESC)` — for the ratee's own anonymized comment list (FR-007)

## `reports`

Maps to spec Key Entity **Report**, FR-012–FR-017.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `ride_id` | UUID NOT NULL | FK → `rides(id) ON DELETE RESTRICT` |
| `booking_id` | UUID NOT NULL | FK → `bookings(id) ON DELETE RESTRICT` |
| `reporter_id` | UUID NOT NULL | FK → `profiles(id) ON DELETE RESTRICT` |
| `reported_user_id` | UUID NOT NULL | FK → `profiles(id) ON DELETE RESTRICT`; `CHECK (reported_user_id != reporter_id)` (FR-013) |
| `category` | `report_category` NOT NULL | fixed set (FR-012) |
| `description` | TEXT NOT NULL | `CHECK (char_length(description) BETWEEN 1 AND 1000)` (FR-014, NFR-003) |
| `status` | `report_status` NOT NULL | `DEFAULT 'open'` (FR-016) |
| `resolution_action` | `report_resolution_action` | nullable; set only when `status IN ('resolved','dismissed')` |
| `resolution_reason` | TEXT | nullable; required by application logic when resolving (FR-021) |
| `resolved_by` | UUID | FK → `profiles(id) ON DELETE SET NULL`, nullable |
| `created_at` | TIMESTAMPTZ NOT NULL | `DEFAULT NOW()` |
| `resolved_at` | TIMESTAMPTZ | nullable |

**Indexes**:
- `(status, created_at DESC)` — moderation queue ordering (FR-018)
- `(reported_user_id, created_at DESC)` — for FR-019(b)'s rolling 30-day report-count check
- `(reporter_id, created_at DESC)` — reporter's own history view (FR-016)

## `moderation_config` (singleton, mirrors `ranking_config`/`pricing_config`)

Backs FR-019/NFR-004's admin-configurable auto-flagging thresholds.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()`, single seeded row |
| `rating_floor` | NUMERIC(2,1) NOT NULL | `DEFAULT 3.0` |
| `rating_window` | SMALLINT NOT NULL | `DEFAULT 10` — most recent N ratings considered |
| `rating_min_count` | SMALLINT NOT NULL | `DEFAULT 5` — minimum ratings received before eligible |
| `report_count_threshold` | SMALLINT NOT NULL | `DEFAULT 3` |
| `report_window_days` | SMALLINT NOT NULL | `DEFAULT 30` |
| `updated_at` | TIMESTAMPTZ NOT NULL | `DEFAULT NOW()`, trigger-maintained (same pattern as `ranking_config`) |

## Extended: `profiles`

No new columns beyond the denormalized rating aggregate (research.md R6):

| Column | Type | Notes |
|---|---|---|
| `rating_avg` | NUMERIC(3,2) | nullable — `NULL` means "not yet rated" (FR-010), distinct from a low numeric score |
| `rating_count` | INTEGER NOT NULL | `DEFAULT 0` |

`verification_status` is reused as-is (no new value) — `'suspended'`/`'verified'` transitions per
FR-021/FR-022 already exist from `003-auth-verification`.

## Extended: `admin_audit_logs`

- `action_type` CHECK constraint gains `'warned'` (research.md R2).
- New nullable column `report_id UUID REFERENCES reports(id) ON DELETE SET NULL` — traces a
  moderation action back to the report(s) that triggered it (Key Entity: Moderation Action).

## State Transitions

**Report status**: `open` → `under_review` (FR-020) → `resolved` | `dismissed` (FR-021). `open` can
also transition directly to `resolved`/`dismissed` (an admin may resolve without first marking
`under_review`). No transition out of `resolved`/`dismissed` — resolution is terminal.

**Rating**: no state machine — a rating row is immutable once inserted (create-only).

**Profile verification_status** (reused, not introduced): `verified` → `suspended` (FR-021) →
`verified` (FR-022, reinstate). No change to the enum or its existing transitions from
`003-auth-verification`.

## Row Level Security

Following the `bookings`/`booking_audit_log` pattern (`20260624000001_phase6_bookings.sql`):

- `ratings`: `SELECT` allowed where `auth.uid() IN (rater_id, ratee_id)`, but the ratee-side `SELECT`
  is exposed to the application through a view/query that excludes `rater_id` and unrevealed rows
  (FR-007/FR-008 enforcement is an application-layer concern on top of RLS, since RLS alone cannot
  express the double-blind time/counterpart condition). No client-side `INSERT`/`UPDATE`/`DELETE`
  policy — all writes go through `services/api` using the service-role key inside a transaction that
  also validates FR-003/004/005/011.
- `reports`: `SELECT` allowed where `auth.uid() = reporter_id` (status-only history, FR-016); no
  `SELECT` policy for `reported_user_id` (a reported user does not see who reported them or that a
  report exists, per spec Edge Cases — the outcome notification (FR-025) is the only signal they
  receive, and it excludes reporter identity). No client-side `INSERT`/`UPDATE`/`DELETE` — writes go
  through `services/api`.
- `moderation_config`: no client policies at all (service-role only), mirroring `ranking_config`.
- `admin_audit_logs`: unchanged from `003-auth-verification` — no client policies (service-role only).
