# Data Model: Authentication & Verification

**Branch**: `003-auth-verification` | **Date**: 2026-06-14

---

## Entity 1 — Profile

Extends Supabase Auth's `auth.users` table with application-specific user data. One `Profile` exists per `auth.users` record.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID | PK, FK → `auth.users(id)` ON DELETE CASCADE | Same UUID as Supabase Auth user |
| `phone_number` | TEXT | UNIQUE, NOT NULL | E.164 format: `+20XXXXXXXXXX` |
| `display_name` | TEXT | NOT NULL, length 2–50 | Set during profile creation (US2) |
| `role` | TEXT | NOT NULL, CHECK IN (`passenger`, `driver`, `admin`) | Permanent after role selection |
| `profile_photo_path` | TEXT | NULLABLE | Storage path in `profile-photos` bucket |
| `verification_status` | TEXT | NOT NULL DEFAULT `unverified` | See state machine below |
| `is_submission_locked` | BOOLEAN | NOT NULL DEFAULT FALSE | Set TRUE after 3rd rejected submission |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| `last_login_at` | TIMESTAMPTZ | NULLABLE | Updated on each OTP verification |

**Verification Status State Machine**:

```
unverified
    │
    ▼ (user submits documents)
pending_review
    │
    ├──► verified         (admin approves)
    │
    ├──► rejected         (admin rejects)
    │       │
    │       ▼ (user re-submits, attempt ≤ 3)
    │    pending_review
    │
    │    (attempt 3 rejected → is_submission_locked = TRUE)
    │
    └──► suspended        (admin suspends; from verified or rejected)
             │
             ▼ (admin reinstates)
          verified
```

**Role-to-Submission-Type mapping**:
- `passenger` → submits `passenger_id` (NID front + back)
- `driver` → submits `driver_id_license` (NID front + back + license)
- `admin` → no verification submission; set manually by platform operator

**RLS Policies**:
- SELECT own row: `auth.uid() = id`
- UPDATE own row (display_name, profile_photo_path, last_login_at only): `auth.uid() = id`
- Admin SELECT any: `is_admin()`
- Admin UPDATE any (verification_status, is_submission_locked): `is_admin()`

---

## Entity 2 — VerificationSubmission

One submission record per attempt. A user may have up to 3 records (attempt_number 1, 2, 3). Only the latest submission is `pending_review` or the terminal state; earlier submissions are `approved` or `rejected`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID | PK DEFAULT gen_random_uuid() | |
| `user_id` | UUID | NOT NULL, FK → `profiles(id)` | |
| `submission_type` | TEXT | NOT NULL, CHECK IN (`passenger_id`, `driver_id_license`) | |
| `front_id_path` | TEXT | NOT NULL | Storage path in `identity-documents` bucket |
| `back_id_path` | TEXT | NOT NULL | Storage path in `identity-documents` bucket |
| `license_path` | TEXT | NULLABLE | Required for `driver_id_license` type; NULL for `passenger_id` |
| `status` | TEXT | NOT NULL DEFAULT `pending_review` | `pending_review` \| `approved` \| `rejected` |
| `rejection_reason` | TEXT | NULLABLE | NOT NULL when status = `rejected` (enforced at app layer) |
| `reviewer_id` | UUID | NULLABLE, FK → `auth.users(id)` | Set on review |
| `reviewed_at` | TIMESTAMPTZ | NULLABLE | Set on review |
| `submitted_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| `attempt_number` | INTEGER | NOT NULL DEFAULT 1, CHECK 1–3 | Incremented on each re-submission |
| `is_locked` | BOOLEAN | NOT NULL DEFAULT FALSE | TRUE on 3rd rejection; cleared by admin unlock |

**Uniqueness constraint**: A user may not have two `pending_review` submissions simultaneously. Enforced at application layer before INSERT.

**Storage paths**:
- `{user_id}/nid_front_{submission_id}.jpg`
- `{user_id}/nid_back_{submission_id}.jpg`
- `{user_id}/license_{submission_id}.jpg` (driver only)

**RLS Policies**:
- SELECT own submissions: `auth.uid() = user_id`
- INSERT own submission: `auth.uid() = user_id`
- Admin SELECT all: `is_admin()`
- Admin UPDATE (status, rejection_reason, reviewer_id, reviewed_at, is_locked): `is_admin()`
- No DELETE for any role

---

## Entity 3 — Vehicle

One vehicle per driver account (enforced by UNIQUE constraint on `driver_id`).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID | PK DEFAULT gen_random_uuid() | |
| `driver_id` | UUID | NOT NULL UNIQUE, FK → `profiles(id)` | One vehicle per driver |
| `plate_number` | TEXT | NOT NULL | Format: 1–3 letters + 1–4 digits (or reverse); validated at app layer |
| `make` | TEXT | NOT NULL | Brand name, e.g., "Toyota" |
| `model` | TEXT | NOT NULL | Model name, e.g., "Corolla" |
| `year` | INTEGER | NOT NULL, CHECK 2000–current year | |
| `color` | TEXT | NOT NULL | Free text, e.g., "White" |
| `seat_count` | INTEGER | NOT NULL, CHECK 2–7 | Passenger seats only (excludes driver) |
| `is_active` | BOOLEAN | NOT NULL DEFAULT TRUE | Soft deactivation for future use |
| `registered_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |

**RLS Policies**:
- SELECT/INSERT/UPDATE own vehicle: `auth.uid() = driver_id`
- Admin SELECT any: `is_admin()`

---

## Entity 4 — AdminAuditLog

Append-only. No UPDATE or DELETE policies. Every admin action on users or submissions is recorded here.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID | PK DEFAULT gen_random_uuid() | |
| `admin_id` | UUID | NOT NULL, FK → `auth.users(id)` | The admin who took the action |
| `action_type` | TEXT | NOT NULL, CHECK IN (`approved`, `rejected`, `suspended`, `reinstated`, `unlocked`) | |
| `target_user_id` | UUID | NOT NULL, FK → `profiles(id)` | The user affected |
| `submission_id` | UUID | NULLABLE, FK → `verification_submissions(id)` | Set for `approved`/`rejected`/`unlocked` actions |
| `reason` | TEXT | NULLABLE | Required for `rejected` and `suspended` actions |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |

**RLS Policies**:
- INSERT: `is_admin()`
- SELECT: `is_admin()`
- UPDATE: none (no policy = no access)
- DELETE: none (append-only)

---

## Entity 5 — PlatformSettings

Key-value store for operator-configurable settings. Initially seeded with `support_email`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `key` | TEXT | PK | e.g., `support_email` |
| `value` | TEXT | NOT NULL | e.g., `support@felseka.com` |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |

**Initial seed**:
```sql
INSERT INTO platform_settings (key, value) VALUES ('support_email', 'support@felseka.com');
```

**RLS Policies**:
- SELECT: any authenticated user (frontend needs to display support email)
- INSERT/UPDATE: `is_admin()` only

---

## Supabase Storage Buckets

### `profile-photos` (private)

| Property | Value |
|---|---|
| Visibility | Private |
| Max file size | 5 MB |
| Allowed MIME types | `image/jpeg`, `image/png` |
| Path pattern | `{user_id}/profile.{ext}` |

**Storage policies**:
- INSERT: `(auth.uid())::text = (storage.foldername(name))[1]` — users upload to own folder only
- SELECT: `(auth.uid())::text = (storage.foldername(name))[1]` — users read own photos
- UPDATE/DELETE: same as SELECT

### `identity-documents` (private)

| Property | Value |
|---|---|
| Visibility | Private |
| Max file size | 10 MB |
| Allowed MIME types | `image/jpeg`, `image/png` |
| Path pattern | `{user_id}/{document_type}_{submission_id}.{ext}` |

**Storage policies**:
- INSERT: `(auth.uid())::text = (storage.foldername(name))[1]` — users upload to own folder only
- SELECT: **none** — no direct user read access; admin access via backend-generated signed URLs only
- Signed URL generation: service role key, 60-minute expiry, generated by FastAPI admin endpoints

---

## Database Migration Order

1. Enable `uuid-ossp` extension (if not already from Phase 1)
2. Create `is_admin()` helper function
3. Create `profiles` table + RLS policies
4. Create `verification_submissions` table + RLS policies
5. Create `vehicles` table + RLS policies
6. Create `admin_audit_logs` table + RLS policies
7. Create `platform_settings` table + RLS policies + seed data
8. Create Supabase Storage buckets (`profile-photos`, `identity-documents`) + storage policies
9. Create Supabase Auth trigger: on new `auth.users` insert, do NOT auto-create profile (profile created explicitly by `/api/profiles/setup` after role selection)

---

## API Request / Response Shapes

### Profile Setup Request
```json
{
  "role": "passenger | driver",
  "display_name": "Ahmed Hassan",
  "profile_photo_path": "uuid/profile.jpg"
}
```

### Verification Submission Request (multipart/form-data)
```
front_id: <file>
back_id: <file>
license: <file>   // driver only
```

### Verification Status Response
```json
{
  "status": "pending_review | verified | rejected | unverified",
  "attempt_number": 1,
  "is_locked": false,
  "rejection_reason": null,
  "lockout_message": null
}
```

### Vehicle Registration Request
```json
{
  "plate_number": "ABC 1234",
  "make": "Toyota",
  "model": "Corolla",
  "year": 2020,
  "color": "White",
  "seat_count": 4
}
```

### Admin Queue Item Response
```json
{
  "submission_id": "uuid",
  "user_id": "uuid",
  "user_name": "Ahmed Hassan",
  "phone_number": "+20123456789",
  "submission_type": "passenger_id | driver_id_license",
  "submitted_at": "2026-06-14T10:00:00Z",
  "attempt_number": 1,
  "document_signed_urls": {
    "front_id": "https://...",
    "back_id": "https://...",
    "license": "https://..."
  }
}
```
