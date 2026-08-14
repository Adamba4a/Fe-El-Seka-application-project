# Quickstart: Required Phone Number & Profile Photo (Email+OTP Only)

Validation guide for this feature once implemented. Assumes the local Supabase stack and `services/api` are already set up per the repo's normal dev workflow (see root `CLAUDE.md` / existing spec quickstarts for base setup — not repeated here).

## Prerequisites

- Local Supabase stack running (`supabase start`), migrations applied including the new `phone_number` column (see [data-model.md](./data-model.md)).
- `services/api` running against the local stack.
- `apps/main` dev server running.
- Mailpit reachable at `http://localhost:54324/api/v1/messages` for reading OTP codes (email-OTP is unchanged by this feature).

## Scenario 1 — New signup is blocked without phone or photo (User Story 1)

1. Go to `/login`, switch to "sign in with code", enter a brand-new email, submit.
2. Read the OTP from Mailpit (`Snippet` field), enter it at `/otp`.
3. Land on `/role-select`, pick a role (passenger or driver), continue.
4. Land on `/profile` (onboarding). Fill in display name and ID documents (and license, if driver) but leave phone and photo empty. Submit.
   - **Expected**: submission is blocked with a validation message; no `pending_review` transition occurs.
5. Fill in a photo only (still no phone), submit.
   - **Expected**: still blocked, phone-specific message shown.
6. Fill in an invalid phone (e.g. `"abc"`), submit.
   - **Expected**: blocked with a format error.
7. Fill in a valid phone (e.g. `+201234567890`) and a valid photo, submit.
   - **Expected**: submission succeeds, screen transitions to the "documents submitted" / `pending_review` state.

## Scenario 2 — Sign-in stays email-only (User Story 2)

1. Visit `/login`.
   - **Expected**: only email/password and "sign in with code" (email) options are visible; no phone entry point anywhere on the page.
2. Confirm `supabase/config.toml` has no `[auth.sms]` block and neither `.env.example` file references `TWILIO_*`.

## Scenario 3 — Existing account is gated until profile is complete (User Story 3)

1. In the local Postgres instance, pick (or create via Scenario 1's flow, then null out) a `verified` profile row and set `phone_number = NULL` and/or `profile_photo_path = NULL`.
2. Sign in as that user via `/login`.
   - **Expected**: redirected to `/complete-profile` before reaching `/rides` or `/search`; the screen asks only for the field(s) actually missing (e.g. a user missing only a photo is not re-asked for phone).
3. Attempt to navigate directly to `/` or `/search`/`/rides` while still on the gate.
   - **Expected**: still redirected back to `/complete-profile` (no skip button exists on the page).
4. Submit the missing field(s).
   - **Expected**: redirected to the normal landing screen (`/rides` or `/search` depending on role).
5. Sign out and sign back in.
   - **Expected**: lands directly on the normal landing screen — the gate does not reappear.

## Scenario 4 — Google OAuth callback respects the gate

1. Sign in via "Continue with Google" using an account whose profile (from a prior local test) is missing `phone_number` or `profile_photo_path`.
2. **Expected**: `apps/main/src/app/auth/callback/route.ts` redirects to `/complete-profile`, not straight into the app.

## Backend verification

```powershell
services/api/.venv/Scripts/python -m pytest tests/unit -q
```

Expect the full suite green, including new tests for `ProfileUpdate.phone_number` format validation and `profile_service.update_profile` persisting `phone_number`.

```powershell
Select-String -Path supabase/config.toml -Pattern "auth.sms"
Select-String -Path .env.example, services/api/.env.example -Pattern "TWILIO"
```

Expect zero matches for both — confirms the vestigial SMS config was fully removed (FR-013).
