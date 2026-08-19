# API Contracts: Deferred Identity Verification (Progressive KYC)

Base: `services/api` (FastAPI). Only endpoints with a contract change are detailed; the three gated-action endpoints are documented for completeness even though their contract is unchanged.

## Changed: `POST /api/profiles/setup` (signup completion)

**Request body** (`ProfileSetup`) — field added:

```json
{
  "role": "passenger | driver",
  "display_name": "string, 2-50 chars",
  "phone_number": "string, matches ^\\+2\\d{11}$",
  "date_of_birth": "string, ISO 8601 date (YYYY-MM-DD)"
}
```

- `date_of_birth` is a **new required field**. `id_number` was never a field on this model and remains absent (dropped per the "Yes, spec it out and drop ID number from required fields!" instruction — nothing to remove, it just never gets added).
- `profile_photo_path` / document fields are **not** part of this request and never were — photo/document submission already happens via separate endpoints (`POST /api/profiles/me/photo`, `POST /api/verification/documents`), which are unchanged and now simply optional at signup time.

**Validation**:
- `date_of_birth` MUST parse as a valid past date and MUST yield an age ≥ the platform minimum-age threshold as of the request time. Failure → `422` with a field-level error (standard FastAPI/Pydantic validation error shape, consistent with existing `display_name`/`phone_number` validation failures).

**Response** (`ProfileResponse`) — field added:

```json
{
  "id": "uuid",
  "email": "string",
  "phone_number": "string | null",
  "display_name": "string",
  "role": "passenger | driver",
  "date_of_birth": "string | null",
  "profile_photo_url": "string | null",
  "verification_status": "unverified | pending_review | verified | rejected | suspended",
  "is_submission_locked": "boolean",
  "rating_avg": "number | null",
  "rating_count": "integer",
  "created_at": "string (ISO 8601 datetime)",
  "language_preference": "en | ar"
}
```

- `date_of_birth` is `null` for every pre-existing account (grandfathered, FR-017) and for the current authenticated user's own profile only.

**Unchanged, reconfirmed**: `PublicProfileResponse` (returned when viewing another user's profile, e.g. a driver's public profile on a ride listing) does **not** and must not gain a `date_of_birth` field — this stays consistent with the constitution's "National identification data MUST NOT be publicly exposed" rule, applied here to DOB by the same caution.

## Changed: `PATCH /api/profiles/me` (`ProfileUpdate`)

No new writable field is added here — `date_of_birth` is set once at signup and is not user-editable afterward (no requirement in the spec calls for post-signup DOB editing; existing accounts remain permanently exempt rather than being prompted to backfill it). `ProfileUpdate` continues to accept only `display_name`, `phone_number`, `language_preference`.

## Unchanged (documented for reference): Gated-action 403 contract

All three endpoints already return this exact shape today when `verification_status != "verified"`; no backend change. Frontend gains new handling for it (see plan.md / research.md Decision 4):

```json
// HTTP 403
{
  "error": "verification_required",
  "message": "Passenger verification required to perform this action"
}
```

Endpoints producing this response:
- `POST /api/bookings` (passenger booking creation) — `get_current_verified_passenger`
- `POST /api/rides` (driver ride creation) — `get_current_verified_driver`
- `POST /api/rides/{ride_id}/bookings/{booking_id}/confirm` and `.../reject` (driver booking decision) — `get_current_verified_driver`

## Unchanged: Document submission and review endpoints

`POST /api/verification/documents` (front/back ID, + license for drivers), `GET /api/verification/status`, and the admin-side review/decision endpoints in `apps/admin` are all reused with zero contract changes — this feature only changes *when* a user is directed to call them, never their shape or behavior.
