# Research: Required Phone Number & Profile Photo (Email+OTP Only)

No `NEEDS CLARIFICATION` markers remain in the Technical Context. This document records the key decisions made while designing this feature, including one significant course-correction discovered during direct code inspection.

## Correction: Spec 019 never merged — this is an addition, not a reversal

The originating request described this feature as "reversing" a shipped phone-OTP sign-in feature (Spec 019). Direct inspection of this branch (`020-required-phone-photo`, created fresh from `origin/main`) shows Spec 019's branch was never merged:

- `services/api/app/models/auth.py`, `app/services/auth_service.py`, `app/api/profiles/router.py` — all already email-only, no phone parameters, no GoTrue-phone derivation.
- `packages/shared/src/types/auth.ts` — `OtpRequest`/`OtpVerifyRequest` are already `{ email }`-only.
- `apps/main/src/app/(auth)/login`, `otp`, `role-select` — no phone toggle, no `PhoneInput` component (it doesn't exist on this branch), no `!session.user.email` branching.
- `profiles` table has no `phone_number` column — it was renamed to `email` in `20260616000001_rename_phone_to_email.sql` (from the project's original phone-primary auth scaffolding) and never re-added.

The only residue of phone-based auth is vestigial, unused config: `supabase/config.toml`'s `[auth.sms]` block (`enable_signup = true` but nothing in the app ever calls phone sign-in) and `TWILIO_*` placeholder lines in both `.env.example` files. These predate Spec 019 entirely — they're leftovers from the original phone-primary design, never invoked by any code path.

**Implication**: this plan implements the four locked-in product decisions as a straightforward addition to the current, already-email-only codebase, plus removing the two vestigial config blocks so FR-001 ("no phone-number-based sign-in or verification path may exist anywhere in the product") is unambiguously true, including in configuration.

## Decision: `phone_number` lives on `ProfileUpdate` (and `ProfileResponse`), not `ProfileSetup`

**Rationale**: The onboarding screen (`(onboarding)/profile/page.tsx`) already runs strictly *after* the profile row is created by `role-select` calling `POST /api/profiles/setup`, and it already calls `updateMe` (`PUT /me`) right after to save `display_name`. Adding `phone_number` to that same `ProfileUpdate` payload means one backend code path serves both "new user completing signup" and "existing user backfilling via the new gate." `ProfileResponse` also needs `phone_number` added so the frontend (gate page, settings page) can read the current value. This closes a pre-existing gap: today there is no way to view or edit a phone number at all.

**Alternatives considered**: Adding `phone_number` to `ProfileSetup` (`POST /setup`) was rejected — existing users being backfilled through the gate already have a profile row, so `POST /setup` doesn't apply to them; a single `ProfileUpdate`-based path avoids duplicating validation logic.

## Decision: Required-ness enforced at the application layer, not via DB `NOT NULL`

**Rationale**: Pre-existing rows may legitimately lack `phone_number` (a new column) or `profile_photo_path` (already nullable today). Adding `NOT NULL` at the database layer would fail the migration outright on any existing row lacking the value. Instead, Pydantic validation guards new-row completion, and old rows are guided through the "complete your profile" gate — the DB stays permissive so migrations never fail on legacy data.

**Alternatives considered**: A backfill script forcing a placeholder into every legacy row, then adding `NOT NULL` — rejected as unnecessarily invasive (fake phone numbers/photos are worse than a gate flow) and contrary to the locked-in product decision to use a gate-based backfill.

## Decision: Per-page redirect checks, not middleware

**Rationale**: `apps/main/src/middleware.ts` already exists and only handles auth plus a `verification_status` check for passenger-verified routes. This repo's established idiom for "you can't proceed until X" gating is a server/client component check at the top of `app/page.tsx` (already the canonical redirect chokepoint) and the OAuth callback route (`auth/callback/route.ts`, which already has a 404→`/role-select` check to extend), not global middleware.

**Alternatives considered**: Adding a middleware matcher for profile-completeness — rejected as inconsistent with the existing pattern and higher risk of interfering with unrelated routes (static assets, API routes) middleware runs against on every request.

## Decision: Phone number format validation uses a plausibility regex, `^\+[1-9]\d{6,14}$`

**Rationale**: A simple E.164-shaped check (leading `+`, 7–15 digits) catches obviously-garbage input ("abc", empty strings) without pretending to be real verification. Since the number is never SMS-sent or otherwise confirmed, format validation is the only signal available and should stay lightweight.

**Alternatives considered**: A looser validation (any non-empty string) was rejected — some format sanity-checking is a reasonable, cheap guard even for unverified input. A stricter, country-aware validation library was rejected as unnecessary complexity for a field that carries no verification guarantee anyway.

## Decision: Existing `profile-photos` storage bucket and `ProfilePhotoUpload` component are reused unchanged

**Rationale**: The bucket (private, 5MB limit, jpeg/png only, keyed by auth user id) and the picker component already do everything needed — client-side type/size validation, circular preview. The only change is *when* calling code treats a missing photo as a submit-blocking error, which lives entirely in the onboarding page's and gate page's validation logic, not the storage layer or the upload component.

**Alternatives considered**: None — rebuilding either would be pure duplication, prohibited by Constitution Principle VII.
