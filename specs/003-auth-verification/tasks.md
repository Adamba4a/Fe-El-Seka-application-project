# Tasks: Authentication & Verification

**Input**: Design documents from `specs/003-auth-verification/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/auth-api.md ✅, quickstart.md ✅

**Tests**: Not requested — no test tasks included.

**Organization**: Tasks are grouped by user story (US1–US6) to enable independent implementation and validation of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no cross-task dependencies)
- **[Story]**: Which user story this task belongs to (US1–US6)
- File paths are relative to the monorepo root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create directory skeleton and install all dependencies before any implementation begins.

- [ ] T001 Create directory structure for apps/main/src, apps/admin/src, services/api/app, supabase/migrations/003_auth_verification, packages/shared-types/src per plan.md
- [ ] T002 [P] Install FastAPI backend dependencies (fastapi, supabase, python-multipart, pydantic-settings, python-jose[cryptography]) in services/api/requirements.txt and install
- [ ] T003 [P] Install apps/main dependencies (@supabase/supabase-js, @supabase/ssr, react-hook-form, zod, shadcn/ui) in apps/main/package.json and install
- [ ] T004 [P] Install apps/admin dependencies (@supabase/supabase-js, @supabase/ssr, react-hook-form, zod, shadcn/ui) in apps/admin/package.json and install
- [ ] T005 [P] Create environment variable template files (.env.example) for services/api, apps/main, and apps/admin documenting all required vars (SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, TWILIO_*, etc.)

**Checkpoint**: All deps installed, directory tree exists — implementation can begin.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database schema, shared types, Supabase clients, and FastAPI core infrastructure that ALL user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Shared TypeScript Types

- [ ] T006 [P] Create packages/shared-types/src/auth.ts (OtpRequest, SessionResponse, AdminLoginRequest)
- [ ] T007 [P] Create packages/shared-types/src/user.ts (Profile, Role enum, VerificationStatus enum)
- [ ] T008 [P] Create packages/shared-types/src/verification.ts (VerificationSubmission, SubmissionStatus, SubmissionType)
- [ ] T009 [P] Create packages/shared-types/src/vehicle.ts (Vehicle, VehicleRegistration, VehicleUpdate)

### Database Migrations

- [ ] T010 Write supabase/migrations/003_auth_verification/001_create_profiles.sql — profiles table with all columns, FK to auth.users ON DELETE CASCADE, CHECK constraints on role and verification_status
- [ ] T011 Write supabase/migrations/003_auth_verification/002_create_verification_submissions.sql — verification_submissions table, CHECK constraint on attempt_number (1–3), CHECK on status
- [ ] T012 Write supabase/migrations/003_auth_verification/003_create_vehicles.sql — vehicles table, UNIQUE on driver_id, CHECK on year and seat_count
- [ ] T013 Write supabase/migrations/003_auth_verification/004_create_admin_audit_logs.sql — admin_audit_logs table, CHECK on action_type, FKs to auth.users and profiles
- [ ] T014 Write supabase/migrations/003_auth_verification/005_create_platform_settings.sql — platform_settings key-value table with seed INSERT for support_email='support@felseka.com'
- [ ] T015 Write supabase/migrations/003_auth_verification/006_rls_policies.sql — enable RLS on all 5 tables; create is_admin() SECURITY DEFINER function; add all SELECT/INSERT/UPDATE policies per data-model.md
- [ ] T016 Write supabase/migrations/003_auth_verification/007_storage_buckets.sql — create profile-photos (private, 5MB, JPEG/PNG) and identity-documents (private, 10MB, JPEG/PNG) buckets; storage RLS policies (identity-documents has NO user SELECT policy)

### Supabase Clients

- [ ] T017 [P] Create apps/main/src/lib/supabase/client.ts — browser-side Supabase client using @supabase/ssr createBrowserClient
- [ ] T018 [P] Create apps/main/src/lib/supabase/server.ts — server-side Supabase client using @supabase/ssr createServerClient with cookie handling for Next.js App Router
- [ ] T019 [P] Create apps/admin/src/lib/supabase/admin-client.ts — Supabase client for admin app (SUPABASE_SERVICE_ROLE_KEY for signed URL generation)

### FastAPI Core

- [ ] T020 Create services/api/app/main.py — FastAPI app with CORS middleware (origins from env), lifespan, and include_router calls for all 6 routers (auth, profiles, verification, vehicles, admin/verification, admin/users); 404/422/500 error handlers
- [ ] T021 Implement services/api/app/dependencies/auth.py — get_current_user() dependency: verify Supabase JWT, query profiles table, raise HTTP 401 with error="account_suspended" if status='suspended', attach profile to request state
- [ ] T022 [P] Implement services/api/app/dependencies/roles.py — get_current_admin() (role='admin' check → 403), get_current_driver() (role='driver'), get_current_passenger() (role='passenger') — all chain from get_current_user()
- [ ] T023 [P] Implement services/api/app/dependencies/verification.py — get_current_verified_driver() (verification_status='verified' + role='driver' → 403 with error="verification_required"), get_current_verified_passenger() (same for passenger role)

**Checkpoint**: Migrations written, Supabase clients ready, FastAPI core wired — all user stories can now begin.

---

## Phase 3: User Story 1 — Phone OTP Registration & Login (Priority: P1) 🎯 MVP

**Goal**: Any Egyptian phone number can request an OTP, receive it via SMS, verify it, and get a session. Admins can log in via email+password.

**Independent Test**: Enter +201234567890 → receive SMS → enter OTP → get `access_token` in response. Verify Supabase Studio → Authentication → Users shows the phone number.

### Backend

- [ ] T024 [P] [US1] Create services/api/app/models/auth.py — OtpRequest (phone_number with +20 regex validation), OtpVerifyRequest (phone_number, otp 6-digit string), SessionResponse (access_token, refresh_token, expires_in, user.id, user.phone_number, user.is_new_user), RefreshRequest, ErrorResponse
- [ ] T025 [US1] Implement services/api/app/services/auth_service.py — request_otp() calls supabase.auth.sign_in_with_otp(phone=...), verify_otp() calls supabase.auth.verify_otp(phone=..., token=..., type='sms'), refresh_session(), sign_out() + admin.sign_out(user_id, 'global') for session revocation; rate-limit tracking for FR-005 (3 resends per 15-min per phone)
- [ ] T026 [US1] Implement services/api/app/api/auth/router.py — POST /api/auth/request-otp (no auth), POST /api/auth/verify-otp (no auth, returns is_new_user flag), POST /api/auth/refresh (no auth), POST /api/auth/sign-out (auth required); map Supabase errors to error codes from contracts/auth-api.md

### Frontend — Main App

- [ ] T027 [P] [US1] Create apps/main/src/lib/api/auth.ts — requestOtp(phone), verifyOtp(phone, otp), refreshToken(token), signOut() typed against shared-types SessionResponse
- [ ] T028 [P] [US1] Create apps/main/src/lib/auth/hooks.ts — useUser() (reads session, returns Profile | null), useSession(), useRole() (returns 'passenger' | 'driver' | 'admin' | null)
- [ ] T029 [P] [US1] Create apps/main/src/lib/auth/guards.ts — requireAuth() redirect to /login if no session, requireRole(role) redirect to appropriate home if role mismatch
- [ ] T030 [P] [US1] Create apps/main/src/components/auth/PhoneInput.tsx — Egyptian phone input (+20 prefix, 10-digit local number, real-time format validation, shadcn/ui Input)
- [ ] T031 [P] [US1] Create apps/main/src/components/auth/OtpInput.tsx — 6-cell OTP input with auto-focus advance, paste support, countdown timer showing OTP expiry and resend button after 60s
- [ ] T032 [US1] Create apps/main/src/app/(auth)/login/page.tsx — phone input form, calls requestOtp, redirects to /otp on success; shows rate-limit error if FR-005 triggered
- [ ] T033 [US1] Create apps/main/src/app/(auth)/otp/page.tsx — OTP entry form, calls verifyOtp, redirects to /role-select if is_new_user else to role-appropriate home; shows attempt count error (FR-004)

### Frontend — Admin App

- [ ] T034 [P] [US1] Create apps/admin/src/app/(auth)/login/page.tsx — email + password form using Supabase Auth signInWithPassword; on success redirect to /dashboard; show error for invalid credentials

**Checkpoint**: Full OTP auth flow works end-to-end. Admin can log in. Validated by quickstart.md Step 1.

---

## Phase 4: User Story 2 — Profile Creation & Role Selection (Priority: P2)

**Goal**: First-time users select Passenger or Driver, enter a display name, optionally upload a profile photo, and land on the correct home screen.

**Independent Test**: POST /api/profiles/setup with role='driver', display_name='Test Driver' → 201 Created, verification_status='unverified'. GET /api/profiles/me → same data returned.

### Backend

- [ ] T035 [P] [US2] Create services/api/app/models/profile.py — ProfileSetup (role: Literal['passenger','driver'], display_name: str 2–50 chars), ProfileResponse (id, phone_number, display_name, role, profile_photo_url, verification_status, is_submission_locked, created_at), ProfileUpdate (display_name optional)
- [ ] T036 [US2] Implement services/api/app/services/profile_service.py — setup_profile() inserts into profiles table (409 if exists), get_profile_me() returns profile + generates signed URL for profile_photo_path if set, update_profile() allows display_name only, upload_photo() uploads to profile-photos bucket and updates profile_photo_path
- [ ] T037 [P] [US2] Implement services/api/app/services/storage_service.py — generate_signed_url(bucket, path, expires_in_seconds) using service role client; get_identity_document_urls(submission) generates signed URLs (60-min expiry) for all documents in identity-documents bucket
- [ ] T038 [US2] Implement services/api/app/api/profiles/router.py — POST /api/profiles/setup (Depends(get_current_user), 409 if exists), GET /api/profiles/me, PUT /api/profiles/me, POST /api/profiles/me/photo (multipart, JPEG/PNG, ≤5MB server-side validation)

### Frontend

- [ ] T039 [P] [US2] Create apps/main/src/lib/api/profiles.ts — setupProfile(role, displayName), getMe(), updateMe(data), uploadPhoto(file)
- [ ] T040 [P] [US2] Create apps/main/src/components/auth/RoleSelector.tsx — two large cards (Passenger / Driver) with description text and shadcn/ui radio-group; selected state highlighted
- [ ] T041 [P] [US2] Create apps/main/src/components/profile/ProfilePhotoUpload.tsx — drag-drop + click-to-upload, JPEG/PNG client-side filter, size preview before upload, 5MB client-side size gate showing error before API call
- [ ] T042 [P] [US2] Create apps/main/src/components/profile/ProfileForm.tsx — display name field (2–50 chars), integrated with ProfilePhotoUpload, react-hook-form + zod validation
- [ ] T043 [US2] Create apps/main/src/app/(auth)/role-select/page.tsx — RoleSelector, calls setupProfile, routes passenger → /onboarding/profile → /home; routes driver → /onboarding/profile → /onboarding/driver/verify-documents
- [ ] T044 [US2] Create apps/main/src/app/(onboarding)/profile/page.tsx — ProfileForm, calls updateMe for display name and uploadPhoto for optional photo; routes to next onboarding step based on role
- [ ] T045 [US2] Create apps/main/src/app/(app)/settings/profile/page.tsx — ProfileForm pre-populated from getMe(), allows updating display_name and replacing profile photo post-onboarding

**Checkpoint**: New user completes role + profile in one flow. Validated by quickstart.md Step 2.

---

## Phase 5: User Story 3 — Passenger ID Submission & Admin Review (Priority: P3)

**Goal**: Passengers upload NID front + back; an admin can approve or reject; passenger status reflects outcome; 3-attempt cap enforced with support email lockout message.

**Independent Test**: Submit 2 ID photos as passenger → status=pending_review. Admin approves → status=verified. Second user: reject 3 times → 4th submit returns 403 submission_locked with support_email.

### Backend

- [ ] T046 [P] [US3] Create services/api/app/models/verification.py — SubmissionResponse (submission_id, status, attempt_number), StatusResponse (verification_status, attempt_number, is_locked, rejection_reason, lockout_message), AdminQueueItem, AdminSubmissionDetail (with document_signed_urls)
- [ ] T047 [US3] Implement services/api/app/services/verification_service.py — submit_documents() checks is_submission_locked → 403 with support_email from platform_settings; checks for existing pending → 409; increments attempt_number; uploads files to identity-documents bucket; inserts verification_submissions row; updates profiles.verification_status='pending_review'. get_status() returns current submission status + lockout_message if locked.
- [ ] T048 [P] [US3] Implement services/api/app/services/audit_service.py — append_log(admin_id, action_type, target_user_id, submission_id=None, reason=None) inserts into admin_audit_logs; returns audit_log_id
- [ ] T049 [US3] Implement services/api/app/api/verification/router.py — POST /api/verification/submit (multipart, Depends(get_current_user)), GET /api/verification/status (Depends(get_current_user))

### Frontend

- [ ] T050 [P] [US3] Create apps/main/src/lib/api/verification.ts — submitDocuments(frontId, backId, license?), getStatus()
- [ ] T051 [P] [US3] Create apps/main/src/components/verification/DocumentUpload.tsx — single file upload slot with label (e.g. "National ID - Front"), JPEG/PNG filter, 10MB client-side limit, preview thumbnail after selection
- [ ] T052 [P] [US3] Create apps/main/src/components/verification/VerificationStatus.tsx — displays current status with icon (pending hourglass, verified checkmark, rejected X), shows rejection_reason if status=rejected
- [ ] T053 [P] [US3] Create apps/main/src/components/verification/LockoutMessage.tsx — displays support email with mailto link and instructions when is_locked=true; reads lockout_message from status response
- [ ] T054 [US3] Create apps/main/src/app/(onboarding)/verify-id/page.tsx — 2× DocumentUpload slots (front + back), submitDocuments() on submit, shows VerificationStatus with pending message on success, shows LockoutMessage if locked

**Checkpoint**: Passenger submission flow complete. Admin review wired in Phase 8 (US6). Validated by quickstart.md Steps 3–5.

---

## Phase 6: User Story 4 — Driver Identity & License Submission (Priority: P4)

**Goal**: Drivers upload 3 documents (NID front, NID back, driving license) — same backend as US3, driver-specific frontend only.

**Independent Test**: Log in as driver, upload 3 files via POST /api/verification/submit → submission_type='driver_id_license', status=pending_review. Admin approves → verification_status=verified → vehicle registration is unblocked.

- [ ] T055 [US4] Create apps/main/src/app/(onboarding)/driver/verify-documents/page.tsx — 3× DocumentUpload slots (NID Front, NID Back, Driving License), passes all 3 to submitDocuments(), shows VerificationStatus on success; reuses DocumentUpload and LockoutMessage from US3

**Checkpoint**: Driver submission flow works with the same backend as passenger. Backend already validated by US3.

---

## Phase 7: User Story 5 — Vehicle Registration (Priority: P5)

**Goal**: Verified drivers register exactly one vehicle. Unverified drivers are blocked (403). Plate number validated against Egyptian format.

**Independent Test**: Log in as verified driver with no vehicle → POST /api/vehicles/register with valid plate 'ABC 1234' → 201. GET /api/vehicles/me → returns vehicle. Attempt with invalid plate 'XXXXXXXXX' → 400.

### Backend

- [ ] T056 [P] [US5] Create services/api/app/models/vehicle.py — VehicleRegister (plate_number with Egyptian regex validation, make, model, year CHECK 2000–current, color, seat_count CHECK 2–7), VehicleResponse (id, plate_number, make, model, year, color, seat_count, registered_at), VehicleUpdate (color optional, seat_count optional)
- [ ] T057 [US5] Implement services/api/app/services/vehicle_service.py — register() Depends(get_current_verified_driver), validates plate with regex `/^[A-Z]{1,3}\s?\d{1,4}$|^\d{1,4}\s?[A-Z]{1,3}$/i`, inserts vehicles row (409 if driver already has vehicle); get_me(); update() allows color and seat_count only
- [ ] T058 [US5] Implement services/api/app/api/vehicles/router.py — POST /api/vehicles/register (Depends(get_current_verified_driver)), GET /api/vehicles/me (Depends(get_current_driver)), PUT /api/vehicles/me (Depends(get_current_verified_driver))

### Frontend

- [ ] T059 [P] [US5] Create apps/main/src/lib/api/vehicles.ts — registerVehicle(data), getMyVehicle(), updateMyVehicle(data)
- [ ] T060 [P] [US5] Create apps/main/src/components/vehicle/VehicleRegistrationForm.tsx — plate number (Egyptian format hint + inline regex validation), make/model/color text, year (2000–current range picker), seat count (2–7 numeric input), react-hook-form + zod
- [ ] T061 [US5] Create apps/main/src/app/(onboarding)/driver/register-vehicle/page.tsx — VehicleRegistrationForm, calls registerVehicle() on submit, shows "Ready to post rides" success screen on 201; shows 409 message ("You already have a registered vehicle") if duplicate

**Checkpoint**: Verified drivers can register a vehicle and land on the ready state. Validated by quickstart.md Step 7.

---

## Phase 8: User Story 6 — Admin Verification Dashboard (Priority: P6)

**Goal**: Admin can view the pending queue (passenger + driver tabs), open a submission to view signed document URLs, approve or reject with a mandatory reason, suspend/reinstate users, unlock locked accounts, and review history.

**Independent Test**: Submit a test passenger submission, log in to admin app, find it in queue, approve it, verify queue length decreases by 1 and audit log has an 'approved' entry.

### Backend

- [ ] T062 [P] [US6] Implement services/api/app/api/admin/verification_router.py — GET /api/admin/verification/queue (Depends(get_current_admin), paginated, type filter), GET /api/admin/verification/{submission_id} (returns signed doc URLs via storage_service), POST /api/admin/verification/{submission_id}/approve (updates submission+profile status, appends audit log, 409 if already processed), POST /api/admin/verification/{submission_id}/reject (requires reason, sets is_locked=True on 3rd rejection + updates platform_settings support_email into profile), POST /api/admin/verification/users/{user_id}/unlock (resets is_submission_locked, audit log), GET /api/admin/verification/history (paginated history of processed submissions)
- [ ] T063 [P] [US6] Implement services/api/app/api/admin/users_router.py — POST /api/admin/users/{user_id}/suspend (Depends(get_current_admin), updates verification_status='suspended', calls auth_service.revoke_sessions(user_id), appends audit log, requires reason, 409 if already suspended), POST /api/admin/users/{user_id}/reinstate (sets status='verified', audit log)

### Frontend — Admin App

- [ ] T064 [P] [US6] Create apps/admin/src/lib/api/admin-verification.ts — getQueue(type?, page), getSubmission(id), approve(id), reject(id, reason), unlock(userId), getHistory(page)
- [ ] T065 [P] [US6] Create apps/admin/src/lib/api/admin-users.ts — suspend(userId, reason), reinstate(userId)
- [ ] T066 [P] [US6] Create apps/admin/src/components/verification/SubmissionQueue.tsx — table with columns: user name, phone, submission time, attempt number; sorted oldest-first; row click navigates to detail page
- [ ] T067 [P] [US6] Create apps/admin/src/components/verification/DocumentViewer.tsx — renders signed URLs as <img> at readable size (max-width 600px), labels each image (NID Front / NID Back / License), gracefully handles missing license for passengers
- [ ] T068 [P] [US6] Create apps/admin/src/components/verification/ApproveButton.tsx — confirm dialog before POST approve; disables after action; shows new_status in success toast
- [ ] T069 [P] [US6] Create apps/admin/src/components/verification/RejectForm.tsx — textarea for rejection reason (required, min 10 chars), submit button disabled until reason entered; shows error if reason empty (NFR-005 enforcement)
- [ ] T070 [P] [US6] Create apps/admin/src/components/verification/UnlockButton.tsx — shown only when user is_submission_locked=true; confirm dialog; calls unlock(userId); shows success toast
- [ ] T071 [P] [US6] Create apps/admin/src/components/users/UserActionPanel.tsx — Suspend button (requires reason textarea) + Reinstate button; only one is active based on current verification_status; both have confirm dialogs
- [ ] T072 [US6] Create apps/admin/src/app/(dashboard)/page.tsx — dashboard home: shows count of pending passenger submissions, pending driver submissions, and total processed today; links to verification queue and history
- [ ] T073 [US6] Create apps/admin/src/app/(dashboard)/verification/page.tsx — tabs for "Passengers" and "Drivers", each renders SubmissionQueue; pagination controls
- [ ] T074 [US6] Create apps/admin/src/app/(dashboard)/verification/[submission_id]/page.tsx — DocumentViewer + user info (name, phone, attempt_number) + ApproveButton + RejectForm side by side; fetches submission detail with signed URLs on load
- [ ] T075 [US6] Create apps/admin/src/app/(dashboard)/verification/history/page.tsx — paginated table of processed submissions with outcome, reviewed_by admin email, and reviewed_at timestamp
- [ ] T076 [US6] Create apps/admin/src/app/(dashboard)/users/[user_id]/page.tsx — shows profile info (name, phone, role, verification_status), UserActionPanel (suspend/reinstate), UnlockButton if locked, audit log history for this user

**Checkpoint**: Full admin verification loop works end-to-end. Validated by quickstart.md Steps 4–8.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final wiring, auth-guard hardening, and quickstart end-to-end validation.

- [ ] T077 [P] Add Next.js middleware for session refresh and auth routing in apps/main/src/middleware.ts — refresh Supabase session on every request using server client; redirect unauthenticated requests to /login; redirect authenticated users without a profile to /role-select
- [ ] T078 [P] Add auth guard middleware to apps/admin — redirect unauthenticated or non-admin users to /login in apps/admin/src/middleware.ts
- [ ] T079 Run quickstart.md Steps 1–9 end-to-end validation against local Supabase + FastAPI + both Next.js apps; record any schema or behavior discrepancies in quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational; no dependency on US2–US6
- **US2 (Phase 4)**: Depends on Foundational; no dependency on US1 (but typically done after US1)
- **US3 (Phase 5)**: Depends on Foundational + US2 (profile must exist before submission)
- **US4 (Phase 6)**: Depends on US3 backend (reuses same service + endpoints)
- **US5 (Phase 7)**: Depends on Foundational + US4 (driver must be verified)
- **US6 (Phase 8)**: Depends on Foundational + US3 backend (needs verification_service, audit_service)
- **Polish (Phase 9)**: Depends on all user story phases complete

### User Story Dependencies

| Story | Depends On | Notes |
|---|---|---|
| US1 (Phone OTP) | Foundational | Independent entry point |
| US2 (Profiles) | Foundational | Logically after US1 (needs authenticated user) |
| US3 (Passenger ID) | US2 backend | Profile must exist before submission; admin review in US6 |
| US4 (Driver Docs) | US3 backend | Reuses verification endpoint; only new task is the page |
| US5 (Vehicle) | US4 | Driver must be verified before vehicle registration |
| US6 (Admin Dashboard) | US3 backend | Needs verification_service + audit_service from US3 |

### Within Each User Story

- Backend models → Backend services → Backend router
- Frontend API helpers → Frontend components → Frontend pages
- Backend must be complete before frontend integration

---

## Parallel Opportunities

### Phase 2 (Foundational) — can parallelize

```
T006–T009 (shared types)    ← all parallel, different files
T010–T016 (migrations)      ← sequential (FK dependencies between tables)
T017–T019 (Supabase clients) ← parallel with each other
T020–T023 (FastAPI core)    ← T020 first, then T021–T023 parallel
```

### Phase 3 (US1) — backend then frontend parallel

```
T024 (models)  →  T025 (service)  →  T026 (router)
                               ↓
T027–T031 (frontend helpers + components)  ← all parallel
                               ↓
T032–T034 (pages)  ← sequential (depend on above)
```

### Phase 8 (US6) — T062–T063 backend parallel, T064–T071 components parallel

```
T062 (verification router) [P]
T063 (users router)        [P]
       ↓
T064–T071 (components + API helpers) — all parallel
       ↓
T072–T076 (pages) — can parallelize across different page files
```

---

## Parallel Example: User Story 6 (Admin Dashboard)

```
# Launch backend routers together:
Task T062: Implement admin/verification_router.py
Task T063: Implement admin/users_router.py

# After backend: Launch all admin components together:
Task T064: admin-verification.ts API helpers
Task T065: admin-users.ts API helpers
Task T066: SubmissionQueue component
Task T067: DocumentViewer component
Task T068: ApproveButton component
Task T069: RejectForm component
Task T070: UnlockButton component
Task T071: UserActionPanel component

# After components: Build pages sequentially:
Task T072 → T073 → T074 → T075 → T076
```

---

## Implementation Strategy

### MVP First (US1 Only — Phone OTP works)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (migrations + core backend)
3. Complete Phase 3: US1 — OTP login works for both apps
4. **STOP and VALIDATE**: OTP login → session → Supabase Studio shows user
5. Proceed to US2

### Incremental Delivery

1. Setup + Foundational → Infra ready
2. US1 → Auth works (both apps can log in) → Validate
3. US2 → Profiles work (role selection) → Validate
4. US3 → Passenger submission + admin approval → Validate
5. US4 → Driver submission → Validate (same backend, new page only)
6. US5 → Vehicle registration → Validate
7. US6 → Full admin dashboard → Validate
8. Polish → End-to-end quickstart run → Done

### Key Constraints During Implementation

- Never hardcode `support@felseka.com` — always read from `platform_settings` table
- `identity-documents` bucket: never add a user SELECT policy — signed URLs are admin-only
- Submission attempt_number: always increment by 1 from the user's previous attempt_number (or 1 if none)
- Session revocation on suspend: must call BOTH `update profiles SET verification_status='suspended'` AND `supabase.auth.admin.sign_out(user_id, 'global')`
- Egyptian plate regex: `/^[A-Z]{1,3}\s?\d{1,4}$|^\d{1,4}\s?[A-Z]{1,3}$/i` — enforce server-side in vehicle_service.py

---

## Notes

- [P] tasks = different files, no unresolved dependencies on that phase's incomplete tasks
- [Story] label maps each task to a user story for traceability
- No test tasks generated (not requested in spec)
- Run migrations in order 001→007 (FK chain: profiles → verification_submissions → vehicles → admin_audit_logs)
- Each user story phase is independently completable and validates against quickstart.md
- Commit after each phase checkpoint, not after individual tasks
