# Contract: Dataset Pipeline (`services/api/app/services/dataset_pipeline_service.py`)

Internal service module — no HTTP surface. Invoked by `retraining_scheduler_loop` before each retraining attempt, and available for on-demand/manual invocation (FR-001, FR-005).

## Function: `generate_dataset_snapshot(model_type: str) -> DatasetSnapshot`

**Preconditions**: none — runs even below the 500-ride threshold (per spec Edge Cases: "the dataset pipeline still runs and produces output" regardless of volume; only *retraining* is gated on volume, not dataset generation).

**Steps** (FR-001 through FR-004):

1. Query `match_events` joined to `match_outcomes` (via `match_event_id`) for events not already covered by a prior snapshot's date range, ordered by `match_events.created_at`.
2. **Exclude** (FR-003) rows where the associated `passenger_id` or the ride's driver has `profiles.verification_status IN ('suspended', 'rejected')`, OR has an associated `reports` row resolved with `resolution_action = 'suspend'` (from `014-trust-community`'s `report_resolution_action` enum). A `'warn'` or `'dismiss'` resolution alone is not exclusion-grade — only an actual suspension indicates the account's behavior shouldn't shape future model training.
3. **Exclude** rows outside the configured retention window (FR-004) — window length follows the same PDPL 151/2020-driven retention policy already governing `match_events`/`match_outcomes` themselves (this feature does not introduce a separate/shorter window).
4. **Label** each retained row with a `signal_strength_tier` per the FR-002 hierarchy, derived from the row's `match_outcomes` transitions:
   - `completed_highly_rated` — has a `'completed'` transition AND a linked rating (`032-ratings-system`) at or above the platform's "highly rated" threshold
   - `completed_unrated` — has `'completed'` but no rating yet, or rating below the highly-rated threshold
   - `booked_not_completed` — has `'accepted'` but no `'completed'` (includes a `'cancelled'` transition — see next point)
   - `shown_not_booked` — has neither `'accepted'` nor `'rejected'` recorded as the last known transition beyond `'requested'`
   - **Cancellation handling** (Acceptance Scenario 2): a `'cancelled'` transition is folded into `booked_not_completed`, never auto-labeled as a hard negative — reflects that cancellations have mixed causes (passenger changed plans, driver unavailable) unrelated to match quality.
5. **Anonymize** (FR-004): drop/hash any directly identifying fields from the row before writing to Parquet (retain `passenger_id`/driver id only as opaque UUIDs already used internally — no names, phone numbers, or free-text fields are included in the feature vector or label; `match_events.feature_vector` as logged by `013` is already numeric-only, so this step mainly asserts no additional PII columns are joined in).
6. Write the resulting rows to `training-datasets/{model_type}/{snapshot_id}/dataset.parquet`.
7. Insert one `dataset_snapshots` row (row_count, excluded_count, date range, exclusion_summary).

**Postconditions**: returns the new `dataset_snapshots` row. Idempotent per invocation — re-running does not mutate or delete prior snapshots (append-only, per FR-016's audit trail requirement).

**Failure handling**: if Storage or the DB is unavailable mid-run, the function raises and the caller (`retraining_scheduler_loop`) logs the miss and retries on the next scheduled tick — no partial snapshot row is committed (INSERT happens only after the Parquet upload succeeds), matching the spec's Edge Case: "the run is skipped and logged as missed; the existing live model continues serving unaffected."

## Function: `get_labeled_row_count(model_type: str, snapshot_id: UUID) -> int`

Used by `model_lifecycle_service.py` to check the 500-completed-ride threshold (Assumptions) before allowing a retraining trigger — reads `dataset_snapshots.row_count` directly (no need to re-scan Storage).
