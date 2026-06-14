# Quickstart & Validation Guide: Authentication & Verification

**Feature**: `003-auth-verification` | **Date**: 2026-06-14

Run steps in order. Each step has a verification check before proceeding.

---

## Prerequisites

- Phase 1 complete: Supabase running locally (`supabase start`), FastAPI backend running, both Next.js apps running
- Supabase Auth phone OTP configured (Twilio credentials in `services/api/.env`)
- A test Egyptian phone number that can receive SMS (e.g., a real SIM or Twilio test number)
- Admin account pre-seeded in Supabase Auth (email + password)
- `curl` or an HTTP client (Bruno, Postman)

**Local service ports**:
- FastAPI backend: `http://localhost:8000`
- Main app: `http://localhost:3000`
- Admin app: `http://localhost:3001`
- Supabase Studio: `http://localhost:54323`

---

## Step 1 — Phone OTP Registration

**Test**: New user registers via phone OTP.

```bash
# Request OTP
curl -X POST http://localhost:8000/api/auth/request-otp \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+201234567890"}'
```

**Expected**:
```json
{ "message": "OTP sent", "expires_in_seconds": 300 }
```

Enter the received SMS code:
```bash
curl -X POST http://localhost:8000/api/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+201234567890", "otp": "XXXXXX"}'
```

**Expected**: `200 OK` with `access_token`, `refresh_token`, and `"is_new_user": true`.

Save the `access_token` as `$TOKEN` for subsequent steps.

**Verify** in Supabase Studio → Authentication → Users: the phone number appears.

---

## Step 2 — Profile Setup & Role Selection

```bash
curl -X POST http://localhost:8000/api/profiles/setup \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "passenger", "display_name": "Test Passenger"}'
```

**Expected**: `201 Created` with `verification_status: "unverified"`.

```bash
# Verify profile exists
curl http://localhost:8000/api/profiles/me \
  -H "Authorization: Bearer $TOKEN"
```

**Expected**: Profile with `role: "passenger"`, `verification_status: "unverified"`.

**UI check**: Open `http://localhost:3000` — after login, role-selection screen appears; selecting "Passenger" routes to the ride-search home.

---

## Step 3 — Passenger ID Submission

```bash
curl -X POST http://localhost:8000/api/verification/submit \
  -H "Authorization: Bearer $TOKEN" \
  -F "front_id=@/path/to/test_front.jpg" \
  -F "back_id=@/path/to/test_back.jpg"
```

**Expected**: `201 Created` with `status: "pending_review"`, `attempt_number: 1`.

```bash
# Check status
curl http://localhost:8000/api/verification/status \
  -H "Authorization: Bearer $TOKEN"
```

**Expected**: `verification_status: "pending_review"`.

**Verify** in Supabase Studio → Table Editor → `verification_submissions`: row exists with `status = 'pending_review'` and `attempt_number = 1`.

---

## Step 4 — Admin Login & Queue Review

Open `http://localhost:3001` (admin app).

Login with admin email + password (pre-seeded credentials).

**Expected**: Admin dashboard loads. Verification queue shows the passenger submission from Step 3 in the "Passenger" section.

```bash
# Via API: admin login
ADMIN_TOKEN=$(curl -X POST http://localhost:8000/api/auth/verify-otp ... )
# Or use Supabase client with email/password

# List queue
curl http://localhost:8000/api/admin/verification/queue \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Expected**: Queue contains the test submission. `total: 1`.

---

## Step 5 — Admin Approval

```bash
# Get submission_id from queue response
SUBMISSION_ID="uuid-from-step-3"

curl -X POST http://localhost:8000/api/admin/verification/$SUBMISSION_ID/approve \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Expected**: `200 OK` with `new_status: "verified"`.

```bash
# Verify passenger status changed
curl http://localhost:8000/api/profiles/me \
  -H "Authorization: Bearer $TOKEN"
```

**Expected**: `verification_status: "verified"`.

**Verify**: Supabase Studio → `profiles` table: `verification_status = 'verified'`. `admin_audit_logs` table: one `approved` record.

---

## Step 6 — Rejection & Re-submission Cap

Register a second test phone number as a passenger. Submit ID documents. Then reject 3 times:

```bash
# Reject (repeat 3 times with different reasons)
curl -X POST http://localhost:8000/api/admin/verification/$SUBMISSION_ID/reject \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Test rejection 1"}'
```

After the 3rd rejection, attempt a 4th submission from the test user:

```bash
curl -X POST http://localhost:8000/api/verification/submit \
  -H "Authorization: Bearer $TOKEN2" \
  -F "front_id=@/path/to/test_front.jpg" \
  -F "back_id=@/path/to/test_back.jpg"
```

**Expected**: `403 Forbidden` with `error: "submission_locked"` and `support_email` in response body.

**Verify**: `profiles.is_submission_locked = TRUE`, `verification_submissions.is_locked = TRUE`.

**Admin unlock**:
```bash
curl -X POST http://localhost:8000/api/admin/verification/users/$USER2_ID/unlock \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Expected**: `200 OK`, `is_submission_locked: false`. User can now submit one more time.

---

## Step 7 — Driver Onboarding

Register a third test phone number. Select "Driver" role during profile setup.

Submit driver documents (3 files):
```bash
curl -X POST http://localhost:8000/api/verification/submit \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -F "front_id=@/path/to/nid_front.jpg" \
  -F "back_id=@/path/to/nid_back.jpg" \
  -F "license=@/path/to/license.jpg"
```

Admin approves the driver submission (same flow as Step 5).

**Vehicle registration**:
```bash
curl -X POST http://localhost:8000/api/vehicles/register \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plate_number": "ABC 1234",
    "make": "Toyota",
    "model": "Corolla",
    "year": 2021,
    "color": "White",
    "seat_count": 4
  }'
```

**Expected**: `201 Created` with vehicle details.

**UI check**: Driver sees "Ready to post rides" confirmation screen in `apps/main`.

---

## Step 8 — Suspension & Session Revocation

```bash
curl -X POST http://localhost:8000/api/admin/users/$DRIVER_USER_ID/suspend \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Policy violation test"}'
```

**Expected**: `200 OK` with `new_status: "suspended"`.

Immediately attempt to use the driver's existing token:
```bash
curl http://localhost:8000/api/profiles/me \
  -H "Authorization: Bearer $DRIVER_TOKEN"
```

**Expected**: `401 Unauthorized` with `error: "account_suspended"` — no grace period.

**Verify**: `profiles.verification_status = 'suspended'`. `admin_audit_logs` has `suspended` entry.

---

## Step 9 — Unverified User Blocking

Attempt to call a protected Phase 4 endpoint (ride creation) with an unverified user token:

```bash
# This endpoint will be implemented in Phase 4 — test the middleware returns the right error
curl -X POST http://localhost:8000/api/rides \
  -H "Authorization: Bearer $UNVERIFIED_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"origin": "...", "destination": "..."}'
```

**Expected**: `403 Forbidden` with `error: "verification_required"` (enforced by `get_current_verified_driver` dependency).

---

---

## T079 Validation Record — 2026-06-14

End-to-end validation performed against implemented code (not against a running environment — local Supabase + FastAPI services require actual runtime). Discrepancies and notes recorded below.

### Schema alignment ✓
- All 5 tables (`profiles`, `verification_submissions`, `vehicles`, `admin_audit_logs`, `platform_settings`) created in migration files with constraints matching contracts.
- `is_submission_locked` column exists on `profiles`; `is_locked` column exists on `verification_submissions`. Both used correctly in verification_service and admin rejection flow.

### Behavioral alignment ✓
- Steps 1–3: OTP + profile + submission chain matches API contracts (request-otp → verify-otp → /setup → /submit).
- Steps 4–5: Admin queue and approve endpoints implemented; `get_current_admin()` dependency enforced.
- Step 6: 3-attempt cap enforced in `verification_service.py`; `is_third = attempt_number >= 3` triggers lock on reject; unlock resets both `profiles.is_submission_locked` and `verification_submissions.is_locked`.
- Step 7: Driver 3-file submission uses same `/api/verification/submit` endpoint; vehicle registration blocked by `get_current_verified_driver()` dependency.
- Step 8: Suspension writes `verification_status='suspended'` to profiles AND calls `auth_service.revoke_sessions(user_id)` (two-layer revocation). `get_current_user()` raises 401 on next request.
- Step 9: `get_current_verified_driver()` / `get_current_verified_passenger()` return 403 `verification_required` for unverified users.

### Known runtime prerequisites (not blocking)
- Twilio credentials must be configured in `services/api/.env` for real SMS delivery.
- Admin user must be seeded manually in Supabase Auth before Step 4 (no seed script included — out of scope for this phase).
- Supabase Storage buckets are created via migration 007; `supabase db push` or `supabase migration up` must be run before file uploads work.

## Reference

- API contracts: [contracts/auth-api.md](contracts/auth-api.md)
- Data model: [data-model.md](data-model.md)
- Research decisions: [research.md](research.md)
- Spec: [spec.md](spec.md)
