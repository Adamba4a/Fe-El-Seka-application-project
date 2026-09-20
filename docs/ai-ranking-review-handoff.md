# AI Ranking Review Handoff

## Production state as of 2026-09-15

- Bunny Magic Containers app: `triplyy-prod`, with separate `main`, `api`, and `ai` services.
- R2 credentials were initially missing from Bunny. Photo uploads were fixed by configuring the API service with `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, and `R2_SECRET_ACCESS_KEY`.
- The AI service also requires those same R2 variables, plus
  `MODEL_REGISTRY_BUCKET=model-registry`, so it can load the `match_score` and
  `ride_ranker` model artifacts from R2 at startup. The R2 token already has
  Object Read & Write access to `model-registry`, `profile-photos`,
  `identity-documents`, and `training-datasets`.

## Confirmed AI/search findings

1. Search cards have two distinct percentage concepts:
   - The horizontal coloured bar is deterministic route overlap, not an AI score.
   - The `MatchScoreBadge` is the AI match score and is only rendered when
     `match_score_pct` is non-null.
2. When the AI service/models were unavailable, the API set `ai_active=false`
   and fell back to sorting by route overlap. This was why the AI badge and the
   ride-detail score were absent.
3. `ranking_config.exploration_rate` defaults to `0.125` (12.5%).
   `ranking_config_service.apply_exploration()` can promote a random lower ranked
   result to the first position. This can deliberately put a very poor match above
   a strong result and should be disabled or tightly constrained for production.
4. The `ride_ranker` response is currently not the final ordering authority:
   `search/router.py` gets `ranked_ids` from `ai_client.rank_candidates()`, but
   later sorts candidates again by match score. This needs correction so the
   ranking model's ordering is either used correctly or the redundant model call
   is removed.
5. The passenger detail endpoint recomputes `match_score_pct` only when it has
   search coordinates and `departure_at` in the URL. It silently logs a warning
   if AI scoring fails. A bare dashboard-card click intentionally uses preview
   mode and has no match score.

## Training-data collection currently implemented

- Every search writes a `search_sessions` record.
- Every returned candidate writes a `match_events` record with route features,
  price, candidate type, predicted match score (when AI is active), rank,
  exploration flag, model/shadow version, and served variant.
- Booking/rating flows write correlated `match_outcomes`: requested, accepted,
  rejected, cancelled, completed, and rated (including stars).
- An hourly scheduler creates anonymized Parquet snapshots in the
  `training-datasets` R2 bucket once the configured minimum dataset size is met,
  then can retrain and evaluate candidates.
- Dataset processing excludes suspended/rejected accounts, marked test/QA data,
  and data older than 365 days.

## Remaining AI review/fix priorities

1. Verify production `search_sessions`, `match_events`, and `match_outcomes`
   rows after a real AI-enabled search and booking.
2. Disable/constrain ranking exploration for passenger-facing production search.
3. Fix final ordering so `ride_ranker` output is actually honoured, and log its
   model version/scores separately from match-score telemetry.
4. Add impression/click/detail-view events; current data records returned
   candidates and booking outcomes but not whether a card was actually viewed or
   opened.
5. Continue the requested full audit: auth/onboarding, API reliability, database,
   storage, security/privacy, data pipelines, model implementation, evaluation,
   monitoring, and deployment readiness.
