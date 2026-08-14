# Data Model: Required Phone Number & Profile Photo (Email+OTP Only)

## Entity: `profiles` (existing table, extended)

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | UUID (PK, FK → `auth.users.id`) | NOT NULL | unchanged |
| `email` | TEXT (UNIQUE) | NOT NULL | unchanged — already the sole sign-in identifier |
| `phone_number` | TEXT | **NULL** (new column) | **NEW.** Plain, unverified, user-typed. No SMS ever sent. No uniqueness constraint (FR-011). Required at the application layer for new signups; pre-existing rows may be NULL until the user completes the gate. Format checked by a `CHECK` constraint mirroring the app-layer regex, applied only when non-NULL. |
| `display_name` | TEXT | NOT NULL | unchanged |
| `role` | TEXT | NOT NULL | unchanged (`passenger` \| `driver` \| `admin`) |
| `profile_photo_path` | TEXT | NULL (unchanged) | Already exists, already nullable. Behavior changes: application layer now treats this as required for *new* signups (submit blocked without it) while leaving the column nullable for legacy rows, consistent with `phone_number`. |
| `verification_status` | TEXT | NOT NULL | unchanged |
| `is_submission_locked` | BOOLEAN | NOT NULL | unchanged |
| `created_at` | TIMESTAMPTZ | NOT NULL | unchanged |
| `last_login_at` | TIMESTAMPTZ | NULL | unchanged |
| `language_preference` | TEXT | NULL | unchanged |

### New DB constraint

```sql
ALTER TABLE profiles ADD COLUMN phone_number TEXT;

ALTER TABLE profiles ADD CONSTRAINT chk_profiles_phone_number_format
    CHECK (phone_number IS NULL OR phone_number ~ '^\+[1-9][0-9]{6,14}$');
```

No `NOT NULL`, no `UNIQUE` — both were deliberately rejected (see [research.md](./research.md) → "Required-ness enforced at the application layer").

### Validation rules (application layer)

| Field | Rule | Enforced by |
|---|---|---|
| `phone_number` | Must match `^\+[1-9]\d{6,14}$` when provided | `ProfileUpdate` Pydantic validator (`services/api/app/models/profile.py`) |
| `phone_number` | Required (non-empty) before onboarding submit succeeds | `apps/main/src/app/(onboarding)/profile/page.tsx` client-side check, mirrored by the gate page for backfill |
| `profile_photo_path` (via uploaded `photo` file) | Required before onboarding submit succeeds | `apps/main/src/app/(onboarding)/profile/page.tsx` — `if (!photo)` blocks submit |
| Photo file | `image/jpeg` or `image/png`, ≤5MB | Already enforced client-side (`ProfilePhotoUpload.tsx`) and server-side (`profile_service.upload_profile_photo`) — unchanged |

### State: "profile complete" (derived, not persisted)

A profile is **complete** when both `phone_number IS NOT NULL` and `profile_photo_path IS NOT NULL`. This is computed on read (in `app/page.tsx`'s existing profile `select`, and in the OAuth callback's `/api/profiles/me` fetch) — it is not a stored column or enum value. No new entity or migration is needed to represent it.

```text
new signup ──(role-select creates row, both fields NULL)──▶ onboarding page
                                                                  │ (blocks submit without phone+photo)
                                                                  ▼
                                                    profile complete, proceeds to ID review

pre-existing row, one or both NULL ──(sign in)──▶ app/page.tsx / auth/callback
                                                          │ redirect
                                                          ▼
                                                  /complete-profile (asks only for missing field(s))
                                                          │ submit
                                                          ▼
                                              profile complete, normal app access resumes
```

## API payload changes

### `ProfileUpdate` (request body of `PUT /api/profiles/me`)

```python
class ProfileUpdate(BaseModel):
    display_name: str | None = None
    language_preference: Literal["en", "ar"] | None = None
    phone_number: str | None = None   # NEW — format-validated when present
```

### `ProfileResponse` (response body of `POST /setup`, `GET /me`, `PUT /me`)

```python
class ProfileResponse(BaseModel):
    id: str
    email: str
    phone_number: str | None   # NEW — None for legacy rows not yet backfilled
    display_name: str
    role: str
    profile_photo_url: str | None
    verification_status: str
    is_submission_locked: bool
    rating_avg: float | None = None
    rating_count: int = 0
    created_at: str
    language_preference: str | None = None
```

### Shared TypeScript types (`packages/shared/src/types/user.ts`)

```ts
export interface Profile {
  id: string;
  email: string;
  phone_number: string | null;   // NEW
  display_name: string;
  role: Role;
  profile_photo_url: string | null;
  verification_status: VerificationStatus;
  is_submission_locked: boolean;
  rating_avg: number | null;
  rating_count: number;
  created_at: string;
  language_preference: Locale | null;
}

export interface ProfileUpdate {
  display_name?: string;
  language_preference?: Locale;
  phone_number?: string;   // NEW
}
```

`ProfileSetup` is unchanged (`{ role, display_name }`) — phone number is submitted via the immediately-following `updateMe` call, not at row-creation time (see [research.md](./research.md) design decision).
