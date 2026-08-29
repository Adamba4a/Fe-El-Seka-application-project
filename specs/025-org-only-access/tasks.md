---

description: "Task list for feature implementation"
---

# Tasks: Organization-Only Access Gate

**Input**: Design documents from `specs/025-org-only-access/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/org-access-api.md, quickstart.md

**Tests**: A small set of targeted unit tests are included — they were already scoped in quickstart.md's "Automated coverage" section during `/speckit-plan` (`test_org_access_service.py`, `test_domain_verification_service.py`), not full TDD for every task.

**Organization**: Tasks are grouped by user story (spec.md) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Monorepo: `apps/main/src/` (frontend), `services/api/app/` (backend), `packages/shared/src/` (shared types), `supabase/migrations/` (DB). See plan.md's Project Structure for the full map.

---

## Phase 1: Setup

**Purpose**: Directory/file scaffolding, no business logic yet

- [X] T001 Create `services/api/app/api/org_access/` package (`__init__.py`, `router.py` stub) and mount it in `services/api/app/main.py` at `/api/v1/org-access`
- [X] T002 [P] Create `apps/main/src/components/org-access/` directory and `apps/main/src/app/(auth)/verify-org-email/` route directory (empty `page.tsx` placeholder)
- [X] T003 [P] Create `packages/shared/src/types/org-access.ts` with `OrgAccessRequestBody`, `OrgAccessRequestResponse`, `OrgAccessConfirmBody`, `OrgAccessConfirmResponse` types per contracts/org-access-api.md

**Checkpoint**: Scaffolding in place, nothing functional yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared schema, shared service module, and shared endpoints that every user story depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Write migration `supabase/migrations/<timestamp>_org_only_access.sql`: add `profiles.org_verified_at TIMESTAMPTZ`, `profiles.org_verified_domain TEXT`; relax `domain_verifications.requested_group_type` to nullable (drop `NOT NULL`, replace `chk_domain_verifications_type` CHECK to allow `NULL`); backfill `profiles.org_verified_at`/`org_verified_domain` from the earliest confirmed `domain_verifications` row per user (see data-model.md Migration summary for exact SQL). Apply to local Supabase stack.
- [X] T005 [P] Extract `_get_domain_blocklist`, `_generate_otp`, `_hash_otp`, `_check_domain_otp_resend_rate` out of `services/api/app/services/group_service.py` into new `services/api/app/services/domain_verification_service.py` (research.md R1) — pure extraction, no behavior change
- [X] T006 Refactor `services/api/app/services/group_service.py` to import the extracted primitives from `domain_verification_service.py` instead of its private copies; run existing Groups tests to confirm no regression
- [X] T007 [P] Create `services/api/app/models/org_access.py` with `OrgAccessRequest`, `OrgAccessConfirm`, `OrgAccessConfirmResponse` Pydantic models (contracts/org-access-api.md)
- [X] T008 Create `services/api/app/services/org_access_service.py` with `request_verification(user_id, email)` and `confirm_verification(user_id, verification_id, code)`, using the shared `domain_verification_service` primitives, writing `domain_verifications` rows with `requested_group_type = NULL`, and setting `profiles.org_verified_at`/`org_verified_domain` on successful confirm (no group side effect) — depends on T004, T005
- [X] T009 Implement `POST /org-access/request` and `POST /org-access/confirm` in `services/api/app/api/org_access/router.py`, requiring `Depends(get_current_user)` only (no `_require_verified`), per contracts/org-access-api.md error codes — depends on T007, T008
- [X] T010 [P] Extend `services/api/app/services/profile_service.py`'s `_format_profile` (and thus `GET /me`) to include `org_verified_at`/`org_verified_domain` read directly from the profile row already fetched — depends on T004
- [X] T011 [P] Add `org_verified_at`/`org_verified_domain` fields to the `Profile` type in `packages/shared/src/types/user.ts`
- [X] T012 Create `services/api/app/dependencies/org_access.py` with a `require_org_verified()` FastAPI dependency that raises `403 org_verification_required` when `profiles.org_verified_at IS NULL` — depends on T004

**Checkpoint**: Backend core (schema, shared OTP module, request/confirm endpoints, profile exposure) is functional and independently testable via `curl`/Postman before any frontend work starts.

---

## Phase 3: User Story 1 - New user must verify an org email before using the app (Priority: P1) 🎯 MVP

**Goal**: A brand-new user is routed to a non-skippable org-email verification screen immediately after signup and cannot reach any other screen until it's completed.

**Independent Test**: Sign up a brand-new account and confirm the very next screen is org-email verification, not the normal home/browse screen; confirm a personal-domain email is rejected and a qualifying one sends a code that, once entered correctly, unlocks the normal app (quickstart.md Scenario 1).

### Tests for User Story 1

- [X] T013 [P] [US1] Unit tests for `org_access_service.request_verification` (success, `invalid_email`, `blocklisted_domain`, `otp_rate_limited`) in `services/api/tests/unit/test_org_access_service.py`
- [X] T014 [P] [US1] Unit tests for `org_access_service.confirm_verification` (success sets `org_verified_at`, `otp_invalid`, `otp_already_used`, `otp_expired`) in the same file

### Implementation for User Story 1

- [X] T015 [US1] Create `apps/main/src/lib/api/org-access.ts` with `requestOrgAccessVerification(email)` / `confirmOrgAccessVerification(verificationId, code)` calling the T009 endpoints
- [X] T016 [US1] Build `apps/main/src/components/org-access/OrgAccessVerifyForm.tsx`, adapted from `apps/main/src/components/groups/DomainVerifyForm.tsx` with the group-type prop removed, using the T015 client — depends on T015
- [X] T017 [US1] Wire `OrgAccessVerifyForm` into `apps/main/src/app/(auth)/verify-org-email/page.tsx` — depends on T016
- [X] T018 [US1] Add the post-signup gate redirect in `apps/main/src/app/page.tsx`: if `profile.org_verified_at` is null (and account is not suspended), redirect to `/verify-org-email` before the existing role/onboarding routing — depends on T010, T017
- [X] T019 [US1] Add `verify-org-email` screen copy (heading, email field, code field, error states) to `apps/main/src/messages/en.json` and `apps/main/src/messages/ar.json`
- [X] T020 [US1] Add `require_org_verified` (T012) to the ride-search endpoint(s) in `services/api/app/api/search/router.py` so unverified accounts get `403 org_verification_required` even if they bypass the frontend redirect
- [X] T021 [US1] Manually run quickstart.md Scenario 1 end-to-end (new signup → blocklist rejection → code → verified → redirected)

**Checkpoint**: User Story 1 fully functional and independently testable — new signups are gated end-to-end, front and back.

---

## Phase 4: User Story 2 - Existing user is gated on next login (Priority: P1)

**Goal**: Every pre-existing account, regardless of role or prior verification state, is routed to the same gate on its next sign-in — except accounts already credited via a prior Groups domain verification (FR-015) or the backfill migration.

**Independent Test**: Sign in with a pre-existing, fully-onboarded test account (`org_verified_at IS NULL`) and confirm it's routed to the gate before its normal landing screen; confirm a suspended account still hits the suspension screen instead (quickstart.md Scenarios 2, 4, 5, 6).

### Tests for User Story 2

- [X] T022 [P] [US2] Unit test: `group_service.confirm_domain_verification` sets `profiles.org_verified_at`/`org_verified_domain` as a side effect when not already set, in `services/api/tests/unit/test_group_service.py`

### Implementation for User Story 2

- [X] T023 [US2] Extend `group_service.py`'s `confirm_domain_verification` to set `profiles.org_verified_at`/`org_verified_domain` (if not already set) on success, alongside its existing group-join behavior (research.md R3) — depends on T006
- [X] T024 [US2] Add the same gate redirect logic from T018 to `apps/main/src/app/(app)/layout.tsx`, `(driver)/layout.tsx`, `(passenger)/layout.tsx`, and `dashboard/page.tsx` (covers direct navigation / already-mounted app shell, not just the initial landing route — Phase 6 review found `(driver)`/`(passenger)`/`dashboard` were missed in the first pass) — depends on T010
- [X] T025 [US2] Add the gate check to `apps/main/src/app/auth/callback/route.ts` so it fires immediately on the post-login redirect for existing users, ordered after the existing suspension check (FR-012) — depends on T010
- [X] T026 [US2] Add `require_org_verified` (T012) to the ride-posting endpoint(s) in `services/api/app/api/rides/router.py` and the booking endpoint(s) in `services/api/app/api/bookings/router.py`
- [X] T027 [US2] Apply migration T004 to a local DB with pre-existing confirmed `domain_verifications` rows and verify the backfill populates `profiles.org_verified_at` correctly (quickstart.md Scenario 5)
- [X] T028 [US2] Manually run quickstart.md Scenarios 2, 4, and 6 (existing-user gate, Groups auto-credit, suspension precedence)

**Checkpoint**: User Stories 1 AND 2 both work independently — new and existing accounts are gated, and Groups-verified accounts are correctly exempted.

---

## Phase 5: User Story 3 - Personal email domains are rejected (Priority: P2)

**Goal**: Personal-provider domains (and any admin-added abusive domain) are rejected before a code is ever sent, with a clear reason shown to the user.

**Independent Test**: Submit `gmail.com` and confirm immediate rejection with no code sent; submit a non-blocklisted domain and confirm it's accepted; add a domain to the blocklist and confirm it's then rejected the same way (quickstart.md Scenario 3).

### Tests for User Story 3

- [X] T029 [P] [US3] Unit test: `domain_verification_service` blocklist check rejects every default blocklisted domain (`gmail.com`, `yahoo.com`, `outlook.com`, `hotmail.com`, `icloud.com`, `protonmail.com`) without generating an OTP, in `services/api/tests/unit/test_domain_verification_service.py`

### Implementation for User Story 3

- [X] T030 [US3] Verify/adjust the `blocklisted_domain` error message surfaced by `OrgAccessVerifyForm.tsx` (T016) so it clearly states the reason (not a generic error) — depends on T016
- [X] T031 [US3] Manually run quickstart.md Scenario 3, including adding a test domain to `group_domain_blocklist` via the existing Groups admin mechanism and confirming it's rejected for this gate too

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Edge cases and validation spanning multiple stories

- [X] T032 [P] Unit test for the FR-010 conflict path: `email_already_verified_elsewhere` returned only at confirm-time, never at request-time, in `services/api/tests/unit/test_org_access_service.py` (quickstart.md Scenario 7)
- [X] T033 [P] Add read-only `org_verified_at`/`org_verified_domain` display to the user detail view in `apps/admin` (no new admin workflow, per Out-of-Scope)
- [X] T034 Run `cd services/api && uv run pytest tests/unit/test_org_access_service.py tests/unit/test_domain_verification_service.py tests/unit/test_group_service.py -v` and confirm all pass
- [X] T035 Run the full quickstart.md validation guide end-to-end (all 7 scenarios) as a final pre-merge check — Scenarios 2 and 6 live-verified via real browser against the local stack (Scenario 2 via a real pre-existing account; Scenario 6 confirmed the suspension screen precedes the org gate per FR-012); live testing of Scenario 2/1's coverage also caught and fixed a real gap where the org gate was missing from `/dashboard`, `(driver)/*`, and `(passenger)/*` (only `(app)/*` had it), reverified live post-fix. Scenarios 1, 3, 4, 5, 7 are covered by the automated suite (48/48 relevant tests, 168/168 full backend suite) and were not separately re-run live this pass.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (T004 in particular gates everything touching `profiles.org_verified_at`)
- **User Story 1 (Phase 3)**: Depends on Foundational only — no dependency on US2/US3
- **User Story 2 (Phase 4)**: Depends on Foundational; reuses US1's `OrgAccessVerifyForm`/redirect pattern (T018) but is independently testable via its own login-path routes (T024/T025)
- **User Story 3 (Phase 5)**: Depends on Foundational; reuses US1's `OrgAccessVerifyForm` (T016) for the error-message task, otherwise independent
- **Polish (Phase 6)**: Depends on all three stories being complete

### Parallel Opportunities

- T002, T003 (Setup) in parallel
- T005, T007, T010, T011 (Foundational) in parallel — different files
- T013, T014 (US1 tests) in parallel
- T022 (US2 test) can run alongside US1 implementation once T006 is done
- T029 (US3 test) can run alongside US1/US2 implementation once T005 is done
- T032, T033 (Polish) in parallel

---

## Parallel Example: Foundational Phase

```bash
# After T004 (migration) completes, launch together:
Task: "Extract shared OTP primitives into services/api/app/services/domain_verification_service.py"
Task: "Create org_access.py Pydantic models in services/api/app/models/org_access.py"
Task: "Extend profile_service._format_profile with org_verified_at/org_verified_domain"
Task: "Add org_verified_at/org_verified_domain to packages/shared/src/types/user.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (T004 migration is the critical path — everything else in this phase can parallelize around it)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Run quickstart.md Scenario 1 (T021) independently
5. This alone gates all *new* signups — demo-able as the MVP slice of the org-only-access pivot

### Incremental Delivery

1. Setup + Foundational → backend core testable via API client
2. Add User Story 1 → new signups gated (MVP)
3. Add User Story 2 → existing accounts gated, Groups auto-credit and backfill verified
4. Add User Story 3 → blocklist/rejection UX polished, admin-extension path confirmed
5. Polish → FR-010 edge case covered, admin visibility added, full quickstart re-run

---

## Notes

- [P] tasks touch different files with no ordering dependency between them
- T004 (migration) is the single hardest blocking dependency — nothing that reads/writes `profiles.org_verified_at` can proceed until it's applied locally
- Per feedback_no_implement_after_plan_approval: this tasks.md is a planning artifact, not authorization to start `/speckit-implement` — a separate explicit go-ahead is required
