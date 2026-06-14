# Research: Authentication & Verification

**Branch**: `003-auth-verification` | **Date**: 2026-06-14

---

## Decision 1: Supabase Auth Phone OTP Provider

**Decision**: Use Supabase Auth's built-in phone OTP provider with Twilio as the SMS gateway.

**Rationale**: Supabase Auth natively supports phone OTP via Twilio, MessageBird, and Vonage. Twilio has strong Egyptian carrier coverage and is the most widely documented option with Supabase. The provider is configured in the Supabase dashboard (no custom implementation) — satisfying the constitution's requirement to use Supabase Auth.

**Configuration**: `SUPABASE_AUTH_SMS_PROVIDER=twilio`, requires `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_MESSAGE_SERVICE_SID` in environment. Phone OTP expires after 5 minutes (configurable in Supabase Auth dashboard).

**Rate limiting**: Supabase Auth has built-in rate limiting on OTP requests. Additional application-level rate limiting (FR-005: 3 resends per 15 minutes) is enforced at the FastAPI backend by tracking resend attempts per phone number in a short-lived cache.

**Alternatives considered**: Custom OTP with direct Twilio SDK — rejected because it duplicates Supabase Auth's built-in capability and introduces an unaudited code path for authentication.

---

## Decision 2: Admin Authentication (Email + Password)

**Decision**: Admin users authenticate via Supabase Auth email + password provider in the same Supabase project, distinguished by a `role = 'admin'` column in the `profiles` table and enforced via FastAPI middleware.

**Rationale**: Supabase Auth supports multiple providers in a single project. Email + password is appropriate for internal staff on desktop — no SMS dependency, no phone required. A separate "admin user" is created by the platform operator via the Supabase dashboard (or admin CLI) using email + password. The admin's role is set in the `profiles` table; all admin API endpoints check `current_user.role == 'admin'` via middleware.

**Security note**: Admin JWTs are indistinguishable from user JWTs at the token level — the role distinction is enforced in the database and backend. Admin credentials are provisioned offline (not self-registerable).

**Alternatives considered**: Separate Supabase project for admin — rejected (adds operational complexity, two separate Supabase instances to manage). Basic HTTP auth — rejected (no session management, not Supabase Auth).

---

## Decision 3: Immediate Session Revocation on Suspension

**Decision**: Two-layer approach — (a) set `verification_status = 'suspended'` in the `profiles` table, and (b) call `supabase.auth.admin.signOut(userId, 'global')` to revoke all refresh tokens.

**Rationale**: Supabase JWTs are short-lived (1 hour by default). Revoking refresh tokens prevents silent re-authentication. The FastAPI auth middleware checks `profiles.verification_status` on every protected request — if `suspended`, the request is rejected with HTTP 401 even if the JWT is technically valid. This two-layer approach achieves effective immediate revocation without waiting for JWT expiry.

**Implementation pattern**:
```
Request → FastAPI middleware:
  1. Verify JWT signature (Supabase) → get user_id
  2. Query profiles WHERE id = user_id → check verification_status
  3. If status = 'suspended' → return 401 {"error": "account_suspended"}
  4. Attach user profile to request context → proceed
```

**Alternatives considered**: JWT blocklist (Redis) — rejected for MVP (adds infrastructure dependency). Waiting for natural JWT expiry — rejected (up to 1 hour gap violates the spec's "no grace period" requirement for FR-024).

---

## Decision 4: Supabase Storage Architecture for Identity Documents

**Decision**: Two private Supabase Storage buckets — `profile-photos` and `identity-documents`. Documents are stored at path `{user_id}/{document_type}_{timestamp}.{ext}`. Signed URLs with 60-minute expiry are generated server-side (FastAPI with service role key) for admin document viewing.

**Rationale**: Private buckets prevent any direct public access (SC-008). Signed URLs give admins time-limited access without exposing permanent links. The 60-minute expiry is generous for a review session while still being meaningfully short. Storing by `user_id` prefix enables easy RLS policies on Storage.

**Storage RLS**:
- `profile-photos`: Authenticated users can upload to `{user_id}/*`; users can read their own photos; no public read.
- `identity-documents`: Authenticated users can upload to `{user_id}/*`; NO user read policy (not even the uploader) — only the backend service role generates signed URLs for admin viewing. This prevents users from extracting permanent links to their own documents.

**Path format**: `{user_id}/nid_front_{submission_id}.jpg`, `{user_id}/nid_back_{submission_id}.jpg`, `{user_id}/license_{submission_id}.jpg`

**Alternatives considered**: Storing base64 in the database — rejected (bloats DB, no streaming, no CDN). Public bucket with obscure paths — rejected (violates FR-012, SC-008, constitution data standards).

---

## Decision 5: Row Level Security (RLS) Strategy

**Decision**: RLS enabled on all four new tables. Policies use `auth.uid()` for user-scoped access and a custom `is_admin()` function for admin-scoped access.

**`is_admin()` helper**:
```sql
CREATE OR REPLACE FUNCTION is_admin()
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin'
  );
$$ LANGUAGE sql SECURITY DEFINER;
```

**Table policies**:
- `profiles`: SELECT/UPDATE own row (`id = auth.uid()`); admins SELECT/UPDATE any row.
- `verification_submissions`: SELECT/INSERT own row; admins SELECT/UPDATE any row.
- `vehicles`: SELECT/INSERT/UPDATE own row (driver only); admins SELECT any row.
- `admin_audit_logs`: INSERT for admins only; SELECT for admins only; no DELETE for anyone (append-only enforced by omitting DELETE policy).
- `platform_settings`: SELECT for all authenticated; UPDATE/INSERT for admins only.

**Alternatives considered**: Application-level access control only (no RLS) — rejected (bypasses DB-level security; a compromised API key could access all data directly).

---

## Decision 6: Egyptian Plate Number Validation

**Decision**: For MVP with English-first interface, accept plate numbers matching the pattern: 1–3 Latin letters followed by 1–4 digits (or vice versa), with an optional space separator. Regex: `/^[A-Z]{1,3}\s?\d{1,4}$|^\d{1,4}\s?[A-Z]{1,3}$/i`

**Rationale**: Modern Egyptian private vehicle plates use alphanumeric formats transliterable to Latin script in an English interface. Older numeric-only plates are accommodated by the digit-only fallback. Full Arabic script validation is deferred with Arabic/RTL support (post-competition). Server-side validation uses this regex; client-side shows the same constraint to the user.

**Examples accepted**: `ABC 1234`, `ABC1234`, `1234ABC`, `12345` (numeric-only older plates).

**Alternatives considered**: Full Arabic Unicode plate validation — deferred (Arabic/RTL is post-competition). No validation — rejected (FR-027 requires format enforcement).

---

## Decision 7: Verification Submission Lock + Support Email Flow

**Decision**: A `platform_settings` table stores the `support_email` key. When a user's submission is locked (3rd rejection), the backend returns a 403 response with a `lockout_message` field containing the current support email from settings. The frontend displays this message.

**Rationale**: Configurable support email (FR-037 requirement) is best served by a settings table rather than environment variables (which require a deploy to change). The admin can update the support email via the admin panel without touching infrastructure.

**Admin unlock**: Sets `profiles.is_submission_locked = FALSE` and `verification_submissions.attempt_number` resets to allow one more attempt. This is recorded in `admin_audit_logs` with `action_type = 'unlocked'`.

**Alternatives considered**: Hard-coded email in frontend — rejected (FR-037 requires configurability). Environment variable — rejected (requires deploy to change; ops overhead for a non-technical setting).

---

## Decision 8: Backend Verification Status Middleware

**Decision**: FastAPI dependency injection pattern — a `get_current_verified_user()` dependency used on protected routes that require verified status.

```python
# Two levels of auth dependency:
# 1. get_current_user() — any authenticated user (checks suspension only)
# 2. get_current_verified_user() — authenticated + verified (for booking/ride endpoints)
```

Applied in:
- Booking endpoints (Phase 6): `Depends(get_current_verified_passenger)`
- Ride creation endpoints (Phase 4): `Depends(get_current_verified_driver)`
- Vehicle registration: `Depends(get_current_verified_driver)` (verified but no vehicle yet)

**Rationale**: FastAPI's dependency injection makes the verification check declarative and reusable across routes. This is the backend enforcement required by FR-019, FR-023, and the constitution's architecture standard. The check queries `profiles.verification_status` on every call — acceptable at 1,000 users scale; results cached per-request within the dependency context.

**Alternatives considered**: Middleware layer (blanket check on all routes) — rejected (overly broad; some endpoints like `/health` don't need verification). Frontend-only check — rejected by constitution.
