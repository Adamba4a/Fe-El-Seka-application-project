# Implementation Plan: Trust & Community

**Branch**: `014-trust-community` | **Date**: 2026-07-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/014-trust-community/spec.md`

## Summary

Add mutual post-ride ratings, a safety-concern reporting flow, and an admin moderation queue on top
of the existing booking lifecycle. Two new Supabase Postgres tables (`ratings`, `reports`); one
`CHECK`-constraint extension (`admin_audit_logs.action_type` gains `warned`, plus an optional report
reference column). Backend changes concentrated in two new `services/api` service modules
(`rating_service.py`, `report_service.py`) plus a moderation router under `app/api/admin/`, all
following the existing `services/api` conventions exactly (asyncpg raw SQL for the booking-adjacent
write paths that participate in existing transactions, `supabase-py` client for admin read/action
endpoints — mirroring `verification_router.py`). Frontend changes: a post-ride rating prompt and
report flow in `apps/main` (both `(passenger)` and `(driver)` route groups), and a moderation queue
screen in `apps/admin`. `services/ai` is unchanged.

## Technical Context

**Language/Version**: Python 3.11 (FastAPI backend, `services/api`); TypeScript / Next.js 14 (`apps/main`, `apps/admin`).

**Primary Dependencies**: FastAPI, `asyncpg` (raw SQL, no ORM) for transactional writes;
`supabase-py` (service-role client) for admin queue/action endpoints, mirroring
`app/api/admin/verification_router.py` and `app/services/audit_service.py`. No new third-party
dependencies. Frontend: existing shadcn/ui component set, existing Supabase client wrappers
(`apps/main/src/lib/supabase`, `apps/admin/src/lib/supabase`).

**Storage**: Supabase PostgreSQL — 2 new tables (`ratings`, `reports`); 1 extended table
(`admin_audit_logs`: `action_type` CHECK constraint gains `warned`, plus a nullable `report_id`
reference column). No changes to `bookings`, `rides`, or `profiles` table shapes (`profiles` is only
read/updated on its existing `verification_status` column, per `003-auth-verification`).

**Testing**: pytest + `asyncpg` test-DB fixtures (existing `services/api` convention) for the backend;
no new test tooling. Frontend testing follows the existing `apps/main` / `apps/admin` convention (no
new test framework introduced).

**Target Platform**: Linux server (FastAPI via uvicorn, `services/api`) + Next.js 14 apps (`apps/main`,
`apps/admin`), consistent with the existing deployment (Bunny containers, per project memory).

**Project Type**: Monorepo — backend change in `services/api` plus frontend changes in two of the
three existing Next.js apps (Principle VII: Shared Foundations, Independent Applications). No new
apps or services are introduced.

**Performance Goals**: NFR-001 — rating/report submission endpoints respond within 300ms p95.
NFR-002 — aggregate rating recalculation reflected within 5 seconds of submission (synchronous
recalculation on write, not a background job, given the low write volume at MVP scale).

**Constraints**:
- Rating and report submission MUST be transactional and synchronous (not fire-and-forget) —
  unlike `013-match-learning-foundation`'s search-path event logging, these are user-facing writes
  the caller needs a definitive success/failure response for.
- Double-blind reveal (FR-008) and the 14-day submission deadline (FR-011) are both computed from
  `bookings`/`rides` timestamps at read/write time, not maintained as a separately-scheduled job —
  no new cron/background loop is needed for the reveal mechanic itself.
- Auto-flagging thresholds (FR-019) MUST be adjustable without a code deployment — reuses the
  singleton-config-table + cached-refresh-loop pattern already established by
  `pricing_config`/`ranking_config` (`pricing_service.py`, `ranking_config_service.py`), not a new
  configuration mechanism.
- `admin_audit_logs.action_type` is a `TEXT CHECK (...)` constraint (not a Postgres `ENUM` type, per
  `20260614000004_create_admin_audit_logs.sql`) — adding `warned` is an `ALTER TABLE ... DROP
  CONSTRAINT` / `ADD CONSTRAINT` migration, not an `ALTER TYPE ... ADD VALUE`.
- Row Level Security (NFR-005) on both new tables, following the `bookings`/`booking_audit_log`
  policy pattern (`20260624000001_phase6_bookings.sql`): party-scoped `SELECT`, no direct client
  `UPDATE`/`DELETE` on ratings or report resolution — those go through the backend using the
  service-role key.

**Scale/Scope**: ~100 rides/day at launch (per prior-phase specs' Assumptions), scaling over time; 2
new tables; 1 extended table; 2 new service modules; 1 new admin router; frontend additions to 2
existing apps (no new apps).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Principle | Assessment |
|------|-----------|------------|
| ✅ | I — Driver-First Route Sharing | No change to the driver-creates/passenger-joins model. Ratings/reports/moderation are post-hoc trust mechanics layered on completed bookings, not a change to how rides are created or joined. |
| ✅ | II — Route Intelligence Over Geographic Proximity | Not touched — this feature has no matching/ranking logic of its own; it only *feeds* a future signal into `013-match-learning-foundation` via the existing `rated` transition (already defined, Out-of-Scope: consuming that signal in ranking). |
| ✅ | III — Trust Before Transportation | Core domain. Directly implements the constitution's mandate for accountability and traceability: ratings, reports, and admin moderation (warn/suspend/reinstate) are the trust-and-safety mechanisms the constitution requires, built on the identity-verification foundation from `003-auth-verification`. |
| ✅ | IV — AI-Augmented Transportation | No AI logic introduced by this feature itself (auto-flagging, FR-019, is an explicit deterministic threshold check, not a model — see spec Out-of-Scope). It unblocks a prerequisite (the `rated` outcome signal) for future AI ranking work, without itself modifying `services/ai` or any ranking model. |
| ✅ | V — Mobile-First UX | Rating prompt and report flow are lightweight, single-screen mobile interactions (SC-003: report submission under 60 seconds); moderation queue is desk-oriented admin tooling, consistent with `apps/admin`'s existing non-mobile-first scope. |
| ✅ | VI — Modular Domain-Driven Architecture | Single new bounded context ("Trust & Safety" / moderation), cleanly separated into 2 new service modules and 1 new router; touches `admin_audit_logs` (existing Verification domain table) only via an additive `CHECK` constraint value and an optional reference column — an explicit, documented cross-domain dependency (spec Dependencies section), not a redesign. |
| ✅ | VII — Shared Foundations, Independent Applications | Business logic lives entirely in the shared `services/api` backend; `apps/main` and `apps/admin` each get presentation-layer additions only (rating/report UI, moderation queue UI respectively) — no duplicated business logic across apps. |

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/014-trust-community/
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
# ── Database Migration ────────────────────────────────────────────────────────
supabase/migrations/
└── <timestamp>_phase10_trust_community.sql
                             # NEW — ratings table, reports table (+ report_status,
                             #       report_category, report_resolution_action enums),
                             #       admin_audit_logs.action_type CHECK constraint extended
                             #       with 'warned', admin_audit_logs.report_id column added,
                             #       moderation_config singleton table (+ seed row, mirrors
                             #       ranking_config's updated_at trigger pattern), RLS on
                             #       ratings/reports (party-scoped SELECT only; no client
                             #       UPDATE/DELETE — writes go through the service-role key
                             #       from services/api)

# ── Backend — New Services ────────────────────────────────────────────────────
services/api/app/services/
├── rating_service.py         # NEW — submit_rating(conn, booking_id, rater_id, stars, comment)
                             #       -> validates FR-003/004/005/011, recalculates ratee aggregate
                             #       (FR-006), calls match_logging_service.record_outcome(conn, ...,
                             #       'rated', ...) when a linked match_outcomes row exists (FR-009);
                             #       get_own_rating_summary(user_id) -> aggregate + anonymized
                             #       comments (FR-007); reveal_state(rating_row) -> bool helper for
                             #       FR-008's double-blind computation
├── report_service.py         # NEW — submit_report(conn, ride_id, booking_id, reporter_id,
                             #       reported_user_id, category, description) -> validates
                             #       FR-013/014/015; get_own_reports(user_id) -> status-only history
                             #       (FR-016)
└── moderation_service.py     # NEW — mirrors pricing_service.py / ranking_config_service.py's
                             #       config pattern: init_moderation_config(),
                             #       moderation_config_refresh_loop(), get_flagging_thresholds();
                             #       list_flagged_users() -> users crossing FR-019 thresholds;
                             #       resolve_report(conn, report_id, admin_id, action, reason) ->
                             #       warn/suspend/dismiss (FR-021), reusing audit_service.append_log
                             #       with the new 'warned' action_type and a report_id reference;
                             #       reinstate_user(conn, user_id, admin_id, reason) -> FR-022

# ── Backend — Extended Services ───────────────────────────────────────────────
services/api/app/services/
└── audit_service.py          # EXTEND — append_log() gains an optional report_id parameter,
                             #   passed through to the new admin_audit_logs.report_id column

# ── Backend — New API Routes ──────────────────────────────────────────────────
services/api/app/api/
├── ratings/
│   └── router.py             # NEW — POST /ratings (submit), GET /profiles/{id}/rating (own
                             #   summary, reuses existing profile-auth dependency)
├── reports/
│   └── router.py             # NEW — POST /reports (submit), GET /reports/mine (own history)
└── admin/
    └── moderation_router.py  # NEW — mirrors verification_router.py's shape: GET /queue,
                             #   GET /queue/flagged, POST /reports/{id}/review,
                             #   POST /reports/{id}/resolve, POST /users/{id}/reinstate

services/api/app/main.py      # EXTEND — register ratings/reports/moderation routers; lifespan:
                             #   await moderation_service.init_moderation_config();
                             #   asyncio.create_task(moderation_service.moderation_config_refresh_loop())
                             #   alongside the existing pricing_config/ranking_config startup calls

services/api/app/services/booking_service.py
                             # EXTEND — complete_ride_bookings(): after existing 'completed'
                             #   outcome/audit recording, enqueue a notification_events row
                             #   prompting both parties to rate (reuses existing
                             #   notification_dispatcher.py delivery path, no new dispatcher).

# ── Frontend — apps/main (passenger + driver route groups) ───────────────────
apps/main/src/app/(passenger)/
└── ratings/                  # NEW — post-ride rating prompt, own-rating view, report flow entry
apps/main/src/app/(driver)/
└── ratings/                  # NEW — same prompt/report flow, driver-facing copy

# ── Frontend — apps/admin ─────────────────────────────────────────────────────
apps/admin/src/app/(dashboard)/
└── moderation/                # NEW — moderation queue screen (open reports + flagged users),
                             #   report detail + resolve action, reinstate action

# ── No changes ─────────────────────────────────────────────────────────────────
services/ai/                 # UNCHANGED — this feature produces the 'rated' outcome signal via
                             # 013-match-learning-foundation's existing plumbing; consuming it in
                             # ranking is explicitly Out-of-Scope for this phase.
```

**Structure Decision**: Backend-and-frontend feature within the existing monorepo — no new apps or
services. Two new service modules (`rating_service.py`, `report_service.py`) plus one new
config-pattern service (`moderation_service.py`) follow the existing `services/api/app/services/`
conventions exactly: transactional write paths use `asyncpg` raw SQL inside existing/new
`conn.transaction()` blocks (mirroring `booking_service.py`), while the admin moderation router uses
the `supabase-py` service-role client (mirroring `verification_router.py`/`audit_service.py`) since it
is read-heavy, paginated, and not part of a booking transaction. Frontend additions land in the two
apps that already have the relevant route groups — `apps/main`'s `(passenger)`/`(driver)` groups for
rating/reporting, `apps/admin`'s `(dashboard)` group for moderation — with no new Next.js app created.

## Complexity Tracking

*No Constitution Check violations — this section is not required.*
