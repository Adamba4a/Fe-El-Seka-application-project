# Data Model: Match Learning Foundation

Four new tables in the existing Supabase Postgres database. No changes to `rides`, `requests`,
`bookings`, or `booking_audit_log`. All primary keys are UUID (`gen_random_uuid()`), per constitution
Data Standards. `asyncpg` raw SQL, no ORM.

---

## `search_sessions`

Groups all match events returned from one passenger search request.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `passenger_id` | UUID NOT NULL | FK → `profiles(id)` |
| `origin_point` | `geometry(Point,4326)` NOT NULL | PostGIS, per constitution Data Standards |
| `destination_point` | `geometry(Point,4326)` NOT NULL | |
| `desired_departure_at` | TIMESTAMPTZ NOT NULL | |
| `ai_available` | BOOLEAN NOT NULL | Whether AI scoring succeeded for this search (mirrors `ai_ranking_active` in the search response) |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |

Index: `(passenger_id, created_at DESC)` — recent-searches-per-passenger queries.

---

## `match_events`

One record per ride candidate shown to a passenger in a search response.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `search_id` | UUID NOT NULL | FK → `search_sessions(id)` |
| `passenger_id` | UUID NOT NULL | FK → `profiles(id)`; denormalized from `search_sessions` for direct query without a join |
| `candidate_ride_id` | UUID NOT NULL | FK → `rides(id)` |
| `feature_vector` | JSONB NOT NULL | Exact feature values used for this candidate — AI feature vector when `ai_scored`, or the deterministic-fallback proxy values (`overlap_pct`, etc.) otherwise |
| `predicted_score` | NUMERIC(5,4) NULL | AI `match_score` (0–1); NULL when `ai_scored = false` (no AI score exists) |
| `rank_position` | INTEGER NOT NULL | Final shown position (1-indexed), after threshold filter and exploration |
| `exploration_selected` | BOOLEAN NOT NULL DEFAULT FALSE | True only for the single candidate promoted by exploration (see `research.md` R2) |
| `ai_scored` | BOOLEAN NOT NULL | True = AI-scored; false = fallback-derived (overlap_pct sort) |
| `model_version` | TEXT NULL | From the AI response; NULL when `ai_scored = false` |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |

Indexes:
- `(search_id)` — reconstruct a full search response.
- `(candidate_ride_id, passenger_id, created_at DESC)` — outcome-correlation lookup (R1).

---

## `match_outcomes`

Append-only log of observed downstream results for a match event — one row per transition.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `match_event_id` | UUID NOT NULL | FK → `match_events(id)` |
| `transition_type` | `match_outcome_transition` ENUM NOT NULL | `('requested', 'accepted', 'rejected', 'completed', 'cancelled', 'rated')` |
| `transition_at` | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |
| `metadata` | JSONB NOT NULL DEFAULT `'{}'` | e.g. `{"booking_id": ..., "cancelled_by": ...}`; holds rating value once 032-ratings-system ships (FR-004 — no schema change needed) |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |

Index: `(match_event_id, transition_at ASC)` — reconstruct full transition history per match-event (mirrors `idx_booking_audit_booking_id`).

Never updated after insert — append-only, per Clarifications.

---

## `ranking_config`

Singleton (always exactly one row), admin-edited directly via the Supabase dashboard — mirrors
`pricing_config`.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `exploration_rate` | NUMERIC(5,4) NOT NULL DEFAULT 0.1250 | Starting value per Clarifications (~10-15%, midpoint) |
| `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT NOW() | Trigger-maintained, same pattern as `pricing_config.updated_at` |

---

## Relationships

```
profiles ──< search_sessions ──< match_events ──< match_outcomes
                                       │
                                       └── candidate_ride_id ──> rides
```

## RLS

All four tables: `ENABLE ROW LEVEL SECURITY`, no public policies. This is internal ML telemetry, not
surfaced in any passenger/driver/admin UI (per spec Out-of-Scope) — unlike `booking_audit_log`, which
has passenger/driver read policies because it is a user-facing audit trail. Only the backend
service-role connection (already used for all `asyncpg` pool access) can read/write these tables,
consistent with the constitution's least-privilege principle.

## Retention

No retention/anonymization policy is implemented by this feature — ownership is explicitly deferred
to Phase 13 item 046 (per spec Assumptions). Tables grow unbounded for now.
