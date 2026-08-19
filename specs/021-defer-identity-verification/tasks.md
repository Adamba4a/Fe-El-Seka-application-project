---

description: "Task list for Deferred Identity Verification (Progressive KYC)"
---

# Tasks: Deferred Identity Verification (Progressive KYC)

**Input**: Design documents from `/specs/021-defer-identity-verification/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Not explicitly requested in the spec — no dedicated test tasks are generated. Validation is via `quickstart.md`'s manual scenarios (Polish phase) and the project's existing `pytest` suite for regression coverage.

**Organization**: Tasks are grouped by user story (US1/US2/US3, per spec.md's P1/P1/P2 priorities) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are exact, per plan.md's Project Structure

---

## Phase 1: Setup

**Purpose**: The one piece of infrastructure every downstream task in US1 needs — the new column must exist before any code can read/write it.

- [x] T001 Create Supabase migration `supabase/migrations/<timestamp>_add_date_of_birth_to_profiles.sql` adding a nullable `date_of_birth DATE` column to `profiles` (no default, no backfill, no CHECK constraint — modeled on `supabase/migrations/20260814000010_add_phone_number_to_profiles.sql`), then apply it to the local Supabase stack *(completed 2026-08-19 as `20260819000002_add_date_of_birth_to_profiles.sql`, applied to local Supabase and verified in schema)*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared type/schema changes that both the signup flow (US1) and any later profile read (US3's persistent affordance reads `verification_status`, already present) depend on.

**⚠️ CRITICAL**: T002/T003 must complete before US1 implementation begins.

- [x] T002 [P] Add `date_of_birth?: string` to `Profile` and `ProfileSetup` in `packages/shared/src/types/user.ts` *(completed 2026-08-19 — corrected during implementation: `ProfileSetup` in this codebase carries only `role`+`display_name` at role-select time; the "collected shortly after signup" precedent (`phone_number`) lives on `ProfileUpdate`/`Profile` instead, so `date_of_birth` was added to `Profile` and `ProfileUpdate`, not `ProfileSetup`, to stay consistent with the actual signup flow)*
- [x] T003 [P] Add `date_of_birth: date` (required) to `ProfileSetup` and `date_of_birth: date | None` (owner-only) to `ProfileResponse` in `services/api/app/models/profile.py`; confirm `PublicProfileResponse` in the same file does **not** gain the field (Constitution: national-ID-grade data must never be publicly exposed) *(completed 2026-08-19 — same correction as T002: `date_of_birth: date | None` added to `ProfileUpdate` (not `ProfileSetup`) and `date_of_birth: str | None` added to `ProfileResponse`; wired through `update_profile()`/`_format_profile()` in `profile_service.py` and the `PUT /me` router; `PublicProfileResponse` and `get_public_profile()` confirmed untouched)*
- [x] T004 [P] Delete `(auth)/complete-profile` route and its references — `apps/main/src/app/(auth)/complete-profile/page.tsx` removed; the `redirect("/complete-profile")` branch and the now-unused `phone_number`/`profile_photo_path` fields removed from the `.select()` in `apps/main/src/app/page.tsx`; the orphaned `auth.completeProfile` keys removed from `apps/main/messages/en.json` and `apps/main/messages/ar.json` *(completed 2026-08-19, ahead of this task list)*

**Checkpoint**: Foundation ready — `date_of_birth` exists end-to-end in schema/types; US1 implementation can begin.

---

## Phase 3: User Story 1 - New user signs up in seconds and starts browsing (Priority: P1) 🎯 MVP

**Goal**: Signup collects only phone, display name, and date of birth; on success the user lands directly in normal app browsing — no photo, no documents, no blocking screen.

**Independent Test**: Sign up a brand-new email address, provide phone/name/date-of-birth, and confirm the very next screen is the normal browsing experience (search for passengers, home for drivers) — not a document-upload or photo screen (quickstart.md Scenario 1).

### Implementation for User Story 1

- [x] T005 [US1] Add minimum-age validation for `date_of_birth` in the signup path of `services/api/app/services/profile_service.py` (reject signups below the minimum-age threshold with a clear message; mirrors the existing `phone_number` validation pattern in the same service) — depends on T003 *(completed 2026-08-19 — `MIN_SIGNUP_AGE_YEARS = 18`, `_calculate_age()` helper, enforced in `update_profile()`; covered by 3 new unit tests)*
- [x] T006 [US1] Persist `date_of_birth` on profile creation in the signup path of `services/api/app/services/profile_service.py` — depends on T003, T005 *(completed 2026-08-19 — same change as T005, `date_of_birth` now persisted via `update_profile()`/router)*
- [x] T007 [US1] Rewrite `apps/main/src/app/(onboarding)/profile/page.tsx` to collect only display name, phone number, and date of birth; remove the photo upload, front/back ID, and license fields, the progress-step bar tied to them, and the post-submit `pending_review` confirmation screen; on successful submit, navigate straight into the app (`/search` for passengers, `/` for drivers) instead of blocking — depends on T002 *(completed 2026-08-19 — page fully rewritten, underage error surfaced from the fixed `updateMe()` error-unwrap)*
- [x] T008 [US1] Remove the `verification_status === "unverified" → redirect("/profile")` gate in `apps/main/src/app/page.tsx` so `unverified`, `pending_review`, and `verified` users all fall through to their normal role-based routing; keep the `rejected` and `suspended` branches unchanged *(completed 2026-08-19 — also deleted the now-dead `components/PendingApprovalWait.tsx`, its only translation namespace was removed in T011)*
- [x] T009 [US1] Remove the verified-only redirect guard in `apps/main/src/app/(passenger)/layout.tsx` so passenger routes no longer require `verification_status === "verified"` to render *(completed 2026-08-19)*
- [x] T010 [US1] Remove the `PASSENGER_VERIFIED_PREFIXES` gate (and the now-unused `isPassengerRoute` check tied to it) in `apps/main/src/middleware.ts` *(completed 2026-08-19 — `language_preference` locale-resolution query preserved)*
- [x] T011 [P] [US1] Update the `onboarding.profile` section of `apps/main/messages/en.json` and `apps/main/messages/ar.json` for the lightweight form (add date-of-birth label/placeholder/validation-error strings; remove the now-unused photo/front-ID/back-ID/license-specific keys that only this page consumed) *(completed 2026-08-19 — `onboarding.pendingApproval` also removed, replaced by `onboarding.verificationRequired` scaffolded ahead of Phase 4)*

**Checkpoint**: User Story 1 is fully functional and independently testable — new signups reach browsing without any document/photo step (quickstart.md Scenarios 1 and 2).

---

## Phase 4: User Story 2 - Unverified user is blocked only at the point of commitment (Priority: P1)

**Goal**: Booking, ride-posting, and booking-acceptance attempts by unverified users are blocked with a clear verification prompt instead of a generic error or silent failure.

**Independent Test**: As an unverified passenger, attempt to book any open ride and confirm the booking is blocked with a message directing to verification (not a generic error). As an unverified driver, attempt to post a new ride and confirm the same (quickstart.md Scenario 3).

### Implementation for User Story 2

- [ ] T012 [US2] Verify `POST /api/rides` (`create_ride`), `POST /api/rides/{ride_id}/bookings/{booking_id}/confirm`, and `.../reject` in `services/api/app/api/rides/router.py` depend on `get_current_verified_driver`, and `POST /api/bookings` in `services/api/app/api/bookings/router.py` depends on `get_current_verified_passenger` — regression checkpoint only; per research.md these guards already exist, so no code change is expected here, only confirmation that Phase 3's gate removals didn't disturb backend enforcement
- [ ] T013 [P] [US2] Create `VerificationRequiredModal` in `apps/main/src/components/verification/VerificationRequiredModal.tsx` that renders the blocked-action message and a link to the role-appropriate verify page (`/verify-id` or `/driver/verify-documents`)
- [ ] T014 [US2] Catch the `403 {"error":"verification_required"}` response from the booking-creation call in `apps/main/src/lib/api/bookings.ts` and surface `VerificationRequiredModal` from the ride detail page's "Book" action — depends on T013
- [ ] T015 [US2] Catch the `403 {"error":"verification_required"}` response from the ride-creation call in `apps/main/src/lib/api/rides.ts` and surface `VerificationRequiredModal` from the driver's ride-creation form — depends on T013
- [ ] T016 [US2] Catch the `403 {"error":"verification_required"}` response from the booking confirm/reject calls in `apps/main/src/lib/api/rides.ts` and surface `VerificationRequiredModal` from the driver's incoming-bookings screen — depends on T013

**Checkpoint**: User Stories 1 AND 2 both work independently — blocked actions show the verification prompt instead of proceeding or erroring generically.

---

## Phase 5: User Story 3 - Persistent "Verify identity" entry point and document submission (Priority: P2)

**Goal**: An always-visible "Verify identity" affordance lets any unverified user reach the existing document-submission flow proactively, not only after being blocked or rejected.

**Independent Test**: As a freshly-signed-up unverified user, locate the "Verify identity" affordance without having attempted a gated action first, submit front/back ID (and license, if a driver), and confirm a "submitted" confirmation is shown while the rest of the app remains usable (quickstart.md Scenario 4).

### Implementation for User Story 3

- [ ] T017 [US3] Add a persistent "Verify identity" badge/button to `apps/main/src/components/layout/TopBar.tsx`, shown when `profile.verification_status` is `unverified`, `pending_review`, or `rejected`, linking to `/verify-id` (passenger) or `/driver/verify-documents` (driver) — `AppShell.tsx` already fetches and passes `profile` down, no new data fetch needed
- [ ] T018 [P] [US3] Confirm `apps/main/src/app/(onboarding)/verify-id/page.tsx` and `apps/main/src/app/(onboarding)/driver/verify-documents/page.tsx` correctly serve `unverified` (not only `rejected`) users when navigated to directly — no gating code should redirect an `unverified` visitor away from either page; fix if any does
- [ ] T019 [P] [US3] Confirm that approval flips a signed-in user's gated-action access without re-login — `AppShell.tsx`'s existing profile fetch must reflect the new `verification_status` on the next relevant navigation; document or fix if it currently caches a stale value

**Checkpoint**: All three user stories are independently functional — the affordance is reachable from anywhere and the reused document pipeline behaves correctly for unverified, pending, approved, and rejected states (quickstart.md Scenarios 4 and 6).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation and regression safety net across all three stories.

- [ ] T020 [P] Run all six `specs/021-defer-identity-verification/quickstart.md` validation scenarios end-to-end against the local Docker Compose stack, including Scenario 5 (legacy grandfathered accounts) and Scenario 6 (rejected-account resubmission)
- [ ] T021 [P] Sweep `apps/main/messages/en.json` and `apps/main/messages/ar.json` for any remaining stale keys from the old bundled onboarding flow left over after T011 (e.g. `onboarding.profile.errors.photoRequired`/`idRequired`/`licenseRequired` if fully unused elsewhere)
- [ ] T022 [P] Run `pytest` in `services/api` and lint/typecheck (`npm run lint`, `tsc --noEmit`) in `apps/main` to confirm the gate removals and model changes introduce no regressions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup (T001) for T003's column to exist; T002/T004 have no such dependency. Blocks all of US1.
- **User Story 1 (Phase 3)**: Depends on Foundational (T002, T003). No dependency on US2/US3.
- **User Story 2 (Phase 4)**: Depends on Foundational only for correctness of the regression checkpoint (T012); does not depend on US1's frontend changes to function, but is only meaningfully testable once US1 lets an unverified user reach a gated action in the first place (booking/posting UI) — implement after US1 for a sane manual-test flow, though the code changes themselves are independent files.
- **User Story 3 (Phase 5)**: Same relationship as US2 — independent files, but proactive verification only matters once US1 lets unverified users linger in the app instead of being forced through the old bundled flow.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Parallel Opportunities

- T002 and T003 (Foundational) can run in parallel — different files/languages.
- T011 (US1 translations) can run in parallel with T008–T010 (US1 gate removals) — different files.
- T013 (US2 modal component) can start in parallel with T012 (US2 backend checkpoint) — different files; T014–T016 each depend on T013 but not on each other, so once T013 lands they can run in parallel.
- T018 and T019 (US3) can run in parallel with T017 — different files.
- T020, T021, T022 (Polish) can all run in parallel.

---

## Parallel Example: User Story 2

```bash
Task: "Create VerificationRequiredModal in apps/main/src/components/verification/VerificationRequiredModal.tsx"
Task: "Verify backend guards on rides/bookings routers (regression checkpoint, no code change expected)"
# After the modal lands:
Task: "Wire 403 handling into lib/api/bookings.ts"
Task: "Wire 403 handling into lib/api/rides.ts (ride creation)"
Task: "Wire 403 handling into lib/api/rides.ts (booking confirm/reject)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (T001) and Phase 2 (T002–T004; T004 already done).
2. Complete Phase 3 (US1, T005–T011).
3. **STOP and VALIDATE**: quickstart.md Scenarios 1 and 2 — signup reaches browsing directly, underage signup is rejected.
4. This alone already delivers the feature's core value (reduced signup friction) even before US2/US3 land, since the old blanket gates are gone.

### Incremental Delivery

1. Setup + Foundational → date_of_birth exists end-to-end.
2. US1 → signup is lightweight, browsing is unblocked → validate → this is the MVP.
3. US2 → gated actions show a real prompt instead of an unhandled 403 → validate.
4. US3 → users can self-serve verification proactively, not only when blocked or rejected → validate.
5. Polish → full quickstart sweep + regression check.

---

## Notes

- [P] tasks touch different files with no dependency on an incomplete task.
- No test tasks were generated — the spec did not request TDD/dedicated tests, and this repo has no existing frontend test runner (consistent with spec 020's precedent); `quickstart.md` scenarios plus the existing `pytest` suite (T022) are the verification net.
- T004 is already complete (done ahead of this task list, per user request) — left in the list, checked, for traceability against plan.md's Project Structure.
- Avoid: reintroducing the deleted `/complete-profile` route or the bundled photo/document fields into `(onboarding)/profile/page.tsx` — both are explicitly removed, not made conditional, per Technical Considerations in spec.md.
