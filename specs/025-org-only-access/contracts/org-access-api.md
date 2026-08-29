# API Contract: Org-Only Access Gate

New router: `services/api/app/api/org_access/router.py`, mounted at `/api/v1/org-access` (mirrors the existing `/api/v1/groups`, `/api/v1/verification` mount pattern). Requires an authenticated, non-suspended user (`Depends(get_current_user)`) — no `_require_verified` (ID-verification) precondition, per FR-013/research.md R1.

---

## `POST /org-access/request`

Request a one-time code to verify a company/university email for app access. Does not require or accept a `requested_group_type` — this flow has no group intent (data-model.md, `requested_group_type = NULL`).

**Request body**
```json
{ "email": "person@acme-corp.com" }
```

**Response `201`**
```json
{ "verification_id": "uuid", "expires_in_seconds": 300 }
```

**Errors**
| Status | `error` | When |
|---|---|---|
| 422 | `invalid_email` | Malformed address |
| 422 | `blocklisted_domain` | Domain is on the rejection list (FR-004) |
| 429 | `otp_rate_limited` | Resend rate limit hit (NFR-003) |
| 500 | `otp_send_failed` | Email delivery failed |

If the account already has `profiles.org_verified_at` set, this endpoint still succeeds (idempotent no-op path is not required — the frontend gate never shows this screen to an already-verified account, per NFR-001/R2).

---

## `POST /org-access/confirm`

**Request body**
```json
{ "verification_id": "uuid", "code": "123456" }
```

**Response `200`**
```json
{ "org_verified_at": "2026-08-29T12:00:00Z", "org_verified_domain": "acme-corp.com" }
```

Sets `profiles.org_verified_at` / `org_verified_domain` (data-model.md). Does **not** return a `membership`/`group` (unlike Groups' `confirm_domain_verification`) — no group side effect.

**Errors**
| Status | `error` | When |
|---|---|---|
| 400 | `otp_invalid` | Wrong code |
| 400 | `otp_already_used` | Verification ID already confirmed |
| 410 | `otp_expired` | Code expired |
| 409 | `email_already_verified_elsewhere` | Correct code, but this email is already org-verified on a *different* account (FR-010) — enforced only here, at confirm-time, never at `request` (Clarifications session 2026-08-29) |

---

## `GET /me` (existing endpoint, extended)

The existing profile-fetch response gains two fields, read directly from `profiles` (no extra query — research.md R2):

```json
{
  "...": "existing fields",
  "org_verified_at": "2026-08-29T12:00:00Z",
  "org_verified_domain": "acme-corp.com"
}
```
(`null` for both if not yet gated through.)

---

## Existing gated endpoints (extended, not new)

Ride search/browse, ride posting, and booking endpoints (already checking `verification_status` for ID-verification-gated actions per Spec 021) additionally reject with `403 org_verification_required` if `profiles.org_verified_at IS NULL`, so the gate is enforced server-side and not just by the frontend redirect (research.md R7). Exact endpoint list is a `/speckit-tasks` concern, not enumerated here.

---

## Existing Groups endpoint (extended, not new)

`POST /groups/domain-verification/confirm` — unchanged request/response contract. Internally, on success, additionally sets `profiles.org_verified_at`/`org_verified_domain` if not already set (data-model.md, R3) — this is a side-effect addition, not a contract change.

---

## Admin surface

No new admin endpoint. `group_domain_blocklist` continues to be managed through whatever mechanism already edits it for Groups (research.md R5) — out of scope to add a new one.
