---

description: "Task list for feature implementation"
---

# Tasks: Groups

> **Superseded 2026-08-30**: The group-type model (`general`/`company`/`university`, one domain per type-group, auto-created-on-first-verification) implemented by the tasks below was replaced by an open-membership redesign — groups no longer have a type, any org-email-verified user can join any group unconditionally, and domain verification was repurposed to prove per-group sponsorship eligibility (many domains per sponsored group, via `group_sponsor_domains`) rather than to gate or create groups. See `specs/024-groups/spec.md`'s "Session 2026-08-30 — Superseding redesign" clarification, `specs/026-sponsored-groups/` for the sponsorship-eligibility flow, and migration `supabase/migrations/20260830000004_open_groups_multi_domain_sponsorship.sql`. The task history below is left unchanged as a record of what was actually built and later revised — it does not reflect the current schema or API contract.

**Input**: Design documents from `specs/024-groups/` (`plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/api.md`, `quickstart.md`)

**Tests**: Not explicitly requested in the specification; dedicated test tasks are included only in the Polish phase (T045–T046), following this repo's existing convention (`services/api/tests/unit/`, `services/api/tests/integration/`) rather than as per-story TDD gates.

**Organization**: Tasks are grouped by user story (US1–US5, per `spec.md`) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)

## Path Conventions

Extends the existing monorepo — no new top-level directories:
- Backend: `services/api/app/`
- Frontend: `apps/main/src/`
- Migrations: `supabase/migrations/`

---

## Phase 1: Setup

**Purpose**: Scaffold the new `groups` module on both sides so later tasks have somewhere to land.

- [X] T001 Create `services/api/app/api/groups/__init__.py` and an empty `APIRouter()` in `services/api/app/api/groups/router.py`
- [X] T002 [P] Create `services/api/app/models/group.py` (empty module, populated in T011)
- [X] T003 [P] Create `services/api/app/services/group_service.py` (empty module, populated in T012)
- [X] T004 Mount the new router in `services/api/app/main.py` (`app.include_router(groups_router, prefix="/api/groups", tags=["groups"])`, alongside the existing domain routers)
- [X] T005 [P] Create `apps/main/src/lib/api/groups.ts` (empty typed-fetch module, populated in T018)

**Checkpoint**: Module skeletons exist and the app boots with the (empty) groups router mounted.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, RLS, config, and shared service helpers that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Write migration `supabase/migrations/20260826000001_groups_schema.sql` — `groups`, `group_memberships`, `domain_verifications` tables, indexes (GIN on `route_tags`, trigram on `name`), and the `member_count` maintenance trigger, per `data-model.md`
- [X] T007 Write migration `supabase/migrations/20260826000002_groups_rls_policies.sql` — RLS policies for all three new tables per `data-model.md`'s RLS Summary
- [X] T008 Write migration `supabase/migrations/20260826000003_rides_add_group_id.sql` — `ALTER TABLE rides ADD COLUMN group_id uuid NULL REFERENCES groups(id) ON DELETE SET NULL`, and extend the existing `rides` SELECT RLS policy with the group-membership clause from `data-model.md`
- [X] T009 Write migration `supabase/migrations/20260826000004_groups_platform_settings.sql` — seed `platform_settings` rows for `group_domain_blocklist` (the six providers named in the spec), `group_new_domain_rate_limit`, and `group_new_domain_rate_limit_window_minutes`, per `research.md` §2
- [X] T010 Applied all four migrations to the local Supabase stack and verified the schema (`\d groups`, `platform_settings` seeds, `rides.group_id`). Docker Desktop was started and the stack came up healthy. Fixed a bug found along the way: `groups.invite_token` used `gen_random_bytes()` (requires the `pgcrypto` extension, which this project deliberately doesn't enable — see `20260612000000_enable_extensions.sql`); changed to `replace(gen_random_uuid()::text, '-', '')` to stay consistent with the project's native-UUID convention. Also worked around the pre-existing `20260805000002_spatial_ref_sys_rls.sql` local-owner-permission blocker (documented in that file's own comment / see memory) via `docker exec ... psql -U supabase_admin` + `supabase migration repair --status applied 20260805000002 --local`, then ran `supabase migration up --local` for the rest. Note: `supabase db push` was tried first by mistake — it targets the **remote** DB, not local; it failed on the same `gen_random_bytes` error and rolled back cleanly (confirmed via `supabase migration list` — remote still at `20260825000003`, no partial state). Remote is unaffected and still needs its own migration run later.
- [X] T011 [P] Populate `services/api/app/models/group.py` with the Pydantic request/response schemas needed across all endpoints in `contracts/api.md` (`CreateGroupRequest`, `GroupSummary`, `GroupDetailResponse`, `InviteLinkResponse`, `DomainVerificationRequest`, `DomainVerificationConfirm`, `MembershipResponse`, `TransferOwnershipRequest`)
- [X] T012 Implement shared helpers in `services/api/app/services/group_service.py`: `_supabase()` (mirrors `verification_service._supabase`), an identity-verified guard (`_require_verified(user_id)`, per `research.md` §6), and config readers for the blocklist / rate-limit / window settings from `platform_settings` (mirrors `verification_service._get_support_email`)

**Checkpoint**: Foundation ready — schema exists, config is readable, shared guards are in place. User story implementation can now begin.

**Gemini review (Phase 1+2) — findings addressed 2026-08-26**:
- Removed the client-facing `insert_own_domain_verifications` RLS policy: it let any authenticated client write `verified_at`/`is_first_for_domain` directly, bypassing the OTP flow entirely. Writes to `domain_verifications` are now service-role only, matching `groups`/`group_memberships`.
- `group_service._get_platform_setting` used `.single().execute()`, which raises (HTTP 406) on zero rows instead of returning `None` — would 500 if a setting key were ever missing instead of falling back to its default. Switched to `.maybe_single()`.
- `rides.group_id`'s FK was `ON DELETE SET NULL`; since `group_id IS NULL` means "public general-feed ride," a hard-deleted group would have silently made all its private rides public. Groups are soft-delete only (`archived_at`) so a hard delete should never happen — changed to `ON DELETE RESTRICT` to enforce that at the DB level.
- Added `chk_groups_type_domain` CHECK constraint tying `type`/`domain` together (general ⇒ domain NULL; company/university ⇒ domain NOT NULL) — nothing previously stopped these from drifting apart.
- `apps/main/src/lib/api/groups.ts`'s `parseErrorResponse` called `res.json()` with no `try/catch`; a non-JSON error body (proxy 502, empty 204, HTML 500 page) would throw and crash the caller. Wrapped in `try/catch` with a status-text fallback.
- `groups_update_member_count` trigger only handled INSERT/DELETE; added UPDATE handling (decrement old group, increment new group when `group_id` changes) for completeness, even though the service layer never reassigns `group_id` on an existing membership row today.
- (Noted, not changed) Gemini flagged that T008 said "extend the existing policy" while the implementation adds a new additive `group_members_read_group_rides` policy — this is correct Postgres practice (multiple permissive `SELECT` policies OR together) and matches `data-model.md`'s own RLS Summary wording; no code change needed.
- All four migrations re-verified end-to-end on the local Supabase stack after the fixes (`\d groups`, `\d domain_verifications`, FK `confdeltype`, and trigger definition all confirmed).

---

## Phase 3: User Story 1 - Create and Discover a General Group (Priority: P1) 🎯 MVP

**Goal**: A driver or passenger can create a general/interest group and any other user can find it via directory search.

**Independent Test**: Create a general group with a name and route tags from one account; search the directory from a different account by name/type/route tag and confirm it's found with correct public details, with no membership required. (`quickstart.md` §1)

### Implementation for User Story 1

- [X] T013 [US1] Implement `create_group()` in `group_service.py` (general type only: name/description/route_tags validation, owner+first-member row) — FR-001, FR-002
- [X] T014 [US1] Implement `POST /api/groups` in `api/groups/router.py`, wired to T013
- [X] T015 [US1] Implement `search_groups()` in `group_service.py` (name via trigram, `type` and `route_tag` filters, paginated) — FR-003
- [X] T016 [US1] Implement `GET /api/groups` in `api/groups/router.py`, wired to T015
- [X] T017 [US1] Implement `get_group_detail()` in `group_service.py` and `GET /api/groups/{group_id}` in `api/groups/router.py` (includes `is_member`/`is_owner` for the caller)
- [X] T018 [US1] Add `createGroup`, `searchGroups`, `getGroup` functions to `apps/main/src/lib/api/groups.ts`
- [X] T019 [P] [US1] Build group directory UI: `apps/main/src/app/(app)/groups/page.tsx` + `apps/main/src/components/groups/GroupDirectorySearch.tsx` + `apps/main/src/components/groups/GroupCard.tsx`
- [X] T020 [P] [US1] Build create-group UI: `apps/main/src/app/(app)/groups/create/page.tsx`
- [X] T021 [US1] Build group detail page skeleton: `apps/main/src/app/(app)/groups/[groupId]/page.tsx` (public metadata view; membership-gated content added in later stories)

**Checkpoint**: US1 fully functional and independently testable per `quickstart.md` §1.

---

## Phase 4: User Story 2 - Post and Book Rides Within a Group (Priority: P1)

**Goal**: A group-member driver posts a ride scoped to the group; group-member passengers see and book it through the existing booking flow; non-members and the general feed never see it.

**Independent Test**: Group-member driver posts a group-scoped ride; group-member passenger sees and books it via the existing flow; a non-member and the general city-wide feed both fail to show it. (`quickstart.md` §2)

### Implementation for User Story 2

- [X] T022 [US2] Extend `CreateRideRequest` in `services/api/app/models/ride.py` with optional `group_id: Optional[UUID]`
- [X] T023 [US2] Extend `ride_service.py`'s ride-creation path to validate caller membership in `group_id` (when provided) before persisting — FR-006, FR-008
- [X] T024 [US2] Add `AND group_id IS NULL` to the base queries in `candidate_service.py`, `search/router.py`, and the general-feed queries in `rides/router.py` so group-scoped rides never appear in the city-wide feed — FR-007, SC-005
- [X] T025 [US2] Implement `list_group_rides()` in `group_service.py` (membership-gated, reuses the existing ride-listing query shape filtered to `group_id = :group_id`) — FR-007, FR-009
- [X] T026 [US2] Implement `GET /api/groups/{group_id}/rides` in `api/groups/router.py`, wired to T025 (403 for non-members)
- [X] T027 [US2] Add `getGroupRides` to `apps/main/src/lib/api/groups.ts`
- [X] T028 [P] [US2] Add an optional group picker to the driver ride-creation flow in `apps/main/src/app/(driver)/rides/...` (lists groups the driver belongs to, defaults to unscoped)
- [X] T029 [P] [US2] Extend `apps/main/src/app/(app)/groups/[groupId]/page.tsx` with the group's active ride listing (member-only), booking through the existing booking flow with zero new steps — SC-006

**Checkpoint**: US1 + US2 both fully functional and independently testable per `quickstart.md` §1–2.

**Implementation note**: T028 ("lists groups the driver belongs to") needed a "my groups" lookup that no task or contract defines. Added `list_my_groups()` in `group_service.py` and `GET /api/groups/mine` in `api/groups/router.py` (registered before `/{group_id}` to avoid the fixed segment being parsed as a UUID — same ordering convention already used in `rides/router.py`), plus `getMyGroups()` in `apps/main/src/lib/api/groups.ts`.

---

## Phase 5: User Story 3 - Join a Group via Invite Link (Priority: P2)

**Goal**: A group owner shares a permanent, revocable invite link; opening it lands any user on the same join screen and gating rules as directory-based joining.

**Independent Test**: Generate an invite link, open it from a fresh account, confirm it resolves to the join screen with directory-equivalent gating; regenerate the link and confirm the old token 404s. (`quickstart.md` §3)

### Implementation for User Story 3

- [X] T030 [US3] Implement `generate_invite_link()` / `regenerate_invite_link()` in `group_service.py` (owner-only, invalidates the previous token) — FR-004
- [X] T031 [US3] Implement `POST /api/groups/{group_id}/invite-link` in `api/groups/router.py`
- [X] T032 [US3] Implement `resolve_invite_token()` in `group_service.py` and `GET /api/groups/join/{invite_token}` in `api/groups/router.py` (404 for unknown/revoked/regenerated tokens) — FR-005, Edge Case: revoked link
- [X] T033 [US3] Implement `join_group()` in `group_service.py` for the general-group path: idempotent (returns existing membership if already a member), `409 domain_verification_required` for company/university groups — FR-005, FR-009
- [X] T034 [US3] Implement `POST /api/groups/{group_id}/join` in `api/groups/router.py`, wired to T033
- [X] T035 [US3] Add `getInviteLink`, `resolveInviteToken`, `joinGroup` to `apps/main/src/lib/api/groups.ts`
- [X] T036 [P] [US3] Build join screen UI: `apps/main/src/app/(app)/groups/join/[inviteToken]/page.tsx`
- [X] T037 [P] [US3] Add `InviteLinkShare` component (copy link, regenerate button) to the group detail page, owner-only

**Checkpoint**: US1–US3 all functional and independently testable per `quickstart.md` §1–3.

---

## Phase 6: User Story 4 - Join a Company or University Group via Domain-Verified Email (Priority: P2)

**Goal**: A user proves control of a work/school email via OTP; non-blocklisted domains are accepted automatically with no admin review; the first verifier on a domain creates its group, later verifiers join it automatically.

**Independent Test**: A blocklisted-domain attempt is rejected with no OTP sent; a valid organizational email completes OTP verification and grants membership; a second user on the same domain joins automatically with no extra step. (`quickstart.md` §4, §6)

### Implementation for User Story 4

- [X] T038 [US4] Implement `request_domain_verification()` in `group_service.py`: normalize domain, blocklist check (reject before sending anything) — FR-010, FR-011, SC-004
- [X] T039 [US4] Generate/hash/store the OTP code and send it via the existing transactional-email sender pattern (`notification_service`'s Resend/Mailpit path), reusing `auth_service`'s resend-rate-limit shape — FR-010, FR-020
- [X] T040 [US4] Implement `POST /api/groups/domain-verification/request` in `api/groups/router.py`, wired to T038/T039
- [X] T041 [US4] Implement `confirm_domain_verification()` in `group_service.py`: hash + expiry check; on success, auto-derive the group name and create the group when `is_first_for_domain` (enforcing the DB-backed new-domain rate limit from `research.md` §3), otherwise attach to the existing group; create the caller's membership either way — FR-012, FR-013, FR-014
- [X] T042 [US4] Implement `POST /api/groups/domain-verification/confirm` in `api/groups/router.py`, wired to T041
- [X] T043 [US4] Add `requestDomainVerification`, `confirmDomainVerification` to `apps/main/src/lib/api/groups.ts`
- [X] T044 [P] [US4] Build `DomainVerifyForm` component (email entry → OTP confirm, mirrors the platform's existing login-OTP UX) in `apps/main/src/components/groups/`
- [X] T045 [US4] Wire `DomainVerifyForm` into the join screen (T036) for company/university groups, triggered by the `409 domain_verification_required` response from T034
- [X] T046 [US4] Audit all new UI copy and API error/response messages to confirm they say "domain-verified," never "employer-verified" or "verified employee" — FR-015

**Checkpoint**: US1–US4 all functional and independently testable per `quickstart.md` §1–4, §6.

---

## Phase 7: User Story 5 - Leave and Manage Group Membership (Priority: P3)

**Goal**: Members can leave, owners can remove members or transfer/archive ownership, and archived groups stop accepting new members/rides while existing rides keep running.

**Independent Test**: A member leaves and immediately loses access to the group's ride listing; an owner removes another member with the same effect; an owner cannot leave with other members present without transferring ownership first. (`quickstart.md` §5)

### Implementation for User Story 5

**Design note (flagged by Gemini review of Phase 3+4, 2026-08-26)**: neither `leave_group()` nor `remove_member()` exists yet, so this isn't exploitable today — but once T047/T049 land, a driver's active `scheduled` rides with that `group_id` must be handled (e.g. reject the leave/removal with `409` while the driver has active group-scoped rides, or null out `group_id` on those rides), otherwise a non-member ends up managing a private group ride that still shows up in `list_group_rides()` for remaining members. Decide and implement this as part of T047/T049, not deferred further.

**Resolution (2026-08-26)**: `spec.md`'s Edge Cases section resolves this — a driver's active rides are left untouched on leave/removal/archive; the group-scoping only affects future ride creation and listing visibility, not existing rides. `leave_group()`/`remove_member()`/`archive_group()` deliberately contain no ride-state mutation logic. Separately, `ride_service.create_ride()`'s group-scoping check was found to be missing the FR-021 "archived groups block new ride postings" enforcement — fixed by adding an `archived_at` check to the membership-lookup query in `create_ride()`.

- [X] T047 [US5] Implement `leave_group()` in `group_service.py` (owner-with-remaining-members returns `409 ownership_transfer_required`) — FR-017, FR-019
- [X] T048 [US5] Implement `POST /api/groups/{group_id}/leave` in `api/groups/router.py`
- [X] T049 [US5] Implement `remove_member()` in `group_service.py` (owner-only) and `DELETE /api/groups/{group_id}/members/{user_id}` in `api/groups/router.py` — FR-018
- [X] T050 [US5] Implement `transfer_ownership()` in `group_service.py` (single transaction: flip both roles) and `POST /api/groups/{group_id}/transfer-ownership` in `api/groups/router.py` — FR-019
- [X] T051 [US5] Implement `archive_group()` in `group_service.py` (owner-only, sets `archived_at`, blocks new joins/invite-link resolution/new group-scoped ride creation; existing rides untouched) and `DELETE /api/groups/{group_id}` in `api/groups/router.py` — FR-021
- [X] T052 [US5] Add `leaveGroup`, `removeMember`, `transferOwnership`, `archiveGroup` to `apps/main/src/lib/api/groups.ts`
- [X] T053 [P] [US5] Build `MemberList` component (leave button; owner-only remove/transfer/archive controls) in `apps/main/src/components/groups/`, wired into the group detail page

**Implementation note**: `GET /api/groups/{group_id}/members` + `group_service.list_group_members()` were added ad hoc (not in the original task list/contract) — `MemberList.tsx` needs a member roster to render, and no prior task covered listing members. Follows the same gap-fill precedent as T028's `list_my_groups`.

**Checkpoint**: All five user stories independently functional per `quickstart.md` §1–6.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T054 [P] Add unit tests for `group_service.py` in `services/api/tests/unit/test_group_service.py` (blocklist rejection, rate-limit threshold, ownership-transfer edge case, at minimum) — 25 tests, all passing
- [X] T055 [P] Add integration tests for the end-to-end groups flows in `services/api/tests/integration/test_groups_flow.py` (create → search → join → post ride → book; invite-link revoke; domain-verification happy/blocklist paths) — 13 tests at the router/HTTP layer (TestClient + dependency overrides), all passing; also covers the `ride_service.create_ride()` archived-group fix at the service layer
- [X] T056 Run `quickstart.md` end-to-end manually against the local stack and confirm every numbered scenario passes — 5/6 scenarios passed cleanly (general group create+directory; invite link; domain verification; membership lifecycle: leave/remove/transfer/archive; rate-limit smoke test). Scenario 2 (group-scoped ride post+book) was blocked only by a pre-existing local-env gap unrelated to Groups: `POST /api/v1/rides` returns `503 route_intelligence_unavailable` because no OSRM instance/`OSRM_URL` is configured in this local dev environment; membership-join, 403-for-non-member, and general-feed-exclusion sub-checks within that scenario all passed. The rate-limit scenario surfaced a real bug (see below) which has since been fixed and re-verified.
  - **Bug found+fixed**: `confirm_domain_verification`'s new-domain rate-limit count query counted the verification row it had just marked `verified_at` on in the same transaction, tightening the effective quota to `limit − 1`. Fixed by excluding the current `verification_id` from the count query (`AND id != $1`).
- [X] T057 Add all new Groups UI strings to `apps/main`'s message catalog (`en.json`/`ar.json`) and republish via `services/api/scripts/publish_message_catalog.py` (repo-text-edits are invisible until republished) — published to local dev R2, 2026-08-26
- [X] T058 Run `ruff check` and the full `pytest` suite in `services/api`; confirm CI stays green — 190 passed, ruff clean (also fixed 2 pre-existing missing-`group_id` fixture gaps in `test_rides_fare_override.py`/`test_rides_fare_override_edit.py` surfaced by the full-suite run, and 2 pre-existing E501 line-length violations in `group_service.py`); re-run after the T056 rate-limiter fix still 190 passed, ruff clean

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational only
- **US2 (Phase 4)**: Depends on Foundational + US1 (needs an existing group to scope a ride to; the group detail page it extends is built in US1)
- **US3 (Phase 5)**: Depends on Foundational + US1 (groups must exist and be joinable via directory before an invite-link shortcut to the same join flow makes sense); independent of US2
- **US4 (Phase 6)**: Depends on Foundational + US3 (reuses the join screen and `409 domain_verification_required` contract built in US3)
- **US5 (Phase 7)**: Depends on Foundational + US1 (needs groups and memberships to exist); independent of US2/US3/US4
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### Parallel Opportunities

- T002, T003, T005 (Setup) in parallel
- T011 (models) can run alongside T006–T010 (migrations) since they touch different files, but T012 (service helpers) needs T009/T011 done first
- Within each story, frontend tasks marked [P] (e.g., T019/T020, T028/T029, T036/T037, T044, T053) can run in parallel with each other and with that story's backend tasks once the relevant API contract is stable
- US2, US3, and US5 can be built in parallel by different developers once US1 is done; US4 must wait on US3

---

## Parallel Example: User Story 1

```bash
Task: "Implement search_groups() in group_service.py"
Task: "Build group directory UI in apps/main/src/app/(app)/groups/page.tsx"
Task: "Build create-group UI in apps/main/src/app/(app)/groups/create/page.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 2)

Both are P1 — the feature has no point without both create/discover (US1) and post/book-within-a-group (US2). Complete Setup → Foundational → US1 → US2, validate against `quickstart.md` §1–2, and that's a demoable MVP even before invite links or domain verification exist.

### Incremental Delivery

1. Setup + Foundational → schema and shared helpers ready
2. US1 → group creation + directory search demoable
3. US2 → the actual point of the feature: group-scoped rides, bookable — **MVP**
4. US3 → invite-link sharing (word-of-mouth growth loop)
5. US4 → company/university domain-verified groups (highest-trust group types)
6. US5 → membership housekeeping (can ship slightly after the rest without harm, per spec's own P3 rationale)
7. Polish → tests, message-catalog publish, quickstart sign-off

---

## Notes

- [P] tasks touch different files with no unmet dependency
- [Story] label maps every story-phase task to its user story for traceability
- File paths above are exact per `plan.md`'s Project Structure
- Commit after each task or logical group, per this repo's `[Commit+Push Every Implementation]` working convention
- After implementation, apply migrations to remote Supabase and republish the message catalog — neither happens automatically
