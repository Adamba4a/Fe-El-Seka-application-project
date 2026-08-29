# Implementation Plan: Organization-Only Access Gate

**Branch**: `025-org-only-access` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/025-org-only-access/spec.md`

## Summary

Require every account — new and existing, passenger and driver — to verify ownership of a company or university email before reaching any other part of `apps/main`. Reuses the OTP mechanics (hash, expiry, resend rate-limit, personal-domain blocklist) already built for Groups (Spec 024) via a newly extracted shared module, but adds dedicated endpoints and a `profiles.org_verified_at` column so the gate (a) doesn't require prior National ID verification, (b) doesn't trigger Groups' group-creation side effect, and (c) auto-credits accounts that already verified a domain through Groups.

## Technical Context

**Language/Version**: TypeScript 5 (Next.js 14, App Router) for `apps/main`; Python 3.11 (FastAPI) for `services/api`

**Primary Dependencies**: Next.js 14, React, Supabase JS client, Supabase Auth (GoTrue), react-hook-form + zod, `next-intl` (existing Arabic/RTL localization, Spec 017); FastAPI, Pydantic, `supabase-py`, `asyncpg`

**Storage**: Supabase PostgreSQL — new nullable `profiles.org_verified_at` / `profiles.org_verified_domain` columns; reuses the existing `domain_verifications` table (schema relaxed, data-model.md) and the existing `platform_settings` row `group_domain_blocklist`. No new tables.

**Testing**: pytest (`services/api/.venv`, unit tests under `services/api/tests/unit`); manual E2E via local Supabase stack + Mailpit for email-OTP capture (`http://localhost:54324/api/v1/messages`), per quickstart.md

**Target Platform**: Web (Next.js), server-side FastAPI service — no mobile-native target

**Project Type**: Monorepo web application (Option 4 — shared foundations, independent apps per Constitution Principle VII)

**Performance Goals**: No new performance goals beyond NFR-001 (no noticeable added delay for already-verified users) — satisfied by reading `org_verified_at` off the same `profiles` row already fetched on every page load (research.md R2), not a new query/join.

**Constraints**: The gate must be reachable by accounts with `verification_status != 'verified'` (Spec 021 leaves most accounts unverified indefinitely) — cannot reuse Groups' `_require_verified`-gated confirm endpoint as-is (research.md R1). Must not weaken or bypass Supabase Auth / `get_current_user`'s existing suspension check (FR-012).

**Scale/Scope**: Touches `apps/main` (frontend), `services/api` (backend, including a refactor of `group_service.py`'s private OTP helpers into a shared module), shared types in `packages/shared`, and one new migration. `apps/admin` gains only read visibility (org-verified status/domain), no new admin workflow.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle III (Trust Before Transportation)** — Establishes company/university email ownership as an interim trust floor while phone-OTP and mandatory ID verification are not yet in place; does not weaken or replace the existing ID-verification flow (Spec 021), which remains independently enforced at gated actions (FR-013). **PASS**.
- **Principle VI (Modular Domain-Driven Architecture)** — Single bounded context (app access / authentication gate); explicitly does not implement the three downstream specs (Sponsored Groups, Recurring Rides, Loyalty Points) that build on top of it (Out-of-Scope). **PASS**.
- **Principle VII (Shared Foundations, Independent Applications)** — The OTP mechanics are extracted into one shared module reused by both Groups and this feature rather than duplicated (research.md R1); the domain rejection list stays a single shared `platform_settings` row rather than forking into a second list (research.md R5). **PASS**.
- **Security & Privacy — Auditability** — `domain_verifications` already provides an append-only record of verification attempts; no new audit gap introduced (research.md R6). **PASS**.
- **Security & Privacy — Data Protection** — OTP codes remain hashed-only, org email/domain get the same TLS/DB-access protections as other profile PII (NFR-002, NFR-004); no new secrets, no new external service. **PASS**.
- **Data Standards (soft deletion / preserved history)** — No deletion involved; `domain_verifications` rows are append-only and untouched by this feature beyond the one schema relaxation (data-model.md). **PASS**.

No violations requiring justification — Complexity Tracking table is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/025-org-only-access/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── org-access-api.md
└── tasks.md             # Phase 2 output (/speckit-tasks — not created by /speckit-plan)
```

### Source Code (repository root)

```text
apps/
├── main/                                   # Next.js 14 — shared passenger + driver experience
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx                              # extend gate: add org_verified_at redirect (mirrors verification_status check)
│   │   │   ├── (app)/layout.tsx                      # extend gate: same check for direct-nav protection
│   │   │   ├── (auth)/
│   │   │   │   └── verify-org-email/page.tsx         # NEW — non-skippable gate screen, modeled on DomainVerifyForm
│   │   │   └── auth/callback/route.ts                # add org-access gate check alongside existing checks
│   │   ├── components/
│   │   │   └── org-access/
│   │   │       └── OrgAccessVerifyForm.tsx           # NEW — adapted from components/groups/DomainVerifyForm.tsx, no requestedGroupType prop
│   │   ├── lib/api/org-access.ts                     # NEW — requestOrgAccessVerification / confirmOrgAccessVerification
│   │   └── messages/{en,ar}.json                     # add verify-org-email screen copy (both locales, per Spec 017)
│   └── admin/                                        # read-only: display org_verified_at/org_verified_domain on user detail
│
packages/
└── shared/src/types/
    ├── user.ts                                       # add org_verified_at, org_verified_domain to Profile
    └── org-access.ts                                 # NEW — request/confirm request+response types

services/
└── api/
    ├── app/
    │   ├── models/org_access.py                      # NEW — OrgAccessRequest/Confirm(+Response) Pydantic models
    │   ├── api/org_access/router.py                  # NEW — POST /org-access/request, /org-access/confirm
    │   ├── api/profiles/router.py                    # extend GET /me response with the two new fields
    │   ├── services/
    │   │   ├── domain_verification_service.py        # NEW — extracted shared OTP primitives (research.md R1)
    │   │   ├── group_service.py                      # refactor: import shared primitives instead of private copies; confirm sets profiles.org_verified_at (R3)
    │   │   ├── org_access_service.py                 # NEW — request_verification / confirm_verification (no group side effect)
    │   │   └── profile_service.py                    # surface org_verified_at/org_verified_domain in _format_profile
    │   └── dependencies/
    │       └── org_access.py                         # NEW — require_org_verified() dependency for gated ride endpoints
    └── tests/unit/
        ├── test_domain_verification_service.py       # NEW
        ├── test_org_access_service.py                # NEW
        └── test_group_service.py                     # extend for the org_verified_at side-effect + refactor

supabase/
└── migrations/<timestamp>_org_only_access.sql        # NEW — see data-model.md Migration summary
```

**Structure Decision**: Monorepo Option 4 (Constitution Principle VII) — scoped to the shared `apps/main` frontend (serving both passenger and driver roles) and the shared `services/api` backend, plus one extracted shared service module. `apps/admin` gets read-only field exposure only, consistent with [[project_admin_app_not_deployed]] (admin is local-only; no deploy implication).

## Complexity Tracking

*No constitution violations — this section is not applicable.*
