# Implementation Plan: Admin Operations (Full)

**Branch**: `015-admin-operations` | **Date**: 2026-08-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/015-admin-operations/spec.md`

## Summary

Turn four already-existing but disconnected admin capabilities (verification queue, per-driver
wallet, safety moderation, flat user list) into a coherent operations console: a KPI + trend
dashboard, searchable/filterable user management with a unified per-user activity view, aging and
search on the verification queue/history, and a financial reporting + driver-balance-overview layer.
No new tables. Backend work is concentrated in **extending** four existing `app/api/admin/` routers
(`users_router.py`, `verification_router.py`, `wallet_router.py` gains a sibling, `moderation_router.py`
untouched) plus **two new** service modules for read-only aggregation (`dashboard_service.py`,
`financial_report_service.py`), following the existing project's two established backend read
patterns: `asyncpg` raw SQL for aggregation/GROUP BY-heavy queries (mirrors `wallet_service.py`), and
`supabase-py` service-role client for simple filtered-list/detail/state-transition endpoints (mirrors
`verification_router.py`/`users_router.py`). Frontend work is entirely in `apps/admin` — a rebuilt
dashboard home screen, a rebuilt user list + new detail page, search/age additions to the existing
verification screens, and a new financial-reporting screen. `apps/main` and `services/ai` are
unchanged.

## Technical Context

**Language/Version**: Python 3.11 (FastAPI backend, `services/api`); TypeScript / Next.js 14
(`apps/admin` only — this phase does not touch `apps/main`).

**Primary Dependencies**: FastAPI; `asyncpg` (raw SQL, no ORM) for the new aggregation-heavy read
paths (dashboard KPIs/trends, financial report, driver balance overview) — mirrors
`app/services/wallet_service.py`'s existing ledger-sum queries, since `supabase-py`'s query builder
does not comfortably express `GROUP BY`/date-bucketed aggregates; `supabase-py` (service-role client)
for filtered-list/detail/state-transition endpoints (user search/filter/detail, verification
search/age/unlock) — mirrors `app/api/admin/verification_router.py` and `app/api/admin/users_router.py`,
which already use this pattern. No new third-party backend dependencies. Frontend: existing shadcn/ui
component set; **`recharts` is a new frontend dependency** for the dashboard/financial trend charts
(no charting library exists in `apps/admin` today — confirmed via `package.json`; `recharts` is the
de facto pairing for shadcn/ui's chart primitives and needs no backend counterpart beyond returning
plain day-bucketed arrays).

**Storage**: Supabase PostgreSQL — **no new tables or columns**. Every capability reads
`profiles`, `verification_submissions`, `admin_audit_logs`, `bookings`, `rides`, `ratings`, `reports`,
`driver_wallets`, and `driver_ledger_entries`, all already established by prior phases.

**Testing**: pytest + `asyncpg` test-DB fixtures (existing `services/api` convention) for the new
aggregation service modules and the extended router endpoints; no new test tooling. Frontend follows
the existing `apps/admin` convention (no new test framework introduced).

**Target Platform**: Linux server (FastAPI via uvicorn, `services/api`) + the existing `apps/admin`
Next.js 14 app, consistent with the current deployment (Bunny containers, per project memory).

**Project Type**: Monorepo — backend extensions in `services/api`, frontend changes confined to the
single existing `apps/admin` app (Principle VII: Shared Foundations, Independent Applications). No new
apps or services are introduced.

**Performance Goals**: NFR-001 — dashboard/user-search/verification-search/financial-report endpoints
respond within 500ms p95 for standard periods/ranges (up to 90 days) under single-digit concurrent
admin load. NFR-002 — user list search/filter returns within 300ms p95 up to 50,000 profiles.

**Constraints**:
- All new endpoints are **strictly read-only aggregation** over existing tables (NFR-003) — this
  phase must not introduce new write paths beyond the suspend/reinstate/unlock actions it re-exposes
  through a second entry point (the user detail page), per FR-009–FR-011.
- **`profiles` has no `phone_number` column** — migration `20260616000001_rename_phone_to_email.sql`
  renamed it to `email` and no separate phone column was reintroduced anywhere in `services/api`
  (confirmed by a repo-wide search). The spec's "search by display name, phone number, or email"
  (FR-005, FR-013) is treated as search over `display_name` and `email` only — "phone number" is a
  stale reference to the pre-rename schema, not a distinct field to add. This is recorded as a
  resolved decision in `research.md`, not a new [NEEDS CLARIFICATION].
- FR-009's admin-role suspension block (`role = 'admin'` accounts cannot be suspended via this
  mechanism) is enforced **inside `users_router.suspend_user`** — the endpoint being extended, not a
  new one — by checking `profiles.role` before the existing `verification_status` checks.
- `admin_audit_logs.action_type` is a `TEXT CHECK (...)` constraint, already extended once (migration
  `20260729000001_phase10_trust_community.sql` added `'warned'`). This phase introduces **no new
  action types** (FR-023 confirms it reuses `approved`/`rejected`/`suspended`/`reinstated`/`unlocked`
  exactly as they exist today) — no further migration to this constraint is needed.
- Financial report export (FR-020, NFR-007) MUST stream a CSV response directly (e.g.
  `StreamingResponse` over a generator) rather than materializing the full ledger in memory or
  writing an intermediate file — no signed-URL/private-storage mechanism, consistent with the
  Clarifications session's "ordinary download" resolution.
- Day-boundary computation for "today"/period presets and the financial date range (FR-024) MUST use
  a single fixed reference timezone (`Africa/Cairo`) applied server-side in the new service modules —
  not computed client-side from the admin's browser timezone.
- Two suspend/reinstate code paths already coexist in the repo: `users_router.py`'s
  general-purpose suspend/reinstate (supabase-py) and `moderation_service.reinstate_user`/
  `resolve_report(..., action="suspend")` (asyncpg, report-driven). FR-011 requires this phase's user
  detail page to reuse the **general-purpose path** (`users_router.py`) — the moderation-queue path
  remains the report-driven entry point and is not touched, consistent with Dependencies (this phase
  adds a *second* entry point, not a merge of the two).

**Scale/Scope**: Up to 50,000 profiles at target scale (NFR-002); 0 new tables; 2 new service
modules; 2 new/extended admin routers; extensions to 2 existing admin routers; frontend changes
confined to `apps/admin` (1 rebuilt screen, 1 rebuilt + 1 new screen, additions to 2 existing screens,
1 new screen).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Principle | Assessment |
|------|-----------|------------|
| ✅ | I — Driver-First Route Sharing | Not touched — this phase adds no ride-creation or matching logic; it only reports on rides/bookings that already exist. |
| ✅ | II — Route Intelligence Over Geographic Proximity | Not touched — no ranking/matching logic is introduced or consumed. |
| ✅ | III — Trust Before Transportation | Directly extends this domain: the user detail page's suspend/reinstate is a second entry point to the exact trust/safety mechanism `003-auth-verification` and `014-trust-community` already established, and the enhanced verification queue is discoverability/visibility on top of the existing approve/reject workflow — no new trust mechanic is invented. |
| ✅ | IV — AI-Augmented Transportation | No AI logic introduced; explicitly Out-of-Scope (fraud/anomaly detection is deferred to `Phase 13`). `services/ai` is unchanged. |
| ✅ | V — Mobile-First UX | Admin panel is desk-oriented tooling for internal staff, consistent with `apps/admin`'s existing non-mobile-first scope (Assumptions: "Admin panel remains desktop-only"). |
| ✅ | VI — Modular Domain-Driven Architecture | New logic lands in 2 new, narrowly-scoped service modules (`dashboard_service.py`, `financial_report_service.py`); existing routers are extended along their existing seams (search/filter/detail added to `users_router.py`/`verification_router.py`, not rewritten). No cross-domain table coupling beyond read-only joins already implied by the spec's Key Entities. |
| ✅ | VII — Shared Foundations, Independent Applications | All business logic (aggregation, search, the admin-role suspension guard) lives in `services/api`; `apps/admin` gets presentation-layer-only additions. No duplicated business logic, no new app created. |

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/015-admin-operations/
├── plan.md                  # This file
├── research.md               # Phase 0 output
├── data-model.md             # Phase 1 output
├── quickstart.md             # Phase 1 output
├── contracts/
│   └── api.md                # Phase 1 output — REST endpoint contracts
├── checklists/
│   └── requirements.md       # Spec quality checklist
└── tasks.md                  # Phase 2 output (created by /speckit-tasks)
```

### Source Code (repository root)

```text
# ── Backend — New Services ────────────────────────────────────────────────────
services/api/app/services/
├── dashboard_service.py        # NEW — get_kpis(conn, period) -> users-by-role, rides
                               #   created/completed, commission collected, pending
                               #   verifications, open reports, zero-balance drivers
                               #   (FR-001); get_daily_trend(conn, period, metric) ->
                               #   rides-completed / commission-collected per-day series
                               #   with zero-filled gaps (FR-002); all queries computed
                               #   against Africa/Cairo day boundaries (FR-024)
└── financial_report_service.py # NEW — get_report(conn, start, end) -> commission
                               #   collected / admin credits / admin debits / net
                               #   revenue for the range (FR-017), per-day series for
                               #   <=60 days else per-week (FR-018); get_driver_balances
                               #   (conn) -> all driver_wallets rows incl. drivers with
                               #   no wallet record (0.00 EGP), sorted balance ascending,
                               #   at-risk flag for available <= 0 (FR-019, FR-021);
                               #   stream_report_csv(conn, start, end) -> async generator
                               #   for StreamingResponse (FR-020, NFR-007, NFR-004)

# ── Backend — Extended Services ───────────────────────────────────────────────
services/api/app/services/
└── (no changes — audit_service.append_log() already supports every action_type this
     phase reuses; no new parameters needed)

# ── Backend — New/Extended API Routes ─────────────────────────────────────────
services/api/app/api/admin/
├── dashboard_router.py         # NEW — GET /overview?period= (FR-001–004),
                               #   admin-only via existing get_current_admin dependency
├── financial_router.py         # NEW — GET /report?start=&end= (FR-017–018),
                               #   GET /report/export?start=&end= -> StreamingResponse
                               #   CSV (FR-020), GET /drivers/balances (FR-019, FR-021)
├── users_router.py             # EXTEND — add GET / (search: q against display_name/
                               #   email ILIKE, filter: role/verification_status,
                               #   paginated) and GET /{user_id} (unified detail: profile
                               #   + ride/booking history + ratings + reports + wallet,
                               #   composed from existing per-domain queries per the
                               #   spec's Technical Considerations — no new "activity"
                               #   table) (FR-005–008); suspend_user() gets a role='admin'
                               #   guard inserted before its existing status checks,
                               #   returning 403 rather than proceeding (FR-009)
└── verification_router.py      # EXTEND — get_queue()/get_history() gain a `q` search
                               #   param (name/email ILIKE) and `age`/pending-duration
                               #   is computed and returned per row (submitted_at ->
                               #   elapsed, flagged if >24h) (FR-012, FR-013); get_history()
                               #   gains an `outcome` filter param (FR-014); the existing
                               #   POST /users/{user_id}/unlock is unchanged (FR-015
                               #   reuses it as-is, only exposed from a new UI surface)

services/api/app/main.py        # EXTEND — register dashboard_router and financial_router
                               #   under prefix="/api/admin/dashboard" and
                               #   prefix="/api/admin/financial" respectively, alongside
                               #   the existing admin router registrations

# ── Frontend — apps/admin ─────────────────────────────────────────────────────
apps/admin/src/app/(dashboard)/
├── page.tsx                    # REBUILD — replace the current 4-tile static dashboard
                               #   with period selector + KPI tiles + recharts trend
                               #   charts + KPI-tile deep links (FR-001–004)
├── users/
│   ├── page.tsx                 # REBUILD — add search box, role/status filter controls,
                               #   pagination, replacing the current flat unfiltered
                               #   table (FR-005–007)
│   └── [user_id]/
│       └── page.tsx             # NEW — unified per-user detail view (profile, ride/
                               #   booking history, ratings, reports, wallet-if-driver,
                               #   suspend/reinstate action with admin-role guard
                               #   reflected in the UI) (FR-008–011)
├── verification/
│   ├── page.tsx                  # EXTEND — add search box + pending-age display/24h
                               #   flag (FR-012, FR-013)
│   └── history/
│       └── page.tsx              # EXTEND — add search box + outcome filter (FR-013, FR-014)
└── financial/
    └── page.tsx                  # NEW — date-range picker, commission/credit/debit/net
                               #   totals, trend chart, driver balance table (sorted
                               #   ascending, at-risk flag), CSV export button
                               #   (FR-017–021)

apps/admin/src/lib/api/
├── admin-dashboard.ts           # NEW — fetch wrapper for GET /api/admin/dashboard/overview
├── admin-financial.ts           # NEW — fetch wrappers for GET /api/admin/financial/report,
                               #   /report/export, /drivers/balances
└── admin-users.ts               # EXTEND — add list(token, {q, role, status, page}) and
                               #   getDetail(token, userId), alongside the existing
                               #   suspend()/reinstate() functions

# ── No changes ─────────────────────────────────────────────────────────────────
apps/main/                     # UNCHANGED — this phase is admin-panel-only
services/ai/                   # UNCHANGED — no AI logic introduced
apps/admin/src/app/(dashboard)/moderation/, drivers/, vehicles/
                               # UNCHANGED — Phase 10's moderation queue, the per-driver
                               #   wallet screen, and vehicle-update review are untouched;
                               #   the user detail page (new) links out to the existing
                               #   drivers/[id]/wallet screen rather than duplicating it
```

**Structure Decision**: Backend-and-frontend feature within the existing monorepo — no new apps or
services. Two new service modules (`dashboard_service.py`, `financial_report_service.py`) use
`asyncpg` raw SQL for aggregation, mirroring `wallet_service.py`'s existing ledger-sum pattern; two new
thin routers (`dashboard_router.py`, `financial_router.py`) expose them. The two existing admin routers
that already handle filtered/paginated reads (`users_router.py`, `verification_router.py`) are extended
in place with search/filter/detail additions using their existing `supabase-py` pattern, rather than
introduced as parallel routers — keeping one canonical place per resource. All frontend work lands in
`apps/admin`'s existing `(dashboard)` route group; no new Next.js app or route group is created.

## Complexity Tracking

*No Constitution Check violations — this section is not required.*
