# Implementation Plan: Deferred Identity Verification (Progressive KYC)

**Branch**: `021-defer-identity-verification` | **Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/021-defer-identity-verification/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Signup collects only email, phone number, display name, and date of birth — ID number and profile photo are dropped as required fields, and document upload (front/back ID, license) moves entirely out of signup. New accounts land in the app immediately at `verification_status = "unverified"` and can browse freely (passenger: search/view rides; driver: view the app). A persistent "Verify identity" affordance, driven by `profile.verification_status` already fetched in `AppShell`, is always visible for unverified users. The three existing blanket verified-only gates (`middleware.ts`, `app/page.tsx`, `(passenger)/layout.tsx`) are removed/narrowed so they stop blocking browsing; the backend guards that already exist (`get_current_verified_passenger`, `get_current_verified_driver`) become the sole enforcement point, applied at exactly three transaction-time boundaries: passenger booking creation, driver ride creation, driver booking confirm/reject. The existing `verify-id` / `driver/verify-documents` pages and the existing document-review + notification pipeline are reused unchanged as the verification destination, now reachable proactively (from the persistent affordance and from a 403 `verification_required` response) instead of only after a forced redirect.

**Ground-truth correction**: The onboarding `profile` page (`(onboarding)/profile/page.tsx`) currently bundles phone + name + photo + documents into one form gating all app access — this plan splits it into (a) a lightweight signup-time collection of phone/name/DOB only, with no post-signup redirect gate, and (b) the existing `verify-id`/`driver/verify-documents` pages taking over as the sole document-submission surface, made reachable at any time rather than only on `rejected`. The `(auth)/complete-profile` page — today a narrow edge-case catcher for accounts missing phone/photo — becomes unreachable dead code for new accounts once phone is collected at signup and photo is fully optional; it is deleted rather than repurposed, per Assumptions in spec.md (no legacy accounts depend on it, per the grandfathering decision in Clarifications).

## Technical Context

**Language/Version**: TypeScript 5 (Next.js 14 App Router) for `apps/main`; Python 3.11 (FastAPI) for `services/api`

**Primary Dependencies**: Next.js 14, next-intl, Supabase JS client (`@supabase/supabase-js`), Tailwind CSS — frontend. FastAPI, Pydantic v2, Supabase Python client, existing `app.services.verification_service` and `app.services.notification_service` — backend. No new dependencies required.

**Storage**: Supabase PostgreSQL (`profiles` table gains one new nullable `date_of_birth DATE` column via migration). No new tables — `verification_status`, `is_submission_locked`, document-submission tables, and `profile_photo_path` already exist and are reused as-is.

**Testing**: pytest (backend, existing `services/api/tests/`); manual/browser validation for frontend flows (no existing frontend test runner in this repo — consistent with spec 020's approach).

**Target Platform**: Web (responsive, mobile-first per Constitution Principle V), served via the existing Docker Compose dev stack and Bunny production deployment for `apps/main` + `services/api`.

**Project Type**: Web application — monorepo (Option 4: Next.js frontend apps + FastAPI backend + shared packages), per Constitution Principle VII.

**Performance Goals**: No new performance targets — this feature removes gating logic rather than adding load-bearing computation. Age-from-DOB computation is O(1) and client/server trivial.

**Constraints**: Backend remains the authoritative enforcement layer (Constitution: "Critical business rules MUST NOT exist exclusively in frontend applications") — the three transaction-time guards are the source of truth; frontend gating is UX-only (fast-fail before a round trip, not a security boundary). `date_of_birth` MUST NOT be exposed via `PublicProfileResponse` (Constitution Data Standards: "National identification data MUST NOT be publicly exposed" — DOB is treated with the same caution as national ID data since it doubles as a KYC field).

**Scale/Scope**: Touches 2 apps (`apps/main` only — `apps/admin` is unaffected, per memory: admin review pipeline is untouched), 1 backend service (`services/api`), 1 shared package (`packages/shared`), 1 new DB migration. No changes to `apps/admin`, AI/verification-review pipeline internals, or notification templates (all reused as-is).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| III. Trust Before Transportation | "Passengers and drivers MUST be verifiable entities before participating in ride-sharing activities" — booking, ride-posting, and booking-acceptance remain hard-gated on `verified` status via unchanged backend dependencies; only *browsing* (not "participating in ride-sharing activities") is unblocked pre-verification. Safety-related decisions (who can transact) still take precedence over convenience (who can browse). | PASS |
| VI. Modular Domain-Driven Architecture | Feature is scoped to the single Verification domain (already established by spec 006/020's document-review pipeline); no new domain introduced, no attempt to redefine ride-creation or booking domains beyond adding a guard reference already used elsewhere. | PASS |
| VII. Shared Foundations, Independent Applications | Reuses shared `Profile`/`VerificationStatus` types in `packages/shared`, the shared verification dependency module, and the shared document-review pipeline — no duplicated logic introduced. `apps/admin` untouched (verification review UI is unaffected by when a user chooses to submit docs). | PASS |
| Data Standards ("National identification data MUST NOT be publicly exposed") | New `date_of_birth` column is nullable, never returned in `PublicProfileResponse`, and only ever readable by the owning user via `ProfileResponse`. | PASS |
| Architecture Standards ("Critical business rules MUST NOT exist exclusively in frontend applications") | Enforcement stays in the three existing FastAPI dependency guards; frontend gate removal is UX-only. | PASS |

No violations — Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/021-defer-identity-verification/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
apps/main/src/
├── app/
│   ├── (auth)/
│   │   ├── role-select/page.tsx              # unchanged
│   │   └── complete-profile/                 # DELETED — superseded by signup collecting
│   │                                          #   phone at creation time + photo being fully optional
│   ├── (onboarding)/
│   │   ├── profile/page.tsx                  # REWRITTEN — collects name + phone + date_of_birth
│   │   │                                      #   only; drops photo/front-ID/back-ID/license fields
│   │   │                                      #   and the post-submit `pending_review` gate; on
│   │   │                                      #   success routes straight into the app (no longer
│   │   │                                      #   blocks on verification)
│   │   ├── verify-id/page.tsx                 # UNCHANGED logic; now also linked from the persistent
│   │   │                                      #   affordance and from 403 verification_required
│   │   │                                      #   responses, not only reached via forced redirect
│   │   └── driver/verify-documents/page.tsx   # UNCHANGED logic; same reachability change as above
│   ├── page.tsx                               # NARROWED — removes the unverified→/profile and
│   │                                          #   missing-phone/photo→/complete-profile branches;
│   │                                          #   keeps rejected→verify page (still a useful nudge)
│   │                                          #   and suspended→inline screen; verified/unverified/
│   │                                          #   pending_review all land on the normal home route
│   ├── (passenger)/layout.tsx                 # NARROWED — removes the verified-only redirect guard;
│   │                                          #   passenger browsing/search no longer requires
│   │                                          #   verification (booking still gated server-side)
│   └── (app)/settings/profile/ProfileEditor.tsx  # EXTENDED — adds date_of_birth display (existing
│                                              #   accounts are exempt/read-only per FR-017; new
│                                              #   accounts already set it at signup, so this is
│                                              #   effectively read-only display, not a new input)
├── components/
│   ├── layout/
│   │   ├── TopBar.tsx                         # EXTENDED — renders a "Verify identity" badge/button
│   │   │                                      #   when profile.verification_status is "unverified"
│   │   │                                      #   or "rejected" (AppShell already fetches profile)
│   │   └── AppShell.tsx                       # UNCHANGED structurally — already fetches profile and
│   │                                          #   passes it down; the badge insertion point
│   └── verification/
│       └── VerificationRequiredModal.tsx      # NEW — shared modal/prompt shown when a gated action
│                                              #   (book / post ride / accept booking) receives a
│                                              #   403 verification_required response; links to the
│                                              #   role-appropriate verify page
├── lib/api/
│   ├── profiles.ts                            # EXTENDED — ProfileSetup/ProfileUpdate payloads gain
│   │                                          #   date_of_birth; existing error-shape handling
│   │                                          #   (`error: "verification_required"`) reused as-is
│   ├── rides.ts                               # EXTENDED — create/accept calls surface 403
│   │                                          #   verification_required via VerificationRequiredModal
│   └── bookings.ts                            # EXTENDED — same 403 handling for booking creation
└── middleware.ts                              # NARROWED — removes PASSENGER_VERIFIED_PREFIXES gate
                                              #   (/search, /bookings no longer verified-only); no
                                              #   other middleware behavior changes

services/api/app/
├── models/profile.py                          # EXTENDED — ProfileSetup gains date_of_birth (required,
│                                              #   validated against minimum-age); ProfileResponse
│                                              #   gains date_of_birth (owner-only, never in
│                                              #   PublicProfileResponse)
├── services/profile_service.py                # EXTENDED — persists date_of_birth on signup; age/
│                                              #   min-age validation lives here (mirrors existing
│                                              #   phone_number validation pattern)
├── dependencies/verification.py               # UNCHANGED — get_current_verified_passenger and
│                                              #   get_current_verified_driver already exist and are
│                                              #   the enforcement point this feature relies on
├── api/rides/router.py                        # UNCHANGED — create_ride (POST /) and the booking
│                                              #   confirm/reject endpoints already depend on
│                                              #   get_current_verified_driver; no new guard needed
└── api/bookings/router.py                     # UNCHANGED — POST "" (create booking) already depends
                                              #   on get_current_verified_passenger; no new guard
                                              #   needed

supabase/migrations/
└── <timestamp>_add_date_of_birth_to_profiles.sql   # NEW — nullable DATE column, no backfill
                                                     #   (existing accounts permanently exempt per FR-017),
                                                     #   modeled on
                                                     #   20260814000010_add_phone_number_to_profiles.sql

packages/shared/src/types/
└── user.ts                                     # EXTENDED — Profile, ProfileSetup, ProfileUpdate gain
                                              #   date_of_birth?: string
```

**Structure Decision**: Monorepo Option 4 (apps/ + services/ + packages/), matching the existing repository layout and Constitution Principle VII. This feature touches only `apps/main`, `services/api`, and `packages/shared` — `apps/admin` requires no changes since the document-review pipeline it drives is fully reused. No new top-level directories are introduced.

## Complexity Tracking

*No entries — Constitution Check has no violations to justify.*
