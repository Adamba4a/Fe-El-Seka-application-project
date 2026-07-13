# Quickstart: Match Learning Foundation

Validation scenarios proving the feature works end-to-end. Assumes local dev stack running
(`services/api`, `services/ai`, Supabase local, per `specs/012-ai-application/quickstart.md`
prerequisites) and migrations applied.

## Prerequisites

- `supabase db reset` (or `supabase migration up`) applied, including this feature's new migration.
- `services/api` and `services/ai` running locally.
- A verified passenger account and at least one active `scheduled` ride whose route overlaps a test
  search.

## Scenario 1 — Every shown candidate is logged (User Story 1)

1. `POST /api/v1/search/rides` with an origin/destination that returns ≥1 candidate.
2. Note the `candidates[].ride_id` values and `total` in the response.
3. Query: `SELECT * FROM match_events WHERE search_id = (SELECT id FROM search_sessions ORDER BY created_at DESC LIMIT 1)`.
4. **Expected**: one `match_events` row per returned candidate, each with a non-null
   `feature_vector`, `rank_position` matching its position in the response, and `ai_scored = true`
   when `ai_ranking_active` was `true` in the response (false otherwise).

## Scenario 2 — Fallback searches are still logged (User Story 1, Acceptance Scenario 2)

1. Stop the `services/ai` container/process.
2. Repeat the search from Scenario 1.
3. **Expected**: response still returns candidates (`ai_ranking_active: false`), and
   `match_events` rows are still inserted with `ai_scored = false`, `predicted_score = NULL`.

## Scenario 3 — Outcome linking (User Story 1, Acceptance Scenario 3)

1. From a search response, book one of the returned `ride_id`s (`POST /api/v1/bookings`).
2. Query: `SELECT * FROM match_outcomes WHERE match_event_id = (SELECT id FROM match_events WHERE candidate_ride_id = '<ride_id>' AND passenger_id = '<passenger_id>' ORDER BY created_at DESC LIMIT 1)`.
3. **Expected**: a `requested` transition row exists.
4. As the driver, confirm the booking. Re-query.
5. **Expected**: an `accepted` transition row is appended (both rows present — append-only).

## Scenario 4 — Exploration produces a measurable deviation (User Story 2)

1. `UPDATE ranking_config SET exploration_rate = 1.0;` (force exploration on every search for this test).
2. Run several identical searches with ≥3 feasible candidates.
3. **Expected**: `match_events.exploration_selected = true` on exactly one row per search, and that
   row's `rank_position = 1` even though it was not the top AI-scored candidate for that search.
4. Reset: `UPDATE ranking_config SET exploration_rate = 0.125;`.

## Scenario 5 — Logging never blocks or slows the search response (User Story 3)

1. Temporarily point the DB connection used by the fire-and-forget task at an unreachable host (or
   simulate by dropping the `match_events` table).
2. Run a search.
3. **Expected**: the search response still returns within the existing performance target and with
   correct candidates; check application logs for a logged persistence failure — the request itself
   must not error or hang.

## Scenario 6 — Exploration rate is adjustable without a deploy (FR-010/NFR-004)

1. `UPDATE ranking_config SET exploration_rate = 0.30;` directly via the Supabase dashboard/SQL.
2. Within 30 seconds (the config refresh interval), run several searches.
3. **Expected**: the observed exploration frequency shifts toward ~30% without any service restart
   or code change.
