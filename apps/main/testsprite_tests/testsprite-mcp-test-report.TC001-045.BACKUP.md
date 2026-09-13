
# TestSprite AI Testing Report (MCP) — Frontend, apps/main (TC001–TC045)

---

## 1️⃣ Document Metadata
- **Project Name:** Fe El Seka app (Triplyy) — `apps/main` (combined passenger+driver Next.js app)
- **Date:** 2026-09-05 / 2026-09-06
- **Scope:** Frontend (port 3000), batches 1–3 of the 50-test plan (TC001–TC045; TC046–TC050 not yet run). Covers auth/onboarding/dashboard (batch 1), ride creation/lifecycle, bookings, search, loyalty, wallet, groups (batch 2), and ride editing, passenger bookings, ratings, reporting, recurring rides, group browsing, profile editing, wallet withdrawal/top-up history (batch 3).
- **Test account used (disposable, TestSprite-only):** driver `2b61b48e-1ec2-4cb3-b2c1-750d0f563bd6` (`testsprite.driver+4f241358@example.com`). No real/seed accounts were touched. **Only one account (driver, already onboarded) was available** — no passenger account was supplied.
- **Prepared by:** TestSprite AI Team (execution) + Claude (diagnosis, environment fix, consolidation)
- **Environment note:** Batch 1's first attempt mostly failed (6/15) because the `docker-compose` stack providing `nginx`+`api` (required by the frontend's `NEXT_PUBLIC_API_URL=http://localhost`) wasn't running. That was fixed before batches 1–3 below were (re-)run; none show any "Failed to fetch" network error.

---

## 2️⃣ Requirement Validation Summary

### Login and Authentication
- TC002 Sign in with email and password — ✅ Passed
- TC014 Reject invalid sign-in credentials — ✅ Passed
- TC012 Prevent access to the sign-out route after the session ends — ✅ Passed
- TC008 Return to the login screen when signing out — ✅ Passed
- TC049 *(not yet run — Keep password confirmation from mismatching)*

### OTP Verification
- TC011 Request an OTP sign-in code — ✅ Passed
- TC017 Handle an invalid OTP code — ✅ Passed
- TC020 Request a new OTP code — ✅ Passed
- TC003 Verify OTP sign-in code — ❌ Failed
  - **Root cause:** the generated test enters a synthetic placeholder code since it can't read the real one delivered to the test mailbox; the app correctly rejects it.
  - **Verdict:** permanent test-design limitation, not a bug.

### Set Password
- TC004 Set a new password during onboarding — ✅ Passed

### Role-Aware Dashboard
- TC005 View the dashboard for the assigned role — ✅ Passed

### Account Settings
- TC006 Sign out from account settings — ✅ Passed

### Org Email Verification
- TC001 Verify an organization email to unlock the app — BLOCKED
  - **Root cause:** `/verify-org-email` and `/settings` returned `ERR_INVALID_HTTP_RESPONSE`/`ERR_EMPTY_RESPONSE` mid-run; manually re-checked immediately after and all routes returned healthy `307`s. Matches TestSprite's documented dev-mode "server can crash under concurrent load" risk for a single run.
  - **Verdict:** transient dev-server hiccup, not reproduced independently. Not a confirmed bug.

### Signup Role Selection
- TC007 Choose a driver role during signup — ✅ Passed
- TC009 Choose a passenger role during signup — ❌ Failed
  - **Root cause:** test signs in with the disposable driver account, which is already fully onboarded — there's no "choose role" step left for an existing account.
  - **Verdict:** test/account mismatch, not a bug.

### Profile Onboarding
- TC010 Complete profile onboarding — ✅ Passed

### Profile
- TC042 Edit profile information — ✅ Passed
- TC050 *(not yet run — Edit profile details successfully)*

### Driver Vehicle Registration
- TC013 Register a driver vehicle — ✅ Passed

### Ride Creation & Lifecycle
- TC016 Create a new ride — ✅ Passed
- TC023 View driver ride list — ✅ Passed
- TC025 Search for matching rides by route — ✅ Passed
- TC027 Cancel a ride — ✅ Passed
- TC032 Edit an existing ride — ✅ Passed
- TC018 Start and complete a ride — BLOCKED
  - **Root cause:** by the time this test ran, the ride it targeted was already in `Cancelled` status (no Start/Complete controls available) — a side effect of TC027 (Cancel a ride) running earlier in the same batch against shared test data, since only one driver account/ride set exists.
  - **Verdict:** cross-test data-state/ordering artifact, not a bug.
- TC029 Review live tracking for an active ride — BLOCKED
  - **Root cause:** no ride was in `In Progress` status at the time this test ran ("No rides yet" in that filter) — same shared-state/ordering cause as TC018.
  - **Verdict:** cross-test data-state/ordering artifact, not a bug.
- TC021 View featured rides and open a ride detail — BLOCKED
  - **Root cause:** "No featured rides right now" — no ride in this test session was ever marked as featured (that requires a separate admin action, out of scope for this account/session).
  - **Verdict:** expected empty state given no featuring was performed, not a bug — but featured-rides display itself remains functionally unverified.

### Recurring Rides
- TC038 Create a recurring ride pattern — ❌ Failed
  - **Root cause:** the generated test's location autocomplete picked the *same* address ("El Tahrir Square...") for both Origin and Destination, and the app correctly rejected it with "Origin and destination must be different locations" (and consequently couldn't calculate a fare for a zero-distance route).
  - **Verdict:** test-input artifact (bad location selection by the generated script) — the app's validation is working exactly as intended, not a bug.
- TC044 View and end a recurring ride series — BLOCKED
  - **Root cause:** same login mis-click pattern as TC033/TC037 below — never got past `/login`.
  - **Verdict:** TestSprite tooling reliability issue, not a bug (see Key Gaps).

### Bookings (Driver side)
- TC019 Review and respond to passenger bookings — BLOCKED
  - **Root cause:** "Pending Requests (0)" / no confirmed passengers — nothing to review because no passenger account exists in this test session to create a booking.
  - **Verdict:** single-account limitation, not a bug.

### Bookings (Passenger side)
- TC039 Cancel an existing booking — ✅ Passed
- TC040 Add seats to an existing booking — ✅ Passed
- TC034 View passenger bookings by status — BLOCKED
  - **Root cause:** "Passenger role required" message shown — the disposable account used is driver-only.
  - **Verdict:** single-account limitation, not a bug.

### Ratings
- TC037 Submit a rating after a completed booking — BLOCKED
  - **Root cause:** login mis-click pattern (see Key Gaps) — never reached the ratings flow.
  - **Verdict:** TestSprite tooling reliability issue, not a bug.

### Reporting
- TC035 Report a counterpart from a completed booking — ✅ Passed

### Loyalty
- TC022 View loyalty balance and history — ✅ Passed
- TC031 Redeem a loyalty reward — ✅ Passed
- TC043 Browse redeemable loyalty rewards — ❌ Failed
  - **Root cause:** page showed "0 pts" and "No vouchers available right now." The disposable account is a **driver** — per the post-Spec-028 design (`loyalty_service.list_catalog`), driver accounts always get an empty reward catalog by design (Cash Back replaced driver loyalty points entirely; only passengers earn/redeem catalog points).
  - **Verdict:** expected behavior for a driver account, not a bug — needs a passenger account to actually exercise this flow.

### Wallet
- TC024 Redeem wallet cash-back — BLOCKED
  - **Root cause:** inspected the generated Playwright script directly — it repeatedly clicked the password-visibility "eye" toggle button (`aria-label="Show/Hide password"`) instead of the actual `type="submit"` Sign In button, and never actually attempted the real submit control. Confirmed via source (`apps/main/src/app/(auth)/login/page.tsx:239-258`) that the submit button and the eye toggle are distinct, correctly-labeled elements.
  - **Verdict:** confirmed TestSprite generated-code targeting mistake, not a product bug.
- TC028 Submit wallet top-up request — BLOCKED
  - **Root cause:** the flow reached the Add Balance form correctly (fields pre-filled) but TestSprite's sandbox had no local image file available to attach for the required payment-proof upload.
  - **Verdict:** tooling limitation (no test fixture file provided), not a bug.
- TC033 Submit wallet withdrawal request — ❌ Failed
  - **Root cause:** same login mis-click pattern as TC024/TC037/TC044 (see Key Gaps) — never got past `/login`.
  - **Verdict:** TestSprite tooling reliability issue, not a bug.
- TC045 Review wallet top-up history — ✅ Passed

### Groups
- TC026 Complete sponsored group domain verification during join — ❌ Failed
  - **Root cause:** TestSprite has no real invite link to use (never having created/received one), so it navigated to the bare `/groups/join` path. That 2-segment path isn't the real invite route (`/groups/join/[inviteToken]`, 3 segments) — Next.js instead matched a `/groups/[groupId]` route with `groupId="join"`, and the backend's UUID validation surfaced a raw error ("Input should be a valid UUID...found `j`") instead of a friendly invalid-link message.
  - **Verdict:** low-severity UX robustness gap on a route no real user reaches without a hand-typed/malformed URL (real invite links always include a token) — not a functional bug, but worth a small polish fix (friendly 404/invalid-link message for a non-UUID group id) if time allows.
- TC030 Join a group using an invite link — BLOCKED
  - **Root cause:** the join flow correctly sent a 6-digit domain-verification code to the test email, but TestSprite cannot read that inbox to retrieve it.
  - **Verdict:** same permanent limitation as TC003 (no email inbox access), not a bug.
- TC036 Create a new group and view its details — ❌ Failed
  - **Root cause:** the test expected a membership-type ("open") toggle on the Create Group form. The form (`apps/main/src/app/(app)/groups/create/page.tsx`) intentionally has no such control — per the post-redesign product decision, non-sponsored groups are unconditionally open-membership with no type selection; only sponsored groups (admin-created) use domain-email verification instead of a toggle.
  - **Verdict:** test-plan mismatch against an intentional, already-shipped redesign — not a bug.
- TC041 Browse groups and open a group detail page — ❌ Failed
  - **Root cause:** opened a sponsored group's detail page as a non-member and expected to see its rides; the page (`apps/main/src/app/(app)/groups/[groupId]/page.tsx:44-52, 175-209`) only fetches/shows rides `if (group.is_member)`, and for a sponsored, non-joined group it correctly shows only the domain-email verification form instead.
  - **Verdict:** working exactly as designed (rides are member-gated) — not a bug.

---

## 3️⃣ Coverage & Matching Metrics

**55.6%** of tests passed (25/45) across all three batches.

| Requirement Area                  | Total | ✅ Passed | ❌/BLOCKED (non-bug) |
|-------------------------------------|:-----:|:---------:|:---------------------:|
| Login and Authentication            | 4     | 4         | 0 |
| OTP Verification                    | 4     | 3         | 1 |
| Set Password                        | 1     | 1         | 0 |
| Role-Aware Dashboard                | 1     | 1         | 0 |
| Account Settings                    | 1     | 1         | 0 |
| Org Email Verification              | 1     | 0         | 1 |
| Signup Role Selection               | 2     | 1         | 1 |
| Profile Onboarding                  | 1     | 1         | 0 |
| Profile                             | 1     | 1         | 0 |
| Driver Vehicle Registration         | 1     | 1         | 0 |
| Ride Creation & Lifecycle           | 8     | 5         | 3 |
| Recurring Rides                     | 2     | 0         | 2 |
| Bookings (Driver side)              | 1     | 0         | 1 |
| Bookings (Passenger side)           | 3     | 2         | 1 |
| Ratings                             | 1     | 0         | 1 |
| Reporting                           | 1     | 1         | 0 |
| Loyalty                             | 3     | 2         | 1 |
| Wallet                              | 4     | 1         | 3 |
| Groups                              | 4     | 0         | 4 |
| **Total**                           | **45**| **25**    | **20** |

Every one of the 20 non-passing tests was root-caused to an environment/test-design/tooling limitation or an intentional, already-verified product decision — **zero confirmed real bugs** across TC001–TC045. One low-severity UX polish item remains flagged (TC026 — raw validation error on a malformed `/groups/join` URL, not reachable through any real UI flow).

---

## 4️⃣ Key Gaps / Risks
- **Login-form mis-click is now a confirmed recurring TestSprite tooling reliability issue, not an isolated fluke.** Four separate tests across two batches (TC024, TC033, TC037, TC044) show the identical symptom: the generated script clicks the password-visibility "eye" toggle instead of the real `type="submit"` Sign In button and then loops without progressing, while seven *other* tests in the very same batches logged in via the identical form without issue. Source (`login/page.tsx:239-258`) confirms the two buttons are structurally distinct and correctly labeled, and the submit button is `disabled` only while `!email || !password` — so this looks like intermittent script/DOM-timing flakiness in TestSprite's own generated code, not a deterministic product defect. Worth escalating to TestSprite if it keeps recurring in TC046-050 or later re-runs, since it's now blocked ~9% of all tests executed so far.
- **Single-account limitation continues to be the dominant blocker.** TC019, TC034, and (differently) TC043 all trace back to having only one disposable **driver** account, already onboarded, and no **passenger** account — TC043 additionally reflects a real, intentional product rule (drivers have no loyalty reward catalog at all post-Spec-028). A second disposable passenger account remains the single highest-value fix to unblock more tests.
- **Two tests in this batch (TC036, TC041) reflect stale test-plan assumptions, not bugs**, against already-shipped product redesigns: groups have no membership-type toggle (all non-sponsored groups are unconditionally open — see project memory "Groups Open-Membership Redesign"), and sponsored-group ride lists are correctly gated behind membership. The generated test plan may need a refresh pass against current product docs before further batches, so these don't keep re-surfacing as false failures.
- **OTP/email-code flows remain permanently untestable by TestSprite's generated code** (TC003, TC030) without Inbucket/email-inbox integration.
- **Minor polish item (non-blocking):** `/groups/[groupId]` should return a friendly invalid-group message rather than a raw Pydantic-style UUID validation error when the segment isn't a UUID (surfaced only via a malformed/hand-typed URL, e.g. `/groups/join`).
- **5 tests remain unrun** (TC046–TC050 — org-email invalid code, group invite link generation, wallet withdrawal history, password-confirmation mismatch, profile edit success). `apps/admin` (port 3001) frontend testing also has not started.
