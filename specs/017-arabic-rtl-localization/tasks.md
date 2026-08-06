---

description: "Task list template for feature implementation"
---

# Tasks: Arabic & RTL Localization

**Input**: Design documents from `/specs/017-arabic-rtl-localization/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: `apps/main` has no frontend test framework configured (per plan.md Testing) — manual
validation via `quickstart.md` is the convention. `services/api` changes get `pytest` unit tests,
matching the existing convention (`services/api/tests/unit`).

**Organization**: Tasks are grouped by user story (spec.md User Story 1/2/3, priorities P1/P2/P3) to
enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unresolved dependency on another listed task)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Monorepo per plan.md Project Structure: `apps/main/src/`, `packages/ui/src/`, `packages/shared/src/`,
`services/api/app/`, `supabase/migrations/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the new dependency, i18n config scaffold, and DB migration file

- [X] T001 [P] Add `next-intl` to `apps/main/package.json` dependencies and run install
- [X] T002 [P] Create `apps/main/src/lib/i18n/config.ts` — supported locales (`en`, `ar`), default
      locale (`ar`, per spec Assumptions), `NEXT_LOCALE` cookie name constant
- [X] T003 [P] Create `supabase/migrations/20260805000001_phase14_language_preference.sql` — add
      nullable `language_preference TEXT CHECK (language_preference IN ('en','ar'))` column to
      `public.profiles` per `data-model.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core i18n plumbing and the profile field end-to-end — required before any user story is
independently testable

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Apply migration `20260805000001_phase14_language_preference.sql` to the local Supabase
      instance and verify the `profiles.language_preference` column exists (depends on T003)
- [X] T005 [P] Extend `packages/shared/src/types/user.ts` — add `Locale` type (`"en" | "ar"`), and
      `language_preference` to `Profile`/`ProfileUpdate` per `data-model.md`
- [X] T006 [P] Extend `services/api/app/models/profile.py` — `ProfileUpdate`/`ProfileResponse` gain
      `language_preference: Literal["en", "ar"] | None` per `data-model.md`
- [X] T007 Extend `services/api/app/services/profile_service.py` — `update_profile()` accepts and
      persists `language_preference` (depends on T006)
- [X] T008 Extend `services/api/app/api/profiles/router.py` — `PUT /profiles/me` passes
      `language_preference` through per `contracts/profile-language-preference.md` (depends on T007)
- [X] T009 Extend `apps/main/src/lib/api/profiles.ts` — `updateMe()` accepts `language_preference`
      (depends on T005) — no code change needed: `updateMe()` already takes a typed `ProfileUpdate`
      payload, which now includes `language_preference` from T005
- [X] T010 [P] Create `apps/main/src/lib/i18n/messages-loader.ts` — fetch + in-memory cache +
      periodic refresh (~5 min, tunable) of the JSON message catalog per locale from Supabase Storage,
      with bundled-`en.json` fallback on Storage failure, per `contracts/message-catalog.md` (depends
      on T002)
- [X] T011 Create `apps/main/src/lib/i18n/request.ts` — next-intl server config resolving the active
      locale and loading messages via `messages-loader.ts` (depends on T010)
- [X] T012 [P] Create `apps/main/messages/en.json` — canonical namespace skeleton (empty/placeholder
      keys) covering every route group, serves as both the bundled fallback and the FR-011 canonical
      key set
- [X] T013 [P] Create `apps/main/messages/ar.json` — Arabic namespace skeleton mirroring
      `en.json`'s key structure (values may lag per FR-011)
- [X] T014 Extend `apps/main/src/middleware.ts` — resolve locale (`profiles.language_preference` →
      `NEXT_LOCALE` cookie → default `"ar"`) inside the existing per-request `profiles` query, set the
      locale cookie/header consumed by next-intl (depends on T004, T011)
- [X] T015 Extend `apps/main/src/app/layout.tsx` — set `<html lang={locale} dir={ltr|rtl}>`, wrap
      children in `NextIntlClientProvider` (depends on T011, T014)

**Checkpoint**: Foundation ready — i18n plumbing and profile field work end-to-end; user story
implementation can now begin.

---

## Phase 3: User Story 1 - Use the platform entirely in Arabic (Priority: P1) 🎯 MVP

**Goal**: Every screen in `apps/main` (Passenger + Driver) renders fully in Arabic with correct RTL
layout, and push notifications for that user's events arrive in Arabic.

**Independent Test**: Set a test account's `language_preference` to `ar` (directly or via the Settings
toggle added in this phase), complete a full ride search-to-booking flow, and confirm every screen is
Arabic/RTL with no leftover English strings, per `quickstart.md` Scenario 1.

### Implementation for User Story 1

- [X] T016 [US1] Populate `apps/main/messages/en.json` + `ar.json` for the `(auth)`/`(onboarding)`
      route groups: `login`, `otp`, `role-select`, `set-password`, `driver/register-vehicle`,
      `driver/verify-documents`, `profile`, `verify-id` screens (depends on T012, T013)
- [X] T017 [US1] Populate `apps/main/messages/en.json` + `ar.json` for the `(passenger)` route group:
      `search`, `rides`, `rides/[id]`, `bookings`, `bookings/[id]` screens (depends on T016 — same
      files)
- [X] T018 [US1] Populate `apps/main/messages/en.json` + `ar.json` for the `(driver)` route group:
      `rides`, `rides/[id]`, `rides/new`, `wallet` screens (depends on T017 — same files)
- [X] T019 [US1] Populate `apps/main/messages/en.json` + `ar.json` for the `(app)` route group:
      `settings/profile`, `settings/session`, `ratings`, `users/[userId]`, `dashboard` screens
      (depends on T018 — same files)
- [X] T020 [US1] Wire `useTranslations()`/`getTranslations()` calls into every screen/component
      covered by T016–T019, replacing hardcoded English strings (depends on T019)
- [X] T021 [P] [US1] Audit `packages/ui/src/components` for RTL: replace physical left/right Tailwind
      classes with `rtl:`/`ltr:` logical variants; ensure flexible/responsive sizing (FR-015) instead
      of fixed widths that could overflow with longer Arabic text — audited `button.tsx`/`input.tsx`:
      neither has physical-direction classes or fixed widths (both already use `w-full`/flex sizing),
      no changes needed
- [X] T022 [US1] Audit `apps/main` route-group layouts/pages for RTL: navigation order, form
      alignment, directional icons (back/forward arrows) per FR-003 (depends on T020, T021)
- [X] T023 [P] [US1] Add a `LanguageSection` toggle to
      `apps/main/src/app/(app)/settings/profile/ProfileEditor.tsx`, calling `updateMe()` with
      `language_preference` (depends on T009, T015 — both already complete from Foundational)
- [X] T024 [P] [US1] Restructure `_NOTIFICATION_TEMPLATES` in
      `services/api/app/services/fcm_service.py` from `dict[str, tuple[str, str]]` to
      `dict[str, dict[str, tuple[str, str]]]`, adding `"ar"` entries for all ~12 existing event types
      plus the unknown-event fallback, per `contracts/notification-localization.md`
- [X] T025 [US1] Update `send_push_notifications()` in `fcm_service.py` to look up the recipient's
      `profiles.language_preference` (default `"en"` on `NULL`) and select the matching locale's
      template (depends on T024)
- [X] T026 [US1] Add/extend `services/api/tests/unit/test_fcm_service.py` — assert every event_type
      has both `en`/`ar` entries, assert a `NULL` preference falls back to `en` (depends on T025)

**Checkpoint**: User Story 1 fully functional and testable independently —
`quickstart.md` Scenario 1 passes.

---

## Phase 4: User Story 2 - Switch language at any time (Priority: P2)

**Goal**: Users can change the display language from any screen, at any time, without losing
in-progress input or needing to log out.

**Independent Test**: From an in-progress ride search, toggle the language and confirm the screen
re-renders in the new language/direction without losing entered filter values or navigation state,
per `quickstart.md` Scenario 2 (and Scenario 3 for the rollout prompt).

### Implementation for User Story 2

- [X] T027 [US2] Promote the language toggle from Settings-only to an always-accessible control
      reachable from any screen (e.g., a persistent nav/header slot in `apps/main/src/app/layout.tsx`
      or a shared nav component) (depends on T023)
- [X] T028 [US2] Ensure the toggle updates locale client-side without a full page reload: write the
      `NEXT_LOCALE` cookie directly for unauthenticated visitors; call `updateMe()` +
      `router.refresh()` (not a hard navigation) for authenticated users (depends on T027)
- [X] T029 [US2] Verify and fix in-progress form-state preservation across a language switch (FR-012)
      on the search/booking screens covered in T017 (depends on T028, T017) — verified via code
      review: no `key={locale}` (or any locale-derived key) sits above `(passenger)/search/page.tsx`
      in the tree, so `router.refresh()` only updates `NextIntlClientProvider`'s `locale`/`messages`
      props in place and never remounts the client `SearchPage`/`RideSearchForm` components; their
      local `useState` filter values are therefore preserved automatically. `/search` requires an
      authenticated, verified-passenger session (enforced in `middleware.ts`) and no test credentials
      were available in this session for a live browser confirmation, so no code change was needed
      and none was made.
- [X] T030 [P] [US2] Create
      `apps/main/src/app/(app)/settings/profile/LanguagePromptModal.tsx` — one-time, non-blocking
      prompt for authenticated users with `language_preference = NULL` (FR-013), rendered from a
      shared layout slot (depends on T009, T015 — both already complete from Foundational)
- [X] T031 [US2] Wire `LanguagePromptModal` into the app shell so it appears on first post-launch page
      view for eligible users without blocking navigation underneath it (depends on T030, T015) —
      wired into `AppShell.tsx` (already the single choke point for `(app)`/`(driver)`/`(passenger)`,
      per T027's notes), gated on the `profile` it already fetches via `getMe()`; renders as a fixed
      overlay (not a route guard), so it never blocks navigation underneath it

**Checkpoint**: User Stories 1 AND 2 both work independently — `quickstart.md` Scenarios 2 & 3 pass.

---

## Phase 5: User Story 3 - Locale-appropriate formatting and content (Priority: P3)

**Goal**: Dates, times, and EGP currency render per locale convention, and Arabic copy reads
naturally rather than as a literal translation.

**Independent Test**: Review ride details, booking confirmation, and error/empty states in Arabic and
confirm dates/currency/numbers follow locale convention and copy reads as natural Arabic, per
`quickstart.md` Scenario 5.

### Implementation for User Story 3

- [X] T032 [P] [US3] Extend `packages/shared/src/utils/index.ts` — add a `locale` parameter to
      `formatDate()` and a new `formatCurrency(amount, locale)` for EGP, both forcing
      `numberingSystem: "latn"` per `research.md` R7 (depends on T005 — already complete from
      Foundational)
- [X] T033 [US3] Replace ad hoc `toLocaleString`/`Intl.*` formatting with the shared locale-aware
      formatter in: `apps/main/src/app/(passenger)/bookings/[id]/page.tsx`,
      `apps/main/src/app/(passenger)/rides/[id]/page.tsx`,
      `apps/main/src/components/bookings/BookingCard.tsx`,
      `apps/main/src/components/bookings/RideCard.tsx`,
      `apps/main/src/app/(app)/users/[userId]/page.tsx`,
      `apps/main/src/app/(app)/ratings/page.tsx`,
      `apps/main/src/app/(driver)/rides/[id]/manage/page.tsx`,
      `apps/main/src/components/driver/DriverDashboard.tsx`, `apps/main/src/lib/api/wallet.ts`,
      `apps/main/src/components/rides/RideCard.tsx`, `apps/main/src/components/rides/RideHistoryLog.tsx`
      (depends on T032). Also migrated 6 additional call sites found via audit (not in the original
      list) with the same ad hoc `EGP {value}`/`toLocaleString("en-US"|"en-EG")` pattern:
      `apps/main/src/components/passenger/PassengerDashboard.tsx`,
      `apps/main/src/components/passenger/AvailableRideCard.tsx`,
      `apps/main/src/components/passenger/JoinedRideCard.tsx`,
      `apps/main/src/components/driver/UpcomingTripCard.tsx`,
      `apps/main/src/app/(driver)/rides/[id]/bookings/page.tsx`,
      `apps/main/src/app/(driver)/rides/new/page.tsx`.
- [X] T034 [P] [US3] Review `apps/main/messages/ar.json` copy for natural (non-literal) Arabic
      phrasing across error, empty-state, and confirmation strings populated in T016–T019 (depends on
      T016–T019). Full-file review found the copy already reads naturally overall (dual forms used
      correctly — `حرفان`, `وجهي`, `مختلفتين`, `كلمتا المرور`, `مقعدان`; idiomatic phrasing rather than
      literal calques throughout). Fixed two spots that read as literal/awkward:
      `rideForm.errors.departureTooFar` (was "يمكن جدولة الرحلات قبل 48 ساعة كحد أقصى." → now
      "لا يمكن جدولة الرحلة قبل أكثر من 48 ساعة من موعدها.") and `upcomingTripCard.waitingForMore`
      (was "في انتظار {count} أكثر..." → now "في انتظار المزيد ({count})...", matching the
      `pendingCount` "معلّق ({count})" pattern already used elsewhere in the file).

**Checkpoint**: All three user stories independently functional — `quickstart.md` Scenario 5 passes.
(Scenario 4, OTP staying English, requires no task — FR-014 is satisfied by never touching Auth SMS
code.)

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation and rollout bookkeeping

- [X] T035 [P] Run `quickstart.md` validation — all 7 scenarios (depends on completion of Phases 3–5).
      No live test credentials/services available this session, so validated via code-review pass
      (traced each scenario through source) rather than click-through — see
      `feedback_code_review_when_no_live_env` memory convention. Findings: Scenarios 1–4, 6, 7 pass
      (high/medium confidence — locale resolution in `middleware.ts`, `switchLocale()` soft-refresh
      for FR-012, `LanguagePromptModal` rollout gating, OTP templates untouched, background message
      refresh, RTL spot-checks on `BottomNav.tsx`/card components). Scenario 5 (FR-011 missing-key
      fallback) initially found to LIKELY FAIL: `messages-loader.ts` only fell back to bundled English
      at the whole-catalog level, so a key present in `en.json` but absent from a successfully-fetched
      `ar.json` was simply missing, not English. **Fixed**: added `_deepMergeMessages()` to
      `apps/main/src/lib/i18n/messages-loader.ts`, which recursively overlays each fetched locale's
      catalog onto the bundled English catalog in `_loadAll()`, so any missing key now falls through to
      its English string per the `contracts/message-catalog.md` contract. Typechecked clean
      (`npx tsc --noEmit`). Scenario 5 now passes by construction.
- [X] T036 [P] Confirm SC-005 (zero critical layout defects) across primary flows in Arabic/RTL mode
      on a narrow mobile viewport, per `quickstart.md` Scenario 7. No live browser/test-account access
      this session either, so extended the T035 Scenario 7 spot-check into a full grep-based audit of
      `apps/main/src` for `truncate`/`whitespace-nowrap`/`overflow-hidden` and fixed pixel `w-*` widths
      across the primary flows (search, booking, ride management). Findings: every `truncate` hit is on
      dynamic user content (driver/passenger display names, geocoded addresses) inside a
      `flex-1 min-w-0` sibling of a fixed-size avatar/icon — the same single-line-ellipsis pattern
      applies identically in English and Arabic, and no translated static UI string (label/button/
      heading) is truncated, so this doesn't trip FR-015 (which targets translated strings rendering
      "without truncation" relative to their English source, not dynamic user data). The one
      `whitespace-nowrap` case (`(driver)/rides/page.tsx` status filter pills) sits inside an
      `overflow-x-auto` scroll container — standard horizontal tab-scroll pattern, no clipping/overlap
      in either direction. Every fixed-pixel `w-*`/`h-*` hit found is an avatar, icon, spinner, skeleton
      loader, OTP single-character digit box, or the `w-10` percentage-progress numeral (forced
      `numberingSystem: "latn"` per T032/R7) — none size a variable-length translated text container,
      consistent with the T021 finding that `packages/ui` has no physical-width text containers. No
      critical layout defects found; no code changes needed.
- [X] T037 Update `docs/implementation-roadmap.md` marking "Phase 14 — Localization" complete (depends
      on T035, T036). Assigned ID `050` (next sequential after `049` in Phase 13), added `✅ Complete`
      to the phase header and table per the convention used by Phases 10/13, and expanded the
      Deliverables line to note all 37 tasks done and the code-review validation caveat.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phase 3–5)**: All depend on Foundational completion
  - US1 has no dependency on US2/US3
  - US2 depends on US1's toggle existing (T023) to have something to promote/extend
  - US3 depends only on Foundational (T005), not on US1/US2, though T033's call-site edits are
    independent of translation-content work
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational — no dependency on other stories
- **User Story 2 (P2)**: Builds on US1's Settings toggle (T023) but is otherwise independently
  testable per its own acceptance scenarios
- **User Story 3 (P3)**: Can start after Foundational in parallel with US1/US2 — formatting utility
  work (T032) has no dependency on translation content; T033/T034 are the only tasks that assume
  earlier files exist

### Within Each User Story

- Foundational plumbing before story-specific UI work
- Message-catalog content tasks (same two files) run sequentially; component/backend work in
  different files runs in parallel
- Story complete before moving to the next priority, or in parallel if staffed

### Parallel Opportunities

- T001, T002, T003 (Setup) — all different files
- T005, T006 (Foundational) — different files; T010, T012, T013 similarly
- T021, T023, T024 (US1) — different files from the message-catalog chain (T016–T020) and from each
  other
- T030 (US2) — independent of the T027–T029 toggle-promotion chain
- T032, T034 (US3) — independent of each other and of T033
- T035, T036 (Polish) — independent validation passes

---

## Parallel Example: Foundational Phase

```bash
# Launch independent foundational tasks together:
Task: "Extend packages/shared/src/types/user.ts with Locale type and language_preference fields"
Task: "Extend services/api/app/models/profile.py with language_preference field"
Task: "Create apps/main/src/lib/i18n/messages-loader.ts"
Task: "Create apps/main/messages/en.json skeleton"
Task: "Create apps/main/messages/ar.json skeleton"
```

## Parallel Example: User Story 1

```bash
# Once the message-catalog content chain (T016-T020) is underway, these can run alongside it:
Task: "Audit packages/ui/src/components for RTL logical variants and responsive sizing"
Task: "Add LanguageSection toggle to ProfileEditor.tsx"
Task: "Restructure _NOTIFICATION_TEMPLATES in fcm_service.py to per-locale dict"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Run `quickstart.md` Scenario 1 independently
5. Deploy/demo if ready — full Arabic UI is the feature's core value (spec Business Objective)

### Incremental Delivery

1. Complete Setup + Foundational → foundation ready
2. Add User Story 1 → validate Scenario 1 → deploy/demo (MVP!)
3. Add User Story 2 → validate Scenarios 2 & 3 → deploy/demo
4. Add User Story 3 → validate Scenarios 5–7 → deploy/demo
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers, once Foundational is done:

- Developer A: User Story 1 (translation content + RTL audit + FCM)
- Developer B: User Story 3 (formatting utility + call-site updates) — no dependency on US1's
  translation content beyond T033/T034
- User Story 2 starts once US1's T023 (toggle) lands, since it builds directly on that control

---

## Notes

- [P] tasks = different files, no unresolved dependency on another listed task
- [Story] label maps task to specific user story for traceability
- Message-catalog tasks (T016–T019, T034) share `en.json`/`ar.json` — treat as a sequential chain
  even though later tasks add distinct namespaces
- Commit after each task or logical group, per this repo's established convention of committing and
  pushing after implementation work
- Avoid: vague tasks, same-file conflicts marked [P], cross-story dependencies that break independent
  testability
