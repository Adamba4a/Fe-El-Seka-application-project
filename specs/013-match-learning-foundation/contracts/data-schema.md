# Contract: Match Learning Data Schema

This feature adds no new external REST endpoints and changes no existing request/response shapes —
`search_rides` and the booking endpoints keep their current API contracts unchanged (per spec
Technical Considerations: backend-only, no UI-visible change). The interface this feature exposes is
the **database schema itself**, which is the direct input contract for the future real-outcome-dataset
ETL (Phase 13 item 046, per FR-012/SC-005).

## Consumers

- Phase 13 item 046 (real-outcome-dataset ETL) — reads `match_events` joined to `match_outcomes` to
  build training rows: feature vector → predicted score → actual outcome.
- Phase 13 item 049 (model monitoring / drift detection) — reads `match_events.predicted_score` vs.
  `match_outcomes` outcome distribution over time.

## Guaranteed shape

See `data-model.md` for full column definitions. The ETL/monitoring consumers can rely on:

- Every `match_events` row has a `feature_vector` JSONB blob containing the complete set of values
  used to rank that candidate (present regardless of `ai_scored` true/false).
- `ai_scored = false` rows have `predicted_score = NULL` and `model_version = NULL` — consumers MUST
  filter or weight these separately, never treat a NULL score as `0`.
- `match_outcomes` is append-only: a `match_event_id` MAY have zero, one, or many outcome rows,
  ordered by `transition_at`. The absence of a `completed`/`cancelled` row means the candidate's
  final state is not yet resolved (e.g. still en route), not that it failed.
- `exploration_selected = true` marks candidates whose shown position was not purely score-ordered —
  required for any counterfactual/off-policy analysis distinguishing exploration from exploitation
  data.
- No column in this schema is ever backfilled retroactively; a row's absence for a time period before
  this feature's deployment means no data exists for that period (see spec Business Objective).

## Non-goals of this contract

- No data-quality filtering, deduplication, or anonymization — owned by 046.
- No guaranteed maximum latency between an event occurring and its row being queryable (best-effort
  for `match_events`, synchronous-but-unbounded-by-this-spec for `match_outcomes`).
