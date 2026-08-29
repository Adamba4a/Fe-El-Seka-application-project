# Quickstart: Organization-Only Access Gate

## Prerequisites

- Local Supabase stack running (`supabase start`), with this feature's migration applied.
- `services/api` running locally with `.venv` active; Mailpit capturing outbound email at `http://localhost:54324`.
- `apps/main` running locally (`pnpm dev` or equivalent).
- At least one test account with a domain **not** on the default blocklist (e.g. `test@my-university.edu`).

## Scenario 1 — New signup is gated (User Story 1)

1. Sign up a brand-new account (email+OTP) through `apps/main`.
2. Expect: immediately after account creation, the app shows the org-email verification screen — not `/dashboard` or `/rides`.
3. Submit a personal-provider email (e.g. `test@gmail.com`).
   - Expect: rejected immediately (`blocklisted_domain`), no email in Mailpit.
4. Submit a non-blocklisted email (e.g. `test@my-university.edu`).
   - Expect: a code arrives in Mailpit within seconds.
5. Enter the code.
   - Expect: redirected to the normal home/browse screen (`/dashboard` for passenger, `/rides` for driver). `profiles.org_verified_at` is now set (check via Supabase Studio or `psql`).
6. Attempt to navigate back to the verification screen's URL directly.
   - Expect: redirected straight past it to the normal app (already verified).

## Scenario 2 — Existing account is gated on next login (User Story 2)

1. Using a pre-existing test account (created before this feature, `org_verified_at IS NULL`), sign in.
2. Expect: routed to the org-email verification screen before any other screen, with no dismiss/skip option.
3. Complete verification as in Scenario 1, steps 3-5.
4. Sign out and sign back in.
   - Expect: goes straight to the normal landing screen — the gate is not shown again.

## Scenario 3 — Personal domains rejected (User Story 3)

1. On the verification screen, submit each of `gmail.com`, `yahoo.com`, `outlook.com`, `hotmail.com`, `icloud.com`, `protonmail.com` (the default blocklist) as the domain.
2. Expect: all rejected with `blocklisted_domain`, no code sent for any.
3. As an admin (via whatever surface currently edits `group_domain_blocklist`), add a test domain (e.g. `disposable-mail.test`) to the list.
4. Submit an email on that domain.
   - Expect: rejected the same way, confirming the admin-extendable rejection list (FR-006).

## Scenario 4 — Groups verification auto-credits the gate (FR-015 / Clarifications)

1. Using a test account that has **not** completed this feature's gate, complete the existing Groups domain-verification flow (`/groups/create` or `/groups/join` → domain verify) for a non-blocklisted domain.
2. Expect: `profiles.org_verified_at` is now set (check via `psql`/Supabase Studio) even though the new `/org-access/*` endpoints were never called.
3. Sign out and back in.
   - Expect: the account goes straight to the normal landing screen — no org-email verification screen shown.

## Scenario 5 — Backfill migration credits pre-existing Groups verifications

1. Before applying this feature's migration, confirm (via `psql`) a test account has a confirmed `domain_verifications` row (`verified_at IS NOT NULL`) from prior use of Groups, but `profiles.org_verified_at IS NULL` (column doesn't exist yet).
2. Apply the migration.
3. Expect: `profiles.org_verified_at` is now populated for that account, matching the earliest confirmed `domain_verifications.verified_at` for that user.

## Scenario 6 — Suspension takes precedence

1. Suspend a test account (`verification_status = 'suspended'`) that has not completed org-email verification.
2. Sign in as that account.
   - Expect: the existing suspension screen is shown; the org-email verification screen is never reached (FR-012).

## Scenario 7 — Email uniqueness conflict surfaces only at confirm-time

1. Complete org-email verification on Account A using `shared@dept.acme-corp.com`.
2. On Account B (a different account), submit the same `shared@dept.acme-corp.com` email on the request step.
   - Expect: the request **succeeds** (a code is sent) — no error yet (Clarifications session 2026-08-29).
3. Enter a correct code (from Account B's own Mailpit message) on Account B.
   - Expect: rejected with `email_already_verified_elsewhere`; Account B remains ungated.

## Automated coverage

- Backend: `services/api/tests/unit/test_org_access_service.py` (new) covering request/confirm success and error paths, plus the shared `domain_verification_service` extraction (research.md R1) via `services/api/tests/unit/test_domain_verification_service.py`.
- Run: `cd services/api && uv run pytest tests/unit/test_org_access_service.py tests/unit/test_domain_verification_service.py -v`
