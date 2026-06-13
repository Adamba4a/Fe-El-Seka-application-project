# API Contract: Authentication & Verification

**Branch**: `003-auth-verification` | **Date**: 2026-06-14

**Base URL**: `http://localhost:8000` (local) | `https://api.felseka.com` (production)

**Auth header**: `Authorization: Bearer {supabase_access_token}` on all protected endpoints.

**Content-Type**: `application/json` unless noted as `multipart/form-data`.

---

## Error Response Schema

All error responses follow this shape:

```json
{
  "error": "error_code",
  "message": "Human-readable description",
  "detail": null
}
```

Common error codes: `invalid_phone`, `otp_expired`, `otp_invalid`, `otp_rate_limited`, `unauthorized`, `forbidden`, `account_suspended`, `not_found`, `validation_error`, `submission_locked`, `already_exists`, `conflict`.

---

## 1. Authentication

### POST /api/auth/request-otp

Request an OTP for a given Egyptian phone number. No auth required.

**Request**:
```json
{ "phone_number": "+20123456789" }
```

**Responses**:
- `200 OK` — OTP sent
```json
{ "message": "OTP sent", "expires_in_seconds": 300 }
```
- `400 Bad Request` — invalid format
```json
{ "error": "invalid_phone", "message": "Phone number must be in Egyptian format: +20XXXXXXXXXX" }
```
- `429 Too Many Requests` — rate limit hit
```json
{ "error": "otp_rate_limited", "message": "Too many OTP requests. Try again in 15 minutes.", "retry_after_seconds": 900 }
```

---

### POST /api/auth/verify-otp

Verify the OTP and create/resume a session. No auth required.

**Request**:
```json
{ "phone_number": "+20123456789", "otp": "123456" }
```

**Responses**:
- `200 OK` — session created
```json
{
  "access_token": "eyJ...",
  "refresh_token": "...",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "phone_number": "+20123456789",
    "is_new_user": true
  }
}
```
- `400 Bad Request` — wrong OTP
```json
{ "error": "otp_invalid", "message": "Incorrect code. 2 attempt(s) remaining." }
```
- `410 Gone` — OTP expired
```json
{ "error": "otp_expired", "message": "Code has expired. Request a new one." }
```
- `403 Forbidden` — account suspended
```json
{ "error": "account_suspended", "message": "Your account has been suspended. Contact support." }
```

---

### POST /api/auth/refresh

Exchange a refresh token for a new access token. No auth required.

**Request**:
```json
{ "refresh_token": "..." }
```

**Response `200 OK`**:
```json
{ "access_token": "eyJ...", "expires_in": 3600 }
```

---

### POST /api/auth/sign-out

Sign out and revoke the current session. Auth required.

**Response `204 No Content`**

---

## 2. Profiles

### POST /api/profiles/setup

Create profile for a first-time user after OTP login. Auth required. Fails if profile already exists.

**Request**:
```json
{
  "role": "passenger",
  "display_name": "Ahmed Hassan"
}
```

**Response `201 Created`**:
```json
{
  "id": "uuid",
  "role": "passenger",
  "display_name": "Ahmed Hassan",
  "verification_status": "unverified",
  "is_submission_locked": false
}
```

- `409 Conflict` — profile already exists
```json
{ "error": "already_exists", "message": "Profile already set up." }
```

---

### GET /api/profiles/me

Get the authenticated user's full profile. Auth required.

**Response `200 OK`**:
```json
{
  "id": "uuid",
  "phone_number": "+20123456789",
  "display_name": "Ahmed Hassan",
  "role": "passenger",
  "profile_photo_url": "https://signed-url...",
  "verification_status": "pending_review",
  "is_submission_locked": false,
  "created_at": "2026-06-14T10:00:00Z"
}
```

---

### PUT /api/profiles/me

Update editable profile fields. Auth required.

**Request** (all fields optional):
```json
{ "display_name": "Ahmed M. Hassan" }
```

**Response `200 OK`**: Updated profile object (same shape as GET /api/profiles/me).

---

### POST /api/profiles/me/photo

Upload or replace profile photo. Auth required. `multipart/form-data`.

**Form fields**:
- `photo` — file (JPEG or PNG, max 5 MB)

**Response `200 OK`**:
```json
{ "profile_photo_url": "https://signed-url..." }
```
- `413 Payload Too Large` — file exceeds 5 MB
- `415 Unsupported Media Type` — not JPEG or PNG

---

## 3. Verification

### POST /api/verification/submit

Submit identity documents for review. Auth required. `multipart/form-data`.

**Form fields**:
- `front_id` — file (JPEG/PNG, max 10 MB) — required
- `back_id` — file (JPEG/PNG, max 10 MB) — required
- `license` — file (JPEG/PNG, max 10 MB) — required for drivers, ignored for passengers

**Responses**:
- `201 Created` — submission accepted
```json
{
  "submission_id": "uuid",
  "status": "pending_review",
  "attempt_number": 1
}
```
- `403 Forbidden` — submission locked (3rd rejection exhausted)
```json
{
  "error": "submission_locked",
  "message": "You have exhausted all submission attempts. Please contact us at support@felseka.com for a manual review.",
  "support_email": "support@felseka.com"
}
```
- `409 Conflict` — already has pending submission
```json
{ "error": "conflict", "message": "You already have a submission under review." }
```

---

### GET /api/verification/status

Get the current user's verification status. Auth required.

**Response `200 OK`**:
```json
{
  "verification_status": "rejected",
  "attempt_number": 2,
  "is_locked": false,
  "rejection_reason": "Photo is blurry. Please retake in good lighting.",
  "lockout_message": null
}
```

When locked:
```json
{
  "verification_status": "rejected",
  "attempt_number": 3,
  "is_locked": true,
  "rejection_reason": "Documents are not readable.",
  "lockout_message": "You have exhausted all submission attempts. Contact support@felseka.com for manual review."
}
```

---

## 4. Vehicles

### POST /api/vehicles/register

Register a vehicle for a verified driver. Auth required. Driver must be `verified`.

**Request**:
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

**Response `201 Created`**:
```json
{
  "id": "uuid",
  "plate_number": "ABC 1234",
  "make": "Toyota",
  "model": "Corolla",
  "year": 2020,
  "color": "White",
  "seat_count": 4,
  "registered_at": "2026-06-14T10:00:00Z"
}
```
- `400` — invalid plate format or seat count out of range
- `403` — driver not verified
- `409` — vehicle already registered for this driver

---

### GET /api/vehicles/me

Get the authenticated driver's registered vehicle. Auth required.

**Response `200 OK`**: Vehicle object (same shape as register response).
**Response `404`** — no vehicle registered yet.

---

### PUT /api/vehicles/me

Update editable vehicle fields (color, seat_count only). Auth required.

**Request** (all fields optional):
```json
{ "color": "Silver", "seat_count": 3 }
```

**Response `200 OK`**: Updated vehicle object.

---

## 5. Admin — Verification Queue

> All admin endpoints require auth and `role = 'admin'` enforced server-side.

### GET /api/admin/verification/queue

List pending submissions. Paginated, ordered oldest first.

**Query params**: `?type=passenger_id|driver_id_license&page=1&limit=20`

**Response `200 OK`**:
```json
{
  "total": 42,
  "page": 1,
  "items": [
    {
      "submission_id": "uuid",
      "user_id": "uuid",
      "user_name": "Ahmed Hassan",
      "phone_number": "+20123456789",
      "submission_type": "passenger_id",
      "submitted_at": "2026-06-14T08:00:00Z",
      "attempt_number": 1
    }
  ]
}
```

---

### GET /api/admin/verification/{submission_id}

Get full submission details including signed document URLs. Admin required.

**Response `200 OK`**:
```json
{
  "submission_id": "uuid",
  "user_id": "uuid",
  "user_name": "Ahmed Hassan",
  "phone_number": "+20123456789",
  "submission_type": "driver_id_license",
  "submitted_at": "2026-06-14T08:00:00Z",
  "attempt_number": 2,
  "document_signed_urls": {
    "front_id": "https://...?token=...&expires=3600",
    "back_id": "https://...?token=...&expires=3600",
    "license": "https://...?token=...&expires=3600"
  }
}
```

---

### POST /api/admin/verification/{submission_id}/approve

Approve a submission. Admin required. Idempotent — approving an already-approved submission returns 409.

**Response `200 OK`**:
```json
{ "submission_id": "uuid", "user_id": "uuid", "new_status": "verified", "audit_log_id": "uuid" }
```
- `404` — submission not found
- `409` — already processed

---

### POST /api/admin/verification/{submission_id}/reject

Reject a submission with a mandatory reason. Admin required.

**Request**:
```json
{ "reason": "Photo is blurry. Please retake in good lighting." }
```

**Response `200 OK`**:
```json
{
  "submission_id": "uuid",
  "user_id": "uuid",
  "new_status": "rejected",
  "is_locked": true,
  "audit_log_id": "uuid"
}
```
- `400` — reason missing or empty
- `409` — already processed

---

### POST /api/admin/verification/users/{user_id}/unlock

Unlock a submission-locked account, resetting submission count for one additional attempt. Admin required.

**Response `200 OK`**:
```json
{ "user_id": "uuid", "is_submission_locked": false, "audit_log_id": "uuid" }
```
- `404` — user not found
- `409` — user is not locked

---

## 6. Admin — User Actions

### POST /api/admin/users/{user_id}/suspend

Suspend a user. Immediately revokes all sessions. Admin required.

**Request**:
```json
{ "reason": "Suspicious activity reported" }
```

**Response `200 OK`**:
```json
{ "user_id": "uuid", "new_status": "suspended", "audit_log_id": "uuid" }
```
- `400` — reason missing
- `409` — user already suspended

---

### POST /api/admin/users/{user_id}/reinstate

Reinstate a suspended user. Admin required.

**Response `200 OK`**:
```json
{ "user_id": "uuid", "new_status": "verified", "audit_log_id": "uuid" }
```

---

### GET /api/admin/verification/history

Paginated history of all processed submissions. Admin required.

**Query params**: `?page=1&limit=20`

**Response `200 OK`**:
```json
{
  "total": 156,
  "page": 1,
  "items": [
    {
      "submission_id": "uuid",
      "user_name": "Ahmed Hassan",
      "outcome": "approved",
      "reviewed_by": "admin@felseka.com",
      "reviewed_at": "2026-06-14T09:30:00Z"
    }
  ]
}
```
