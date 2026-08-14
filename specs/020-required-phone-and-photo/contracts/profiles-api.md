# Contract: Profiles API changes

Base path: `/api/profiles` (FastAPI router `services/api/app/api/profiles/router.py`)

## `PUT /api/profiles/me` — extended request

**Auth**: Bearer token (existing `get_current_user` dependency) — unchanged.

**Request body** (extends existing `ProfileUpdate`):

```json
{
  "display_name": "string, optional",
  "language_preference": "en | ar, optional",
  "phone_number": "string, optional, e.g. +201234567890"
}
```

- `phone_number`, when present, MUST match `^\+[1-9]\d{6,14}$`. A non-matching value returns `422 Unprocessable Entity` (standard Pydantic validation error shape — no new error code).
- Partial update semantics are unchanged: omitted fields are left untouched; this is not a full-resource replace.
- No new success/error status codes are introduced beyond what `PUT /me` already returns (`200` with the updated `ProfileResponse`).

## `GET /api/profiles/me`, `POST /api/profiles/setup`, `PUT /api/profiles/me` — extended response

All three endpoints return `ProfileResponse`, which gains one new field:

```json
{
  "id": "uuid",
  "email": "string",
  "phone_number": "string | null",
  "display_name": "string",
  "role": "passenger | driver",
  "profile_photo_url": "string | null",
  "verification_status": "unverified | pending_review | verified | rejected | suspended",
  "is_submission_locked": "boolean",
  "rating_avg": "number | null",
  "rating_count": "number",
  "created_at": "ISO 8601 string",
  "language_preference": "en | ar | null"
}
```

`phone_number` is `null` for any profile row created before this feature shipped and not yet backfilled through the completion gate.

**No changes** to `POST /api/profiles/setup`'s request body (`ProfileSetup` stays `{ role, display_name }`) — phone is submitted via the immediately-following `PUT /me` call from the onboarding page, not at row-creation time.

**No changes** to `POST /api/profiles/me/photo`, `GET /api/profiles/{user_id}/public`, or `GET /api/profiles/{user_id}/rating`.

## Frontend consumption contract

`apps/main/src/lib/api/profiles.ts`'s `updateMe(token, body)` already forwards its `body` argument as the `PUT /me` JSON payload via the shared `ProfileUpdate` type — no signature change needed, only the type gains the optional `phone_number` field, which callers may now include.

## Non-API contract: "profile complete" redirect condition

Not a network contract, but a behavioral one relied on by two call sites:

- `apps/main/src/app/page.tsx` — after fetching `profiles.select("role, verification_status, phone_number, profile_photo_path")`, if `!profile.phone_number || !profile.profile_photo_path`, redirect to `/complete-profile` (checked after the `!profile` → `/role-select` check, before the `verification_status` branches).
- `apps/main/src/app/auth/callback/route.ts` — after the existing `meRes.status === 404` check (→ `/role-select`), a `200` response's JSON body (`ProfileResponse`) is checked the same way: missing `phone_number` or `profile_photo_url` → redirect to `/complete-profile`.

Both call sites derive the same boolean from the same two fields — no new persisted state, no new endpoint.
