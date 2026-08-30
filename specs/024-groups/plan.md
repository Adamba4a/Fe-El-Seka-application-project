# Implementation Plan: Groups

**Branch**: `024-groups` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/024-groups/spec.md`

> **Superseded 2026-08-30**: The design below (general/company/university group types, one domain per type-group, auto-created-on-first-verification) was replaced by an open-membership redesign. Groups no longer have a type or a domain; any org-email-verified user joins any group unconditionally. Domain-verified email OTP survives but was repurposed to prove per-group sponsorship eligibility on an already-existing sponsored group (many domains per group via `group_sponsor_domains`), per `specs/026-sponsored-groups/`. This document is left as a historical record of the original design and is not updated further below.

## Summary

Add a Groups domain that scopes ride discovery to focused communities — general/interest (route-based), company, and university groups — on top of the existing ride-creation, search, and booking flows. Drivers optionally scope a ride to exactly one group they belong to; passengers who are members see and book those rides through the unchanged booking flow. Company/university groups are gated by domain-verified email OTP (custom-built, not Supabase Auth's login OTP, to avoid hijacking the user's primary sign-in identity) against a configurable public-provider blocklist, with no manual admin review. Both drivers and passengers can discover groups via a searchable directory or a permanent, revocable invite link — both paths enforce identical gating rules. This is the deterministic membership/community substrate that a later AI recommendation spec (025) will build on; no AI or chat is introduced here.

## Technical Context

**Language/Version**: Python 3.11 (FastAPI backend), TypeScript / Next.js 14 (frontend)

**Primary Dependencies**: FastAPI, `supabase-py` (sync client, offloaded via `asyncio.to_thread`), `asyncpg` (raw pool, used by `notification_service`/`wallet_topup_service` for transactional queries), `resend` (transactional email, with Mailpit fallback in dev), Next.js 14 / React / Tailwind / shadcn/ui

**Storage**: Supabase PostgreSQL, extending existing schema (`groups`, `group_memberships`, `domain_verifications` new tables; `rides` gains a nullable `group_id` column); `pg_trgm` (already enabled) for route-tag/name search

**Testing**: `pytest` (backend unit/integration, `services/api/tests/`), existing frontend test conventions in `apps/main`

**Target Platform**: Linux containers (Bunny.net), existing `apps/main` (passenger + driver, role-gated route groups) and `services/api`

**Project Type**: Web application — monorepo (Next.js frontend + FastAPI backend), extending the existing single `apps/main` app rather than adding a new application

**Performance Goals**: Directory search sub-second under normal load (NFR-001), matching existing ride search; OTP email delivery within the platform's existing transactional-email latency envelope (NFR-002)

**Constraints**: No new realtime/messaging infrastructure (chat explicitly out of scope); no AI/ML components (deferred to spec 025); domain blocklist and new-domain rate-limit threshold must be runtime-configurable without redeploy (NFR-004, NFR-005)

**Scale/Scope**: One new backend domain (`groups`), 3 new tables, 1 existing-table extension (`rides.group_id`), ~12 new API endpoints, new frontend surfaces in `apps/main` only (no admin or AI service changes)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — see below.*

| Principle | Assessment |
|---|---|
| I. Driver-First Route Sharing | PASS — Groups only scopes *discovery* of existing driver-initiated rides; no passenger-request/on-demand mechanic is introduced. |
| II. Route Intelligence Over Geographic Proximity | N/A / PASS — general-group route tags are free-form text (per spec Assumptions), not a matching mechanism; no route-feasibility logic is added or bypassed. Existing OSRM/PostGIS overlap logic for actual ride matching is untouched. |
| III. Trust Before Transportation | PASS — org-email verification (Spec 025) is the hard floor for all group/ride posting/booking (FR-016); National ID verification (Spec 021) is not required anywhere on the platform as of 2026-08-30 (legal constraint), so it is no longer the mechanism satisfying this principle. |
| IV. AI-Augmented Transportation | PASS (by design) — this spec deliberately implements only the deterministic membership/community foundation; "Ride Grouping" AI enhancement is out of scope here and reserved for spec 025, consistent with Principle VI's one-domain-per-spec rule. |
| V. Mobile-First User Experience | PASS — all new UI (group directory, create/join screens, domain-verification OTP flow, group ride listing) ships in `apps/main`'s existing mobile-first shell; no new steps added to the core booking flow (FR-009, SC-006). |
| VI. Modular Domain-Driven Architecture | PASS — single bounded context ("Groups"); reuses (does not duplicate) Ride Creation, Search, Booking, and Identity/Verification domains via a scoping filter and a new OTP sub-flow, not parallel systems. |
| VII. Shared Foundations, Independent Applications | PASS — no new application; extends `apps/main` (shared passenger+driver app) and `services/api`; reuses existing Supabase Auth session, existing transactional-email infrastructure (`notification_service`), and existing `platform_settings` config pattern rather than introducing new shared infrastructure. |

No violations requiring Complexity Tracking justification.

**Post-Phase-1 re-check**: Design artifacts (`research.md`, `data-model.md`, `contracts/api.md`) confirm the above — no new tables, endpoints, or flows introduced during design require AI, a new application, a new verification mechanism, or route-feasibility logic beyond what's already justified. All PASS assessments stand unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/024-groups/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── api.md            # Phase 1 output — REST contract for the groups domain
└── tasks.md               # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
services/api/app/
├── api/
│   └── groups/                       # NEW
│       ├── __init__.py
│       └── router.py                 # directory search, create, join (link+directory),
│                                      # invite-link mgmt, domain-verification request/confirm,
│                                      # leave/remove/transfer-ownership
├── models/
│   └── group.py                      # NEW — request/response Pydantic schemas
├── services/
│   └── group_service.py              # NEW — business logic, mirrors verification_service's
│                                      # asyncio.to_thread pattern for Supabase calls
│   # existing, extended:
│   ├── ride_service.py                # optional group_id on create; group-scoped visibility rules
│   ├── candidate_service.py           # / search/router.py — exclude group-scoped rides from
│   └── ...                            #   the general feed; add group-scoped listing path
└── core/config.py                     # no new settings — reuses existing Resend/Mailpit config

supabase/migrations/
├── 20260826000001_groups_schema.sql          # groups, group_memberships, domain_verifications
├── 20260826000002_groups_rls_policies.sql    # RLS: directory read, membership read/write, ride visibility
└── 20260826000003_rides_add_group_id.sql     # ALTER TABLE rides ADD COLUMN group_id ...

apps/main/src/
├── app/
│   ├── (app)/groups/                 # NEW — directory (search), group detail, create form,
│   │   ├── page.tsx                  #   join screen (invite-link deep link target),
│   │   ├── [groupId]/page.tsx        #   domain-verification OTP screen, member management
│   │   ├── create/page.tsx
│   │   └── join/[inviteToken]/page.tsx
│   ├── (driver)/rides/...            # EXTENDED — optional group picker on ride creation
│   └── (passenger)/search/...        # EXTENDED — group-scoped listing entry point
├── components/
│   └── groups/                       # NEW — GroupCard, GroupDirectorySearch, DomainVerifyForm,
│                                      #   InviteLinkShare, GroupRideList, MemberList
└── lib/api/
    └── groups.ts                     # NEW — typed fetch wrappers for the groups API
```

**Structure Decision**: Extends the existing two-application monorepo (`apps/main` for passenger+driver, `apps/admin` untouched) and the existing single FastAPI service (`services/api`) with one new domain module each side, following the same file-organization convention already used for every other domain (e.g., `verification`, `wallet_topup`). No new application, service, or top-level package is introduced — this satisfies Principle VII's "no duplication of shared functionality."

## Complexity Tracking

*No entries — Constitution Check passed without violations.*
