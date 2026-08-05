# Quickstart: Arabic & RTL Localization

Validation guide for confirming the feature works end-to-end once implemented. `apps/main` has no
automated frontend test suite (see `plan.md` Technical Context), so this is the manual verification
path — mirrors the convention already used for other `apps/main` features.

## Prerequisites

- Local Supabase instance running with the `20260805000001_phase14_language_preference.sql`
  migration applied (`profiles.language_preference` column present).
- `apps/main` running locally (`npm run dev` in `apps/main`, per its existing `package.json` scripts)
  with `next-intl` installed and `messages/en.json` / `messages/ar.json` present (or the Storage
  bucket seeded — see `contracts/message-catalog.md`).
- `services/api` running locally with the updated `fcm_service.py` / `profile_service.py`.
- Two test accounts: one existing account seeded with `language_preference = NULL` (to exercise the
  rollout prompt), one fresh signup.

## Scenario 1 — Full Arabic experience (User Story 1, P1)

1. Log in as a passenger or driver test account with `language_preference = 'ar'` already set.
2. Navigate through: home/dashboard → search or ride creation → a ride detail page → booking
   management → Settings.
3. **Expect**: every screen renders Arabic text, right-to-left layout (nav order, form alignment,
   directional icons — `←` in `ProfileEditor.tsx` should read as pointing the correct direction for
   RTL), no leftover English strings.
4. Trigger a booking event (e.g., request a booking) and confirm the resulting FCM push arrives in
   Arabic (per `contracts/notification-localization.md`).

## Scenario 2 — Language toggle without losing state (User Story 2, P2)

1. Start a ride search with filters entered (e.g., origin/destination, date) but not submitted.
2. Toggle the language from within Settings (or wherever the always-accessible toggle lives).
3. **Expect**: layout/labels switch language and direction within ~2s (NFR-001); the in-progress
   search filter values are still populated (FR-012) — only chrome re-renders.
4. Log out, log back in on a different browser session. **Expect**: the app opens in the
   just-selected language (FR-004).
5. In a private/incognito window (unauthenticated), toggle language, close the window, reopen.
   **Expect**: the device remembers the last selection (FR-005).

## Scenario 3 — Existing-user rollout prompt (FR-013 / clarified rollout behavior)

1. Log in as the seeded `language_preference = NULL` account.
2. **Expect**: the one-time `LanguagePromptModal` appears; the app is otherwise still usable/navigable
   underneath it (it must not block routing — see `research.md` R5).
3. Choose a language. **Expect**: `PATCH /profiles/me` fires with `language_preference` set, modal
   does not reappear on next login.

## Scenario 4 — OTP stays English (FR-014)

1. With the test account's `language_preference = 'ar'`, trigger a phone-verification OTP flow.
2. **Expect**: the OTP SMS content is in English regardless of the account's Arabic display
   preference — confirms Auth domain SMS templates were correctly left untouched.

## Scenario 5 — Missing translation fallback (FR-011)

1. Temporarily remove one key from `ar.json` that exists in `en.json` (or point the loader at a
   catalog version missing a key).
2. View the corresponding screen with Arabic selected.
3. **Expect**: that specific string renders in English (fallback), not blank and not a raw key like
   `search.emptyState` — everything else on the screen stays Arabic.

## Scenario 6 — No-redeploy copy update (NFR-003)

1. Edit `ar.json` in the Storage bucket directly (or via whatever publish tooling `/speckit-tasks`
   sets up) — change one visible string, bump `version`.
2. Wait for the loader's refresh interval (see `contracts/message-catalog.md`) without restarting or
   redeploying `apps/main`.
3. **Expect**: the updated string appears on next page load, confirming no redeploy was required.

## Scenario 7 — Overflow / responsive sizing (clarified text-overflow behavior)

1. View a screen with a naturally long Arabic string (e.g., a booking-status label with a longer
   Arabic translation than its English source) on a narrow mobile viewport.
2. **Expect**: the containing UI element grows/wraps to fit (FR-015) — no truncation, no visual
   overlap with neighboring elements (SC-005).

## Success check

All seven scenarios pass → feature matches spec Success Criteria SC-001 through SC-005 for the
implemented scope. SC-004 (90% of surveyed users find the experience natural) is a post-launch
measurement, not verifiable via this quickstart.
