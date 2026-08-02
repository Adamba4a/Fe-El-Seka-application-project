# Quickstart: Admin Operations (Full)

Validation guide for the dashboard / user management / verification tooling / financial reporting
feature, once implemented per `tasks.md`. Assumes the local dev stack (`services/api`, Supabase local,
`apps/admin`) is already running per repo-root setup docs. No migration is required — this phase
introduces no schema changes.

## Prerequisites

- One admin account (`profiles.role = 'admin'`).
- At least 25 test `profiles` across `passenger`/`driver`/`admin` roles with varying
  `verification_status` values (reuse `009-passenger-experience`/`003-auth-verification` fixtures).
- A mix of `rides`/`bookings` (some `completed`) and `driver_ledger_entries`
  (`COMMISSION_DEBIT`/`ADMIN_CREDIT`/`ADMIN_DEBIT`) spanning at least a 7-day window, per
  `011-financial-system`'s existing test fixtures.
- At least one `verification_submissions` row older than 24 hours and one under 24 hours (adjust
  `submitted_at` directly in the seed data — no need for real elapsed time).
- At least one `reports` row in `open` status, per `014-trust-community`'s fixtures.
- At least one driver with no `driver_wallets` row at all (never topped up).

## Scenario 1 — Dashboard KPIs and trends (US1, FR-001–FR-004)

1. As the admin, `GET /api/admin/dashboard/overview?period=7d` → confirm `users_by_role`,
   `rides_created`, `rides_completed`, `commission_collected_egp`, `pending_verifications`,
   `open_reports`, and `drivers_at_or_below_zero` each match a direct DB count/sum for the same
   window.
2. Confirm `trends.rides_completed.points` and `trends.commission_collected_egp.points` each have one
   entry per day in the 7-day window, including any day with `value: 0`.
3. Repeat with `period=30d` and `period=90d` → confirm all values recompute (do not equal the 7-day
   response).
4. As a non-admin authenticated user, attempt the same endpoint → expect `403 forbidden`.
5. Point the admin UI's dashboard KPI tiles at a fresh/empty environment → confirm every tile reads
   `0` and the charts render an empty (not erroring) period.

## Scenario 2 — User search, filter, detail, suspend/reinstate (US2, FR-005–FR-011)

1. As the admin, `GET /api/admin/users?q=<partial phone/email fragment unique to one seeded user>` →
   confirm exactly that user appears.
2. `GET /api/admin/users?role=driver&status=verified` → confirm only verified drivers appear.
3. `GET /api/admin/users?page=2&limit=10` on a 25-user seed set → confirm pagination metadata and a
   distinct second page of results.
4. As the admin, `GET /api/admin/users/{driver_id}` for a driver with ride history, ratings, a report,
   and a wallet → confirm all five sections (`profile`, `rides`, `ratings_received`, `reports`,
   `wallet`) are populated without a second request.
5. Repeat step 4 for a brand-new user with none of the above → confirm each section is present but
   empty (not omitted, not erroring).
6. `POST /api/admin/users/{passenger_id}/suspend` with `{ "reason": "test" }` → expect `200`,
   `verification_status: "suspended"`; confirm an `admin_audit_logs` row exists with
   `action_type = 'suspended'`.
7. `POST /api/admin/users/{passenger_id}/reinstate` with `{ "reason": "test" }` → expect `200`,
   `verification_status: "verified"`.
8. `POST /api/admin/users/{admin_account_id}/suspend` (target `role = 'admin'`, including the acting
   admin's own id) → expect `403 forbidden`; confirm `verification_status` is unchanged and the admin
   UI does not render a suspend control on that account's detail page.
9. As a non-admin authenticated user, attempt `GET /api/admin/users` or `GET /api/admin/users/{id}` →
   expect `403 forbidden`.

## Scenario 3 — Enhanced verification queue and history (US3, FR-012–FR-016)

1. As the admin, `GET /api/admin/verification/queue` → confirm the submission seeded >24h ago has
   `is_aged: true` and the recent one has `is_aged: false`.
2. `GET /api/admin/verification/queue?q=<partial applicant name>` → confirm only matching submissions
   appear, oldest-first ordering preserved.
3. `GET /api/admin/verification/history?q=<partial applicant name>&outcome=approved` → confirm only
   matching, approved submissions appear.
4. For a user with 3 exhausted submission attempts, `POST /api/admin/verification/users/{user_id}/unlock`
   → confirm `is_submission_locked: false` and the user can submit exactly one more attempt.
5. `POST /api/admin/verification/{submission_id}/approve` from the enhanced queue view → confirm
   identical outcome (status update, audit log, notification) to the pre-existing approve flow.
6. As a non-admin, attempt any `/api/admin/verification/*` endpoint → expect `403 forbidden`.

## Scenario 4 — Financial report, export, driver balances (US4, FR-017–FR-021)

1. As the admin, `GET /api/admin/financial/report?start=<7-day-window-start>&end=<7-day-window-end>`
   → confirm `commission_collected_egp` equals the sum of seeded `COMMISSION_DEBIT` entries,
   `admin_credits_egp` equals the sum of `ADMIN_CREDIT` entries, and `net_revenue_egp` reflects
   commission minus corrective debits.
2. Confirm `trend.granularity` is `"day"` for the 7-day window; repeat with a >60-day range and
   confirm it switches to `"week"`.
3. `GET /api/admin/financial/drivers/balances` → confirm every driver appears sorted by
   `available_egp` ascending, the never-topped-up driver appears with `"0.00"` values and
   `is_at_risk: true`, and every driver at/below zero available balance has `is_at_risk: true`.
4. `GET /api/admin/financial/report/export?start=...&end=...` → confirm the streamed CSV's totals
   match the `GET /report` response for the identical range byte-for-byte, and confirm no file
   appears in Supabase Storage or on the server's filesystem after the request completes.
5. Repeat step 1 for a date range with zero ledger activity → confirm all totals are `"0.00"` and the
   trend renders a zero-filled, non-erroring series.
6. As a non-admin, attempt any `/api/admin/financial/*` endpoint → expect `403 forbidden`.

## Expected outcome

All steps above pass without manual database intervention between steps — every value shown is
derived live from existing tables (no new schema), and the two re-exposed actions (suspend/reinstate,
verification unlock) produce identical audit-log and state effects to their pre-existing entry points,
matching the acceptance scenarios in `spec.md`.
