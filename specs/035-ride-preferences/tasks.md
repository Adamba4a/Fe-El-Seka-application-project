# Tasks: Ride Preferences and Round Trips

**Input**: Design artifacts in `specs/035-ride-preferences/`  
**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/rides-api.md`

## Phase 1 — Data and shared contracts

- [x] T001 Create migration `supabase/migrations/<timestamp>_ride_preferences_and_round_trips.sql`: add `profile_gender` and `ride_trip_leg` enums; private nullable `profiles.gender`; `rides.is_women_only`, `rides.round_trip_group_id`, and `rides.trip_leg` with legacy-safe defaults, checks, and pairing unique index; extend `recurring_ride_definitions` with journey, women-only, and return-leg schedule fields; replace the recurring one-row-per-date unique index with a per-leg variant.
- [x] T002 Update `packages/shared/src/types/user.ts` and its exports with private `Gender`, `Profile.gender`, and `ProfileUpdate.gender`; do not change public profile types.
- [x] T003 Update `packages/shared/src/types/rides.ts` with journey/leg fields, women-only flag, round-trip create/edit payload fields, and recurring return-leg fields/occurrence override types.
- [x] T004 Update FastAPI profile, ride, and recurring Pydantic schemas to match the new private profile, paired one-off, recurring round-trip, and occurrence-override contracts.

## Phase 2 — Profile gender and women-only enforcement

- [x] T005 Extend `services/api/app/services/profile_service.py` and `services/api/app/models/profile.py`/router to read and write gender only through authenticated private-profile endpoints; retain its exclusion from `get_public_profile` and public schemas.
- [x] T006 Update `apps/main/src/app/(onboarding)/profile/page.tsx`, profile API client/types, bilingual messages, and profile settings/remediation UI so gender is required for onboarding and can be supplied by legacy profiles.
- [x] T007 Add `is_women_only` to one-off and recurring ride service validation. Enforce `women_only_driver_required` in the API for create/edit/definition operations before persistence.
- [x] T008 Add the `women_only_ride` booking guard at the beginning of `booking_service.create_booking`, before a seat claim, pricing, wallet/loyalty mutations, or booking insert.
- [ ] T009 Add tests for gender privacy, onboarding validation, woman-driver-only posting, woman-passenger booking success, and side-effect-free ineligible booking rejection.

## Phase 3 — One-off round trips

- [x] T010 Extend `ride_service.create_ride` and `/api/v1/rides` response handling to validate one-way versus round-trip payloads, call routing/pricing for the reverse return route, and atomically create linked outbound/return rows with separate driver-selected seats and prices.
- [x] T011 Extend ride response mapping, list/detail/search SQL/selects, and shared API client types to return `is_women_only`, pairing ID, and leg label without exposing profile gender.
- [x] T012 Update `ride_service.edit_ride` to preserve trip ordering: lock the paired sibling when applicable and reject changes that make the return depart at/before outbound. Prevent changing a ride's journey type/pair topology after creation.
- [x] T013 Update `RideForm`, create/edit pages, cards/detail/booking UI, and English/Arabic messages to choose women-only, one-way/round-trip, and independent return date/time/seats/price; show women-only and outbound/return identity clearly.
- [ ] T014 Add service/API tests for legacy one-way compatibility, paired atomic create, reversed route, separate availability/pricing, chronology validation, and independent bookings/cancellations.

## Phase 4 — Recurring round trips and occurrence overrides

- [x] T015 Extend recurring definition create/update/list/detail schemas, service SQL, and UI form to collect and display women-only, journey type, return time, return seats, and return price; apply woman-driver validation.
- [x] T016 Update `recurring_ride_service.generate_upcoming_instances` to generate one normal ride for one-way definitions or a linked outbound/return pair per selected date, with separate reverse route/fare and per-leg data.
- [x] T017 Update recurring-definition propagation and visibility/count/detail queries to operate on both legs and retain the correct one-way behavior for existing definitions.
- [x] T018 Add `PATCH /api/v1/rides/recurring/{definition_id}/occurrences/{date}` and its service operation: lock both pair rows; require no confirmed bookings and both legs outside the edit cutoff; validate chronology and schedule conflicts; update both timings atomically.
- [x] T019 Add the driver recurring-detail UI control for one-date outbound/return-time overrides, with clear errors and refreshed paired ride data.
- [ ] T020 Add recurring tests for paired generation/idempotency, definition edits, independently bookable legs, and atomic date override rejection/success.

## Phase 5 — Regression validation

- [ ] T021 Run migration against local Supabase and execute the quickstart scenarios, including legacy record compatibility.
- [x] T022 Run targeted Python test suites for profile, ride, booking, and recurring services, then the relevant API integration tests.
- [x] T023 Run `pnpm --filter @fe-el-seka/main typecheck` and relevant frontend tests; fix type, i18n, or UI regressions.
- [x] T024 Inspect `git diff` and `git status`; confirm unrelated untracked `.claude/settings.local.json` and `docs/ai-ranking-review-handoff.md` are neither staged nor changed.

## Dependencies and Order

`T001–T004` block all implementation. `T005–T009` establish the safety rule before ride UI work. `T010–T014` provide the linked-leg foundation that `T015–T020` reuses. `T021–T024` run only after implementation is complete.
