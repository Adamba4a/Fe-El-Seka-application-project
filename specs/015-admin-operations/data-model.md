# Phase 1 Data Model: Admin Operations (Full)

No new tables, columns, enums, or constraints are introduced by this phase (spec Key Entities: "No
new persisted entities are introduced by this phase"). This document describes how each existing
entity is **read and derived** by the new aggregation/search endpoints, and the shape of the
**computed, non-persisted** values this phase introduces (age flags, at-risk flags, KPI/trend
payloads).

## Reused entities (read-only, no schema change)

| Entity | Origin | How this phase reads it |
|---|---|---|
| `profiles` | `003-auth-verification` (renamed `phone_number`→`email` in `20260616000001`) | Searched via `ILIKE` on `display_name`/`email` (FR-005); filtered by `role`, `verification_status` (FR-006); paginated (FR-007); source of the detail view's profile section (FR-008); `role='admin'` gates the suspend action (FR-009); `verification_status` counted by role for dashboard KPIs (FR-001) |
| `verification_submissions` | `003-auth-verification` | Searched via `ILIKE` on the joined `profiles.display_name`/`email` (FR-013); `submitted_at` used to compute the age/24h flag (FR-012); `status`/`attempt_number`/`is_locked` read for history filtering and the unlock precondition (FR-014, FR-015); counted (`status = 'pending_review'`) for dashboard KPI (FR-001) |
| `admin_audit_logs` | `003-auth-verification`, extended `014-trust-community` | Write-only from this phase's perspective (FR-023) — every suspend/reinstate/unlock action appends a row via the existing `audit_service.append_log()`; no new `action_type` values |
| `bookings`, `rides` | `004-ride-management`, `009-passenger-experience` | Counted (`created_at`, `completed_at` within period) for dashboard KPIs and trend series (FR-001, FR-002); joined into the per-user detail view as ride history (driver) or booking history (passenger) (FR-008) |
| `ratings` | `014-trust-community` | Joined into the per-user detail view (ratings received, aggregate) (FR-008) |
| `reports` | `014-trust-community` | Counted (`status IN ('open','under_review')`) for dashboard KPI (FR-001); joined into the per-user detail view (reports filed by/against the user) (FR-008) |
| `driver_wallets`, `driver_ledger_entries` | `011-financial-system` | Aggregated (`SUM` by `type`) for the financial report (FR-017); every row read for the driver balance overview, `LEFT JOIN`ed against `profiles` so drivers without a wallet row still appear (FR-021); joined into the per-user detail view when the user is a driver (FR-008) |

## Computed values (request-time only, never stored)

### Verification submission age (FR-012)

```
elapsed = now() - verification_submissions.submitted_at
is_aged = elapsed > interval '24 hours'
```
Computed in `verification_router.get_queue()` per row at read time. Not a stored column — recomputed
on every request, consistent with `research.md`'s existing-pattern precedent (no new background job).

### Driver at-risk flag (FR-019, FR-021)

```
available_egp = balance_egp - reserved_egp   -- balance_egp defaults to 0.00 for a driver with no
                                               -- driver_wallets row (LEFT JOIN + COALESCE)
is_at_risk = available_egp <= 0
```
Computed in `financial_report_service.get_driver_balances()`. Identical formula to the existing
`wallet_router.get_driver_wallet()` `available_egp` computation — reused, not reinvented.

### Dashboard KPI payload (FR-001)

```
{
  "period": "today" | "7d" | "30d" | "90d",
  "users_by_role": { "passenger": int, "driver": int, "admin": int },
  "rides_created": int,
  "rides_completed": int,
  "commission_collected_egp": string,          # sum of COMMISSION_DEBIT in period
  "pending_verifications": int,
  "open_reports": int,
  "drivers_at_or_below_zero": int
}
```
All counts/sums scoped to `[period_start, now())` in the `Africa/Cairo` reference timezone
(FR-024, research.md R4). `users_by_role` is NOT period-scoped (it is a point-in-time total, matching
Acceptance Scenario 1's "total users (by role)" wording, not a "new users in period" count).

### Trend series payload (FR-002, FR-018)

```
{
  "metric": "rides_completed" | "commission_collected_egp",
  "granularity": "day" | "week",                # week only for financial report ranges > 60 days
  "points": [ { "date": "2026-08-01", "value": number }, ... ]  # zero-filled, no gaps
}
```
`dashboard_service.get_daily_trend()` always returns `granularity: "day"` (dashboard periods top out
at 90 days). `financial_report_service.get_report()` switches to `"week"` above 60 days (FR-018).

### Financial report payload (FR-017, FR-020)

```
{
  "range": { "start": "date", "end": "date" },
  "commission_collected_egp": string,   # SUM(amount_egp) WHERE type = 'COMMISSION_DEBIT'
  "admin_credits_egp": string,          # SUM(amount_egp) WHERE type = 'ADMIN_CREDIT'
  "admin_debits_egp": string,           # SUM(amount_egp) WHERE type = 'ADMIN_DEBIT'
  "net_revenue_egp": string,            # commission_collected_egp - admin_debits_egp
  "trend": { ... }                      # Trend series payload, commission_collected_egp metric
}
```
The CSV export (FR-020) is the same fields flattened to rows (one summary row + one row per trend
point), streamed via `financial_report_service.stream_report_csv()` — no separate export data shape.

## State Transitions

No new state machines. This phase re-exposes two existing transitions through a new UI surface:

- **Profile `verification_status`**: `verified` ⇄ `suspended` via the user detail page's
  suspend/reinstate actions (FR-009, FR-010) — identical transition already defined in
  `003-auth-verification`/`014-trust-community`, now guarded by `role != 'admin'` at the `suspended`
  transition only (FR-009's clarification).
- **`verification_submissions.is_locked` / `profiles.is_submission_locked`**: `true` → `false` via the
  existing `verification_router.unlock_user()` endpoint (FR-015), now discoverable from the enhanced
  history view — the endpoint and its transition are unchanged.

## Row Level Security

No RLS changes. Every new/extended endpoint in this phase is admin-only and reads via the
service-role key (`supabase-py`) or an `asyncpg` pool connection (never the anon/authenticated client
role), so no table's existing RLS policies are exercised by this phase's traffic — consistent with
NFR-005 ("no new authentication mechanism is introduced").
