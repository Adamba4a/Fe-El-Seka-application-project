# Quickstart: Deferred Identity Verification (Progressive KYC)

Validation guide for confirming the feature works end-to-end once implemented. Assumes the local Docker Compose stack (`feelsekaapp-*` + `supabase_*` containers) is running (`docker compose up -d` from repo root) and the `021-defer-identity-verification` migration has been applied locally.

## Prerequisites

- Local stack healthy: `curl http://localhost:8000/health` returns 200.
- Migration applied: `date_of_birth` column exists on `profiles` (verify via `supabase db diff` or a direct `\d profiles` in the local Postgres).
- A fresh, never-used email/phone for signup (existing accounts are grandfathered and won't exercise the new-signup path — see Scenario 4 for grandfathering).

## Scenario 1 — Lightweight signup reaches the app without documents

1. Go to signup, complete role-select as a passenger.
2. On the profile step, provide only display name, phone number, and date of birth (≥ minimum age). No photo, no ID upload fields should be present.
3. Submit.
4. **Expected**: Lands directly on the passenger home/search screen — no redirect to a document-upload step, no blocking screen. `GET /api/profiles/me` shows `verification_status: "unverified"`.

## Scenario 2 — Underage signup is rejected

1. Repeat Scenario 1 but supply a `date_of_birth` yielding an age below the minimum threshold.
2. **Expected**: Signup is rejected with a clear age-related message; no profile row is created (or is left incomplete) for this identity.

## Scenario 3 — Browsing works while unverified; transacting is blocked

1. As the unverified passenger from Scenario 1, browse/search posted rides.
2. **Expected**: Ride listings render normally; the persistent "Verify identity" affordance is visible somewhere in the shell (e.g. top bar).
3. Attempt to book a ride.
4. **Expected**: The booking action is blocked client-side (or the `POST /api/bookings` call returns `403 {"error":"verification_required", ...}`), and a prompt directs the user to identity verification instead of a generic error.
5. Repeat for a driver account: sign up, browse the app, attempt to post a ride (`POST /api/rides`) → same 403/prompt behavior.

## Scenario 4 — Verification flow, unchanged pipeline

1. From the "Verify identity" affordance (or from the blocked-action prompt), reach the document upload screen (`verify-id` for passenger, `driver/verify-documents` for driver).
2. Submit front/back ID (+ license for driver).
3. **Expected**: `verification_status` becomes `pending_review`; existing review pipeline picks it up (admin panel, unchanged) and, on approval, `verification_status` becomes `verified` and the existing push/email decision notification fires (unchanged — see spec 019's notification pipeline).
4. Re-attempt the previously blocked action (booking / posting a ride).
5. **Expected**: Action succeeds without requiring re-login (session already reflects the updated status on next fetch).

## Scenario 5 — Legacy accounts are grandfathered

1. Sign in as a pre-existing test account created under the old flow (has `phone_number` and/or `profile_photo_path` populated, no `date_of_birth`).
2. **Expected**: No prompt to backfill `date_of_birth`; no `/complete-profile` redirect (route no longer exists); account behaves exactly like any other account at its current `verification_status` — fully normal access if already `verified`.

## Scenario 6 — Rejected accounts can resubmit via the same reusable screen

1. As an account with `verification_status: "rejected"`, open the "Verify identity" affordance.
2. **Expected**: Lands on `verify-id`/`driver/verify-documents` showing the rejection reason, same as the pre-existing resubmission behavior — this path is unchanged, only its entry point (now also reachable proactively, not just via forced redirect) is new.
