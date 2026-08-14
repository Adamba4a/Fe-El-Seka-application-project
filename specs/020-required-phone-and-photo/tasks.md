# Tasks: Required Phone Number & Profile Photo (Email+OTP Only)

**Input**: Design documents from `specs/020-required-phone-and-photo/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included for the backend (unit tests), per the existing repo convention (`services/api/tests/unit`) — not explicitly requested for frontend, so frontend verification relies on the quickstart.md manual scenarios.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1/US2/US3), or none for Setup/Foundational/Polish

---

## Phase 1: Setup

No new dependencies, tooling, or project scaffolding is required — this feature extends existing, already-wired infrastructure (see [research.md](./research.md) "ground-truth correction"). Setup is limited to confirming the target branch is checked out.

- [ ] T001 Confirm branch `020-required-phone-photo` is checked out and up to date with `origin/main` (no new tooling needed)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: End-to-end plumbing for `phone_number` — DB column through to API response — that both User Story 1 (new signup) and User Story 3 (existing-user gate) depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T002 Create migration `supabase/migrations/<timestamp>_add_phone_number_to_profiles.sql` adding nullable `phone_number TEXT` column to `profiles` plus `CHECK (phone_number IS NULL OR phone_number ~ '^\+[1-9][0-9]{6,14}$')` per [data-model.md](./data-model.md)
- [ ] T003 Apply the new migration to the local Supabase stack (`supabase migration up` / `supabase db reset` per repo convention) and confirm `phone_number` column exists via `\d profiles`
- [ ] T004 [P] Add `phone_number: str | None = None` with a format `field_validator` (regex `^\+[1-9]\d{6,14}$`) to `ProfileUpdate` in `services/api/app/models/profile.py`
- [ ] T005 [P] Add `phone_number: str | None` to `ProfileResponse` in `services/api/app/models/profile.py`
- [ ] T006 [US-shared] Extend `update_profile(user_id, display_name, language_preference, phone_number=None)` in `services/api/app/services/profile_service.py` to include `phone_number` in the `updates` dict when provided (depends on T004)
- [ ] T007 [US-shared] Add `phone_number` to the dict returned by `_format_profile()` in `services/api/app/services/profile_service.py` (depends on T005)
- [ ] T008 [US-shared] Pass `body.phone_number` through to `profile_service.update_profile(...)` in the `update_profile` route handler, `services/api/app/api/profiles/router.py` (depends on T006)
- [ ] T009 [P] Add `phone_number: string | null` to the `Profile` interface in `packages/shared/src/types/user.ts`
- [ ] T010 [P] Add `phone_number?: string` to the `ProfileUpdate` interface in `packages/shared/src/types/user.ts`

**Checkpoint**: Backend accepts and returns `phone_number` on `PUT /me`, `GET /me`, `POST /setup` responses. User story implementation can now begin.

---

## Phase 3: User Story 1 - New user completes signup with phone and photo (Priority: P1) 🎯 MVP

**Goal**: A new user cannot finish onboarding without providing both a phone number and a profile photo.

**Independent Test**: Sign up a brand-new email address, verify via OTP, select a role, and confirm the app blocks submission at `/profile` until both a phone number and a photo are provided (see [quickstart.md](./quickstart.md) Scenario 1).

### Implementation for User Story 1

- [ ] T011 [US1] Add `phoneNumber` state and a plain-text phone input to `apps/main/src/app/(onboarding)/profile/page.tsx` (no OTP/verification UI — plain input matching the backend format)
- [ ] T012 [US1] In `handleSubmit`'s validation chain in `apps/main/src/app/(onboarding)/profile/page.tsx`, add a phone-format check (block submit with an error message on failure) and a `if (!photo)` required-photo check, positioned alongside the existing name/ID-document checks
- [ ] T013 [US1] Extend the `updateMe(session.access_token, { display_name: ... })` call in `apps/main/src/app/(onboarding)/profile/page.tsx` to include `phone_number: phoneNumber` (depends on T011, T012, and Foundational T008/T010)
- [ ] T014 [P] [US1] Add new i18n keys to `apps/main/messages/en.json` and `apps/main/messages/ar.json` under `onboarding.profile`: phone field label/placeholder, phone-format error, photo-required error

**Checkpoint**: User Story 1 is fully functional and independently testable — run quickstart.md Scenario 1.

---

## Phase 4: User Story 2 - Sign-in remains email+OTP only (Priority: P1)

**Goal**: No phone-based sign-in path exists anywhere in the product, including vestigial configuration.

**Independent Test**: Visit `/login` and confirm only email-based sign-in is offered; confirm no SMS provider configuration remains in the repo (see [quickstart.md](./quickstart.md) Scenario 2).

### Implementation for User Story 2

- [ ] T015 [P] [US2] Remove the `[auth.sms]` block from `supabase/config.toml` (vestigial — unused by any code path; see [research.md](./research.md))
- [ ] T016 [P] [US2] Remove the `TWILIO_*` placeholder lines (and the "Twilio SMS" comment header) from `.env.example` (root)
- [ ] T017 [P] [US2] Remove the `TWILIO_*` placeholder lines (and comment header) from `services/api/.env.example`
- [ ] T018 [US2] Verify `apps/main/src/app/(auth)/login/page.tsx` and `otp/page.tsx` have no phone-related UI or logic (expected: no changes needed — confirm only)

**Checkpoint**: `grep -ri twilio` / `grep -ri "auth.sms"` across the repo returns zero hits. Run quickstart.md Scenario 2.

---

## Phase 5: User Story 3 - Existing users are prompted to complete their profile (Priority: P2)

**Goal**: Any signed-in user whose profile is missing `phone_number` and/or a photo is routed to a non-skippable completion screen before reaching any other part of the app.

**Independent Test**: Null out `phone_number` and/or `profile_photo_path` on an existing profile row, sign in, and confirm the user is routed to `/complete-profile` with no way to skip (see [quickstart.md](./quickstart.md) Scenario 3 and 4).

### Implementation for User Story 3

- [ ] T019 [US3] Extend `ProfileForm` (`apps/main/src/components/profile/ProfileForm.tsx`) with an optional `showPhone` prop and phone input/validation, reusing the existing `zod` schema pattern, so it can render just the missing field(s) prefilled from current profile data
- [ ] T020 [US3] Create `apps/main/src/app/(auth)/complete-profile/page.tsx`, modeled on `apps/main/src/app/(auth)/set-password/page.tsx`'s structure (`"use client"`, `<Suspense>`, on-mount `supabase.auth.getSession()` check redirecting to `/login` if none) — **no "skip for now" button** — using the extended `ProfileForm` from T019, submitting via `updateMe` (+ `uploadPhoto` when photo is the missing field) (depends on T019, Foundational T008/T010)
- [ ] T021 [US3] In `apps/main/src/app/page.tsx`, extend the `profiles` `select` from `"role, verification_status"` to `"role, verification_status, phone_number, profile_photo_path"`; add a redirect to `/complete-profile` when either is missing, positioned after the `!profile` → `/role-select` check and before the `verification_status` branches (depends on Foundational T002/T003)
- [ ] T022 [US3] In `apps/main/src/app/auth/callback/route.ts`, after the existing `meRes.status === 404` check, inspect the `200` JSON body for missing `phone_number`/`profile_photo_url` and redirect to `/complete-profile` accordingly (depends on Foundational T005/T007)
- [ ] T023 [US3] Add a phone display/edit row to `apps/main/src/app/(app)/settings/profile/ProfileEditor.tsx` (new row alongside existing profile fields, wired through the extended `ProfileForm` from T019) so users can view/update their phone number after signup (depends on T019)
- [ ] T024 [P] [US3] Add new i18n keys to `apps/main/messages/en.json` and `apps/main/messages/ar.json` for: `complete-profile` page (title, subtitle, submit label, field errors), `profileForm` phone field label/placeholder, `settings.profile.editor` phone row label

**Checkpoint**: All three user stories are independently functional. Run quickstart.md Scenarios 3 and 4.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Backend test coverage, documentation, and full end-to-end validation across all stories.

- [ ] T025 [P] Add unit tests for `ProfileUpdate.phone_number` format validation (valid/invalid formats, `None` allowed) in `services/api/tests/unit/test_profile_service.py` (or the appropriate existing test file for profile models)
- [ ] T026 [P] Add a unit test confirming `update_profile` persists `phone_number` when provided, in the same test file as T025
- [ ] T027 Run `services/api/.venv/Scripts/python -m pytest tests/unit -q` — full suite must be green
- [ ] T028 [P] Add a one-line "Superseded by 020-required-phone-and-photo" note atop `specs/019-phone-signup/spec.md` if that spec file exists in this repo's history (skip if the 019 spec directory isn't present on this branch)
- [ ] T029 Run all quickstart.md scenarios (1–4) end-to-end against the local stack
- [ ] T030 Run the config/grep verification commands from quickstart.md ("Backend verification" section) and confirm zero `TWILIO`/`auth.sms` matches

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS User Story 1 and User Story 3 (both need `phone_number` plumbed through the backend/shared types). User Story 2 does not depend on Foundational.
- **User Story 1 (Phase 3)**: Depends on Foundational.
- **User Story 2 (Phase 4)**: Independent — can run in parallel with Foundational/US1/US3 (touches only config files and does a verification pass).
- **User Story 3 (Phase 5)**: Depends on Foundational. Independent of User Story 1 (different pages), though both call the same `updateMe`/`ProfileForm` surface — no file conflicts since US1 edits the onboarding page and US3 edits the gate page + settings page + `ProfileForm.tsx` (T019 is the one shared-file task).
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### Parallel Opportunities

- T004/T005 (Pydantic model fields) can run in parallel with each other, and with T009/T010 (TS types).
- T015/T016/T017 (US2 config cleanup) can all run in parallel — three different files.
- T025/T026/T028 (Polish) can run in parallel.

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 (trivial) + Phase 2 (Foundational — backend/shared-type plumbing).
2. Complete Phase 3 (User Story 1 — required phone+photo at signup). **STOP and VALIDATE** via quickstart.md Scenario 1.
3. This alone satisfies the core business objective for *new* accounts.

### Incremental Delivery

1. Foundational → User Story 1 (MVP: new signups compliant).
2. User Story 2 (config cleanup — can be done anytime, low risk, no dependencies).
3. User Story 3 (existing-user gate — closes the gap for pre-existing accounts).
4. Polish (tests, full E2E, docs).

### Commit & Push

Per project convention, commit and push to `origin/020-required-phone-photo` after each phase (or logical group of tasks) completes, so the work is reviewable from another IDE.
