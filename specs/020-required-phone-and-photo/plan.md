# Implementation Plan: Required Phone Number & Profile Photo (Email+OTP Only)

**Branch**: `020-required-phone-photo` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/020-required-phone-and-photo/spec.md`

## Summary

Add a required, unverified, plain-text `phone_number` field to signup, and make the already-existing (currently optional) profile photo required at signup — for both passenger and driver roles. Existing accounts missing either field are forced through a non-skippable "complete your profile" gate on next sign-in. Email+OTP remains, and stays, the only sign-in method.

**Ground-truth correction**: an earlier draft of this plan assumed a prior feature (Spec 019, phone-as-SMS-verified-sign-in) had shipped to `main` and needed to be reverted. Direct inspection of this branch (created fresh off `origin/main`) confirms Spec 019's branch was **never merged** — `services/api/app/models/auth.py`, `auth_service.py`, `packages/shared/src/types/auth.ts`, and `apps/main/src/app/(auth)/login|otp|role-select` are all already email-only with no phone logic anywhere. The `profiles` table has no `phone_number` column (it was renamed to `email` back in migration `20260616000001_rename_phone_to_email.sql`). The only phone-OTP residue present is vestigial: an `[auth.sms]` block in `supabase/config.toml` and `TWILIO_*` placeholders in both `.env.example` files, left over from the project's original phone-primary scaffolding (`20260614000001_create_profiles.sql`) and never cleaned up. **This plan is therefore a pure addition + small cleanup, not a reversal.**

## Technical Context

**Language/Version**: TypeScript 5 (Next.js 14, App Router) for `apps/main`; Python 3.11 (FastAPI) for `services/api`

**Primary Dependencies**: Next.js 14, React, Supabase JS client, Supabase Auth (GoTrue), react-hook-form + zod; FastAPI, Pydantic, `supabase-py`, asyncpg

**Storage**: Supabase PostgreSQL (`profiles` table — new `phone_number` column, nullable); Supabase Storage `profile-photos` bucket (already exists, reused as-is — private, 5MB limit, jpeg/png only, path `{user_id}/profile.{ext}`)

**Testing**: pytest (`services/api/.venv`, unit tests under `services/api/tests/unit`); manual E2E via local Supabase stack + Mailpit for email-OTP capture (`http://localhost:54324/api/v1/messages`)

**Target Platform**: Web (Next.js), server-side FastAPI service — no mobile-native target

**Project Type**: Monorepo web application (Option 4 — shared foundations, independent apps per Constitution Principle VII)

**Performance Goals**: No new performance goals — reuses existing `PUT /me` and `POST /me/photo` endpoints; the completeness-gate check only adds one extra selected column to the already-required per-page profile fetch in `app/page.tsx`, no additional round trip.

**Constraints**: Phone number is never SMS-verified — plain user input with format validation only (reuses the E.164-ish `^\+[1-9]\d{6,14}$` pattern). No uniqueness enforced on `phone_number`. DB layer must not hard-fail on legacy rows missing the new required fields — `phone_number` stays nullable at the DB level; "required" is enforced at the application layer (Pydantic on new-row completion + the post-login completeness gate for pre-existing rows).

**Scale/Scope**: Touches `apps/main` (frontend), `services/api` (backend), and shared types in `packages/shared`. `apps/admin` is untouched. Single feature branch, ~15 files.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle III (Trust Before Transportation)** — Requiring a phone number and a photo on every account strengthens identity accountability and reachability. Phone number is explicitly *not* used as a verification/authentication factor — identity verification continues to rely on the existing ID-document review flow, unchanged by this feature. **PASS**.
- **Principle VII (Shared Foundations, Independent Applications)** — Changes live in shared foundations (`services/api`, `packages/shared`) and the one app (`apps/main`) serving both passenger and driver roles without duplication; `apps/admin` needs no changes. **PASS**.
- **Data Standards (sensitive information MUST be protected and access-controlled)** — Phone number is stored in the existing `profiles` table under existing RLS; no new exposure surface. **PASS**.
- **Development Workflow Standards (spec-driven, domain-focused)** — This plan follows the full spec-kit ceremony; the domain is Authentication/Profile, a single bounded context. **PASS**.

No violations requiring justification — Complexity Tracking table is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/020-required-phone-and-photo/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/            # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks — not created by /speckit-plan)
```

### Source Code (repository root)

```text
apps/
├── main/                         # Next.js 14 — shared passenger + driver experience
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx                          # add completeness-gate redirect
│   │   │   ├── (auth)/
│   │   │   │   └── complete-profile/page.tsx     # NEW — non-skippable gate, modeled on set-password/page.tsx
│   │   │   ├── (onboarding)/profile/page.tsx     # add required phone input + required-photo validation
│   │   │   ├── (app)/settings/profile/ProfileEditor.tsx  # add phone display/edit row
│   │   │   └── auth/callback/route.ts            # add completeness-gate check alongside existing 404 check
│   │   ├── components/profile/
│   │   │   ├── ProfileForm.tsx                   # extend for reuse (optional phone field)
│   │   │   └── ProfilePhotoUpload.tsx            # unchanged, reused
│   │   └── lib/api/profiles.ts                   # updateMe payload picks up phone_number automatically via shared types
│   └── messages/{en,ar}.json                     # add new field labels/errors + gate-page copy
└── admin/                                        # untouched

packages/
└── shared/src/types/user.ts                      # add phone_number to Profile + ProfileUpdate

services/
└── api/
    ├── app/
    │   ├── models/profile.py                     # add phone_number to ProfileUpdate (+ validator) and ProfileResponse
    │   ├── api/profiles/router.py                # pass body.phone_number through to update_profile
    │   └── services/profile_service.py           # extend update_profile + _format_profile with phone_number
    └── tests/unit/                                # add ProfileUpdate.phone_number validation + update_profile tests

supabase/
├── config.toml                                   # remove vestigial [auth.sms] block
└── migrations/<timestamp>_add_phone_number_to_profiles.sql   # NEW

.env.example, services/api/.env.example            # remove vestigial TWILIO_* placeholders
```

**Structure Decision**: Monorepo Option 4 (per Constitution Principle VII) — this feature is scoped entirely to the shared `apps/main` frontend (serving both passenger and driver roles), the shared `services/api` backend, and shared type packages. `apps/admin` requires no changes.

## Complexity Tracking

*No constitution violations — this section is not applicable.*
